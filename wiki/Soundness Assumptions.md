---
type: project
tags: [wiki, project, soundness]
sources: ["[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[SDRacer (paper)]]", "[[BMC4AV (paper)]]", "[[LLift (paper)]]"]
updated: 2026-10-22
status: draft
---

# Soundness Assumptions

**The list [[Thesis Goal]]'s central claim is relative to.** Unconditional
zero-false-negatives is not attainable for C with pointers, function-pointer
vector tables and hardware-dependent control flow. What is attainable, and
defensible, is *soundness relative to an explicitly stated abstraction*
([[Soundness and False Negatives]]). This page is that statement.

Written 2026-09-10 as the [[Roadmap]] W2 deliverable. It is a `type: project`
page: the assumptions are the human's stated design decisions, not findings, and
claims *about the literature* still cite. Every entry gives the assumption, why
it is the recall-safe reading, **what would have to be true for it to hide a
defect**, and where it is implemented — so that each one is checkable rather than
merely asserted.

> [!warning] How to read the third column
> "How it can hide a defect" is not a disclaimer. It is the list a reader should
> attack, and the list that says what to do next if a false negative ever turns
> up. An assumption with an empty failure mode has not been thought about
> carefully enough.

## A. Input and build

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| A1 | The analysis sees **whole-program bitcode**: every translation unit that contributes to the subject is compiled and linked with `llvm-link`. | A file excluded from the build contributes no accesses. On a real project this is a build-system question, not an analysis one, and it fails silently. | `build.py`; manifest records `translation_units` |
| A2 | Every access maps back to a source range, because the build carries `-g` and keeps `DILocation`. | An access with no `DebugLoc` cannot enter a context record. Where one is genuinely absent the enclosing function's line is used and the record is marked `overapproximated` — **the candidate is never dropped**, because an imprecise location is recoverable by a reader and a missing candidate is not. | `build.py` refuses to build without `-g`; `irqrace-stage1` warns `source-range-recovered` |
| A2b | **Prologue argument spills are not accesses.** At `-O0` clang stores each parameter into an alloca in the entry block, with no `DebugLoc`. | Those stores have no source-level existence, and the alloca they write is the parameter's own slot — any real sharing of that value appears at the loads and stores that follow. Skipping them is what keeps A2 honest rather than papered over. | `irqrace-stage1.cpp` |
| A3 | `-O0 -Xclang -disable-O0-optnone` preserves the program's access structure. Optimisation is not applied, so no access is folded away. | Building at `-O1` or above would let the optimiser delete or merge accesses that a real target would perform. Not currently supported. | C1 `subject.build.flags` |
| A4 | **Accesses are loads and stores.** Stage 1 enumerates `LoadInst` and `StoreInst` only; memory intrinsics (`llvm.memcpy`, `llvm.memset`, `llvm.memmove`) are not enumerated as accesses. | *An honest gap, found while writing stage 3* — which does model them, as havoc of their destination. A `memset` of a shared buffer in an ISR is an access stage 1 never reports, so no candidate is formed from it. No Racebench simple case calls one; real firmware does. To close before the real-world suite. | `irqrace-stage1.cpp` |

## B. Entry points and the call graph

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| B1 | **The configuration file names every flow.** Each task and each ISR listed in C1 `flows` is a root of reachability; nothing else is. | *The single largest recall risk in the design.* A handler not listed contributes no accesses and every defect reachable only from it disappears with no error. Mitigated by `irqrace-probe`'s R7 check, which warns when a configured entry has no body — but it cannot warn about a handler nobody configured. | C1 `flows`; probe warning `entry-point-missing` |
| B2 | An **indirect call whose targets cannot be resolved may call every address-taken function with a matching signature.** An empty points-to set is never read as "calls nothing". | If SVF returns an empty target set and it is trusted, whole subtrees of reachable accesses vanish invisibly ([[Soundness and False Negatives]] §1). Still to be verified against SVF's actual behaviour — an open item. | C1 `analysis.indirect_calls`; probe reports `indirect_call_sites` |
| B3 | A call through a **bitcast is a direct call**, resolved by stripping pointer casts. | Not a recall risk but a precision one, and a large one: `common.h` declares `init`, `idlerun` and `rand` K&R-style, so without cast-stripping all 31 subjects look like they dispatch through function pointers and all 31 call graphs get over-approximated. Measured: exactly **one** case, `svp_simple_029_001`, uses genuine function-pointer dispatch. | `irqrace-probe`; `project-src/docs/toolchain-notes.md` |
| B4 | Reachability is **transitive and inter-procedural** from each entry point; accesses in nested callees are found. | A missed call edge is a missed subtree. Depends entirely on B2. | stage 1 (not yet built) |

