//===- irqrace-stage3.cpp -------------------------------------------------===//
//
// Stage 3: path feasibility, decided by Z3. The only stage whose verdict may
// discard a candidate -- and only an UNSAT one (wiki/Pipeline Design.md, "Z3
// and path feasibility"; Soundness Assumptions H1, H2).
//
// The question, for a candidate (A1, B, A2) with A1 and A2 in flow F and B in H:
// is there an execution in which F reaches A1, H runs from its entry to B while
// F is somewhere between A1 and A2, and F then reaches A2 -- the three accesses
// touching the same memory? This is REACHABILITY ONLY. Whether the interleaving is harmful, or even
// unserializable, is not the solver's question (Roadmap W6-W7).
//
// The encoding is built to OVER-approximate the executions of the program, so
// that UNSAT is a proof and SAT is only "not refuted":
//
//   * symbolic execution over the LLVM IR, every call inlined, every branch
//     forked and pruned by the solver;
//   * memory is one byte array per SVF object; a pointer is (object << 40 |
//     offset), and a load or store through it is a case split over the
//     object's may-points-to set;
//   * loops: everything a loop may write is havocked at its header, so one pass
//     through the body covers every iteration. Back edges are cut while looking
//     for A1 or B, and crossed at most once between A1 and A2, which is what
//     lets the same statement be both A1 and A2;
//   * interference: at every instruction boundary where stage 2 says some flow
//     may run, everything that flow may write is havocked (lazily, at the next
//     access). Masking enters stage 3 only through those run sets;
//   * the splice, after IntRace: H runs from its entry on the memory at the
//     preemption point; afterwards everything that may have run there is
//     havocked again;
//   * an ISR's own entry state is havoc: it may fire anywhere.
//
// Anything the encoding cannot express soundly -- recursion, an irreducible
// CFG, an unknown terminator -- makes the verdict `inconclusive`, as do the
// timeout and the exploration budget. Never `sat`, never a drop (H2).
//
// Input: the bitcode, and a query file written by src/irqrace/stage3.py
// (flows, run sets, candidates). Output: one JSON object per candidate per line
// on stdout.
//
//===----------------------------------------------------------------------===//

#include "SVF-LLVM/LLVMModule.h"
#include "SVF-LLVM/SVFIRBuilder.h"
#include "WPA/Andersen.h"
#include "Util/Options.h"

#include "llvm/ADT/MapVector.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/Analysis/ValueTracking.h"
#include "llvm/IR/CFG.h"
#include "llvm/IR/DataLayout.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/Dominators.h"
#include "llvm/IR/InstIterator.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Operator.h"

#include <z3++.h>

#include <algorithm>
#include <chrono>
#include <deque>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#include "json.h"

using namespace SVF;
using irqrace::q;

namespace {

using Clock = std::chrono::steady_clock;

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
// The query file
// ---------------------------------------------------------------------------

struct Target {
  int flow = -1;
  std::string fn;
  unsigned block = 0, inst = 0;
  const llvm::Instruction *I = nullptr;
};

struct Candidate {
  std::string id;
  Target a1, b, a2; // A1 and A2 in the preempted flow, B in the preempting one
};

struct Query {
  unsigned timeoutMs = 10000;
  unsigned maxStates = 40000;
  std::set<std::string> primitives;
  std::map<std::string, std::string> models; // function -> effect
  bool externalsTouchAll = true;            // C1 externals.default
  std::vector<std::string> flowIds, flowKinds, flowEntries;
  std::map<std::string, int> flowIndex;
  std::vector<std::vector<int>> runSets;    // set id -> flows
  // (flow, function, block) -> run set id per instruction boundary (-1: none)
  std::map<std::tuple<int, std::string, unsigned>, std::vector<int>> runAt;
  std::vector<std::vector<int>> staticRun;  // per flow, for unlisted points
  std::vector<Candidate> cands;
};

bool readQuery(const std::string &path, Query &qy, std::string &err) {
  std::ifstream in(path);
  if (!in) { err = "cannot open query file " + path; return false; }
  std::string line;
  auto flowsOf = [&](const std::string &s) {
    std::vector<int> out;
    if (s == "-" || s.empty()) return out;
    for (const std::string &f : split(s, ','))
      if (qy.flowIndex.count(f)) out.push_back(qy.flowIndex[f]);
    return out;
  };
  auto target = [&](const std::string &flow, const std::string &fn,
                    const std::string &b, const std::string &i) {
    Target t;
    t.flow = qy.flowIndex.count(flow) ? qy.flowIndex[flow] : -1;
    t.fn = fn;
    t.block = std::stoul(b);
    t.inst = std::stoul(i);
    return t;
  };
  while (std::getline(in, line)) {
    std::istringstream ls(line);
    std::vector<std::string> w;
    std::string tok;
    while (ls >> tok) w.push_back(tok);
    if (w.empty() || w[0][0] == '#') continue;
    const std::string &k = w[0];
    if (k == "timeout_ms" && w.size() == 2) qy.timeoutMs = std::stoul(w[1]);
    else if (k == "max_states" && w.size() == 2) qy.maxStates = std::stoul(w[1]);
    else if (k == "primitive" && w.size() == 2) qy.primitives.insert(w[1]);
    else if (k == "model" && w.size() == 3) qy.models[w[1]] = w[2];
    else if (k == "externals" && w.size() == 2) qy.externalsTouchAll = (w[1] != "none");
    else if (k == "flow" && w.size() == 4) {
      qy.flowIndex[w[1]] = static_cast<int>(qy.flowIds.size());
      qy.flowIds.push_back(w[1]);
      qy.flowKinds.push_back(w[2]);
      qy.flowEntries.push_back(w[3]);
      qy.staticRun.emplace_back();
    } else if (k == "static" && w.size() == 3) {
      qy.staticRun.at(qy.flowIndex.at(w[1])) = flowsOf(w[2]);
    } else if (k == "run" && w.size() == 7) {
      int flow = qy.flowIndex.at(w[1]);
      unsigned b = std::stoul(w[3]), lo = std::stoul(w[4]), hi = std::stoul(w[5]);
      int id = static_cast<int>(qy.runSets.size());
      qy.runSets.push_back(flowsOf(w[6]));
      auto &vec = qy.runAt[{flow, w[2], b}];
      if (vec.size() <= hi) vec.resize(hi + 1, -1);
      for (unsigned j = lo; j <= hi; ++j) vec[j] = id;
    } else if (k == "cand") {
      // cand <id> <flow> <fnA1> <bA1> <iA1> <flowB> <fnB> <bB> <iB> <fnA2> <bA2> <iA2>
      if (w.size() != 13) {
        err = "malformed candidate line: " + line;
        return false;
      }
      Candidate c;
      c.id = w[1];
      c.a1 = target(w[2], w[3], w[4], w[5]);
      c.b = target(w[6], w[7], w[8], w[9]);
      c.a2 = target(w[2], w[10], w[11], w[12]);
      qy.cands.push_back(c);
    } else {
      err = "unrecognised query line: " + line;
      return false;
    }
  }
  return true;
}

// ---------------------------------------------------------------------------
// Static facts about the module
// ---------------------------------------------------------------------------

struct FnInfo {
  std::vector<const llvm::BasicBlock *> blocks;
  std::map<const llvm::BasicBlock *, unsigned> blockIndex;
  std::map<const llvm::BasicBlock *, std::vector<const llvm::Instruction *>> insts;
  std::unique_ptr<llvm::DominatorTree> dt;
  std::unique_ptr<llvm::LoopInfo> li;
  bool irreducible = false;
};

struct WriteSet {
  std::set<NodeID> objs;
  bool all = false;
  void add(const WriteSet &o) {
    objs.insert(o.objs.begin(), o.objs.end());
    all = all || o.all;
  }
};

class Facts {
public:
  Facts(llvm::Module &M, SVFIR *pag, Andersen *pta, const Query &qy)
      : M(M), DL(M.getDataLayout()), pag(pag), pta(pta), qy(qy) {
    // SymbolTableInfo::getObjSym asserts on a value with no object, and the
    // assert is compiled out in a Release SVF: look the symbol up instead.
    SymbolTableInfo *sym = SymbolTableInfo::SymbolInfo();
    auto obj = [&](const llvm::Value *v) {
      const SVFValue *sv = LLVMModuleSet::getLLVMModuleSet()->getSVFValue(v);
      if (!sv) return;
      if (const auto *g = SVFUtil::dyn_cast<SVFGlobalValue>(sv))
        sv = g->getDefGlobalForMultipleModule();
      auto it = sym->objSyms().find(sv);
      if (it == sym->objSyms().end()) return;
      NodeID base = pag->getBaseObjVar(it->second);
      objOf[v] = base;
      valueOf[base] = v;
    };
    for (llvm::GlobalVariable &g : M.globals()) obj(&g);
    for (llvm::Function &f : M) {
      obj(&f);
      if (f.isDeclaration()) continue;
      for (llvm::Instruction &I : llvm::instructions(f))
        if (llvm::isa<llvm::AllocaInst>(&I)) obj(&I);
    }
  }

