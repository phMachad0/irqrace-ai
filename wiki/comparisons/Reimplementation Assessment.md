---
type: comparison
tags: [wiki, comparison]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-27
status: draft
---

# Reimplementation Assessment

Which of the four tools to study first, what to take from each, what is realistically
reimplementable, and on what stack — judged against [[Thesis Goal]], not against the papers'
own claims. Filed 2026-08-18 in answer to the question "where do I start".

## Verdict

| Order | Tool | Read it for | Reimplement? |
| --- | --- | --- | --- |
| 1 | [[SDRacer (paper)]] | the problem statement (§2.5) and the **repair vocabulary** (§4) | repair templates yes; Simics validation no |
| 2 | [[IntRace (paper)]] | **the architecture to build** — stages 1 and 2 | **yes, this is the base** |
| 3 | [[NIChecker (paper)]] | interrupt semantics done properly, [[Loop Abstraction]], the only correctness proof | ideas yes, tool no |
| 4 | [[BMC4AV (paper)]] | how far in-solver optimization can go | no |

**Start with [[IntRace (tool)]].** It is the only source whose architecture *is* the
architecture you need: purely static, staged, no execution, no model checker, and its
expensive last stage — [[Path Feasibility Analysis]], 69.7% of its runtime — is precisely the
component the LLM triage stage is meant to replace or supplement. Reimplementing IntRace
stages 1–2 gives you a working sound candidate generator; everything downstream is your
contribution rather than someone else's reimplementation.

Read [[SDRacer (paper)]] §2.5 first anyway — it is a day's reading and it is the clearest
statement in the corpus of why thread techniques do not transfer ([[Asymmetric Preemption]]).
Its repair section is the only prior art for the fix-generation half of your loop.

## Which tool "yields the best results"

Two different questions, with different answers.

