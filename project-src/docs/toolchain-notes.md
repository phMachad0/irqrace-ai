# Toolchain notes

Decisions and traps from getting the W1 toolchain up. Kept because each one cost
time and none of it is in the papers.

## SVF against the system LLVM, not SVF's own

SVF's `setup.sh` downloads a prebuilt LLVM (several gigabytes unpacked). The
development machine has under 4 GB free, so `scripts/setup-svf.sh` builds SVF
against the distribution's `llvm-14-dev` instead. Cost: **64 MB and about ten
minutes on four cores.**

Version pairing matters. **SVF 2.7 is the release that targets LLVM 14.0.0** —
its `setup.sh` names `llvm-14.0.0.obj`. SVF 2.6 targets LLVM 13 and SVF 3.x
requires LLVM 16, which would reintroduce the download. Using the same LLVM to
compile subjects and to analyse them also keeps the bitcode version and the
analysis in step.

Two build details:

- **Use `g++-11`, not `clang-14`.** clang-14 here defaults to the GCC 12
  installation, which ships no `libstdc++.so`, and the CMake compiler check fails
  with `cannot find -lstdc++`. SVF 2.7 also builds with `-Werror`, so
  `-DCMAKE_CXX_FLAGS=-Wno-error` is needed under GCC.
- **Anything linking SVF must be built `-fno-rtti -fno-exceptions`**, because SVF
  is, to match LLVM.

## `-g` and the `optnone` trap

`-g` is mandatory: `DILocation` is what lets an IR result be expressed as C, and
"every candidate maps back to a source range" is a hard requirement from day one.
`-O0` alone marks every function `optnone` and the pass manager skips them, so
the flags are `-g -O0 -Xclang -disable-O0-optnone` ([[Pipeline Design]]).

Measured on all 31 subjects: **every load, store and call carries a `DebugLoc`.**
Two things had to be excluded from that count before it was true, and neither is
a defect:

- the **parameter-spill stores** clang emits in a function's entry block at `-O0`
  (`store i32 %0, i32* %2`) carry no `DebugLoc`;
- `volatile` on an array is recorded on the *element* type in debug info, not on
  the array, so `declaredVolatile` has to walk into `DW_TAG_array_type`.
  Racebench's shared state is mostly arrays, so missing this reported all of them
  as non-volatile.

## `getCalledFunction()` returns null for direct calls

The one that cost the most. `common.h` declares its helpers K&R-style:

```c
void idlerun();
void init();
extern int rand();
```

An empty parameter list in C means *unspecified arguments*, so those declarations
have LLVM type `void (...)` while the definitions in `common.c` have type
`void ()`. After `llvm-link` every call site goes through a `ConstantExpr`
bitcast, and `CallBase::getCalledFunction()` — which is a plain
`dyn_cast<Function>` of the callee operand, with no cast stripping — returns
null.

Read naively, that makes **every one of the 31 subjects look like it contains
indirect calls.** For a sound analyzer that is not merely cosmetic: the rule for
an unresolved indirect call is to assume it may reach *every address-taken
function with a matching signature* ([[Pipeline Design]], *Indirect calls*), so
the mistake would over-approximate all 31 call graphs and inflate every candidate
set, for nothing.

The fix is `ci->getCalledOperand()->stripPointerCasts()`. With it,
**exactly one of the 31 simple cases uses genuine function-pointer dispatch**:
`svp_simple_029_001`, which assigns three function pointers in an init routine
and calls them from both the task and an ISR. That case is the only one that can
exercise stage 1's indirect-call handling, and `irqrace-probe` now reports
`indirect_call_sites` and `direct_calls_through_cast` separately so the
distinction stays visible.
