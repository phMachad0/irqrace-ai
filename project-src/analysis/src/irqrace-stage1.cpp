//===- irqrace-stage1.cpp -------------------------------------------------===//
//
// Stage 1: the sound candidate generator.
//
// Walks outward from the entry points named in the C1 configuration file,
// identifies shared locations through SVF's may-alias analysis, and enumerates
// every access to them with the evidence a context record needs: flow, R/W,
// enclosing function, call path, source range and loop nest.
//
// It deliberately IGNORES guard conditions and interrupt state, so that nothing
// is missed (wiki/Pipeline Design.md, stage 1; this is IntRace's design intent
// and the reason to start from it). Masking is stage 2's job and path
// feasibility is stage 3's. Nothing here discards a candidate.
//
// Candidate derivation itself -- pairs and triples from this one access set --
// happens in Python, on top of the `may_precede` relation this tool emits. The
// split follows the stack decision in wiki/comparisons/Reimplementation
// Assessment.md: C++ for anything touching LLVM and SVF, Python for the
// bookkeeping.
//
// Output is a single JSON object on stdout.
//
//===----------------------------------------------------------------------===//

#include "SVF-LLVM/LLVMModule.h"
#include "SVF-LLVM/SVFIRBuilder.h"
#include "WPA/Andersen.h"
#include "Util/Options.h"

#include "llvm/Analysis/LoopInfo.h"
#include "llvm/IR/CFG.h"
#include "llvm/IR/DebugInfo.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/Dominators.h"
#include "llvm/IR/InstIterator.h"
#include "llvm/IR/Module.h"

#include <algorithm>
#include <cstring>
#include <deque>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "json.h"

using namespace SVF;
using irqrace::esc;
using irqrace::q;

namespace {

// ---------------------------------------------------------------------------
// Configuration, passed on the command line by the Python driver
// ---------------------------------------------------------------------------

struct FlowSpec {
  std::string id;
  std::string kind;
  std::string entry;
  int irq = -1;
  int priority = 0;
};

struct Config {
  std::vector<FlowSpec> flows;
  std::set<std::string> maskingPrimitives;   // modelled, never descended into
  std::set<std::string> transparentExternals; // modelled as touching nothing
  bool signatureFallback = true;              // C1 analysis.indirect_calls
};

std::vector<std::string> split(const std::string &s, char sep) {
  std::vector<std::string> out;
  std::string cur;
  for (char c : s) {
    if (c == sep) { out.push_back(cur); cur.clear(); }
    else cur += c;
  }
  out.push_back(cur);
  return out;
}

// ---------------------------------------------------------------------------
// Source ranges
// ---------------------------------------------------------------------------

struct SourceRange {
  std::string file;
  unsigned line = 0;
  unsigned col = 0;
  bool valid() const { return line != 0; }
};

SourceRange rangeOf(const llvm::Instruction *I) {
  SourceRange r;
  if (const llvm::DebugLoc &dl = I->getDebugLoc()) {
    r.line = dl.getLine();
    r.col = dl.getCol();
    if (auto *scope = llvm::dyn_cast_or_null<llvm::DIScope>(dl.getScope()))
      r.file = scope->getFilename().str();
  }
  return r;
}

std::string emitRange(const SourceRange &r) {
  std::ostringstream o;
  o << "{\"file\": " << q(r.file) << ", \"line\": " << r.line
    << ", \"column\": " << r.col << "}";
  return o.str();
}

// ---------------------------------------------------------------------------
// Call graph
// ---------------------------------------------------------------------------

struct CallEdge {
  const llvm::Function *callee;
  const llvm::Instruction *site;
  const char *resolution; // "direct" | "indirect-resolved" | "indirect-overapproximated"
};

class CallGraph {
public:
  CallGraph(llvm::Module &M, Andersen *pta, SVFIR *pag, const Config &cfg)
      : M(M), pta(pta), pag(pag), cfg(cfg) {
    for (llvm::Function &f : M)
      if (!f.isIntrinsic() && f.hasAddressTaken())
        addressTaken.push_back(&f);
    for (llvm::Function &f : M)
      if (!f.isDeclaration() && !f.isIntrinsic())
        build(f);
  }

