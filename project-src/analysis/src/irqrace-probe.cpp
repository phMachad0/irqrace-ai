//===- irqrace-probe.cpp --------------------------------------------------===//
//
// W1 toolchain probe. Loads whole-program bitcode through SVF, runs the
// may-alias pointer analysis, and prints a JSON report of what the module
// actually contains.
//
// This is not a throwaway smoke test. Its output populates the `build` block of
// the C3 run manifest (translation units, functions with bodies, functions
// declared only) and answers Dashboard Design R4 and R7:
//
//   R4  report what the build produced; the declared-only list IS the external
//       function problem and the user must see its size before trusting a result
//   R7  validate the C1 interrupt model against the built bitcode and warn in
//       both directions -- an entry point that does not exist in the module, and
//       a listed masking primitive that is never called
//
// Usage:
//   irqrace-probe [--entry NAME]... [--primitive NAME]... whole.bc
//
//===----------------------------------------------------------------------===//

#include "SVF-LLVM/LLVMModule.h"
#include "SVF-LLVM/SVFIRBuilder.h"
#include "WPA/Andersen.h"
#include "Util/Options.h"

#include "llvm/IR/Module.h"
#include "llvm/IR/DebugInfo.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/InstIterator.h"

#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

using namespace SVF;

namespace {

/// Minimal JSON string escaping. The module under analysis is untrusted input,
/// so nothing from it is ever emitted raw.
std::string esc(const std::string &s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (char c : s) {
    switch (c) {
    case '"':  out += "\\\""; break;
    case '\\': out += "\\\\"; break;
    case '\n': out += "\\n";  break;
    case '\r': out += "\\r";  break;
    case '\t': out += "\\t";  break;
    default:
      if (static_cast<unsigned char>(c) < 0x20) {
        char buf[8];
        snprintf(buf, sizeof buf, "\\u%04x", c);
        out += buf;
      } else {
        out += c;
      }
    }
  }
  return out;
}

/// Walk DW_TAG_volatile_type / typedef / const wrappers to decide whether the
/// declared type of a global carries `volatile`. Racebench declares all shared
/// state as `volatile int`, and the LLVM GlobalVariable itself does not record
/// it -- volatility lives on the loads and stores. Debug info is the only place
/// the declared type survives.
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
    // `volatile int a[10]` puts the qualifier on the array's element type, not
    // on the array. Racebench's shared state is mostly arrays, so missing this
    // would report every one of them as non-volatile.
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
      // A pointer to an unnamed subroutine type is a function pointer, which is
      // how embedded code dispatches -- worth naming rather than printing " *".
      if (llvm::isa_and_nonnull<llvm::DISubroutineType>(d->getBaseType()))
        return "function pointer";
      return base + " *";
    default:                                return base;
    }
  }
  if (const auto *c = llvm::dyn_cast<llvm::DICompositeType>(t)) {
    if (c->getTag() == llvm::dwarf::DW_TAG_array_type)
      return typeName(c->getBaseType()) + "[]";
  }
  return "";
}

} // namespace