  FnInfo &info(const llvm::Function *f) {
    auto it = fns.find(f);
    if (it != fns.end()) return *it->second;
    auto fi = std::make_unique<FnInfo>();
    unsigned n = 0;
    for (const llvm::BasicBlock &bb : *f) {
      fi->blocks.push_back(&bb);
      fi->blockIndex[&bb] = n++;
      auto &v = fi->insts[&bb];
      for (const llvm::Instruction &I : bb) v.push_back(&I);
    }
    auto *mut = const_cast<llvm::Function *>(f);
    fi->dt = std::make_unique<llvm::DominatorTree>(*mut);
    fi->li = std::make_unique<llvm::LoopInfo>(*fi->dt);
    fi->irreducible = isIrreducible(*f, *fi);
    return *(fns[f] = std::move(fi));
  }

  /// Is u -> v the back edge of a natural loop?
  bool isBackEdge(const llvm::BasicBlock *u, const llvm::BasicBlock *v) {
    FnInfo &fi = info(u->getParent());
    const llvm::Loop *l = fi.li->getLoopFor(v);
    return l && l->getHeader() == v && l->contains(u);
  }

  /// May-points-to set of a pointer operand, as base objects. `unknown` is set
  /// when it may point somewhere SVF does not name.
  std::set<NodeID> pointsTo(const llvm::Value *ptr, bool &unknown) {
    std::set<NodeID> out;
    unknown = false;
    const llvm::Value *under = llvm::getUnderlyingObject(ptr);
    if (auto it = objOf.find(under); it != objOf.end()) {
      out.insert(it->second);
      return out;
    }
    SVFValue *sv = LLVMModuleSet::getLLVMModuleSet()->getSVFValue(ptr);
    if (!sv || !pag->hasValueNode(sv)) { unknown = true; return out; }
    for (NodeID o : pta->getPts(pag->getValueNode(sv))) {
      if (pag->isBlkObjOrConstantObj(o)) { unknown = true; continue; }
      out.insert(pag->getBaseObjVar(o));
    }
    if (out.empty()) unknown = true;
    return out;
  }

  /// Call targets: the direct callee, or the points-to targets of the pointer.
  std::vector<const llvm::Function *> targets(const llvm::CallBase *ci) {
    std::vector<const llvm::Function *> out;
    const llvm::Value *callee = ci->getCalledOperand()->stripPointerCasts();
    if (const auto *f = llvm::dyn_cast<llvm::Function>(callee)) {
      out.push_back(f);
      return out;
    }
    bool unknown = false;
    for (NodeID o : pointsTo(ci->getCalledOperand(), unknown)) {
      auto it = valueOf.find(o);
      if (it == valueOf.end()) continue;
      if (const auto *f = llvm::dyn_cast<llvm::Function>(it->second)) out.push_back(f);
    }
    return out;
  }

  /// Everything a function may write, its callees included.
  const WriteSet &writes(const llvm::Function *f) {
    if (auto it = fnWrites.find(f); it != fnWrites.end()) return it->second;
    fnWrites[f] = WriteSet{}; // breaks recursion; recursion is inconclusive anyway
    WriteSet ws;
    if (f->isDeclaration()) {
      ws = externalWrites(f, nullptr);
    } else {
      for (const llvm::Instruction &I : llvm::instructions(*f)) ws.add(instWrites(&I));
    }
    return fnWrites[f] = ws;
  }

  WriteSet instWrites(const llvm::Instruction *I) {
    WriteSet ws;
    // A load writes no program object -- not even a volatile one, which LLVM's
    // mayWriteToMemory() counts as a write because the hardware may react to
    // it. Racebench declares every shared global volatile, so missing this
    // makes every ISR "write everything" and havocs every proof away.
    if (llvm::isa<llvm::LoadInst>(I)) return ws;
    if (const auto *st = llvm::dyn_cast<llvm::StoreInst>(I)) {
      bool unk = false;
      ws.objs = pointsTo(st->getPointerOperand(), unk);
      ws.all = unk;
    } else if (const auto *ci = llvm::dyn_cast<llvm::CallBase>(I)) {
      if (ci->isInlineAsm()) { ws.all = true; return ws; }
      auto ts = targets(ci);
      if (ts.empty()) { ws.all = true; return ws; }
      for (const llvm::Function *t : ts) {
        if (t->isIntrinsic()) ws.add(intrinsicWrites(ci));
        else if (qy.primitives.count(t->getName().str())) continue;
        else if (t->isDeclaration()) ws.add(externalWrites(t, ci));
        else ws.add(writes(t));
      }
    } else if (I->mayWriteToMemory() && !llvm::isa<llvm::FenceInst>(I)) {
      ws.all = true; // atomics, cmpxchg: not modelled -- assume anything
    }
    return ws;
  }

  WriteSet intrinsicWrites(const llvm::CallBase *ci) {
    WriteSet ws;
    if (!ci->mayWriteToMemory()) return ws;
    if (llvm::isa<llvm::DbgInfoIntrinsic>(ci)) return ws;
    if (const auto *ii = llvm::dyn_cast<llvm::IntrinsicInst>(ci))
      if (ii->isLifetimeStartOrEnd()) return ws;
    for (const llvm::Use &u : ci->args()) {
      if (!u->getType()->isPointerTy()) continue;
      bool unk = false;
      auto p = pointsTo(u.get(), unk);
      ws.objs.insert(p.begin(), p.end());
      ws.all = ws.all || unk;
    }
    return ws;
  }

  WriteSet externalWrites(const llvm::Function *f, const llvm::CallBase *ci) {
    WriteSet ws;
    const std::string name = f->getName().str();
    if (qy.primitives.count(name)) return ws;
    auto m = qy.models.find(name);
    if (m == qy.models.end()) {
      ws.all = qy.externalsTouchAll; // D1: may write anything
      return ws;
    }
    if (m->second == "writes-args" || m->second == "reads-writes-args") {
      if (!ci) { ws.all = true; return ws; }
      for (const llvm::Use &u : ci->args()) {
        if (!u->getType()->isPointerTy()) continue;
        bool unk = false;
        auto p = pointsTo(u.get(), unk);
        ws.objs.insert(p.begin(), p.end());
        ws.all = ws.all || unk;
      }
    }
    return ws;
  }

  /// What one pass through loop `l` may write.
  const WriteSet &loopWrites(const llvm::Loop *l) {
    if (auto it = lWrites.find(l); it != lWrites.end()) return it->second;
    WriteSet ws;
    for (const llvm::BasicBlock *bb : l->blocks())
      for (const llvm::Instruction &I : *bb) ws.add(instWrites(&I));
    return lWrites[l] = ws;
  }

  llvm::Module &M;
  const llvm::DataLayout &DL;
  SVFIR *pag;
  Andersen *pta;
  const Query &qy;
  std::map<const llvm::Value *, NodeID> objOf;
  std::map<NodeID, const llvm::Value *> valueOf;

private:
  static bool isIrreducible(const llvm::Function &f, FnInfo &fi) {
    // Remove every natural back edge; what remains must be acyclic.
    std::map<const llvm::BasicBlock *, int> color;
    bool cyclic = false;
    std::function<void(const llvm::BasicBlock *)> dfs = [&](const llvm::BasicBlock *u) {
      color[u] = 1;
      for (const llvm::BasicBlock *v : llvm::successors(u)) {
        const llvm::Loop *l = fi.li->getLoopFor(v);
        if (l && l->getHeader() == v && l->contains(u)) continue;
        if (color[v] == 1) { cyclic = true; continue; }
        if (color[v] == 0) dfs(v);
      }
      color[u] = 2;
    };
    dfs(&f.getEntryBlock());
    return cyclic;
  }