  const std::vector<CallEdge> &edgesOf(const llvm::Function *f) const {
    static const std::vector<CallEdge> none;
    auto it = edges.find(f);
    return it == edges.end() ? none : it->second;
  }

  unsigned indirectSites = 0;
  unsigned overApproximatedSites = 0;

private:
  void build(llvm::Function &f) {
    std::vector<CallEdge> out;
    for (auto I = llvm::inst_begin(f), E = llvm::inst_end(f); I != E; ++I) {
      const auto *ci = llvm::dyn_cast<llvm::CallBase>(&*I);
      if (!ci || ci->isInlineAsm())
        continue;

      // A call through a bitcast is still a direct call. K&R-style prototypes
      // in a header produce one for every call site after llvm-link, and
      // reading those as indirect would over-approximate every call graph in
      // the benchmark (docs/toolchain-notes.md).
      const llvm::Value *callee = ci->getCalledOperand()->stripPointerCasts();
      if (const auto *cf = llvm::dyn_cast<llvm::Function>(callee)) {
        if (!cf->isIntrinsic())
          out.push_back({cf, &*I, "direct"});
        continue;
      }

      ++indirectSites;
      std::set<const llvm::Function *> targets = pointsToTargets(ci);
      const char *how = "indirect-resolved";
      if (targets.empty() && cfg.signatureFallback) {
        // The recall-critical rule: an unresolved target set is NEVER read as
        // "calls nothing". Resolving to nothing silently deletes whole subtrees
        // of reachable accesses, and the loss is invisible in the output
        // (Soundness Assumptions B2).
        ++overApproximatedSites;
        how = "indirect-overapproximated";
        for (const llvm::Function *cand : addressTaken)
          if (signatureMatches(cand, ci))
            targets.insert(cand);
      }
      for (const llvm::Function *t : targets)
        out.push_back({t, &*I, how});
    }
    edges[&f] = std::move(out);
  }

  std::set<const llvm::Function *> pointsToTargets(const llvm::CallBase *ci) {
    std::set<const llvm::Function *> out;
    SVFValue *sv = LLVMModuleSet::getLLVMModuleSet()->getSVFValue(
        ci->getCalledOperand());
    if (!sv || !pag->hasValueNode(sv))
      return out;
    for (NodeID o : pta->getPts(pag->getValueNode(sv))) {
      if (pag->isBlkObjOrConstantObj(o))
        continue;
      const MemObj *obj = pag->getBaseObj(o);
      if (!obj || !obj->getValue())
        continue;
      const llvm::Value *v =
          LLVMModuleSet::getLLVMModuleSet()->getLLVMValue(obj->getValue());
      if (const auto *f = llvm::dyn_cast_or_null<llvm::Function>(v))
        if (!f->isDeclaration())
          out.insert(f);
    }
    return out;
  }

  static bool signatureMatches(const llvm::Function *f, const llvm::CallBase *ci) {
    llvm::FunctionType *ft = f->getFunctionType();
    if (ft == ci->getFunctionType())
      return true;
    // Be generous: a mismatch in exact types should not exclude a target, since
    // excluding one is the unsound direction. Require only arity compatibility.
    if (ft->isVarArg())
      return true;
    return ft->getNumParams() == ci->arg_size();
  }

