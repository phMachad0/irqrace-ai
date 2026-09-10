---
type: project
tags: [wiki, project]
sources: ["[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[SDRacer (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-27
status: draft
---

# Pipeline Design — the techniques, and how they apply here

How each borrowed technique works and what it has to become in the tool described by
[[Thesis Goal]]. The literature-facing accounts live on the concept pages; this page is the
engineering reading. Study order and stack are in [[Reimplementation Assessment]].

The pipeline: **build to whole-program bitcode → shared front end → pair and triple candidates →
concurrency filter → Z3 feasibility → context capture → LLM triage → LLM repair → fix
validation.** Only the *filters* may discard
candidates, and only by proving impossibility ([[Soundness and False Negatives]]).

## Input scope and build requirements

**Multi-file and whole-repository input is a stated capability of this tool**, not a later
extension. The benchmarks will never exercise it — every subject in [[Racebench]] and the
[[Real-World Program Benchmark]] is a single extracted `main.c` of 157–1639 lines — but the
tier-3 subjects in [[Candidate Evaluation Subjects]] are real projects with several tasks and
several ISRs spread across many files, and the tool is meant to run on them.

Note the distinction, because the two are easy to confuse: **input scope** is whole-repository;
**evaluation scope** stays per-module, for ground-truth cost and comparability with the corpus.
Handing the analyzer a repository is a capability claim, exercised where no annotated ground
truth exists anyway.

### Two input modes

1. **Single translation unit** — the benchmark mode. Every comparable number comes from here.
2. **Linked whole-program bitcode** — many translation units combined into one LLVM `Module`.

### Get there by linking bitcode, not by concatenating source

The pre-step is `llvm-link`, applied to per-TU bitcode, and the practical routes are:

- `clang -g -emit-llvm -c` per translation unit, then `llvm-link *.bc -o whole.bc`;
- **`wllvm` / `gllvm`** — wrap the compiler, build the project by its own build system, then
  `extract-bc` yields the linked module. The right choice for anything with a non-trivial build;
- `clang -flto` with the LTO bitcode retained.

Merging at the **C source** level is the wrong level, for four reasons, the first of which is
disqualifying:

- **It destroys the source ranges.** This pipeline requires every candidate to map back to a
  source range (see *Context capture*). Concatenated source carries its own line numbering, so
  the originals survive only if correct `#line` directives are emitted everywhere. Bitcode
  linking preserves `DILocation` for free — after linking, every instruction still knows its
  original file and line.
- **`static` symbols collide.** Two files each declaring `static int count;` or
  `static void helper()` is legal and ubiquitous; concatenation will not compile. `llvm-link`
  renames internal-linkage symbols correctly.
- **Preprocessor state is per-translation-unit** — different `-D` flags, include order,
  conflicting macro definitions. Compiling each TU separately preserves it.
- **Only the build system knows what is actually compiled**, with which flags, for which target.
  Compiler interception captures that; a source merger would have to reimplement it.

Amalgamation works for projects that ship one deliberately. It does not generalize.

**Build flags.** `-g` is mandatory (debug metadata is what makes the source mapping possible).
`-O0` is the natural companion, but it marks functions `optnone`, which causes the pass manager
to skip them — a known trap when running analyses through `opt`. The usual workarounds are
`-O0 -Xclang -disable-O0-optnone` or building at `-O1 -g` and accepting some inlining. Verify
against SVF's own recommended flags before settling.

### The configuration file bounds the analysis, not the input

This is what makes whole-repository input tractable, and it is worth stating plainly:
**analysis cost is proportional to code reachable from the declared entry points, not to
repository size.** Stage 1 walks outward from the flows named in the configuration file; a
repository's code that no task and no ISR reaches contributes no accesses and no candidates. For
a driver inside a large tree, the transitive closure of its entry points is small.

The one component that does not automatically respect that boundary is the **points-to
analysis**, which SVF runs over the whole module. An optional refinement is to compute
reachability on a cheap, signature-based call graph first, extract that subset with
`llvm-extract`, and run SVF on the reduced module. The chicken-and-egg — indirect-call targets
need points-to, which is what is being pruned for — is handled by starting conservatively and
refining. Recorded as a design option, not a settled decision.

### Two policies that must be stated, because both are recall-critical

**Functions with no body in the module.** Library calls, vendor blobs, inline assembly. This is
[[LLift (paper)]]'s "inherent knowledge boundary", and it gets worse at repository scope. The
sound default is to assume such a function **may read and write any shared location reachable
from its arguments, and any global** — correct, and expensive in precision. The refinement is
the same closed-set argument that settled [[Specification Inference]]: hand-model the small,
recurring set (the `mem*`/`str*` family, kernel accessors), exactly as SVF already models
hundreds of common APIs. Which functions were modelled and which were assumed opaque belongs in
the assumption list, because it is part of the abstraction the soundness claim rests on.

**Indirect calls.** The recall-critical one at repository scale, and the one that most threatens
the claim that accesses in nested callees are found. Reachability from an entry point is only as
good as the call graph, and driver code dispatches through function-pointer `ops` structs
constantly. SVF resolves indirect calls through points-to, which is over-approximate in
principle — but an unresolved or empty target set must **never** be read as "calls nothing". The
rule: *an indirect call whose targets cannot be resolved is treated as potentially calling every
address-taken function with a matching signature.* Resolving to nothing silently deletes whole
subtrees of reachable accesses, and the loss is invisible in the output
([[Soundness and False Negatives]] §1).

### Scale

Candidates grow faster than linearly in reachable code: for one shared location with `m`
accesses in one flow and `n` in another, there are `m·n` pairs and on the order of `m²·n`
triples. The reachability bound above is the main mitigation; the [[Path Feasibility Analysis]]
stage is the other, and it is why that stage is mandatory rather than optional.

Precedent that this is achievable: UBITect analysed the **whole Linux kernel** and produced
~140,000 candidates from it ([[LLift (paper)]]). Neither that paper nor [[IntRace (paper)]]
describes its build mechanics, so the corpus offers no recipe — only an existence proof.

## Stage 1 — interleaving pattern matching on Clang/LLVM

[[IntRace (paper)]] §3.1 builds a CFG from the Clang AST plus an LLVM pass, runs
inter-procedural alias analysis into a shared-resource pool of globals and pointer-typed
parameters, then matches [[Access Interleaving Patterns]] while **deliberately ignoring guard
conditions and interrupt state** so that nothing is missed. That last decision is the whole
reason to start here: it is a recall-first design already.

Concretely, four sub-problems:

1. **Entry-point identification.** Every flow — the main task and each ISR — is a root of its
   own reachability analysis. In [[Racebench]] these are named by convention (`*_main`,
   `*_isr_N`). In real firmware they are found through `request_irq`-style registration,
   interrupt vector tables of function pointers, or compiler attributes. **This is a
   first-class soundness assumption**: a handler whose registration is not recognized
   contributes no accesses and its defects become invisible.
2. **Shared-location identification.** LLVM `GlobalVariable`s, plus everything a flow can
   reach through pointers. Take the may-points-to set of each `LoadInst`/`StoreInst` pointer
   operand; a location is shared if two different flows' points-to sets intersect. Must be
   **may**-alias — a must-alias shortcut here silently deletes candidates.
3. **Access enumeration per flow.** Walk functions reachable from each entry point, collect
   loads and stores to shared locations, and record for each: flow, `R`/`W`, the enclosing
   function, the call path from the entry point, the `DILocation` source range, and whether
   the access sits inside a loop (see loop handling below). This record is not a by-product —
   it is the raw material for the context capture the LLM stage consumes.
4. **Candidate derivation.** Pairs and triples are derived separately from the same access
   set, per [[Pair-Triple Unification]]. Do not derive triples by joining confirmed pairs.

Expect roughly **208 candidates per real program** at this point — IntRace's measured figure,
and the budget to plan the rest of the pipeline against.

## Stage 2 — potential concurrency relationship analysis

IntRace's cheap filter, which removes **54.2%** of stage-1 candidates for a fraction of the
runtime. Each flow becomes a block `(T, I, S, p)` — name, interrupt status, timing, priority —
and pairs whose blocks provably cannot overlap are discarded. Three components matter here,
and one of them does not:

**Priority.** A flow can only be preempted by a strictly higher-priority flow. The convention
is now settled from the benchmark's own README rather than from the papers' prose: **larger
number = higher priority** ([[Contradictions]] #3). Getting this backwards drops exactly the
real preemptions and reports exactly the impossible ones.

**Masking.** A dataflow analysis over `disable_isr(n)` / `enable_isr(n)` and their real-world
equivalents, computing at each program point the set of interrupts that are disabled. The
soundness direction is the part that is easy to get wrong: an interrupt may be treated as
**masked at a point only if it is masked on every path reaching that point**. Anything less —
"masked on some path" — turns into a dropped real defect. Unrecognized register writes must
count as *not* masking. `disable_isr(-1)` masks everything; nesting means an ISR can re-enable
a lower-priority interrupt inside itself, as `svp_simple_003_001_isr_1` does with
`enable_isr(2)`, so this is a flow-sensitive, inter-procedural analysis and not a syntactic
scan ([[Interrupt Masking and Synchronization]]).

**Nesting.** An ISR is itself preemptible by higher-priority ISRs. IntRace handles this by an
inside-out sequential conversion; [[NIChecker (paper)]]'s *invocation conditions* are the
cleaner formalization and are worth borrowing even without its sequentialization
([[Interrupt Nesting]]).

**Timing — skip it.** IntRace's `S` component encodes periodicity. [[Racebench]]'s README
states explicitly that the suite assumes no periodicity: an interrupt may fire at any enabled
point, any number of times, at unspecified moments. Assuming a timing model the subject does
not guarantee is an unsound filter, so leave `S` unconstrained unless a subject genuinely
documents its timing.

**The interval/instant split.** For pair candidates the query is "can `B` run at the instant of
`A`?" For triple candidates it is "can `B` run anywhere in `[A₁, A₂]`?" Run both; do not
answer one and infer the other ([[Pair-Triple Unification]]).

## Loop handling — and why [[Loop Abstraction]] is mostly not your problem

[[Loop Abstraction]] solves a *bounded model checking* problem: [[Racebench]] has cases whose
defect only appears after **10,000** unwindings, so NIChecker over-approximates loops before
unwinding to bring deep bugs within a small bound, and [[CPA4AV]] fails on exactly those cases
without it. A purely static pattern matcher never unwinds, so it never has that problem —
which is one more argument for the static front end.

What a static detector *does* need from loops is subtler and cheaper: **a single syntactic
access inside a loop is many dynamic accesses**, so one statement can form a triple with
itself. The benchmark confirms this directly — `svp_simple_029_001` annotates a bug point as
`<R,#80>, <W,#83>, <R,#80>`, the *same source line* as both `A₁` and `A₂`. `svp_simple_003_001`
does it across two separate loops, each guarded by `if (i == TRIGGER)`, which is also why that
case needs a huge unwind bound in a BMC tool and none at all in a static one.

So the requirement is: mark each access with its enclosing loop nest, and when forming triples
allow `A₁` and `A₂` to be the same instruction provided it lies in a loop that can iterate more
than once. Missing this loses a substantial share of the ground truth — 25 of the 48 annotated
bug points are `(R,W,R)`, and repeated-read shapes are common among them.

Loop abstraction returns only if [[CBMC]] is used downstream for fix validation, where the
unwind bound is back in play.

## Z3 and path feasibility — the only component allowed to discard

[[Path Feasibility Analysis]] is IntRace's stage 3: build a symbolic summary of the ISR,
splice the high-priority block into the low-priority block at the preemption point, conjoin
the path constraints from flow entry to `A₁`, through `B`, and on to `A₂`, and ask Z3 for
satisfiability. `UNSAT` means the interleaving cannot occur and the candidate is a proven
false positive. It costs **69.7% of IntRace's runtime** and eliminates **86.2%** of what
reaches it.

The design rule that follows is the most important one in this pipeline:

> **A solver may drop a candidate. The LLM may not.**

That rule is now backed by measurement rather than principle: triage stages built as classifiers
that discard lose 6 to 25 points of recall, while a conservative decision policy at the same
integration point reached recall 1.00 ([[LLM Triage]]). The stage itself is designed in
[[LLM Stage Design]].

An `UNSAT` result is a proof of impossibility, which is what
[[Soundness and False Negatives]] requires of a filter. An LLM's judgement is not a proof, so
the LLM stage **ranks and explains** — it may sort candidates into "almost certainly real",
"probably benign", "probably infeasible" — but every candidate stays in the report. Collapsing
those two roles is how a recall-first tool quietly becomes a precision-first one.

**The Z3 stage is fixed in the pipeline, ahead of the LLM.** It is not an alternative to triage
and not an ablation option. Three reasons compound: it is the only sound filter, so removing it
leaves nothing that may legitimately discard; it eliminates **86.2%** of what reaches it, taking
a program's ~95 post-stage-2 candidates down to roughly 13 and the triage bill from about $90
to about $6; and it mirrors [[LLift (paper)]]'s architecture exactly, where symbolic execution
runs first and the LLM receives only the cases it could not decide. LLift is what happens at the
solver's limit, not a substitute for it.

Two engineering consequences. The solver's verdict — `UNSAT`, `SAT`, or **inconclusive**
(timeout, unsupported construct) — belongs in the context record, because "the solver could not
settle this, here is how far it got" is precisely the handover the LLM stage exploits. And
inconclusive must never be collapsed into either decided outcome: `UNSAT` discards, `SAT` and
inconclusive both continue to triage ([[LLM Stage Design]]).

## Context capture

The context record is specified in [[LLM Stage Design]]. Two decisions belong here because they
constrain the static side:

**Every candidate must map back to a source range.** Compile with `-g -O0` and keep `DILocation`
metadata, so that IR-level analysis results can always be expressed as C. This is a hard
requirement from day one, not a later feature.

**Context is retrieved on demand, not precomputed.** The record carries the cheap always-useful
layers — accesses, flows, call paths, masking state, enclosing function bodies — and the model
requests anything further through progressive prompting ([[Prompt Architecture]]). Precomputed
**slicing is not in the design**; [[Program Slicing]] records why and keeps it as a documented
alternative. `dg` remains a justified dependency for its **dependence graph**, which the
concurrency analysis and the harmfulness criterion both need — the slicer specifically is what
is unused.

## Fix validation — CBMC, or the tool's own static analysis?

Both, in that order, because they fail in opposite directions.

**The tool's own analysis is a sound but incomplete validator.** This follows directly from
the drop rule: if a filter discards candidates only when it *proves* impossibility, then a
candidate disappearing after a fix is a proof — under the stated abstraction — that the defect
is gone. That is a real certificate, and it is cheap. Two caveats. First, if the candidate
*persists*, the result is inconclusive rather than negative: an over-approximate analysis may
keep reporting a repaired defect purely from imprecision, so "still flagged" must never be
read as "fix failed". Second, and more valuable than either outcome, re-running the whole
analysis is the only step that catches **regressions** — a fix that closes one violation while
opening another elsewhere, which is exactly what happens when a critical section is extended
across unrelated accesses. [[CBMC]] asked about one assertion will never tell you that.

**CBMC resolves the inconclusive cases.** Encode the specific violation as an assertion in the
repaired program and ask whether it is still reachable. The bounded guarantee that makes BMC
unsuitable as the *detector* ([[Reimplementation Assessment]]) is well matched here: the
question is small, targeted, and about one already-witnessed defect rather than about the
whole program. Loop abstraction becomes relevant again at this point.

There is now a shortcut worth taking: **[[BMC4AV (tool)]]'s binary is in the local artifact**
and is fully automatic, taking only a source file and an entry function. For atomicity
violations it can serve directly as the third-party validator, which is stronger evidence than
self-validation by the same analysis that found the defect. Its limitation is that it does not
consider `(R,W,W)`, so violations of that shape — 10 of the 48 annotated bug points — need
CBMC with a hand-written assertion instead.

**Then check the fix did no harm.** [[SDRacer (paper)]] measured repair overhead and found
9 of 11 subjects under 0.09 while two degraded markedly, because disabling interrupts changed
the main task's control flow. Any applied fix needs that check; for interrupt code, an
extended critical section is a latency change, and latency is a correctness property.

**Recommended loop**: re-run own analysis (certificate + regression check) → if inconclusive,
CBMC or `bmc4av` on the sliced program → overhead and control-flow check → report.

Related: [[Pair-Triple Unification]], [[Program Slicing]], [[Soundness and False Negatives]].