int main(int argc, char **argv) {
  std::vector<std::string> entries;     // C1 flows[].entry
  std::vector<std::string> primitives;  // C1 masking.primitives[].function
  std::vector<char *> passthrough;
  passthrough.push_back(argv[0]);

  // SVF prints its statistics to stdout, which would corrupt the JSON report.
  // Off by default; `-stat=true` anywhere on the command line restores them.
  bool wantStats = false;
  for (int i = 1; i < argc; ++i)
    if (std::string(argv[i]).rfind("-stat", 0) == 0)
      wantStats = true;
  static char statOff[] = "-stat=false";
  if (!wantStats)
    passthrough.push_back(statOff);

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--entry" && i + 1 < argc)
      entries.push_back(argv[++i]);
    else if (a == "--primitive" && i + 1 < argc)
      primitives.push_back(argv[++i]);
    else
      passthrough.push_back(argv[i]);
  }

  int pc = static_cast<int>(passthrough.size());
  std::vector<std::string> moduleNameVec = OptionBase::parseOptions(
      pc, passthrough.data(), "irqrace toolchain probe",
      "[--entry NAME]... [--primitive NAME]... <input-bitcode...>");

  if (moduleNameVec.empty()) {
    std::cerr << "irqrace-probe: no input bitcode\n";
    return 2;
  }

  SVFModule *svfModule = LLVMModuleSet::buildSVFModule(moduleNameVec);
  SVFIRBuilder builder(svfModule);
  SVFIR *pag = builder.build();

  // May-alias, field-sensitive Andersen. MUST be may: a must-alias shortcut
  // here silently deletes candidates (Pipeline Design, stage 1.2).
  Andersen *ander = AndersenWaveDiff::createAndersenWaveDiff(pag);

  llvm::Module *M = LLVMModuleSet::getLLVMModuleSet()->getMainLLVMModule();

  // ---- globals -----------------------------------------------------------
  std::ostringstream globals;
  bool first = true;
  size_t nGlobals = 0;
  for (llvm::GlobalVariable &g : M->globals()) {
    if (g.getName().startswith("llvm."))
      continue;
    ++nGlobals;

    llvm::SmallVector<llvm::DIGlobalVariableExpression *, 2> dbg;
    g.getDebugInfo(dbg);
    std::string file, name = g.getName().str();
    unsigned line = 0;
    const llvm::DIType *dty = nullptr;
    if (!dbg.empty()) {
      if (const llvm::DIGlobalVariable *dv = dbg[0]->getVariable()) {
        file = dv->getFilename().str();
        line = dv->getLine();
        dty = dv->getType();
        if (!dv->getName().empty())
          name = dv->getName().str();
      }
    }

    long long nodeId = -1;
    const SVFValue *sv = LLVMModuleSet::getLLVMModuleSet()->getSVFValue(&g);
    if (sv && pag->hasValueNode(sv))
      nodeId = static_cast<long long>(pag->getValueNode(sv));

    globals << (first ? "\n    " : ",\n    ") << "{"
            << "\"name\": \"" << esc(name) << "\""
            << ", \"declared_type\": \"" << esc(typeName(dty)) << "\""
            << ", \"volatile\": " << (declaredVolatile(dty) ? "true" : "false")
            << ", \"has_debug_info\": " << (dbg.empty() ? "false" : "true")
            << ", \"decl\": {\"file\": \"" << esc(file) << "\", \"line\": " << line << "}"
            << ", \"constant\": " << (g.isConstant() ? "true" : "false")
            << ", \"internal_linkage\": "
            << (g.hasInternalLinkage() || g.hasPrivateLinkage() ? "true" : "false")
            << ", \"svf_node\": " << nodeId
            << "}";
    first = false;
  }

  // ---- functions ---------------------------------------------------------
  std::set<std::string> defined, declaredOnly, called;
  unsigned withDebugLoc = 0, totalInstr = 0, indirectCalls = 0, addressTaken = 0,
           callsThroughCast = 0;
  for (llvm::Function &f : *M) {
    if (f.isIntrinsic())
      continue;
    if (f.isDeclaration()) {
      declaredOnly.insert(f.getName().str());
      continue;
    }
    defined.insert(f.getName().str());
    for (llvm::inst_iterator I = llvm::inst_begin(f), E = llvm::inst_end(f); I != E; ++I) {
      // Only memory operations and calls have to map back to a source range --
      // they are what becomes an access or a call-path frame. At -O0 the entry
      // block's allocas legitimately carry no DebugLoc, so counting every
      // instruction would raise a false alarm on a correctly built module.
      bool mappable = llvm::isa<llvm::LoadInst>(&*I) ||
                      llvm::isa<llvm::StoreInst>(&*I) ||
                      llvm::isa<llvm::CallBase>(&*I);
      // At -O0 clang spills each parameter into an alloca in the entry block
      // and gives that store no DebugLoc. It is a prologue artefact, not an
      // access to anything the analysis reports, so counting it would raise a
      // false "rebuild with -g" alarm on a correctly built module.
      if (const auto *st = llvm::dyn_cast<llvm::StoreInst>(&*I))
        if (llvm::isa<llvm::Argument>(st->getValueOperand()) &&
            st->getParent() == &f.getEntryBlock())
          mappable = false;
      if (mappable) {
        ++totalInstr;
        if (I->getDebugLoc())
          ++withDebugLoc;
      }
      if (const auto *ci = llvm::dyn_cast<llvm::CallBase>(&*I)) {
        if (const llvm::Function *cf = ci->getCalledFunction()) {
          called.insert(cf->getName().str());
        } else if (!ci->isInlineAsm()) {
          // getCalledFunction() returns null for a call through a bitcast, and
          // a bitcast is what a K&R-style prototype produces: common.h declares
          // `void init();` -- unspecified arguments, type void(...) -- while
          // common.c defines `void init() {}` of type void(). After llvm-link
          // every such call site goes through a ConstantExpr bitcast.
          //
          // Those are still DIRECT calls. Counting them as indirect would mark
          // all 31 subjects as containing function-pointer dispatch and, worse,
          // would make a call-graph walk over-approximate every one of them to
          // "may call any address-taken function". Strip the casts first.
          const llvm::Value *callee = ci->getCalledOperand()->stripPointerCasts();
          if (const auto *cf = llvm::dyn_cast<llvm::Function>(callee)) {
            called.insert(cf->getName().str());
            ++callsThroughCast;
          } else {
            ++indirectCalls;
          }
        }
      }
    }
  }

  for (llvm::Function &f : *M)
    if (!f.isIntrinsic() && f.hasAddressTaken())
      ++addressTaken;

  auto strArray = [&](const std::set<std::string> &s) {
    std::ostringstream o;
    bool f1 = true;
    for (const auto &x : s) {
      o << (f1 ? "" : ", ") << "\"" << esc(x) << "\"";
      f1 = false;
    }
    return o.str();
  };

  // ---- C1 validation (R7): warn in both directions -----------------------
  std::ostringstream warnings;
  bool wfirst = true;
  auto warn = [&](const std::string &severity, const std::string &code,
                  const std::string &msg) {
    warnings << (wfirst ? "\n    " : ",\n    ") << "{\"severity\": \""
             << esc(severity) << "\", \"code\": \"" << esc(code)
             << "\", \"message\": \"" << esc(msg) << "\"}";
    wfirst = false;
  };
  for (const auto &e : entries)
    if (!defined.count(e))
      warn("error", "entry-point-missing",
           "configured entry point '" + e + "' has no body in the module; "
           "its accesses and every defect reachable from it are invisible");
  for (const auto &p : primitives) {
    if (!called.count(p))
      warn("info", "masking-primitive-never-called",
           "configured masking primitive '" + p + "' is never called; "
           "either the name is a typo or masking is done some other way");
    if (defined.count(p))
      warn("warn", "masking-primitive-has-body",
           "configured masking primitive '" + p + "' has a body in the module; "
           "the analysis models it and will not descend into it");
  }
  if (indirectCalls > 0)
    warn("warn", "indirect-calls-present",
         std::to_string(indirectCalls) + " indirect call site(s) and " +
             std::to_string(addressTaken) +
             " address-taken function(s). Reachability is only as good as the "
             "call graph: an unresolved target set must be read as 'may call "
             "every address-taken function with a matching signature', never as "
             "'calls nothing'");
  if (totalInstr > 0 && withDebugLoc < totalInstr)
    warn("warn", "debug-info-sparse",
         "only " + std::to_string(withDebugLoc * 100 / totalInstr) +
             "% of loads, stores and calls carry a DebugLoc; every candidate must map back "
             "to a source range, so rebuild with -g");

  // ---- report ------------------------------------------------------------
  std::cout << "{\n"
            << "  \"tool\": \"irqrace-probe\",\n"
            << "  \"svf\": \"2.7\",\n"
            << "  \"module\": \"" << esc(M->getName().str()) << "\",\n"
            << "  \"translation_units\": " << moduleNameVec.size() << ",\n"
            << "  \"functions_with_bodies\": " << defined.size() << ",\n"
            << "  \"functions_declared_only\": [" << strArray(declaredOnly) << "],\n"
            << "  \"mappable_instructions\": " << totalInstr << ",\n"
            << "  \"mappable_with_debug_loc\": " << withDebugLoc << ",\n"
            << "  \"indirect_call_sites\": " << indirectCalls << ",\n"
            << "  \"direct_calls_through_cast\": " << callsThroughCast << ",\n"
            << "  \"address_taken_functions\": " << addressTaken << ",\n"
            << "  \"globals_count\": " << nGlobals << ",\n"
            << "  \"pag_nodes\": " << pag->getTotalNodeNum() << ",\n"
            << "  \"globals\": [" << globals.str() << (nGlobals ? "\n  " : "") << "],\n"
            << "  \"warnings\": [" << warnings.str() << (wfirst ? "" : "\n  ") << "]\n"
            << "}\n";

  AndersenWaveDiff::releaseAndersenWaveDiff();
  SVFIR::releaseSVFIR();
  LLVMModuleSet::releaseLLVMModuleSet();
  return 0;
}