  std::map<const llvm::Function *, std::unique_ptr<FnInfo>> fns;
  std::map<const llvm::Function *, WriteSet> fnWrites;
  std::map<const llvm::Loop *, WriteSet> lWrites;
};

// ---------------------------------------------------------------------------
// The symbolic executor
// ---------------------------------------------------------------------------

enum class Phase {
  SeekA1,     // the preempted flow, before A1
  SeekSplice, // the preempted flow, after A1, before the preemption
  SeekB,      // the preempting flow, from its entry, looking for B
  SeekA2,     // the preempted flow resumed, looking for A2
  Collect,    // projection: every path from a flow's entry to one access
};

struct Addr {
  z3::expr ptr;
  unsigned size;
};

struct Frame {
  const llvm::Function *fn;
  const llvm::BasicBlock *bb;
  unsigned idx = 0;
  const llvm::BasicBlock *prev = nullptr;
  std::map<const llvm::Value *, z3::expr> regs;
  const llvm::CallBase *site = nullptr;
  // Two different decisions live at one position, and they must not mask each
  // other: the boundary BEFORE the instruction (interference, the preemption)
  // and the instruction ITSELF (choosing it as A1, B or A2). A preemption just
  // before A2 is exactly the case where both happen at once.
  bool boundaryDone = false;
  bool targetDone = false;
};

struct Activation {
  int flow;
  std::vector<Frame> frames;
};

struct State {
  std::vector<Activation> acts;
  std::map<NodeID, z3::expr> mem;
  std::set<NodeID> dirty;
  bool initMode = true; // objects not yet materialised take their initializer
  std::vector<z3::expr> pc;
  Phase phase = Phase::SeekA1;
  std::set<std::pair<const llvm::BasicBlock *, const llvm::BasicBlock *>> crossed;
  std::optional<Addr> first, remote, second;
  int spliceRun = -1;
  // A preemption was already tried in the current segment: a stretch of
  // boundaries in one block, with no store or call by the preempted flow and
  // one run set. Preempting anywhere in it is equivalent -- everything the
  // flows of that run set write is havocked at each of its boundaries anyway --
  // so one try per segment is complete.
  bool segmentSpliced = false;
  int segmentRun = -3;
  std::string spliceFn;
  unsigned spliceLine = 0;
  std::vector<unsigned> trace;
};

enum class Verdict { Unsat, Sat, Inconclusive };

struct Result {
  Verdict verdict = Verdict::Unsat;
  std::string reason;
  std::set<std::string> unconstrained;
  std::string witness; // JSON object, for SAT
  std::string method;  // how an UNSAT was reached: "projection" or "search"
  unsigned states = 0, solverCalls = 0;
  unsigned wallMs = 0;
};

class Executor {
public:
  Executor(Facts &facts, const Query &qy, z3::context &C)
      : facts(facts), qy(qy), C(C), memSort(C.array_sort(C.bv_sort(64), C.bv_sort(8))) {}

  Result run(const Candidate &cand) {
    Result res;
    auto t0 = Clock::now();
    deadline = t0 + std::chrono::milliseconds(qy.timeoutMs);
    notes.clear();
    notes.insert("timing");
    inc = std::make_unique<z3::solver>(C);
    lits.clear();
    sawUnknown = false;
    unsupported.clear();
    solverCalls = 0;

    bool sat = false;
    std::string witness;
    bool exhausted = true;
    unsigned states = 0;
    // The address projection: a relaxation of the query that drops ordering
    // and shared memory. Refuting it refutes the query.
    this->cand = &cand;
    if (projectionRefutes(cand, states)) {
      res.states = states;
      res.solverCalls = solverCalls;
      res.unconstrained = notes;
      res.method = "projection";
      res.wallMs = static_cast<unsigned>(
          std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - t0).count());
      res.verdict = unsupported.empty() ? Verdict::Unsat : Verdict::Inconclusive;
      if (!unsupported.empty()) res.reason = "unsupported-construct:" + *unsupported.begin();
      return res;
    }
    Outcome o = explore(cand, cand.a1, cand.b, states);
    if (o == Outcome::Sat) { sat = true; witness = lastWitness; }
    if (o == Outcome::Stopped) exhausted = false;
    res.states = states;
    res.solverCalls = solverCalls;
    res.unconstrained = notes;
    res.wallMs = static_cast<unsigned>(
        std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - t0).count());
    if (sat) {
      res.verdict = Verdict::Sat;
      res.witness = witness;
    } else if (!exhausted) {
      res.verdict = Verdict::Inconclusive;
      res.reason = stopReason;
    } else if (!unsupported.empty()) {
      res.verdict = Verdict::Inconclusive;
      res.reason = "unsupported-construct:" + *unsupported.begin();
    } else if (sawUnknown) {
      res.verdict = Verdict::Inconclusive;
      res.reason = "solver-unknown";
    } else {
      res.verdict = Verdict::Unsat;
      res.method = "search";
    }
    return res;
  }