## C. Memory model

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| C1 | Shared locations are identified by **may-alias**, never must-alias. Two flows share a location when their points-to sets intersect. | A must-alias shortcut silently deletes candidates ([[Pipeline Design]], stage 1.2). Pinned by the C1 schema, which admits only `may`. | C1 `analysis.alias` |
| C1b | Points-to results are normalised to the **base object**: `a[i]` and `a[TRIGGER]` are one location. | Field sensitivity would separate them, and separating them is the unsound direction — two accesses that *may* be to the same element must stay comparable. Proving they are not is stage 3's job, which can. The cost is precision: `svp_simple_001_001`'s second planted trap survives stage 1 for exactly this reason, correctly. | `irqrace-stage1.cpp`, `objectsTouched` |
| C2 | **SVF's field-sensitive Andersen analysis is itself sound** over the module it is given. | Inherited, not proven here. This project does not re-verify SVF; if SVF's points-to set is incomplete, so is everything downstream. Worth stating plainly rather than assuming away. | SVF 2.7 |
| C2b | **A location is shared when two or more flows reach it — not when it is a global.** Stack objects are in scope; objects only one flow touches are dropped, since no candidate of either class can be formed from them. | Restricting stage 1 to module-level globals loses `svp_simple_009_001`'s annotated bug point, which shares a **stack** variable between task and ISR by storing its address into two global pointers. It was lost silently until the recall gate caught it. | `irqrace-stage1.cpp`; test `test_a_stack_object_shared_through_a_global_pointer_is_found` |
| C3 | Aliased names denote the same location: the ground truth's `*p`, `*ptr_var`, `global_array[1]` resolve to the underlying object. | If alias resolution fails, 12 annotated bug points and traps become unmatchable and recall is understated — a *reporting* failure rather than a detection one, but it looks identical in a table. | `evaluation.py`, `normalise_variable` |

## D. External functions

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| D1 | A function with **no body in the module may read and write any global**, and anything reachable from its arguments. | The sound default, and ruinous for precision. This is [[LLift (paper)]]'s "inherent knowledge boundary". | C1 `externals.default` |
| D2 | Hand-modelled externals are correctly modelled. On Racebench: `idlerun` and `init` touch no shared state, `rand` touches none. | A wrong model is a deliberate blind spot. The modelled set must stay small and be listed in full — which is why it lives in the configuration file and the manifest rather than in code. | C1 `externals.models` |
| D3 | `disable_isr` and `enable_isr` have no bodies and are modelled as masking primitives rather than descended into. | Verified: on all 31 subjects both appear in `functions_declared_only`. | probe warning `masking-primitive-has-body` |

## E. Interrupt semantics

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| E1 | **Larger priority number = higher priority.** | Inverting it drops exactly the real preemptions and reports exactly the impossible ones. Settled from the Racebench and NIChecker READMEs against the papers' prose ([[Contradictions]] #3). | `config.can_preempt`, with a test pinning it |
| E2 | **Equal-priority flows may preempt each other** (default). | The recall-safe reading. `svp_real_002` has two ISRs sharing priority 1 and no formal model in the corpus covers the case ([[Asymmetric Preemption]]). Setting this false is an unsound filter unless the platform guarantees otherwise. | C1 `semantics.equal_priority_preemption` |
| E3 | An ISR **does not preempt itself** (default). | The one assumption on this page that is *not* recall-safe, and it is a deliberate, recorded choice. Racebench's README says an interrupt may fire an unspecified number of times, so re-entrancy is not excluded by the subject; [[SDRacer (tool)]] excludes it and [[NIChecker (tool)]] bounds ISR executions, so the corpus does not agree either. Enabling it multiplies candidates. **Flagged for revisit before any recall claim is final.** *W5 (2026-10-22):* the README's own wording bears on it — an interrupt may preempt "the main program or **lower-level** interrupts" (打断主程序或者低级中断), which excludes same-level preemption, so for Racebench the default reads the subject rather than departing from it. Not yet confirmed as a decision; it does not carry over to other suites. | C1 `semantics.isr_reentrant` |
| E4 | Interrupt **arrival is unbounded**: an ISR may fire at any enabled point, any number of times, at unspecified moments. No periodicity is assumed. | Assuming a timing model the subject does not guarantee is an unsound filter, so IntRace's `S` component is left unconstrained ([[Pipeline Design]], stage 2). | C1 `semantics.isr_arrival`, `timing_model` |
| E5 | **Nesting is permitted**: an ISR is preemptible by a strictly higher-priority ISR. | Disabling it would drop every nested-preemption defect ([[Interrupt Nesting]]). | C1 `semantics.nesting` |