**Best reported numbers**: [[BMC4AV (tool)]] — 94/94 and 38/38 with zero false positives,
21.12 s and 6.35 s ([[Reported Results Across Papers]]). But it is an **SSRN preprint, not
peer reviewed**, its headline denominator is its own team's manual re-count of a rival's
benchmark, and its authors wrote [[CPA4AV]], one of the baselines
([[Contradictions]] #1). The most trustworthy numbers in the whole corpus are its *ablation*
table, which is single-team and single-machine.

**Best suited to this project**: [[IntRace (tool)]] architecturally,
[[NIChecker (tool)]] semantically. Neither has the best headline numbers, and that is fine —
their numbers are *precision* results, and precision is what you are deliberately trading away
([[Soundness and False Negatives]]).

A further point that decides this: **the BMC lineage cannot give you what you want.**
[[NIChecker (tool)]] and [[BMC4AV (tool)]] establish absence of a counterexample *up to a
bound*, which is not zero false negatives ([[Contradictions]] #4). Soundness in your tool has
to come from an over-approximating pattern-match front end, not from a model checker. BMC
belongs at the *end* of your loop — as the check that an applied fix removed the defect —
where bounded absence is exactly the right guarantee and the property under test is small.

## What to take from each

**[[SDRacer (paper)]]** — the five reasons thread techniques fail (§2.5); the repair
strategies: insert `irq_disable(n)`/`irq_enable(n)` around the offending access, add locks,
extend an existing critical section, and **merge adjacent critical sections** to avoid
redundant operations; and the discipline of *measuring repair overhead* (<0.09 on 9 of 11
subjects, markedly worse on two where disabling interrupts changed the main task's control
flow). That overhead-measurement methodology is directly reusable as the acceptance test for
LLM-proposed fixes. Skip the Simics stage — commercial simulator, and a documented
false-negative source ([[Soundness and False Negatives]] §7).

**[[IntRace (paper)]]** — the three-stage pipeline, and specifically:
- Stage 1: Clang AST + LLVM CFG, inter-procedural alias analysis into a shared-resource pool
  of globals and pointer-typed parameters, then pattern matching that **deliberately ignores
  guard conditions and interrupt state so nothing is missed**. This is your sound front end,
  and its design intent already matches your goal.
- Stage 2: model each task/ISR as a block `(T, I, S, p)` — name, interrupt status, timing,
  priority — and discard only pairs that provably cannot overlap; nesting handled by
  inside-out sequential conversion. Cheap, and it removes **54.2%** of candidates.
- The attrition budget: ~**208 candidates per real program** after stage 1, ~95 after stage 2,
  a further 86.2% removed by stage 3. That is your LLM cost model — roughly 100 candidates per program reaching triage if you stop after stage 2, and it tells you whether to keep a
  cheap solver stage before the LLM.
- Its confessed weaknesses are your feature list: the user-written config file for ad-hoc
  masking, and unclassified benign races.

**[[NIChecker (paper)]]** — do not reimplement, but steal three things. **[[Loop Abstraction]]
applied before unwinding** is the most recall-relevant technique in the corpus and IntRace has
no equivalent (it asks the user for a loop depth). **Invocation conditions** are the cleanest
formalization available of how priority and masking gate an ISR — reuse the model even without
the sequentialization. And it is the only source with a **bounded-correctness proof** (§6.1),
so it is your template for what a soundness argument looks like written down. Its slicing step is useful in the
one place this project still model-checks — validating an applied fix ([[Program Slicing]]) —
rather than in context capture, which retrieves on demand instead.

**[[BMC4AV (paper)]]** — read for orientation and for the ablation, but its contribution lives
*inside* CBMC's encoding and SAT interaction. Reimplementing it means modifying a model
checker's internals, which is not TCC-scale and produces nothing reusable for a static+LLM
pipeline. Its transferable idea is the cheap one: identify candidates first, then confirm only
the **key partial orders** each candidate requires, rather than encoding all orderings up
front. Whether the [[Memory Access Graph]] idea transfers to [[Data Race]] detection at all is
an open question ([[Open Questions]]).

## Reimplementation difficulty

| Component | Effort | Notes |
| --- | --- | --- |
| Whole-program bitcode build | **low** | `wllvm`/`gllvm` or `llvm-link`; off-the-shelf. Required for multi-file input ([[Pipeline Design]]). |
| IntRace stage 1 (shared resources + pattern match) | **low–moderate** | Clang/LLVM + an off-the-shelf pointer analysis. The bulk of the value. |
| IntRace stage 2 (concurrency relationship) | **low** | Block model + priority/masking/timing checks. Mostly bookkeeping. |
| Context capture for the LLM | **low–moderate** | Call-stack reconstruction + masking state + debug-info mapping. No precomputed slicing ([[Program Slicing]]), so smaller than first estimated. |
| SDRacer repair templates | **low** | Source-level rewrites; the hard part is validating them. |
| IntRace stage 3 (Z3 path feasibility) | **moderate–high** | **Required, not optional** — the only sound filter, and what makes LLM triage affordable ([[Pipeline Design]]). |
| Loop abstraction | **moderate** | Worth it; the alternative is missing deep bugs entirely. |
| CBMC-based fix validation | **low** | Use CBMC as a black box, or `bmc4av` directly. Do not modify either. See [[Pipeline Design]]. |
| NIChecker lazy sequentialization | **high** | Only sane via [[Lazy-CSeq]], which is available. |
| BMC4AV guided MAG | **very high** | Inside CBMC + MiniSat. Out of scope. |
| SDRacer dynamic replay | **out of reach** | Simics is commercial. |

## Technology stack

- **Build — `wllvm` or `gllvm`** to intercept a project's own build and produce linked
  whole-program bitcode, since multi-file input is a stated capability. Single-file benchmark
  subjects skip this and go straight to `clang -g -emit-llvm -c`.
- **Front end — Clang/LibTooling for the AST, LLVM IR for the analysis.** This is what
  [[IntRace (tool)]] and [[SDRacer (tool)]] both use. Compile subjects with `-g -O0` and keep
  `DILocation` debug metadata: the LLM stage needs source files, line numbers and identifier
  names, and analysing IR without debug info throws away exactly that. Treat "every candidate
  maps back to a source range" as a hard requirement from day one, not a later feature.
- **Pointer/alias analysis — SVF** (field-sensitive Andersen's over LLVM IR), used in
  **may-alias** mode. Also gives the call graph, which matters because embedded ISR dispatch
  goes through function-pointer vector tables ([[Soundness and False Negatives]] §1).
- **Dependence analysis — `dg`** (`github.com/mchalupa/dg`), cited by IntRace itself (ref. 26).
  Taken for its **data- and control-dependence graphs**, which the concurrency analysis and the
  harmfulness criterion both need. Its slicer is *not* used: context is retrieved on demand
  through progressive prompting rather than precomputed ([[Program Slicing]]).
- **SMT — Z3**, as a **required** stage before the LLM. It costs ~70% of IntRace's runtime and
  removes 86.2% of what reaches it, but it is the only component permitted to discard
  candidates, and it is what takes triage from ~95 candidates per program to ~13 — roughly $90
  down to $6 at LLift's measured per-candidate cost ([[Pipeline Design]]).
- **Bounded verification — CBMC**, as a black box, for the fix-validation step only. Add
  [[Lazy-CSeq]] if you need sequentialization semantics.
- **LLM — Claude** (Opus 5 for triage/repair reasoning) via the Anthropic API. Pin the API
  details when that stage is actually built rather than designing around them now; what
  matters at this stage is that the static phase emits a structured, self-contained context
  record per candidate.
- **Language for the tool itself — C++** for anything touching LLVM/SVF/dg (they are C++
  libraries and bindings will fight you), with Python for orchestration, the LLM loop, and
  result handling.

## Artifact availability (obtained 2026-08-20)

All three obtainable artifacts are now local, one directory above the vault: `../racebench`,
`../NIChecker`, `../BMC4AV`.

| Artifact                                                                      | Status                                                                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [[Racebench]]                                                                 | **open** — `github.com/chenruibuaa/racebench`. Used by all four papers.                                                                                                                                                                                   |
| [[NIChecker (tool)]] benchmarks + results                                     | **open** — `github.com/zhvngyuan/NIChecker`, Apache-2.0. Contains `NIChecker_Experiments/` and the CPA4AV and iCBMC comparison results.                                                                                                                   |
| [[NIChecker (tool)]] source                                                   | **withheld** — the repository states the tool source is private pending patents; access by institutional email request only, anonymous requests declined.                                                                                                 |
| [[BMC4AV (tool)]]                                                             | **claimed open** — Figshare `figshare.com/s/2fbd2c948c9722bc5c59` (paper §9). The link did not resolve to an automated fetch on 2026-08-18; open it in a browser and mirror the contents into the vault's raw layer, since anonymous review links expire. |
| [[Lazy-CSeq]]                                                                 | **open** — CSeq project, Southampton / `github.com/CSeq`.                                                                                                                                                                                                 |
| [[CBMC]], Z3, SVF, `dg`, Clang/LLVM                                           | **open**.                                                                                                                                                                                                                                                 |
| [[SDRacer (tool)]], [[IntRace (tool)]], [[Rchecker]], [[intAtom]], [[CPA4AV]] | **not obtainable** — consistent with every paper in the corpus failing to obtain its baselines ([[Contradictions]] #6).                                                                                                                                   |

Three practical consequences. First, **both community benchmarks are in hand**, so the
evaluation half of the thesis is unblocked — and both repositories ship per-program results,
so the detector's output can be diffed against NIChecker's and BMC4AV's actual output rather
than against a number in a table. Second, **BMC4AV is a working, fully automatic checker**,
which makes it usable as a third-party validator in the repair loop
([[Pipeline Design]]) — a role that needs no reimplementation at all. Third, **NIChecker is
reconstructible in principle** from open components ([[Lazy-CSeq]] + [[CBMC]]) even though its
source is withheld, and its repository ships the sequentialized and sliced intermediates, so
its transformation can be studied without rebuilding it.

Reading these artifacts has already returned more than the availability question:
[[Contradictions]] #3 is resolved, #1 is largely explained as a counting-unit mismatch, and
BMC4AV's Racebench ground truth is now traceable to the benchmark's own annotations.

## Suggested sequencing

1. ~~Obtain both benchmarks and the BMC4AV artifact.~~ Done — all three are local.
2. Read SDRacer §2.5 and §4, then IntRace end to end.
3. Build IntRace stage 1 on Clang/LLVM + SVF. Validate on [[Racebench]]'s 31 simple cases
   against the **48** measured bug points — target **recall 100%**, and report the candidate
   count without embarrassment.
4. Add stage 2, measuring attrition against IntRace's reported 54.2% as a sanity check.
5. Design the context record and the candidate derivation — pairs *and* triples, from one
   access set, per [[Pair-Triple Unification]]. This is where the data-race/atomicity
   unification actually happens, and it is not a matter of merging pattern sets.
6. Add stage 3 (Z3). It is required, not optional, and everything downstream is sized by it.
7. Only then: LLM triage on the solver's residue, LLM repair, CBMC re-verification
   ([[LLM Stage Design]]).

Steps 3–5 alone, with an honest soundness statement, are already a complete TCC. Steps 6
onward are the part that is new to the field.