private:
  enum class Outcome { Sat, Exhausted, Stopped };

  Facts &facts;
  const Query &qy;
  z3::context &C;
  z3::sort memSort;
  Clock::time_point deadline;
  std::set<std::string> notes;
  std::set<std::string> unsupported;
  bool sawUnknown = false;
  unsigned solverCalls = 0;
  unsigned freshCounter = 0;
  std::string lastWitness;
  std::string stopReason;
  const Candidate *cand = nullptr;
  Target baseT, remoteT;
  int baseFlow = -1, remoteFlow = -1;

  // -- helpers ----------------------------------------------------------

  z3::expr fresh(unsigned bits, const char *tag = "h") {
    return C.bv_const((std::string(tag) + std::to_string(freshCounter++)).c_str(), bits);
  }
  z3::expr freshMem() {
    return C.constant(("m" + std::to_string(freshCounter++)).c_str(), memSort);
  }
  z3::expr ptrOf(NodeID obj, uint64_t off = 0) {
    return C.bv_val((static_cast<uint64_t>(obj) << 40) | off, 64);
  }
  z3::expr objField(const z3::expr &p) { return p.extract(63, 40); }
  z3::expr offField(const z3::expr &p) { return z3::zext(p.extract(39, 0), 24); }

  unsigned bitsOf(llvm::Type *t) {
    if (t->isIntegerTy()) return t->getIntegerBitWidth();
    if (t->isPointerTy()) return 64;
    uint64_t b = facts.DL.getTypeSizeInBits(t).getFixedSize();
    return b ? static_cast<unsigned>(b) : 8;
  }

  z3::expr fit(const z3::expr &e, unsigned bits) {
    unsigned have = e.get_sort().bv_size();
    if (have == bits) return e;
    if (have < bits) return z3::zext(e, bits - have);
    return e.extract(bits - 1, 0);
  }

  bool timeUp() const { return Clock::now() > deadline; }

  // One incremental solver per candidate. Every path condition and query term
  // is asserted once, guarded by an indicator literal, and each check passes
  // the indicators of the current path as assumptions: Z3 then reuses the
  // bit-blasting and the learned clauses across the whole search, instead of
  // re-encoding the path condition at every branch.
  std::unique_ptr<z3::solver> inc;
  std::map<unsigned, z3::expr> lits;

  z3::expr lit(const z3::expr &e) {
    unsigned id = Z3_get_ast_id(C, e);
    if (auto it = lits.find(id); it != lits.end()) return it->second;
    z3::expr b = C.bool_const(("p" + std::to_string(id)).c_str());
    inc->add(z3::implies(b, e));
    return lits.emplace(id, b).first->second;
  }

  z3::check_result solve(const std::vector<z3::expr> &pc, const z3::expr *extra,
                         z3::model *model = nullptr) {
    ++solverCalls;
    auto left = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - Clock::now()).count();
    if (left <= 0) return z3::unknown;
    z3::params p(C);
    p.set("timeout", static_cast<unsigned>(left));
    inc->set(p);
    z3::expr_vector as(C);
    for (const z3::expr &e : pc) as.push_back(lit(e));
    if (extra) as.push_back(lit(*extra));
    z3::check_result r = inc->check(as);
    if (r == z3::unknown) sawUnknown = true;
    if (r == z3::sat && model) *model = inc->get_model();
    return r;
  }

  /// Fork on a boolean: returns which sides are (possibly) feasible.
  void branch(const z3::expr &cond, State &st, bool &canT, bool &canF) {
    z3::expr c = cond.simplify();
    if (c.is_true()) { canT = true; canF = false; return; }
    if (c.is_false()) { canT = false; canF = true; return; }
    // The path condition is satisfiable (or unknown) on entry, so if one side
    // is refuted the other is feasible without asking. If both may be, the
    // false side is taken without a check: an infeasible path dies at its next
    // check, which always includes the whole path condition.
    canT = solve(st.pc, &c) != z3::unsat;
    canF = true;
  }

  // -- memory -------------------------------------------------------------

  z3::expr initial(NodeID obj, bool initMode) {
    auto it = facts.valueOf.find(obj);
    if (initMode && it != facts.valueOf.end())
      if (const auto *g = llvm::dyn_cast<llvm::GlobalVariable>(it->second))
        if (g->hasInitializer()) {
          bool ok = true;
          z3::expr arr = z3::const_array(C.bv_sort(64), C.bv_val(0, 8));
          arr = writeConstant(arr, 0, g->getInitializer(), ok);
          if (ok) return arr;
          notes.insert("initializer:" + g->getName().str());
        }
    return freshMem();
  }

  z3::expr &memOf(State &st, NodeID obj) {
    if (st.dirty.count(obj)) {
      st.dirty.erase(obj);
      st.mem.insert_or_assign(obj, freshMem());
      return st.mem.at(obj);
    }
    auto it = st.mem.find(obj);
    if (it == st.mem.end()) it = st.mem.emplace(obj, initial(obj, st.initMode)).first;
    return it->second;
  }

  void havocAll(State &st, const std::string &why) {
    notes.insert(why);
    for (auto &[obj, _] : st.mem) st.dirty.insert(obj);
    st.initMode = false; // objects not yet seen are no longer at their initializer
  }

  void havoc(State &st, const WriteSet &ws, const std::string &why) {
    if (ws.all) { havocAll(st, why); return; }
    if (!ws.objs.empty()) notes.insert(why);
    st.dirty.insert(ws.objs.begin(), ws.objs.end());
  }

  z3::expr readBytes(const z3::expr &arr, const z3::expr &off, unsigned n) {
    z3::expr r = z3::select(arr, off);
    for (unsigned i = 1; i < n; ++i) r = z3::concat(z3::select(arr, off + C.bv_val(i, 64)), r);
    return r;
  }

  z3::expr writeBytes(z3::expr arr, const z3::expr &off, const z3::expr &v, unsigned n) {
    z3::expr w = fit(v, 8 * n);
    for (unsigned i = 0; i < n; ++i)
      arr = z3::store(arr, off + C.bv_val(i, 64), w.extract(8 * i + 7, 8 * i));
    return arr;
  }

  z3::expr writeConstant(z3::expr arr, uint64_t off, const llvm::Constant *c, bool &ok) {
    const llvm::DataLayout &DL = facts.DL;
    if (llvm::isa<llvm::ConstantAggregateZero>(c) || c->isNullValue()) return arr;
    if (const auto *ci = llvm::dyn_cast<llvm::ConstantInt>(c)) {
      unsigned n = static_cast<unsigned>(DL.getTypeStoreSize(ci->getType()));
      return writeBytes(arr, C.bv_val(off, 64),
                        C.bv_val(ci->getValue().getZExtValue(), 8 * n), n);
    }
    if (const auto *cd = llvm::dyn_cast<llvm::ConstantDataSequential>(c)) {
      uint64_t es = DL.getTypeAllocSize(cd->getElementType());
      for (unsigned i = 0; i < cd->getNumElements(); ++i)
        arr = writeConstant(arr, off + i * es, cd->getElementAsConstant(i), ok);
      return arr;
    }
    if (const auto *ca = llvm::dyn_cast<llvm::ConstantArray>(c)) {
      uint64_t es = DL.getTypeAllocSize(ca->getType()->getElementType());
      for (unsigned i = 0; i < ca->getNumOperands(); ++i)
        arr = writeConstant(arr, off + i * es, ca->getOperand(i), ok);
      return arr;
    }
    if (const auto *cs = llvm::dyn_cast<llvm::ConstantStruct>(c)) {
      const llvm::StructLayout *sl = DL.getStructLayout(cs->getType());
      for (unsigned i = 0; i < cs->getNumOperands(); ++i)
        arr = writeConstant(arr, off + sl->getElementOffset(i), cs->getOperand(i), ok);
      return arr;
    }
    if (c->getType()->isPointerTy()) {
      const llvm::Value *base = c->stripPointerCasts();
      llvm::APInt delta(64, 0);
      base = c->stripAndAccumulateConstantOffsets(DL, delta, true);
      auto it = facts.objOf.find(base);
      if (it != facts.objOf.end())
        return writeBytes(arr, C.bv_val(off, 64), ptrOf(it->second, delta.getZExtValue()), 8);
    }
    ok = false;
    return arr;
  }

  z3::expr load(State &st, const llvm::Value *ptrV, const z3::expr &ptr, unsigned n) {
    bool unknown = false;
    std::set<NodeID> objs = facts.pointsTo(ptrV, unknown);
    z3::expr off = offField(ptr);
    z3::expr obj = objField(ptr);
    // Default: a fresh value. Sound whatever the pointer turns out to be.
    z3::expr out = fresh(8 * n);
    if (unknown) notes.insert("unresolved-pointer");
    for (NodeID o : objs) {
      z3::expr v = readBytes(memOf(st, o), off, n);
      out = objs.size() == 1 && !unknown ? v : z3::ite(obj == C.bv_val(o, 24), v, out);
    }
    return out;
  }

  void store(State &st, const llvm::Value *ptrV, const z3::expr &ptr, const z3::expr &v,
             unsigned n) {
    bool unknown = false;
    std::set<NodeID> objs = facts.pointsTo(ptrV, unknown);
    if (unknown) { havocAll(st, "unresolved-pointer"); return; }
    z3::expr off = offField(ptr);
    z3::expr obj = objField(ptr);
    for (NodeID o : objs) {
      z3::expr cur = memOf(st, o);
      z3::expr upd = writeBytes(cur, off, v, n);
      st.mem.insert_or_assign(o, objs.size() == 1 ? upd : z3::ite(obj == C.bv_val(o, 24), upd, cur));
    }
  }

  // -- values ---------------------------------------------------------------

  z3::expr val(const llvm::Value *v, Frame &fr) {
    if (auto it = fr.regs.find(v); it != fr.regs.end()) return it->second;
    llvm::Type *t = v->getType();
    if (const auto *ci = llvm::dyn_cast<llvm::ConstantInt>(v))
      return C.bv_val(ci->getValue().getZExtValue(), ci->getBitWidth());
    if (llvm::isa<llvm::ConstantPointerNull>(v)) return C.bv_val(0, 64);
    if (llvm::isa<llvm::GlobalValue>(v)) {
      auto it = facts.objOf.find(v);
      return it != facts.objOf.end() ? ptrOf(it->second) : fresh(64);
    }
    if (const auto *ce = llvm::dyn_cast<llvm::ConstantExpr>(v)) {
      if (ce->getOpcode() == llvm::Instruction::GetElementPtr ||
          ce->getOpcode() == llvm::Instruction::BitCast ||
          ce->getOpcode() == llvm::Instruction::AddrSpaceCast) {
        llvm::APInt delta(64, 0);
        const llvm::Value *base = ce->stripAndAccumulateConstantOffsets(facts.DL, delta, true);
        if (base != ce) return val(base, fr) + C.bv_val(delta.getZExtValue(), 64);
      }
      if (ce->getOpcode() == llvm::Instruction::PtrToInt)
        return fit(val(ce->getOperand(0), fr), bitsOf(t));
      if (ce->getOpcode() == llvm::Instruction::IntToPtr)
        return fit(val(ce->getOperand(0), fr), 64);
      notes.insert("constant-expression");
      return fresh(bitsOf(t));
    }
    if (const auto *cf = llvm::dyn_cast<llvm::ConstantFP>(v))
      return C.bv_val(cf->getValueAPF().bitcastToAPInt().getZExtValue(), bitsOf(t));
    // undef, poison, metadata, aggregates as values, an argument never bound
    return fresh(bitsOf(t));
  }

  z3::expr asBool(const z3::expr &bv) { return bv == C.bv_val(1, bv.get_sort().bv_size()); }
  z3::expr fromBool(const z3::expr &b) { return z3::ite(b, C.bv_val(1, 1), C.bv_val(0, 1)); }

  // -- control --------------------------------------------------------------

  int runSetAt(int flow, const Frame &fr) {
    FnInfo &fi = facts.info(fr.fn);
    unsigned b = fi.blockIndex.at(fr.bb);
    auto it = qy.runAt.find({flow, fr.fn->getName().str(), b});
    if (it == qy.runAt.end()) return -2; // not listed: fall back to the static set
    return fr.idx < it->second.size() ? it->second[fr.idx] : -1;
  }

  const std::vector<int> &runFlows(int flow, int id) {
    static const std::vector<int> none;
    if (id == -2) return qy.staticRun.at(flow);
    if (id < 0) return none;
    return qy.runSets.at(id);
  }

  bool runs(int flow, int id, int who) {
    const auto &v = runFlows(flow, id);
    return std::find(v.begin(), v.end(), who) != v.end();
  }

  void interfere(State &st, int flow, int id) {
    for (int y : runFlows(flow, id)) havoc(st, flowWrites(y), "interference");
  }

  const WriteSet &flowWrites(int y) {
    if (auto it = fwCache.find(y); it != fwCache.end()) return it->second;
    const llvm::Function *f = facts.M.getFunction(qy.flowEntries.at(y));
    WriteSet ws;
    if (!f || f->isDeclaration()) ws.all = true;
    else ws = facts.writes(f);
    return fwCache[y] = ws;
  }
  std::map<int, WriteSet> fwCache;

  bool backEdgesAllowed(Phase p) { return p == Phase::SeekSplice || p == Phase::SeekA2; }

  /// Follow a CFG edge. Returns false when the path ends here.
  bool go(State &st, Frame &fr, const llvm::BasicBlock *to) {
    const llvm::BasicBlock *from = fr.bb;
    FnInfo &fi = facts.info(fr.fn);
    bool back = facts.isBackEdge(from, to);
    if (back) {
      // Every later iteration is covered by the havoc at the header, so
      // looking for A1 or B a back edge adds nothing; between A1 and A2 one
      // crossing is what reaches a later iteration (Soundness Assumptions G2).
      if (!backEdgesAllowed(st.phase) || st.acts.size() > 1) return false;
      if (!st.crossed.insert({from, to}).second) return false;
    }
    const llvm::Loop *l = fi.li->getLoopFor(to);
    bool header = l && l->getHeader() == to;
    bool havocked = false;
    if (header && (back || !l->contains(from))) {
      havoc(st, facts.loopWrites(l), "loop");
      havocked = true;
    }
    // PHIs, evaluated simultaneously on the predecessor's values.
    std::vector<std::pair<const llvm::PHINode *, z3::expr>> phis;
    for (const llvm::PHINode &phi : to->phis()) {
      if (havocked) { phis.emplace_back(&phi, fresh(bitsOf(phi.getType()))); continue; }
      int k = phi.getBasicBlockIndex(from);
      phis.emplace_back(&phi, k >= 0 ? val(phi.getIncomingValue(k), fr)
                                     : fresh(bitsOf(phi.getType())));
    }
    for (auto &[p, e] : phis) fr.regs.insert_or_assign(p, e);
    fr.prev = from;
    fr.bb = to;
    fr.idx = 0;
    newSegment(st);
    while (fr.idx < fi.insts.at(to).size() && llvm::isa<llvm::PHINode>(fi.insts.at(to)[fr.idx]))
      ++fr.idx;
    fr.boundaryDone = fr.targetDone = false;
    return true;
  }

  void advance(Frame &fr) { ++fr.idx; fr.boundaryDone = fr.targetDone = false; }
  void newSegment(State &st) { st.segmentSpliced = false; }

  Frame enter(const llvm::Function *f, const llvm::CallBase *site,
              const std::vector<z3::expr> &args) {
    Frame fr{f, &f->getEntryBlock()};
    unsigned i = 0;
    for (const llvm::Argument &a : f->args()) {
      fr.regs.insert_or_assign(&a, i < args.size() ? fit(args[i], bitsOf(a.getType()))
                                                   : fresh(bitsOf(a.getType())));
      ++i;
    }
    fr.site = site;
    if (facts.info(f).irreducible) unsupported.insert("irreducible-cfg:" + f->getName().str());
    return fr;
  }

  Addr addrOf(const llvm::Instruction *I, Frame &fr) {
    if (const auto *ld = llvm::dyn_cast<llvm::LoadInst>(I))
      return {val(ld->getPointerOperand(), fr),
              static_cast<unsigned>(facts.DL.getTypeStoreSize(ld->getType()))};
    const auto *st = llvm::cast<llvm::StoreInst>(I);
    return {val(st->getPointerOperand(), fr),
            static_cast<unsigned>(facts.DL.getTypeStoreSize(st->getValueOperand()->getType()))};
  }

  z3::expr overlap(const Addr &a, const Addr &b) {
    z3::expr oa = offField(a.ptr), ob = offField(b.ptr);
    return objField(a.ptr) == objField(b.ptr) && z3::ult(oa, ob + C.bv_val(b.size, 64)) &&
           z3::ult(ob, oa + C.bv_val(a.size, 64));
  }

  void splice(State &st, int runId, const Frame &at) {
    const llvm::Function *f = facts.M.getFunction(qy.flowEntries.at(remoteFlow));
    if (!f || f->isDeclaration()) {
      unsupported.insert("missing-entry");
      st.acts.clear();
      return;
    }
    st.spliceRun = runId;
    st.spliceFn = at.fn->getName().str();
    if (at.idx < facts.info(at.fn).insts.at(at.bb).size())
      if (const llvm::DebugLoc &dl = facts.info(at.fn).insts.at(at.bb)[at.idx]->getDebugLoc())
        st.spliceLine = dl.getLine();
    st.acts.back().frames.back().boundaryDone = true;
    st.acts.push_back(Activation{remoteFlow, {enter(f, nullptr, {})}});
    st.phase = Phase::SeekB;
  }

  // -- the address projection -----------------------------------------------
  //
  // Every path from a flow's entry to one access, with its condition and the
  // address it touches. No preemption is spliced in and back edges are cut, as
  // when looking for A1: the havoc at loop headers and at every interference
  // point already covers every state the access can be reached in. Each side is
  // explored on its own, so values the flows share are NOT tied together --
  // which is what makes this a relaxation, and its UNSAT a proof.

  int collectFlow = -1;
  const llvm::Instruction *collectI = nullptr;
  std::vector<std::pair<std::vector<z3::expr>, Addr>> collected;
  static constexpr unsigned kMaxProjectionPaths = 256;

  /// Returns false when the projection could not be computed completely.
  bool project(const Target &t, z3::expr &env, unsigned &size, unsigned &states) {
    const llvm::Function *entry = facts.M.getFunction(qy.flowEntries.at(t.flow));
    if (!entry || entry->isDeclaration()) return false;
    collectFlow = t.flow;
    collectI = t.I;
    collected.clear();
    baseFlow = t.flow;
    remoteFlow = -1;
    State init;
    init.acts.push_back(Activation{t.flow, {enter(entry, nullptr, {})}});
    init.initMode = qy.flowKinds.at(t.flow) == "task";
    init.phase = Phase::Collect;
    std::vector<State> work;
    work.push_back(std::move(init));
    unsigned local = 0;
    while (!work.empty()) {
      if (timeUp() || ++local > qy.maxStates / 4 || collected.size() > kMaxProjectionPaths)
        return false;
      ++states;
      State st = std::move(work.back());
      work.pop_back();
      step(st, work);
    }
    z3::expr p = fresh(64, "proj");
    env = C.bool_val(false);
    size = 0;
    for (auto &[pc, a] : collected) {
      z3::expr conj = (p == a.ptr);
      for (const z3::expr &e : pc) conj = conj && e;
      env = env || conj;
      size = std::max(size, a.size);
    }
    env = env && (p == p); // keep `p` referenced when there are no paths
    projVar = p;
    return true;
  }
  std::optional<z3::expr> projVar;

  bool projectionRefutes(const Candidate &c, unsigned &states) {
    Target a1 = c.a1, b = c.b, a2 = c.a2;
    if (!resolve(a1) || !resolve(b) || !resolve(a2)) return false;
    z3::expr e1 = C.bool_val(true), eb = C.bool_val(true), e2 = C.bool_val(true);
    unsigned s1 = 0, sb = 0, s2 = 0;
    if (!project(a1, e1, s1, states)) return false;
    Addr p1{*projVar, s1};
    if (!project(b, eb, sb, states)) return false;
    Addr pb{*projVar, sb};
    if (!project(a2, e2, s2, states)) return false;
    Addr p2{*projVar, s2};
    z3::expr goal = e1 && eb && e2 && overlap(p1, pb) && overlap(pb, p2) && overlap(p1, p2);
    std::vector<z3::expr> none;
    return solve(none, &goal) == z3::unsat;
  }

  // -- the search -----------------------------------------------------------

  Outcome explore(const Candidate &c, const Target &base, const Target &remote,
                  unsigned &states) {
    cand = &c;
    baseT = base;
    remoteT = remote;
    baseFlow = base.flow;
    remoteFlow = remote.flow;
    const llvm::Function *entry = facts.M.getFunction(qy.flowEntries.at(baseFlow));
    if (!entry || entry->isDeclaration()) { unsupported.insert("missing-entry"); return Outcome::Exhausted; }
    if (!resolve(baseT) || !resolve(remoteT) || !resolveA2()) {
      unsupported.insert("unresolved-target");
      return Outcome::Exhausted;
    }

    State init;
    init.acts.push_back(Activation{baseFlow, {enter(entry, nullptr, {})}});
    // F8's counterpart for values: an ISR may fire anywhere, so its view of
    // memory on entry is unconstrained. Only the main task starts from the
    // initializers.
    init.initMode = qy.flowKinds.at(baseFlow) == "task";
    if (!init.initMode) notes.insert("isr-entry-state");
    init.phase = Phase::SeekA1;

    std::vector<State> work;
    work.push_back(std::move(init));
    while (!work.empty()) {
      if (timeUp()) { stopReason = "timeout"; return Outcome::Stopped; }
      if (++states > qy.maxStates) { stopReason = "budget"; return Outcome::Stopped; }
      State st = std::move(work.back());
      work.pop_back();
      if (step(st, work)) return Outcome::Sat;
    }
    return Outcome::Exhausted;
  }

  Target a2T;
  bool resolveA2() { a2T = cand->a2; return resolve(a2T); }

  bool resolve(Target &t) {
    const llvm::Function *f = facts.M.getFunction(t.fn);
    if (!f || f->isDeclaration()) return false;
    FnInfo &fi = facts.info(f);
    if (t.block >= fi.blocks.size()) return false;
    const auto &v = fi.insts.at(fi.blocks[t.block]);
    if (t.inst >= v.size()) return false;
    t.I = v[t.inst];
    return llvm::isa<llvm::LoadInst>(t.I) || llvm::isa<llvm::StoreInst>(t.I);
  }

  /// Run one state until it forks, ends, or proves the query. Returns true on SAT.
  bool step(State &st, std::vector<State> &work) {
    unsigned guard = 0;
    while (true) {
      if (++guard > 200000) { stopReason = "budget"; unsupported.insert("path-length"); return false; }
      if (st.acts.empty()) return false;
      Activation &act = st.acts.back();
      if (act.frames.empty()) return false;
      Frame &fr = act.frames.back();
      FnInfo &fi = facts.info(fr.fn);
      const auto &insts = fi.insts.at(fr.bb);
      if (fr.idx >= insts.size()) return false;
      const llvm::Instruction *I = insts[fr.idx];

      // Interference at this boundary, then the decisions that live here.
      int rid = runSetAt(act.flow, fr);
      if (!fr.boundaryDone) {
        interfere(st, act.flow, rid);
        if (rid != st.segmentRun) { st.segmentRun = rid; st.segmentSpliced = false; }
        if (st.phase == Phase::SeekSplice && act.flow == baseFlow && !st.segmentSpliced &&
            runs(baseFlow, rid, remoteFlow)) {
          st.segmentSpliced = true;
          State alt = st;
          alt.acts.back().frames.back().boundaryDone = true;
          work.push_back(std::move(alt)); // keep looking further on
          splice(st, rid, fr);
          continue;
        }
        fr.boundaryDone = true;
      }

      if (const llvm::DebugLoc &dl = I->getDebugLoc())
        if (act.flow == baseFlow && (st.trace.empty() || st.trace.back() != dl.getLine())) {
          st.trace.push_back(dl.getLine());
          if (st.trace.size() > 400) st.trace.erase(st.trace.begin());
        }

      if (!fr.targetDone) {
        bool handled = false;
        if (decide(st, work, I, act, fr, handled)) return true;
        if (handled) continue;
      }
      if (!execute(st, work, I, fr)) return false;
    }
  }

  /// Fork decisions at a target instruction. Returns true on SAT.
  bool decide(State &st, std::vector<State> &work, const llvm::Instruction *I,
              Activation &act, Frame &fr, bool &handled) {
    if (st.phase == Phase::Collect && act.flow == collectFlow && I == collectI) {
      State skip = st;
      skip.acts.back().frames.back().targetDone = true;
      work.push_back(std::move(skip));
      collected.emplace_back(st.pc, addrOf(I, fr));
      handled = true;
      st.acts.clear();
      return false;
    }
    if (act.flow == baseFlow && st.phase == Phase::SeekA1 && I == baseT.I) {
      State skip = st;
      skip.acts.back().frames.back().targetDone = true;
      work.push_back(std::move(skip));
      st.first = addrOf(I, fr);
      st.phase = Phase::SeekSplice;
      fr.targetDone = true;
      return false;
    }
    if (act.flow == baseFlow && st.phase == Phase::SeekA2 && I == a2T.I) {
      State skip = st;
      skip.acts.back().frames.back().targetDone = true;
      work.push_back(std::move(skip));
      Addr a2 = addrOf(I, fr);
      z3::expr goal = overlap(*st.first, *st.remote) && overlap(*st.remote, a2) &&
                      overlap(*st.first, a2);
      z3::model m(C);
      if (solve(st.pc, &goal, &m) == z3::sat) {
        lastWitness = witness(st, I);
        return true;
      }
      handled = true;
      st.acts.clear(); // this branch is refuted
      return false;
    }
    if (act.flow == remoteFlow && st.phase == Phase::SeekB && I == remoteT.I) {
      State skip = st;
      skip.acts.back().frames.back().targetDone = true;
      work.push_back(std::move(skip));
      st.remote = addrOf(I, fr);
      // A1 and B must touch the same memory; refute early when they cannot.
      {
        z3::expr ab = overlap(*st.first, *st.remote);
        if (solve(st.pc, &ab) == z3::unsat) { handled = true; st.acts.clear(); return false; }
        st.pc.push_back(ab);
      }
      // Back to the preempted flow. Everything that may have run at the
      // preemption point -- B's flow included, which goes on after B -- may
      // have changed what it writes.
      st.acts.pop_back();
      havoc(st, flowWritesOf(st.spliceRun), "interference");
      st.phase = Phase::SeekA2;
      // One crossing per back edge per phase: the preemption and A2 may each
      // lie in a later iteration than the one before them.
      st.crossed.clear();
      handled = true;
      return false;
    }
    return false;
  }

  WriteSet flowWritesOf(int runId) {
    WriteSet ws;
    for (int y : runFlows(baseFlow, runId)) ws.add(flowWrites(y));
    return ws;
  }

  std::string witness(const State &st, const llvm::Instruction *last) {
    std::ostringstream o;
    o << "{\"preempted_at\": {\"function\": " << q(st.spliceFn) << ", \"line\": "
      << st.spliceLine << "}, \"path_lines\": [";
    for (size_t i = 0; i < st.trace.size(); ++i) o << (i ? ", " : "") << st.trace[i];
    o << "]}";
    (void)last;
    return o.str();
  }

  /// Execute one instruction. Returns false when the path ends.
  bool execute(State &st, std::vector<State> &work, const llvm::Instruction *I, Frame &fr) {
    using namespace llvm;
    const DataLayout &DL = facts.DL;

    if (const auto *a = dyn_cast<AllocaInst>(I)) {
      auto it = facts.objOf.find(a);
      if (it != facts.objOf.end()) {
        st.dirty.erase(it->second);
        st.mem.insert_or_assign(it->second, freshMem());
        fr.regs.insert_or_assign(a, ptrOf(it->second));
      } else {
        fr.regs.insert_or_assign(a, fresh(64));
      }
      advance(fr);
      return true;
    }
    if (const auto *ld = dyn_cast<LoadInst>(I)) {
      unsigned n = static_cast<unsigned>(DL.getTypeStoreSize(ld->getType()));
      z3::expr v = load(st, ld->getPointerOperand(), val(ld->getPointerOperand(), fr), n);
      fr.regs.insert_or_assign(ld, fit(v, bitsOf(ld->getType())));
      advance(fr);
      return true;
    }
    if (const auto *s = dyn_cast<StoreInst>(I)) {
      unsigned n = static_cast<unsigned>(DL.getTypeStoreSize(s->getValueOperand()->getType()));
      store(st, s->getPointerOperand(), val(s->getPointerOperand(), fr),
            val(s->getValueOperand(), fr), n);
      newSegment(st);
      advance(fr);
      return true;
    }
    if (const auto *bo = dyn_cast<BinaryOperator>(I)) {
      if (!bo->getType()->isIntegerTy()) {
        notes.insert("floating-point");
        fr.regs.insert_or_assign(bo, fresh(bitsOf(bo->getType())));
        advance(fr);
        return true;
      }
      z3::expr a = val(bo->getOperand(0), fr), b = val(bo->getOperand(1), fr);
      std::optional<z3::expr> r;
      switch (bo->getOpcode()) {
      case Instruction::Add: r = a + b; break;
      case Instruction::Sub: r = a - b; break;
      case Instruction::Mul: r = a * b; break;
      case Instruction::UDiv: r = z3::udiv(a, b); break;
      case Instruction::SDiv: r = a / b; break;
      case Instruction::URem: r = z3::urem(a, b); break;
      case Instruction::SRem: r = z3::srem(a, b); break;
      case Instruction::Shl: r = z3::shl(a, b); break;
      case Instruction::LShr: r = z3::lshr(a, b); break;
      case Instruction::AShr: r = z3::ashr(a, b); break;
      case Instruction::And: r = a & b; break;
      case Instruction::Or: r = a | b; break;
      case Instruction::Xor: r = a ^ b; break;
      default: r = fresh(bitsOf(bo->getType())); break;
      }
      fr.regs.insert_or_assign(bo, *r);
      advance(fr);
      return true;
    }
    if (const auto *un = dyn_cast<UnaryOperator>(I)) {
      notes.insert("floating-point");
      fr.regs.insert_or_assign(un, fresh(bitsOf(un->getType())));
      advance(fr);
      return true;
    }
    if (const auto *ic = dyn_cast<ICmpInst>(I)) {
      z3::expr a = val(ic->getOperand(0), fr), b = val(ic->getOperand(1), fr);
      unsigned w = std::max(a.get_sort().bv_size(), b.get_sort().bv_size());
      a = fit(a, w);
      b = fit(b, w);
      std::optional<z3::expr> c;
      switch (ic->getPredicate()) {
      case CmpInst::ICMP_EQ: c = a == b; break;
      case CmpInst::ICMP_NE: c = a != b; break;
      case CmpInst::ICMP_UGT: c = z3::ugt(a, b); break;
      case CmpInst::ICMP_UGE: c = z3::uge(a, b); break;
      case CmpInst::ICMP_ULT: c = z3::ult(a, b); break;
      case CmpInst::ICMP_ULE: c = z3::ule(a, b); break;
      case CmpInst::ICMP_SGT: c = a > b; break;
      case CmpInst::ICMP_SGE: c = a >= b; break;
      case CmpInst::ICMP_SLT: c = a < b; break;
      case CmpInst::ICMP_SLE: c = a <= b; break;
      default: c = asBool(fresh(1)); break;
      }
      fr.regs.insert_or_assign(ic, fromBool(*c));
      advance(fr);
      return true;
    }
    if (isa<FCmpInst>(I)) {
      notes.insert("floating-point");
      fr.regs.insert_or_assign(I, fresh(1));
      advance(fr);
      return true;
    }
    if (const auto *se = dyn_cast<SelectInst>(I)) {
      unsigned w = bitsOf(se->getType());
      fr.regs.insert_or_assign(se, z3::ite(asBool(val(se->getCondition(), fr)),
                                           fit(val(se->getTrueValue(), fr), w),
                                           fit(val(se->getFalseValue(), fr), w)));
      advance(fr);
      return true;
    }
    if (const auto *ca = dyn_cast<CastInst>(I)) {
      z3::expr a = val(ca->getOperand(0), fr);
      unsigned w = bitsOf(ca->getType());
      std::optional<z3::expr> r;
      switch (ca->getOpcode()) {
      case Instruction::ZExt: r = fit(a, w); break;
      case Instruction::SExt: r = z3::sext(a, w - a.get_sort().bv_size()); break;
      case Instruction::Trunc: r = a.extract(w - 1, 0); break;
      case Instruction::BitCast:
      case Instruction::AddrSpaceCast:
      case Instruction::PtrToInt:
      case Instruction::IntToPtr: r = fit(a, w); break;
      default: notes.insert("floating-point"); r = fresh(w); break;
      }
      fr.regs.insert_or_assign(ca, *r);
      advance(fr);
      return true;
    }
    if (const auto *gep = dyn_cast<GetElementPtrInst>(I)) {
      MapVector<Value *, APInt> vars;
      APInt cst(64, 0);
      z3::expr p = val(gep->getPointerOperand(), fr);
      if (cast<GEPOperator>(gep)->collectOffset(DL, 64, vars, cst)) {
        p = p + C.bv_val(cst.getZExtValue(), 64);
        for (auto &[v, scale] : vars) {
          z3::expr idx = val(v, fr);
          unsigned iw = idx.get_sort().bv_size();
          idx = iw < 64 ? z3::sext(idx, 64 - iw) : fit(idx, 64);
          p = p + idx * C.bv_val(scale.getZExtValue(), 64);
        }
      } else {
        notes.insert("pointer-arithmetic");
        p = fresh(64);
      }
      fr.regs.insert_or_assign(gep, p);
      advance(fr);
      return true;
    }
    if (const auto *ci = dyn_cast<CallBase>(I)) { newSegment(st); return call(st, work, ci, fr); }
    if (const auto *br = dyn_cast<BranchInst>(I)) {
      if (br->isUnconditional()) return go(st, fr, br->getSuccessor(0));
      z3::expr c = asBool(val(br->getCondition(), fr));
      bool canT = false, canF = false;
      branch(c, st, canT, canF);
      if (canT && canF) {
        State alt = st;
        alt.pc.push_back(!c);
        if (go(alt, alt.acts.back().frames.back(), br->getSuccessor(1)))
          work.push_back(std::move(alt));
      }
      if (canT) { st.pc.push_back(c); return go(st, fr, br->getSuccessor(0)); }
      if (canF) { st.pc.push_back(!c); return go(st, fr, br->getSuccessor(1)); }
      return false;
    }
    if (const auto *sw = dyn_cast<SwitchInst>(I)) {
      z3::expr c = val(sw->getCondition(), fr);
      z3::expr none = C.bool_val(true);
      for (auto &cs : sw->cases()) {
        z3::expr eq = c == C.bv_val(cs.getCaseValue()->getZExtValue(), c.get_sort().bv_size());
        none = none && !eq;
        if (solve(st.pc, &eq) == z3::unsat) continue;
        State alt = st;
        alt.pc.push_back(eq);
        if (go(alt, alt.acts.back().frames.back(), cs.getCaseSuccessor()))
          work.push_back(std::move(alt));
      }
      if (solve(st.pc, &none) == z3::unsat) return false;
      st.pc.push_back(none);
      return go(st, fr, sw->getDefaultDest());
    }
    if (const auto *ret = dyn_cast<ReturnInst>(I)) {
      std::optional<z3::expr> rv;
      if (ret->getReturnValue()) rv = val(ret->getReturnValue(), fr);
      Activation &act = st.acts.back();
      const CallBase *site = fr.site;
      act.frames.pop_back();
      if (act.frames.empty()) return false; // the flow finished without the target
      Frame &caller = act.frames.back();
      newSegment(st);
      if (rv && site && !site->getType()->isVoidTy())
        caller.regs.insert_or_assign(site, fit(*rv, bitsOf(site->getType())));
      advance(caller);
      return true;
    }
    if (isa<UnreachableInst>(I)) return false;
    if (I->isTerminator()) {
      unsupported.insert(std::string("terminator:") + I->getOpcodeName());
      return false;
    }
    // Anything else: its value is unconstrained, and if it may write memory,
    // so is everything it may write.
    notes.insert(std::string("instruction:") + I->getOpcodeName());
    if (I->mayWriteToMemory()) havoc(st, facts.instWrites(I), "instruction");
    if (!I->getType()->isVoidTy()) fr.regs.insert_or_assign(I, fresh(bitsOf(I->getType())));
    advance(fr);
    return true;
  }

  bool call(State &st, std::vector<State> &work, const llvm::CallBase *ci, Frame &fr) {
    using namespace llvm;
    auto result = [&](State &s) {
      Frame &f = s.acts.back().frames.back();
      if (!ci->getType()->isVoidTy()) f.regs.insert_or_assign(ci, fresh(bitsOf(ci->getType())));
      advance(f);
    };
    if (ci->isInlineAsm()) { havocAll(st, "inline-asm"); result(st); return true; }
    std::vector<const Function *> ts = facts.targets(ci);
    if (ts.empty()) { havocAll(st, "unresolved-indirect-call"); result(st); return true; }
    bool indirect = !isa<Function>(ci->getCalledOperand()->stripPointerCasts());
    z3::expr calleePtr = indirect ? val(ci->getCalledOperand(), fr) : C.bv_val(0, 64);

    // One branch per possible target; the first continues in `st`.
    for (size_t k = 0; k < ts.size(); ++k) {
      const Function *t = ts[k];
      bool last = k + 1 == ts.size();
      State *s = &st;
      State alt;
      if (!last) { alt = st; s = &alt; }
      if (indirect) {
        auto it = facts.objOf.find(t);
        if (it != facts.objOf.end()) {
          z3::expr eq = calleePtr == ptrOf(it->second);
          if (solve(s->pc, &eq) == z3::unsat) { if (last) return false; continue; }
          s->pc.push_back(eq);
        }
      }
      Frame &f = s->acts.back().frames.back();
      bool keep = invoke(*s, ci, t, f);
      if (!last) { if (keep) work.push_back(std::move(alt)); }
      else return keep;
    }
    return false;
  }

  bool invoke(State &st, const llvm::CallBase *ci, const llvm::Function *t, Frame &fr) {
    using namespace llvm;
    auto result = [&]() {
      if (!ci->getType()->isVoidTy()) fr.regs.insert_or_assign(ci, fresh(bitsOf(ci->getType())));
      advance(fr);
    };
    const std::string name = t->getName().str();
    if (t->isIntrinsic()) {
      WriteSet ws = facts.intrinsicWrites(ci);
      if (!ws.objs.empty() || ws.all) havoc(st, ws, "intrinsic:" + name);
      result();
      return true;
    }
    if (qy.primitives.count(name)) { result(); return true; } // the mask is stage 2's
    if (t->isDeclaration()) {
      WriteSet ws = facts.externalWrites(t, ci);
      if (!ws.objs.empty() || ws.all) havoc(st, ws, "external:" + name);
      result();
      return true;
    }
    for (const Activation &a : st.acts)
      for (const Frame &f : a.frames)
        if (f.fn == t && &a == &st.acts.back()) {
          unsupported.insert("recursion:" + name);
          return false;
        }
    if (st.acts.back().frames.size() > 64) { unsupported.insert("call-depth"); return false; }
    std::vector<z3::expr> args;
    for (const Use &u : ci->args()) args.push_back(val(u.get(), fr));
    st.acts.back().frames.push_back(enter(t, ci, args));
    return true;
  }
};