## F. Masking

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| F1 | An interrupt is **masked at a point only if it is masked on every path** reaching that point. "Masked on some path" is never enough. | The direction that is easy to get backwards, and getting it backwards drops real defects. Encoded structurally: the contract has no boolean `is_masked`, only the three-valued `{disabled, enabled, unknown}`. | C2 `MaskingState` |
| F2 | An interrupt is masked **throughout `[A₁, A₂]`** only if it is masked at every point of every path *and* **no flow that may execute within the interval re-enables it**. | The second clause is not optional. `svp_simple_001_001` masks irq 2 across its bug point's whole interval in `main`, yet the bug point is real because `isr_1` preempts the interval and calls `enable_isr(2)`. Computing this from the local CFG alone drops an annotated bug point on case 1 of 31. | C2 `IntervalMaskingState.reenabled_within_interval_by`; `project-src/docs/masking-semantics.md` |
| F3 | Unrecognised writes to hardware registers **do not mask**. Anything not proven disabled is `unknown`, and consumers must treat `unknown` as enabled. | Treating an unmodelled register write as masking is how a real defect becomes invisible. This is [[IntRace (tool)]]'s first acknowledged false-positive cause, run in the safe direction. | C1 `masking.primitives[].non_constant_arg` |
| F4 | `disable_isr(-1)` masks exactly the interrupts named in the configuration file. | Circular with B1 and honestly so: if a handler is missing from `flows` it is missing from the "all interrupts" set too. The two losses are the same loss. | `config.all_irqs` |
| F5 | Masking state at flow entry is `all-enabled` on Racebench, because `init()` calls `enable_isr(-1)`. | On an unfamiliar platform the safe default is `unknown`, not `all-enabled`. | C1 `masking.initial_state` |
| F6 | An external with no body that is not a masking primitive **may unmask any interrupt**, unless it is listed in C1 `externals.models` — a modelled external leaves the mask alone. Inline assembly and an indirect call with no resolved target may unmask anything. Functions *with* bodies are descended into for masking even when stage 1 treats them as transparent for accesses. | A vendor HAL call that executes `cpsie i` would otherwise be read as a no-op inside a critical section. The models list is therefore a masking claim as well as a memory claim; on Racebench it covers `idlerun`, `init` and `rand`. `init` is descended into regardless, and its `enable_isr(-1)` is what the analysis sees. | `masking.py`, `MaskAnalysis._call` |
| F7 | Mask changes an ISR makes **may or may not persist** after it returns — platform-dependent — so the analysis takes the union: an ISR's enables may break a proof in the flow it preempted, its disables never help one. | Assuming hardware restores the mask on return would hide every defect enabled by an ISR that unmasks and returns — exactly `svp_simple_001_001`'s bug point. Assuming disables persist would invent protection. | `masking.py`, `MaskAnalysis._close` |
| F8 | An ISR **starts in the union of the states at every point where it may fire**, in every flow — including points before the main task's first masking call, and points after an earlier activation of itself left the mask changed. | Taking "the state where the author expected it to fire" is the unsound shortcut. It is what made `svp_simple_001_001`'s first trap look provably infeasible in W1: `isr_1` may fire before main's `disable_isr(2)`, or a second time after its own `enable_isr(2)`, and either way starts with irq 2 unmasked (`project-src/docs/masking-semantics.md`, "Correction"). | `masking.py`, `MaskAnalysis._entries` |
| F9 | Masking is computed **with function summaries relative to the entry state**: a callee's effect is applied at each call site to that site's own state; the states *inside* a callee are the union over its call sites in the flow. A nested activation of an ISR is judged from the state at the point it fired, not from its global entry. | Context-insensitivity can only add values, so it is sound; the cost is precision for accesses inside helpers called under different masks. Judging nested activations by the global entry is also sound, and kept three masking-protected traps (`svp_simple_027/028/030`, `isr_3`) until W5 replaced it with the firing state. | `masking.py`; `stage2.py`, `Concurrency.inside` |