  llvm::Module &M;
  Andersen *pta;
  SVFIR *pag;
  const Config &cfg;
  std::vector<const llvm::Function *> addressTaken;
  std::map<const llvm::Function *, std::vector<CallEdge>> edges;
};

// ---------------------------------------------------------------------------
// Per-flow reachability
// ---------------------------------------------------------------------------

struct Frame {
  const llvm::Function *fn;
  const llvm::Instruction *site; // call site that entered `fn`; null for the entry
  const char *resolution;
};

struct Reach {
  // One representative call path per reachable function: the shortest, found by
  // breadth-first search. `multiplePaths` records that others exist, which the
  // context record surfaces as CallPath.is_one_of_many so a consumer knows the
  // path shown is not the only one.
  std::map<const llvm::Function *, std::vector<Frame>> path;
  std::set<const llvm::Function *> multiplePaths;
  // Every reachable call site of each callee, as (caller, site). Used to decide
  // whether a function may run more than once in this flow, which is what makes
  // one instruction in it two dynamic accesses.
  std::map<const llvm::Function *,
           std::vector<std::pair<const llvm::Function *, const llvm::Instruction *>>>
      callSites;
};

Reach reachableFrom(const llvm::Function *entry, const CallGraph &cg,
                    const Config &cfg) {
  Reach r;
  r.path[entry] = {{entry, nullptr, "direct"}};
  std::deque<const llvm::Function *> work{entry};
  while (!work.empty()) {
    const llvm::Function *f = work.front();
    work.pop_front();
    for (const CallEdge &e : cg.edgesOf(f)) {
      // Masking primitives and modelled externals are described by the
      // configuration file, not descended into (Soundness Assumptions D2, D3).
      if (cfg.maskingPrimitives.count(e.callee->getName().str()) ||
          cfg.transparentExternals.count(e.callee->getName().str()))
        continue;
      if (e.callee->isDeclaration())
        continue;
      r.callSites[e.callee].push_back({f, e.site});
      if (r.path.count(e.callee)) {
        r.multiplePaths.insert(e.callee);
        continue;
      }
      std::vector<Frame> p = r.path[f];
      p.push_back({e.callee, e.site, e.resolution});
      r.path[e.callee] = std::move(p);
      work.push_back(e.callee);
    }
  }
  return r;
}

// ---------------------------------------------------------------------------
// Intra-function CFG reachability, at instruction granularity
// ---------------------------------------------------------------------------

class FunctionCFG {
public:
  explicit FunctionCFG(const llvm::Function &F) {
    unsigned n = 0;
    for (const llvm::BasicBlock &bb : F)
      index[&bb] = n++;
    reach.assign(n, std::vector<bool>(n, false));
    for (const llvm::BasicBlock &bb : F) {
      // Successor closure by BFS. `from` never marks itself unless a real path
      // returns to it -- which is exactly the property that makes "the same
      // statement twice inside a loop" a valid triple.
      std::deque<const llvm::BasicBlock *> work;
      for (const llvm::BasicBlock *s : llvm::successors(&bb))
        work.push_back(s);
      std::vector<bool> &row = reach[index[&bb]];
      while (!work.empty()) {
        const llvm::BasicBlock *cur = work.front();
        work.pop_front();
        unsigned ci = index[cur];
        if (row[ci])
          continue;
        row[ci] = true;
        for (const llvm::BasicBlock *s : llvm::successors(cur))
          work.push_back(s);
      }
    }
    unsigned pos = 0;
    for (const llvm::BasicBlock &bb : F)
      for (const llvm::Instruction &I : bb)
        order[&I] = pos++;
  }

  /// Can execution pass `a` and later reach `b` within one call of this
  /// function? Over-approximate by construction.
  bool mayPrecede(const llvm::Instruction *a, const llvm::Instruction *b) const {
    const llvm::BasicBlock *ba = a->getParent(), *bb = b->getParent();
    if (ba != bb)
      return reach.at(index.at(ba)).at(index.at(bb));
    if (order.at(a) < order.at(b))
      return true;
    // Same block, b at or before a: only reachable by going round a cycle.
    return reach.at(index.at(ba)).at(index.at(ba));
  }