const char *verdictName(Verdict v) {
  switch (v) {
  case Verdict::Unsat: return "unsat";
  case Verdict::Sat: return "sat";
  default: return "inconclusive";
  }
}

} // namespace

int main(int argc, char **argv) {
  std::string queryPath;
  std::vector<char *> passthrough{argv[0]};
  bool wantStats = false;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--query" && i + 1 < argc) { queryPath = argv[++i]; continue; }
    if (a.rfind("-stat", 0) == 0) wantStats = true;
    passthrough.push_back(argv[i]);
  }
  static char statOff[] = "-stat=false";
  if (!wantStats) passthrough.push_back(statOff);

  Query qy;
  std::string err;
  if (queryPath.empty() || !readQuery(queryPath, qy, err)) {
    std::cerr << "irqrace-stage3: " << (err.empty() ? "need --query FILE" : err) << "\n";
    return 2;
  }

  int pc = static_cast<int>(passthrough.size());
  std::vector<std::string> moduleNameVec = OptionBase::parseOptions(
      pc, passthrough.data(), "irqrace stage 3", "--query FILE <input-bitcode>");
  if (moduleNameVec.empty()) {
    std::cerr << "irqrace-stage3: need bitcode\n";
    return 2;
  }
  SVFModule *svfModule = LLVMModuleSet::buildSVFModule(moduleNameVec);
  SVFIRBuilder builder(svfModule);
  SVFIR *pag = builder.build();
  Andersen *pta = AndersenWaveDiff::createAndersenWaveDiff(pag);
  llvm::Module *M = LLVMModuleSet::getLLVMModuleSet()->getMainLLVMModule();

  Facts facts(*M, pag, pta, qy);
  if (std::getenv("IRQRACE_STAGE3_DEBUG")) {
    unsigned g = 0, a = 0, f = 0;
    for (const auto &[v, o] : facts.objOf) {
      if (llvm::isa<llvm::GlobalVariable>(v)) ++g;
      else if (llvm::isa<llvm::AllocaInst>(v)) ++a;
      else if (llvm::isa<llvm::Function>(v)) ++f;
    }
    std::cerr << "objects: " << g << " globals, " << a << " allocas, " << f << " functions\n";
    for (size_t y = 0; y < qy.flowIds.size(); ++y) {
      const llvm::Function *fn = M->getFunction(qy.flowEntries[y]);
      if (!fn) continue;
      const WriteSet &ws = facts.writes(fn);
      std::cerr << "writes " << qy.flowIds[y] << (ws.all ? " ALL" : "") << ":";
      for (NodeID o : ws.objs) {
        auto it = facts.valueOf.find(o);
        std::cerr << " " << o << "="
                  << (it != facts.valueOf.end() && it->second->hasName() ? it->second->getName().str() : "?");
      }
      std::cerr << "\n";
    }
  }
  z3::context C;
  Executor ex(facts, qy, C);

  unsigned major, minor, build, rev;
  Z3_get_version(&major, &minor, &build, &rev);
  std::ostringstream ver;
  ver << major << "." << minor << "." << build;

  for (const Candidate &c : qy.cands) {
    Result r = ex.run(c);
    std::ostringstream o;
    o << "{\"candidate_id\": " << q(c.id) << ", \"verdict\": " << q(verdictName(r.verdict))
      << ", \"engine\": \"z3\", \"engine_version\": " << q(ver.str()) << ", \"reason\": "
      << (r.reason.empty() ? "null" : q(r.reason)) << ", \"assignment\": "
      << (r.witness.empty() ? "null" : r.witness) << ", \"unconstrained\": [";
    bool first = true;
    for (const std::string &u : r.unconstrained) {
      o << (first ? "" : ", ") << q(u);
      first = false;
    }
    o << "], \"wall_ms\": " << r.wallMs << ", \"timeout_ms\": " << qy.timeoutMs
      << ", \"states\": " << r.states << ", \"solver_calls\": " << r.solverCalls
      << ", \"method\": " << (r.method.empty() ? "null" : q(r.method)) << "}";
    std::cout << o.str() << std::endl;
  }

  AndersenWaveDiff::releaseAndersenWaveDiff();
  SVFIR::releaseSVFIR();
  LLVMModuleSet::releaseLLVMModuleSet();
  return 0;
}