## G. Loops

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| G1 | A loop **may iterate more than once** unless the trip count is provably ≤ 1. | The sound default. | C2 `LoopContext.may_iterate_more_than_once` |
| G2 | A single syntactic access inside such a loop is **many dynamic accesses**, so one statement may serve as both `A₁` and `A₂`. | Forbidding it loses a substantial share of the ground truth. Measured: **7 of the 86 annotated triples** name the same line for `A₁` and `A₂` — 3 bug points and 4 traps. | C1 `analysis.allow_same_statement_a1_a2` |
| G2b | A function that **may run more than once within a flow** turns one instruction in it into many dynamic accesses, so that instruction may serve as both `A₁` and `A₂`. A function counts as multiply-invoked when the flow reaches two or more of its call sites, or one call site inside a loop. | The same argument as G2, reached through repeated calls rather than a back edge, and intra-procedural CFG reachability alone misses it entirely. `svp_simple_029_001` calls `GetTmData` twice in a row, so its single `return tm_blocks[tm_name];` is two accesses and the suite annotates exactly that triple. *W5:* counting call sites over-approximates — two call sites in the arms of one `if/else` are not a repetition — and stage 2 refines it on the flow's supergraph (`no-path`, H1d): `svp_simple_029_001`'s `isr_1` reaches `SetTmData` from both arms and cannot run line 83 twice in one activation. | `irqrace-stage1.cpp`, `multiInvocation`; `stage2.py`, `FlowGraph` |
| G2c | The **entry function of a flow is excluded** from G2b: an ISR firing twice is not treated as supplying `A₁` and `A₂` across two separate invocations. | Deliberately conservative in the *precision* direction and therefore a potential recall gap, shared with E3. Whether an interval may span two activations of the same flow is a question about the arrival model, not about the call graph, and deciding it inside the reachability code would decide it by accident. **Revisit with E3.** | `irqrace-stage1.cpp`, `multiInvocation` |
| G3 | No unwinding is performed; the front end is a pattern matcher. | Sidesteps the bound problem entirely, which is the main argument for a static front end over BMC. [[Loop Abstraction]] returns only for [[CBMC]]-based fix validation. | stage 1 |