  bool inCycle(const llvm::Instruction *i) const {
    unsigned b = index.at(i->getParent());
    return reach.at(b).at(b);
  }

private:
  std::map<const llvm::BasicBlock *, unsigned> index;
  std::map<const llvm::Instruction *, unsigned> order;
  std::vector<std::vector<bool>> reach;
};

// ---------------------------------------------------------------------------
// Accesses
// ---------------------------------------------------------------------------

struct Access {
  unsigned id;
  std::string flow;
  NodeID object;
  bool isWrite;
  const llvm::Function *fn;
  const llvm::Instruction *inst;
  SourceRange src;
  bool inLoop = false;
  bool sourceRecovered = false; // no DebugLoc; the function's line was used
  std::vector<SourceRange> loopHeaders;
  std::vector<Frame> callPath;
  bool pathIsOneOfMany = false;
};

struct ObjectInfo {
  NodeID id;
  std::string name;
  std::string type;
  bool isVolatile = false;
  SourceRange decl;
  std::set<std::string> flows;
};

bool declaredVolatile(const llvm::DIType *t) {
  while (t) {
    if (const auto *d = llvm::dyn_cast<llvm::DIDerivedType>(t)) {
      if (d->getTag() == llvm::dwarf::DW_TAG_volatile_type)
        return true;
      if (d->getTag() == llvm::dwarf::DW_TAG_typedef ||
          d->getTag() == llvm::dwarf::DW_TAG_const_type ||
          d->getTag() == llvm::dwarf::DW_TAG_restrict_type) {
        t = d->getBaseType();
        continue;
      }
    }
    if (const auto *c = llvm::dyn_cast<llvm::DICompositeType>(t)) {
      if (c->getTag() == llvm::dwarf::DW_TAG_array_type) {
        t = c->getBaseType();
        continue;
      }
    }
    return false;
  }
  return false;
}

std::string typeName(const llvm::DIType *t) {
  if (!t)
    return "";
  if (!t->getName().empty())
    return t->getName().str();
  if (const auto *d = llvm::dyn_cast<llvm::DIDerivedType>(t)) {
    std::string base = typeName(d->getBaseType());
    switch (d->getTag()) {
    case llvm::dwarf::DW_TAG_volatile_type: return "volatile " + base;
    case llvm::dwarf::DW_TAG_const_type:    return "const " + base;
    case llvm::dwarf::DW_TAG_pointer_type:
      if (llvm::isa_and_nonnull<llvm::DISubroutineType>(d->getBaseType()))
        return "function pointer";
      return base + " *";
    default: return base;
    }
  }
  if (const auto *c = llvm::dyn_cast<llvm::DICompositeType>(t)) {
    if (c->getTag() == llvm::dwarf::DW_TAG_array_type)
      return typeName(c->getBaseType()) + "[]";
    if (!c->getName().empty())
      return c->getName().str();
    return "struct";
  }
  return "";
}

} // namespace