## H. What the pipeline may discard

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| H1 | **Only a proof discards.** Stage 2 drops a candidate only when the flows provably cannot overlap; stage 3 drops only on `UNSAT`. | The rule the whole design rests on. Enforced mechanically: `irqrace runstore check` fails a run in which any candidate lacks both a context record and an `unsat` verdict, and — since W5 — one in which a stage-1 candidate is missing from stage 2 without a line in `stage2/dropped.jsonl`. | `runstore.check`, C3 rule 6 |
| H1b | Triple candidates are restricted to the **four unserializable interleavings** — `(R,W,R)`, `(R,W,W)`, `(W,W,R)`, `(W,R,W)`. The other four — `(R,R,*)`, `(W,R,R)`, `(W,W,W)` — are serializable and are not atomicity violations. | This is a genuine **filter** applied at generation time, and the only one outside stage 3, so it is stated rather than applied quietly. It is sound with respect to the standard definition of an atomicity violation, and all 48 annotated bug points fall inside the set. Two planted traps do not — `svp_simple_002_001` trap 3 and `svp_simple_017_001` trap 1 are both `(W,W,W)` once corrected — and stage 1 correctly declines to report them. If the definition is ever widened, this is the line to change. | `stage1.py`, `UNSERIALIZABLE` |
| H1c | A triple is **not generated** when the CFG proves `A₁` cannot precede `A₂`. | Generation, not filtering: there is no candidate to discard. `svp_simple_015_001`'s planted trap names the two arms of `p == 1 ? v : v` as `A₁` and `A₂`; they are mutually exclusive, so no execution performs both, and the CFG establishes it structurally without appealing to any guard condition. | `irqrace-stage1.cpp`, `FunctionCFG::mayPrecede` |
| H1d | **Stage 2 drops a candidate only when the interleaving is impossible under the priority and masking model.** A pair goes when neither flow may run while the other is at its access; a triple when B's flow may run at no point of any path from `A₁` to `A₂` — callees included, directly or nested, after every mask change a flow able to run there could make; or when the flow's supergraph has no path from `A₁` to `A₂` at all. Every drop writes its reason, its argument and the identifiers of the assumptions it relies on to `stage2/dropped.jsonl`. | Every drop inherits every assumption it names; that is the point of naming them. A wrong `relies_on` list is a documentation bug, a wrong drop is a recall bug — the recall gate is checked after stage 2 for this reason, and passes 48/48. | `stage2.py`; C3 `c3-drop-record.schema.json` |
| H2 | **`inconclusive` is not a decision.** A solver timeout or unsupported construct keeps the candidate and passes it on. | Collapsing `inconclusive` into `unsat` would be a silent recall loss; into `sat`, a lost signal for the LLM. The C2 schema gives the verdict four values and requires a reason for the third. | C2 `SolverResult` |
| H3 | **The LLM never discards.** Triage ranks, explains and buckets; the report retains everything. | Measured elsewhere: classify-and-discard designs lose 6 to 25 points of recall, while a conservative policy at the same integration point reached recall 1.00 ([[LLM Triage]]). | [[LLM Stage Design]] |

## I. Evaluation

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| I1 | The ground truth is **48 bug points and 38 traps**, counted per triple instance. | Certified by hand on five adversarial cases. A strict parser reads 28 and raises no error. | `groundtruth.py`; `docs/groundtruth-handcount.md` |
| I2 | Twelve annotations are **corrected before matching**, per a curated errata. | Matching the shipped text scores 0 on `svp_simple_019_001`'s bug point, whose ISR write is annotated six lines above where it is. Every correction carries its evidence, and no correction changes a count. | `bench/racebench-errata.yaml` |
| I3 | `svp_simple_019_001`'s bug/trap **labels** are as shipped. | The weakest entry on this page. Its annotations predate an edit that inserted `enable_isr(1)` into two guarded blocks — a semantically significant change — so the labels may be as stale as the line numbers. Not corrected, because correcting a label is re-deciding the ground truth rather than reading it. Open. | [[Open Questions]] |
| I4 | `svp_simple_001_001`'s first trap, `<W#43><R#63><W#44>`, is **labelled as shipped** — a false positive — although under the suite's own arrival model it is reachable (F8). | Not a recall risk: the analysis keeps it, so the disagreement costs trap rejection, not recall. It means the trap-rejection ceiling for a sound tool on this suite is below 38. Recorded, not corrected, for the same reason as I3. | [[Contradictions]] #7 |

## J. Path feasibility (stage 3)

Added 2026-10-22 (W6–W7). The solver's verdict is the only one that may discard a candidate,
so the encoding must over-approximate **every** execution: every entry here is a place where
it does so, and the one place it relies on the program being well defined.

| # | Assumption | How it can hide a defect | Where |
| --- | --- | --- | --- |
| J1 | **Memory is one byte array per SVF object**, and a pointer is *(object, offset)*. A load or store through a pointer is a case split over its may-points-to set; an unresolved pointer reads a fresh value, and storing through one havocs all of memory. | Inherits C2: a points-to set SVF left incomplete is a store the encoding never makes, and a value it never changes. | `irqrace-stage3.cpp`, `load`, `store` |
| J2 | **A loop is one pass**, with everything it may write — its callees included — havocked at the header. Back edges are cut while looking for A1 or B, and crossed **at most once per phase** between A1 and A2. | Havoc over-approximates any number of iterations. Crossing once in total instead of once per phase refutes a real violation whose preemption and A2 lie in two later iterations; pinned by `test_the_back_edge_is_crossed_once_per_phase`. Irreducible control flow is `inconclusive`. | `Executor::go` |
| J3 | **Interference is havoc**: at every instruction boundary where stage 2 says a flow may run, everything that flow may write is havocked before its next use. Masking enters stage 3 only through those run sets, so J3 inherits F1–F9. | A write set that misses something is a value the encoding wrongly keeps. A **volatile load is not a write** — LLVM's `mayWriteToMemory()` says it is, and reading it that way made every Racebench ISR "write everything" until fixed; pinned by `test_a_volatile_read_is_not_a_write`. | `Executor::interfere`, `Facts::instWrites` |
| J4 | **The preempting flow runs from its entry, on the memory at the preemption point**, until B; what it does after B is not modelled, and everything the run set may write is havocked when the preempted flow resumes. | Dropping the rest of B's flow only removes constraints. A preemption point immediately before A2 must leave A2 selectable — the bug `test_a_preemption_just_before_a2_does_not_hide_a2` pins. | `Executor::splice` |
| J5 | **An ISR's view of memory on entry is unconstrained**; the main task starts from the global initializers, with interference applied from its first instruction. | Starting an ISR from initializers would be wrong in the unsound direction: it may fire anywhere. Startup code that writes globals before `main` is assumed to be the initializers. | `Executor::explore` |
| J6 | **The program has no undefined behaviour the analysis must follow.** A dereference of a pointer holding none of its points-to targets — null included — touches no object; a call through such a pointer does not happen; accesses stay inside their object; integer arithmetic wraps. | *The recall-relevant one.* A program with UB may do anything, and the encoding does not. Two audited Racebench UNSATs rest on it: `svp_simple_029_001`'s pair (45, 83), where `ptr_SetTmData` is still NULL, and `svp_simple_009_001`'s pair (26, 44), where `p` is. | `irqrace-stage3.cpp` |
| J7 | **A triple is a conflict on one memory cell**: the byte ranges of A1, B and A2 must pairwise overlap. | This is C1b's normalisation made precise — what stage 1 could not separate, stage 3 proves apart. It is what refutes `001`'s trap 2 (element 1000 against 9999) and `010`'s (struct fields at 0 and 4). | `Executor::overlap` |
| J8 | **`sat` means not refuted.** A SAT witness is an execution of the over-approximate encoding, not of the program. | Reading SAT as confirmation is the precision-side mistake; the record's `unconstrained` list says what the witness may have invented. Stated in the C2 `SolverResult` description since W6–W7. | `stage3.py`; `common.defs.schema.json` |
| J9 | **The address projection is a relaxation**: every path to each access explored on its own, with ordering and shared values dropped; UNSAT there refutes the query. | Sound for the same reason a pair is weaker than a triple. It is what keeps index traps from timing out: 001 went from 14 s to 0.6 s. | `Executor::projectionRefutes` |

## Where this list is checked

An assumption that only lives on a page decays. These are the mechanical checks
that currently hold parts of it up:

- `config.can_preempt` has a test pinning **E1**, and tests for **E2** and **E3**.
- `irqrace-probe` reports on **A2**, **B1**, **B3**, **D3**, and warns on **B2**.
- `build.py` refuses to build without `-g`, which is **A2**.
- `runstore.check` enforces **H1** on every run.
- `tests/test_masking.py` pins **F1–F9** and **H1d** one rule per test, on hand-built
  programs, and `tests/test_stage2.py` checks the Racebench cases that motivated them.
- `runstore.check` enforces **H1d**'s drop records on every run, and **H1** for the solver:
  a stage-2 candidate without a context record must have an `unsat`.
- `tests/test_stage3.py` compiles small C programs and pins **J2**, **J3**, **J4**, **J6**,
  **J7** and **H2** one rule per test; three of those tests are mutation-checked against the
  bugs they were written for.
- The C2 schema makes **F1**, **F2** and **H2** structural — there is no field to
  express the unsound alternative.
- **G2** is exercised by `svp_simple_029_001` and six other annotated triples.

The unchecked entries — **C2**, **B2**, **B4**, **I3** — are the honest gaps, and
B2 in particular is listed in [[Open Questions]] as needing verification against
SVF's actual behaviour rather than its documentation.