int main(int argc, char **argv) {
  Config cfg;
  std::vector<char *> passthrough{argv[0]};
  bool wantStats = false;

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    auto next = [&]() -> std::string { return i + 1 < argc ? argv[++i] : ""; };
    if (a == "--flow") {
      auto p = split(next(), ':');
      if (p.size() < 5) { std::cerr << "bad --flow\n"; return 2; }
      cfg.flows.push_back({p[0], p[1], p[2], std::atoi(p[3].c_str()),
                           std::atoi(p[4].c_str())});
    } else if (a == "--primitive") {
      cfg.maskingPrimitives.insert(next());
    } else if (a == "--transparent") {
      cfg.transparentExternals.insert(next());
    } else if (a == "--indirect-calls") {
      cfg.signatureFallback = (next() != "points-to-only");
    } else {
      if (a.rfind("-stat", 0) == 0)
        wantStats = true;
      passthrough.push_back(argv[i]);
    }
  }
  static char statOff[] = "-stat=false";
  if (!wantStats)
    passthrough.push_back(statOff);

  int pc = static_cast<int>(passthrough.size());
  std::vector<std::string> moduleNameVec = OptionBase::parseOptions(
      pc, passthrough.data(), "irqrace stage 1",
      "[--flow id:kind:entry:irq:priority]... <input-bitcode>");
  if (moduleNameVec.empty() || cfg.flows.empty()) {
    std::cerr << "irqrace-stage1: need bitcode and at least one --flow\n";
    return 2;
  }

  SVFModule *svfModule = LLVMModuleSet::buildSVFModule(moduleNameVec);
  SVFIRBuilder builder(svfModule);
  SVFIR *pag = builder.build();
  // MAY-alias. A must-alias shortcut here silently deletes candidates
  // (Soundness Assumptions C1).
  Andersen *pta = AndersenWaveDiff::createAndersenWaveDiff(pag);
  llvm::Module *M = LLVMModuleSet::getLLVMModuleSet()->getMainLLVMModule();

  std::ostringstream warnings;
  bool wfirst = true;
  auto warn = [&](const std::string &sev, const std::string &code,
                  const std::string &msg) {
    warnings << (wfirst ? "\n    " : ",\n    ") << "{\"severity\": " << q(sev)
             << ", \"code\": " << q(code) << ", \"message\": " << q(msg) << "}";
    wfirst = false;
  };

  CallGraph cg(*M, pta, pag, cfg);

  // ---- per-flow reachability -------------------------------------------
  std::map<std::string, Reach> reach;
  for (const FlowSpec &f : cfg.flows) {
    llvm::Function *fn = M->getFunction(f.entry);
    if (!fn || fn->isDeclaration()) {
      warn("error", "entry-point-missing",
           "configured entry point '" + f.entry + "' has no body in the module; "
           "flow '" + f.id + "' contributes no accesses and every defect "
           "reachable only from it is invisible");
      continue;
    }
    reach[f.id] = reachableFrom(fn, cg, cfg);
  }

  // ---- loop info and CFG reachability, per function --------------------
  std::map<const llvm::Function *, std::unique_ptr<FunctionCFG>> cfgs;
  std::map<const llvm::Function *, std::unique_ptr<llvm::DominatorTree>> dts;
  std::map<const llvm::Function *, std::unique_ptr<llvm::LoopInfo>> loops;
  auto analyse = [&](const llvm::Function *f) {
    if (cfgs.count(f))
      return;
    auto *mut = const_cast<llvm::Function *>(f);
    cfgs[f] = std::make_unique<FunctionCFG>(*f);
    dts[f] = std::make_unique<llvm::DominatorTree>(*mut);
    loops[f] = std::make_unique<llvm::LoopInfo>(*dts[f]);
  };

  // ---- access enumeration ----------------------------------------------
  std::vector<Access> accesses;
  std::map<NodeID, ObjectInfo> objects;
  unsigned recoveredRanges = 0;

  auto objectsTouched = [&](const llvm::Value *ptr) {
    std::set<NodeID> out;
    SVFValue *sv = LLVMModuleSet::getLLVMModuleSet()->getSVFValue(ptr);
    if (!sv || !pag->hasValueNode(sv))
      return out;
    for (NodeID o : pta->getPts(pag->getValueNode(sv))) {
      if (pag->isBlkObjOrConstantObj(o))
        continue;
      // Normalise to the BASE object. Field sensitivity would separate
      // `a[TRIGGER]` from `a[1000]`, and separating them is the unsound
      // direction here: two accesses that may be to the same element must stay
      // comparable. Distinguishing them is a job for stage 3, which can prove
      // it (Soundness Assumptions C1).
      out.insert(pag->getBaseObjVar(o));
    }
    return out;
  };

  for (const FlowSpec &f : cfg.flows) {
    auto it = reach.find(f.id);
    if (it == reach.end())
      continue;
    for (const auto &[fn, path] : it->second.path) {
      analyse(fn);
      const FunctionCFG &fcfg = *cfgs[fn];
      const llvm::LoopInfo &li = *loops[fn];
      for (auto I = llvm::inst_begin(*const_cast<llvm::Function *>(fn)),
                E = llvm::inst_end(*const_cast<llvm::Function *>(fn));
           I != E; ++I) {
        const llvm::Value *ptr = nullptr;
        bool isWrite = false;
        if (const auto *ld = llvm::dyn_cast<llvm::LoadInst>(&*I)) {
          ptr = ld->getPointerOperand();
        } else if (const auto *st = llvm::dyn_cast<llvm::StoreInst>(&*I)) {
          // At -O0 clang spills each parameter into an alloca in the entry
          // block. That store is a prologue artefact with no DebugLoc and no
          // source-level existence, so it is not an access to anything a report
          // could point at. Skipping it is safe precisely because the alloca it
          // writes is the parameter's own slot -- any real sharing of that value
          // shows up at the loads and stores that follow.
          if (llvm::isa<llvm::Argument>(st->getValueOperand()) &&
              st->getParent() == &fn->getEntryBlock())
            continue;
          ptr = st->getPointerOperand();
          isWrite = true;
        } else {
          continue;
        }
        for (NodeID o : objectsTouched(ptr)) {
          const MemObj *mo = pag->getObject(o);
          if (!mo || mo->isFunction())
            continue; // a function pointer target is not data
          // Deliberately NOT restricted to globals. `svp_simple_009_001` shares
          // a STACK variable between its task and its ISR by storing its address
          // into two global pointers, and its annotated bug point is a triple on
          // that stack object. Filtering to module-level state loses it, and
          // loses it silently -- which is how the recall gate caught this.
          //
          // What makes a location shared is that two flows reach it, not where
          // it was allocated. That test is applied by candidate derivation,
          // which already requires the accesses to be in different flows.
          Access a;
          a.id = static_cast<unsigned>(accesses.size());
          a.flow = f.id;
          a.object = o;
          a.isWrite = isWrite;
          a.fn = fn;
          a.inst = &*I;
          a.src = rangeOf(&*I);
          if (!a.src.valid()) {
            // No debug location. Dropping the access would be a silent recall
            // loss (Soundness Assumptions A2), so fall back to the enclosing
            // function's own line and mark the record: an imprecise location is
            // recoverable by a reader, a missing candidate is not.
            if (const llvm::DISubprogram *sp = fn->getSubprogram()) {
              a.src.file = sp->getFilename().str();
              a.src.line = sp->getLine();
            }
            a.sourceRecovered = true;
            ++recoveredRanges;
          }
          a.callPath = path;
          a.pathIsOneOfMany = it->second.multiplePaths.count(fn) > 0;
          for (const llvm::Loop *l = li.getLoopFor(I->getParent()); l;
               l = l->getParentLoop()) {
            a.inLoop = true;
            SourceRange h;
            if (const llvm::BasicBlock *hb = l->getHeader())
              if (const llvm::Instruction *hi = hb->getFirstNonPHI())
                h = rangeOf(hi);
            a.loopHeaders.push_back(h);
          }
          // A block on a cycle is reachable from itself, which is what makes a
          // single statement serve as both A1 and A2 (Soundness Assumptions G2).
          if (!a.inLoop && fcfg.inCycle(&*I))
            a.inLoop = true;
          accesses.push_back(std::move(a));

          ObjectInfo &oi = objects[o];
          oi.id = o;
          oi.flows.insert(f.id);
        }
      }
    }
  }

  // ---- keep only genuinely shared objects -------------------------------
  //
  // A candidate of either class needs accesses in two different flows, so an
  // object only one flow ever touches cannot produce one. Dropping those is
  // sound -- it removes nothing that could become a candidate -- and it matters
  // for legibility: without it every loop induction variable and every spilled
  // local shows up in the access set once stack objects are in scope.
  {
    std::set<NodeID> shared;
    for (const auto &[id, oi] : objects)
      if (oi.flows.size() >= 2)
        shared.insert(id);
    unsigned dropped = 0;
    std::vector<Access> kept;
    std::map<unsigned, unsigned> remap;
    for (const Access &a : accesses) {
      if (!shared.count(a.object)) { ++dropped; continue; }
      remap[a.id] = static_cast<unsigned>(kept.size());
      Access b = a;
      b.id = static_cast<unsigned>(kept.size());
      kept.push_back(std::move(b));
    }
    accesses = std::move(kept);
    for (auto it = objects.begin(); it != objects.end();)
      it = shared.count(it->first) ? std::next(it) : objects.erase(it);
    if (dropped)
      warn("info", "unshared-objects-dropped",
           std::to_string(dropped) +
               " access(es) were to objects only one flow reaches; no candidate "
               "of either class can be formed from them");
  }

  // ---- describe the objects --------------------------------------------
  for (auto &[id, oi] : objects) {
    const MemObj *mo = pag->getObject(id);
    const llvm::Value *v =
        mo && mo->getValue()
            ? LLVMModuleSet::getLLVMModuleSet()->getLLVMValue(mo->getValue())
            : nullptr;
    const auto *gv = llvm::dyn_cast_or_null<llvm::GlobalVariable>(v);
    if (!gv) {
      oi.name = v && v->hasName() ? v->getName().str() : ("obj_" + std::to_string(id));
      continue;
    }
    oi.name = gv->getName().str();
    llvm::SmallVector<llvm::DIGlobalVariableExpression *, 2> dbg;
    gv->getDebugInfo(dbg);
    if (!dbg.empty())
      if (const llvm::DIGlobalVariable *dv = dbg[0]->getVariable()) {
        oi.decl.file = dv->getFilename().str();
        oi.decl.line = dv->getLine();
        oi.type = typeName(dv->getType());
        oi.isVolatile = declaredVolatile(dv->getType());
        if (!dv->getName().empty())
          oi.name = dv->getName().str();
      }
  }

  // A function that may run more than once in a flow turns ONE instruction in
  // it into many dynamic accesses -- the same argument that makes a statement
  // inside a loop able to serve as both A1 and A2, but reached through repeated
  // calls instead of a back edge.
  //
  // `svp_simple_029_001` is the case that forced this: its `GetTmData` is called
  // twice in a row from one caller, so the single `return tm_blocks[tm_name];`
  // at line 80 is two accesses, and the suite annotates exactly that triple.
  // Intra-procedural CFG reachability alone reports the instruction as unable to
  // precede itself and the candidate is never generated.
  //
  // The entry function of a flow is deliberately excluded. Whether an ISR firing
  // twice can supply A1 and A2 across two separate invocations is a question
  // about the arrival model, not about the call graph (Soundness Assumptions E3,
  // E4), and answering it here would decide it by accident.
  auto multiInvocation = [&](const std::string &flow, const llvm::Function *fn) {
    auto rit = reach.find(flow);
    if (rit == reach.end())
      return false;
    for (const FlowSpec &f : cfg.flows)
      if (f.id == flow && f.entry == fn->getName().str())
        return false;
    auto sit = rit->second.callSites.find(fn);
    if (sit == rit->second.callSites.end())
      return false;
    if (sit->second.size() >= 2)
      return true;
    for (const auto &[caller, site] : sit->second) {
      analyse(caller);
      if (cfgs[caller]->inCycle(site))
        return true;
    }
    return false;
  };

  // ---- may-precede, within a flow --------------------------------------
  //
  // Only ordered pairs inside one flow are emitted: this is the relation
  // triple derivation needs, and it is quadratic, so it is not computed
  // across flows where it would be meaningless anyway.
  std::ostringstream precede;
  bool pfirst = true;
  unsigned precedeCount = 0;
  for (size_t i = 0; i < accesses.size(); ++i) {
    for (size_t j = 0; j < accesses.size(); ++j) {
      const Access &a = accesses[i], &b = accesses[j];
      if (a.flow != b.flow || a.object != b.object)
        continue;
      bool ok;
      if (a.fn == b.fn) {
        ok = cfgs[a.fn]->mayPrecede(a.inst, b.inst) || multiInvocation(a.flow, a.fn);
      } else {
        // Across functions within one flow, over-approximate. Proving that one
        // callee cannot run before another needs inter-procedural ordering the
        // front end does not have, and guessing would be the unsound direction.
        ok = true;
      }
      if (!ok)
        continue;
      precede << (pfirst ? "\n    " : ", ") << "[" << i << ", " << j << "]";
      pfirst = false;
      ++precedeCount;
    }
  }

  // ---- emit -------------------------------------------------------------
  std::ostringstream out;
  out << "{\n  \"tool\": \"irqrace-stage1\",\n  \"svf\": \"2.7\",\n";

  out << "  \"flows\": [";
  bool first = true;
  for (const FlowSpec &f : cfg.flows) {
    auto it = reach.find(f.id);
    size_t n = it == reach.end() ? 0 : it->second.path.size();
    out << (first ? "\n    " : ",\n    ") << "{\"id\": " << q(f.id)
        << ", \"kind\": " << q(f.kind) << ", \"entry\": " << q(f.entry)
        << ", \"irq\": " << f.irq << ", \"priority\": " << f.priority
        << ", \"reachable_functions\": " << n
        << ", \"resolved\": " << (it == reach.end() ? "false" : "true") << "}";
    first = false;
  }
  out << "\n  ],\n";

  out << "  \"objects\": [";
  first = true;
  for (const auto &[id, oi] : objects) {
    out << (first ? "\n    " : ",\n    ") << "{\"id\": " << id
        << ", \"name\": " << q(oi.name) << ", \"declared_type\": " << q(oi.type)
        << ", \"volatile\": " << (oi.isVolatile ? "true" : "false")
        << ", \"decl\": " << emitRange(oi.decl) << ", \"flows\": [";
    bool f2 = true;
    for (const std::string &fl : oi.flows) {
      out << (f2 ? "" : ", ") << q(fl);
      f2 = false;
    }
    out << "]}";
    first = false;
  }
  out << "\n  ],\n";

  // Function line ranges, so the driver can lift enclosing bodies out of the
  // source without reparsing C. Start comes from the DISubprogram; end is the
  // largest line any instruction in the function is attributed to.
  out << "  \"functions\": [";
  first = true;
  {
    std::set<const llvm::Function *> seen;
    for (const Access &a : accesses)
      seen.insert(a.fn);
    for (const llvm::Function *fn : seen) {
      unsigned start = 0, end = 0;
      std::string file;
      if (const llvm::DISubprogram *sp = fn->getSubprogram()) {
        start = sp->getLine();
        file = sp->getFilename().str();
      }
      for (auto I = llvm::inst_begin(*const_cast<llvm::Function *>(fn)),
                E = llvm::inst_end(*const_cast<llvm::Function *>(fn));
           I != E; ++I) {
        SourceRange r = rangeOf(&*I);
        if (r.line > end)
          end = r.line;
        if (start == 0 || r.line < start)
          if (r.line)
            start = r.line;
      }
      out << (first ? "\n    " : ",\n    ") << "{\"name\": "
          << q(fn->getName().str()) << ", \"file\": " << q(file)
          << ", \"line_start\": " << start << ", \"line_end\": " << end << "}";
      first = false;
    }
  }
  out << "\n  ],\n";

  out << "  \"accesses\": [";
  first = true;
  for (const Access &a : accesses) {
    out << (first ? "\n    " : ",\n    ") << "{\"id\": " << a.id
        << ", \"flow\": " << q(a.flow) << ", \"object\": " << a.object
        << ", \"kind\": " << q(a.isWrite ? "write" : "read")
        << ", \"function\": " << q(a.fn->getName().str())
        << ", \"source\": " << emitRange(a.src)
        << ", \"source_recovered\": " << (a.sourceRecovered ? "true" : "false")
        << ", \"in_loop\": " << (a.inLoop ? "true" : "false")
        << ", \"loop_headers\": [";
    bool f2 = true;
    for (const SourceRange &h : a.loopHeaders) {
      out << (f2 ? "" : ", ") << emitRange(h);
      f2 = false;
    }
    out << "], \"call_path\": {\"is_one_of_many\": "
        << (a.pathIsOneOfMany ? "true" : "false") << ", \"frames\": [";
    f2 = true;
    for (const Frame &fr : a.callPath) {
      out << (f2 ? "" : ", ") << "{\"function\": " << q(fr.fn->getName().str())
          << ", \"resolution\": " << q(fr.resolution);
      if (fr.site) {
        SourceRange cs = rangeOf(fr.site);
        out << ", \"call_site\": " << emitRange(cs);
      }
      out << "}";
      f2 = false;
    }
    out << "]}}";
    first = false;
  }
  out << "\n  ],\n";

  out << "  \"may_precede\": [" << precede.str() << (precedeCount ? "\n  " : "")
      << "],\n";

  if (cg.overApproximatedSites)
    warn("warn", "indirect-calls-overapproximated",
         std::to_string(cg.overApproximatedSites) + " of " +
             std::to_string(cg.indirectSites) +
             " indirect call site(s) could not be resolved by points-to and were "
             "treated as calling every address-taken function with a matching "
             "signature");
  if (recoveredRanges)
    warn("warn", "source-range-recovered",
         std::to_string(recoveredRanges) +
             " access(es) carried no DebugLoc; the enclosing function's line was "
             "used instead. The candidates are kept -- dropping them would be a "
             "silent recall loss -- but their source ranges are imprecise");
  if (accesses.empty())
    warn("error", "no-accesses",
         "no accesses to any shared global were found; check the entry points");

  out << "  \"indirect_call_sites\": " << cg.indirectSites << ",\n"
      << "  \"indirect_overapproximated\": " << cg.overApproximatedSites << ",\n"
      << "  \"may_precede_pairs\": " << precedeCount << ",\n"
      << "  \"warnings\": [" << warnings.str() << (wfirst ? "" : "\n  ") << "]\n}\n";

  std::cout << out.str();

  AndersenWaveDiff::releaseAndersenWaveDiff();
  SVFIR::releaseSVFIR();
  LLVMModuleSet::releaseLLVMModuleSet();
  return 0;
}
