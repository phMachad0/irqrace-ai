---
type: log
tags: [wiki, log]
---

# Log

Append-only, newest at the bottom. Greppable: `grep "^## \[" log.md | tail -5`.

## [2026-08-17] setup | wiki instantiated

Instantiated the LLM-wiki pattern for this vault. Wrote `CLAUDE.md` (schema: layers, page
conventions, ingest/query/lint workflows, domain-specific rules on precision metrics and
ground-truth counting). Created `wiki/` with `sources/`, `concepts/`, `tools/`, `benchmarks/`,
`comparisons/`, plus [[Overview]], [[Synthesis]], [[Open Questions]]. Copied the four PDFs
into `raw/`. Decisions: wiki in English; paper pages and tool pages kept separate because
tools recur as baselines across papers; wiki filenames disambiguated with `(paper)`/`(tool)`
so they never collide with the raw clippings.

## [2026-08-17] ingest | BMC4AV

Extracted `raw/BMC4AV.pdf` (35 pp., SSRN preprint) to `Clippings/BMC4AV.md` with pdftotext —
watermark fragments and page furniture stripped, prose reflowed, the three result tables
re-extracted in `-layout` mode and appended as an appendix. Wrote [[BMC4AV (paper)]] and
[[BMC4AV (tool)]]. New concept pages: [[Memory Access Graph]], [[Bounded Model Checking]],
[[Loop Abstraction]]. Recorded the ablation numbers as the most trustworthy in the corpus.
Filed the two conflicts it raises with [[NIChecker (paper)]] — the 37/47-vs-94 re-count and
the `(R,W,W)`-is-benign classification — in [[Contradictions]].

## [2026-08-17] ingest | SDRacer, IntRace, NIChecker

Ingested the three existing clippings. Wrote source pages, tool pages, and the remaining
concept pages; created [[Racebench]] and [[Real-World Program Benchmark]] recording each
paper's own defect count; built [[Tool Capability Matrix]] and
[[Reported Results Across Papers]]. Baseline tools mentioned but not yet read
([[intAtom]], [[CPA4AV]], [[Rchecker]], [[iCBMC]]) got second-hand pages marked stub/draft
and were queued in [[Open Questions]].

## [2026-08-18] ingest | racebench repository documentation (DeepWiki)

Ingested `raw/racebench-deepwiki/` (25 pages). Wrote [[Racebench (documentation)]] with a
provenance warning — it is AI-generated documentation whose quoted, line-referenced content is
reliable but whose seven-defect-pattern enumeration and JSON schema are its own inference.
Rewrote [[Racebench]] around the benchmark's own ground truth (33 cases, 53 bug points, 38
planted FP traps, annotation grammar, conventions) and added
[[NASAC 2019 Prototype Competition]].

Findings that moved other pages: the benchmark annotates defects as **access triples**, so the
data-race/atomicity split may be vocabulary rather than substance ([[Contradictions]] #5);
[[IntRace (paper)]]'s count of 50 matches the benchmark exactly while [[NIChecker (paper)]]'s
54 exceeds it by four with no derivation ([[Contradictions]] #2); Racebench's priority
direction matches [[BMC4AV (paper)]] and contradicts the two data-race papers' prose
([[Contradictions]] #3); false positives are *planted* and were scored at −3 against +2, which
reframes every precision claim in the corpus ([[Precision Metrics]], [[Synthesis]] §4b).
Also recovered authorship: [[Rchecker]] began as competition entry "Verian"; R. Chen maintains
the benchmark and co-authors [[intAtom]] and NIChecker; [[CPA4AV]] is by BMC4AV's own authors.
Updated 6 concept pages, 4 tool pages, [[Synthesis]], [[Open Questions]], [[Overview]] and
`CLAUDE.md` (raw/ may hold multi-file documentation sets; AI-generated docs must be marked).

## [2026-08-18] direction | project goal recorded, and where to start studying

The human stated the research direction: build a static analyzer for **both** data races and
atomicity violations in interrupt-driven embedded C with **no false negatives**, emitting a
per-candidate context record (call stacks, variables, priority and masking state, slice) that
feeds an **LLM stage** which triages false positives, proposes interrupt-specific fixes,
applies them, and re-verifies — a closed loop. Benchmarks: Racebench and the 18-program
real-world suite, plus a real large-scale interrupt-driven open-source subject still to be
chosen.

Recorded it as [[Thesis Goal]] (new `type: project`, added to the schema) and summarized it at
the top of `CLAUDE.md` so every session inherits it, with the two reading consequences: recall
outranks precision here, and techniques are judged by reimplementability rather than headline
numbers. New concept page [[Soundness and False Negatives]] catalogs the eight places recall is
lost across the corpus and states the filter rule (drop only when provably impossible). New
comparison page [[Reimplementation Assessment]] answers the "where do I start" question:
**IntRace first** as the architecture to reimplement, SDRacer for the problem statement and
repair vocabulary, NIChecker for loop abstraction and invocation conditions, BMC4AV last;
stack is Clang/LLVM + SVF + `dg` + optional Z3, with CBMC as a black box for fix validation
only.

Two findings from verifying artifact availability, which corrected the working assumption that
only BMC4AV is open: `github.com/zhvngyuan/NIChecker` is **Apache-2.0 and contains the
benchmarks and per-program results** (tool source withheld pending patents, access by
institutional request), so both community benchmarks are obtainable today and NIChecker's
actual output can be diffed rather than quoted; and BMC4AV's Figshare artifact link from the
paper's §9 did not resolve to an automated fetch and should be mirrored from a browser before
it expires. Updated [[Tool Capability Matrix]] (availability row), [[Synthesis]] (§7),
[[Open Questions]] (new "blocking the build" and tool-method sections), [[Overview]] and
`index.md`.

## [2026-08-20] ingest | local artifacts: racebench, NIChecker, BMC4AV source

The human placed the three obtainable artifacts in `../` and confirmed the priority convention
(larger number = higher). Read them directly rather than through the papers. **BMC4AV's
Figshare artifact turned out to be full source** — a [[CBMC]] fork with bundled MiniSat,
prebuilt `bmc4av`/`bmc4av-ng`, both benchmarks and every reproduction script — which closes the
"blocking the build" item and makes the tool usable as a third-party fix validator.

Findings from measuring rather than quoting:

- **[[Racebench]] ground truth re-measured**: 48 bug points and 38 traps in the 31 simple
  cases, against 50/33 from the DeepWiki export and 54 from [[NIChecker (paper)]]. The
  annotations use **four incompatible grammars** plus several typos; a strict parser returns 28,
  a 42% undercount with no error. Recorded as a recall hazard in
  [[Soundness and False Negatives]] §7b.
- **[[Contradictions]] #3 resolved** from the benchmark READMEs and `priority.info`: larger
  number = higher priority; the two data-race papers' prose is inverted relative to the suite.
- **[[Contradictions]] #1 largely explained**: the `violation.info` files are byte-identical in
  both repositories and hold **45 per-variable** `true violation` entries, while BMC4AV's tables
  count **per instance** — the counts agree on small programs and diverge monotonically with
  size (`wdt_pci_3`: 4 vs 29). A units mismatch, not a 57-defect recall failure.
- **[[Contradictions]] #2 sharpened**: BMC4AV's 38 matches the annotations pattern-for-pattern
  once `(R,W,W)` is removed — but `(R,W,W)` bug points also sit inside its own 25-case subset,
  making its Racebench recall 38/48 = 79.2% against the benchmark's own ground truth, plus six
  `rww` entries it cannot report on the real-world suite.
- **Equal-priority ISRs are in the main suite**, not just `svp_real_002`: `wdt_pci_1` has two
  pairs of same-priority ISRs ([[Asymmetric Preemption]]).

## [2026-08-20] direction | pair/triple unification, pipeline techniques, evaluation subjects

Answered four design questions and filed them. [[Pair-Triple Unification]] evaluates the
human's proposal to detect at pair granularity: the containment argument **holds** — every
harmful triple projects onto two write-bearing pairs, proved in general and verified on all 48
bug points — but it holds only at the matching stage. After a masking filter the abstraction
loses atomicity violations whose two local accesses sit in separate critical sections, because
the pair query is about an instant and the triple query about an interval. Recommendation:
unify the front end, derive both candidate sets from one access enumeration, filter each with
its own query, and reconstruct triples before reporting so the repair scope is right.

[[Pipeline Design]] (new, `type: project`) explains IntRace stages 1–2, loop handling, Z3 and
slicing as they apply to this tool, and answers the fix-validation question: the tool's own
analysis is a **sound but incomplete** validator (a candidate disappearing is a proof under the
abstraction; persistence is inconclusive) and is the only step that catches regressions, while
[[CBMC]] or the local `bmc4av` resolves the inconclusive cases. Establishes the pipeline's
central rule — **a solver may drop a candidate, the LLM may not**. [[Program Slicing]] (new)
covers `dg` and argues for a layered context record rather than a raw slice.
[[Candidate Evaluation Subjects]] (new) recommends mined Linux driver commits as tier 3 over
RTOS codebases, on the grounds that RTOS work changes the concurrency model rather than just
the input size, and notes the SMP-versus-interrupt-preemption filter that tier-3 mining needs.

Also noted: seven LLM-and-static-analysis PDFs arrived in `../` and are unread — queued in
[[Open Questions]] rather than ingested, per the ingest workflow.

## [2026-08-23] ingest | seven LLM-assisted static analysis sources

Converted `raw/SAST-Genius.pdf` and `raw/Static-Chatgpt.pdf` with pdftotext into `Clippings/`
(frontmatter records the method and, for SAST-Genius, that its two-column layout extracts **out
of reading order**). The other five clippings were already present. Ingested all seven.

Wrote source pages for [[LLift (paper)]], [[IRIS (paper)]], [[SkipAnalyzer (paper)]],
[[ChatGPT for Static Analysis (paper)]], [[AdaTaint (paper)]],
[[Reducing False Alarms (paper)]] and [[SAST-Genius (paper)]]; four concept pages
([[Prompt Architecture]], [[LLM Triage]], [[Specification Inference]],
[[LLM-Assisted Repair]]); the comparison [[LLM Integration Patterns]]; and the project page
[[LLM Stage Design]]. Expanded [[Thesis Goal]] with the decision policy and what the LLM
literature says the design must get right.

Deliberate schema decision: **no tool pages for this branch.** The transferable content is
technique, not artifact, and only IRIS ships an obtainable tool
(`github.com/iris-sast/iris`); five thin tool stubs would have added navigation cost without
content. [[LLM Integration Patterns]] carries the per-artifact comparison instead.

Findings that moved other pages:

- **The intersection of the two literatures is empty.** All seven sources address *sequential*
  defects; [[LLift (paper)]] names concurrency as a case static analysis handles badly and then
  sets it aside. Recorded in [[Synthesis]] §7 and [[Overview]] as the sharpest novelty claim
  available.
- **Prompt architecture dominates outcome**: LLift's ablation moves recall 0.15 → 1.00 with one
  model on one dataset. [[Prompt Architecture]] carries the table; it reframes prompt design as
  the load-bearing engineering decision rather than a finishing step.
- **The drop-versus-rank rule now has measurements behind it**, not just principle: filtering
  designs lose 6 points of recall ([[Reducing False Alarms (paper)]]) to ~25
  ([[AdaTaint (paper)]]), while a conservative decision policy reached 1.00.
- **A fifth LLM attach point** that was not in the original plan — inferring the interrupt model
  itself, the analogue of IRIS's taint-specification inference and the automated answer to
  IntRace's user-written configuration file ([[Specification Inference]]).
- **[[Racebench]] is already a triage benchmark**: 48 bug points plus 38 *deliberately planted*
  traps is 86 adversarial labelled candidates, which is exactly the test set the LLM stage
  needs.
- New metric adopted: **Inspection Ratio** ([[Precision Metrics]]), the only effort-aware metric
  in the corpus and the right headline for a tool that holds recall at 100%.
- New false-negative sources catalogued in [[Soundness and False Negatives]] §7c: context gaps
  becoming confident verdicts, specification inference that narrows, and **prompt injection
  through analysed source comments**.

Queued in [[Open Questions]]: UBITect, Kharkar et al., and Bai et al. as sources to acquire,
plus six LLM-stage experiments — chief among them a domain-specific LLift-style ablation, and a
ten-candidate feasibility probe to run *before* building the pipeline.

## [2026-08-27] direction | four design decisions recorded; blocking-questions sweep

The human settled four open design points, all in the direction of doing less:

- **Specification inference demoted** from a design pillar to a documented alternative
  ([[Specification Inference]], rewritten). The IRIS analogy breaks on four counts: masking
  primitives are a **closed set per platform** rather than an open world, the unit of work is a
  module and identifying entry points is part of extracting it anyway, both benchmarks already
  ship the configuration (`priority.info`, 3–9 flows per program), and — the decisive one — the
  page's two soundness directions were conflated. Split out: *missing an ISR* costs recall but
  is a `grep`; *missing a masking primitive* costs only precision given the standing default;
  *wrongly listing one* costs recall and an LLM is likelier to do it than a human. The
  recall-critical half is the mechanically easy half, which inverts the case. What survives is
  an optional LLM **audit** of a hand-written config — additive only, so it cannot hurt
  soundness.
- **Role (A) dropped from [[LLM Stage Design]]**; the architecture is now two LLM roles, triage
  and repair, both downstream of the solver.
- **Z3 is fixed in the pipeline ahead of the LLM**, not an ablation option
  ([[Pipeline Design]], [[Path Feasibility Analysis]], [[Thesis Goal]],
  [[Reimplementation Assessment]]). Three compounding reasons: it is the only sound filter; it
  cuts ~95 candidates per program to ~13, taking triage from about $90 to about $6 per program;
  and it mirrors [[LLift (paper)]] exactly, where symbolic execution runs first and the LLM
  receives the undecided residue. Consequences recorded: the solver's verdict belongs in the
  context record, **inconclusive must not collapse into `SAT`**, and the LLM now sees a biased
  sample — the hardest candidates — so evaluation must say which population it measured.
- **Precomputed slicing removed from context retrieval**, replaced by progressive prompting
  ([[Program Slicing]], rewritten as an alternative). `dg` stays as a dependency for its
  dependence graphs; its slicer does not. The request distribution from progressive prompting is
  now treated as *the specification* of the context record, which makes instrumenting that
  channel the cheapest experiment in the project.

Also fixed a stale section: **"Blocking the build" in [[Open Questions]] still listed three
items resolved on 2026-08-20** — an edit that session did not apply. Rewrote it as "Decisions
that block development", separating struck-through resolved decisions from what is genuinely
still open, and split into static and LLM sides.

Two blockers surfaced by the sweep that the wiki had not recorded anywhere:

- **No match rule between a reported candidate and an annotated bug point.** Exact line triple?
  Variable plus overlapping accesses? [[IRIS (paper)]] faced this and answered it explicitly;
  without an equivalent, "recall 100%" is not a computable claim. Interacts with
  [[Pair-Triple Unification]], since pairs must be reconstructed into triples before matching.
- **The soundness assumption list does not exist as a page**, although
  [[Soundness and False Negatives]] names it as the deliverable. Until it is written, the
  central claim of [[Thesis Goal]] cannot be stated precisely or tested.

Plus two semantic decisions that change the candidate set and must precede coding: whether
**equal-priority flows** can preempt each other (present in `wdt_pci_1`, uncovered by every
paper), and the **interrupt arrival model** — Racebench allows firing an unspecified number of
times, while SDRacer excludes reentrancy and NIChecker bounds ISR executions.

## [2026-08-27] direction | multi-file / whole-repository input recorded as a capability

The human specified that processing **entire repositories, or multi-file projects with several
tasks and several ISRs, is a feature the tool should have** — not exercised by the benchmarks,
which are all single extracted `main.c` files, but wanted for testing against real embedded
projects.

Wrote *Input scope and build requirements* in [[Pipeline Design]]: two input modes; the
`llvm-link` / `wllvm` / `gllvm` route to linked whole-program bitcode; and why merging at the C
**source** level is the wrong level — it destroys the source ranges the context record depends
on, collides `static` symbols, collapses per-TU preprocessor state, and discards what only the
build system knows. Bitcode linking preserves `DILocation` for free. Also recorded the `-O0`
`optnone` trap.

Two points that reframe the scaling worry, both now on the page:

- **The configuration file bounds the analysis, not the input.** Cost follows code reachable
  from the declared entry points, not repository size, so pointing the tool at a whole tree is
  not the same as analysing a whole tree. The exception is the points-to analysis, which SVF
  runs whole-module; pre-pruning with a signature-based call graph plus `llvm-extract` is
  recorded as a design option.
- **Two recall-critical policies must be stated**, both of which matter far more at repository
  scope than at single-file scope: functions with **no body** in the module (sound default:
  may touch any global; refined by a hand-modelled set, the same closed-set argument that
  settled [[Specification Inference]]), and **indirect calls** — an unresolvable target set must
  be treated as *every address-taken function with a matching signature*, never as empty.
  Resolving to nothing deletes whole subtrees of reachable accesses invisibly.

Reconciled [[Candidate Evaluation Subjects]], which recommended "scope per module, not per
repository": that recommendation is about **evaluation** scope and stands, while **input** scope
is now whole-repository. The two were conflated and are now stated separately, so a later
session does not read the old wording as cancelling the capability. Also updated
[[Thesis Goal]] (new step 0), [[Reimplementation Assessment]] (build step added to the effort
table and the stack), [[Soundness and False Negatives]] §1 (the indirect-call rule), and
[[Open Questions]] with three new blockers: the external-function model list, verifying SVF's
default on unresolved indirect calls, and confirming the build flags.

## [2026-08-27] direction | dashboard architecture recorded

The human specified a **UI/dashboard** as a usability requirement covering the whole scope —
subject configuration, interrupt model, run management, results, static analysis through LLM
triage and repair — and proposed Streamlit. Wrote [[Dashboard Design]] (`type: project`):
architecture, 45 numbered requirements across eight areas, run-store layout, and a build order.

**Streamlit endorsed, with one architectural constraint that shaped the whole page:** the UI is
a launcher and a viewer, never the executor. Streamlit re-runs its script on every interaction,
which cannot host a multi-minute pipeline; the job runner is a separate process writing NDJSON
into a run directory, and the UI polls. That constraint turns out to be good engineering
regardless — batch evaluation (31 Racebench cases, the ablation matrix) has to be scriptable, so
every UI capability must exist in the CLI first, and a run must be a directory rather than a
session.

Framed the UI as **part of the contribution rather than packaging**, on the wiki's own evidence:
[[Synthesis]] §5 records that automation is the axis this field competes on — IntRace needs a
config file, NIChecker a variable and pattern per run — and advises making the adoption argument
there rather than on runtime. Two further hooks: the **Inspection Ratio is paid in the UI**, so a
design that buries candidates inflates the metric it reports; and three of the four concurrency
tools are unobtainable, so an operable artifact is itself a differentiator.

Requirements where the wiki's rules had to become interface decisions:

- **R24**: candidates proved impossible by the solver are shown collapsed **with the proof**,
  never deleted; low-ranked LLM candidates are ranked, never hidden. A UI that hides low-ranked
  candidates by default reimplements the filter the design rejects ([[LLM Triage]]).
- **R14**: the solver-timeout policy defaults to `inconclusive → keep`, and "discard on timeout"
  is only reachable behind an explicit unsound-mode warning.
- **R13**: `(R,W,W)` included by default, with a warning if switched off.
- **R10**: the two unresolved semantic decisions — equal-priority preemption and the interrupt
  arrival model — are exposed as labelled, defaulted settings recorded in the manifest, rather
  than buried as constants.
- **R30**: the full LLM conversation including **progressive-prompt requests and what the
  harness supplied** is shown, because that log is how the context record gets specified now
  that precomputed slicing is out.
- **R5/R7**: the priority convention is stated on screen and the config is validated against the
  bitcode in both directions, since a typo in the interrupt model is invisible in the results.

Also updated [[Thesis Goal]] (the loop is driven from a dashboard), [[Synthesis]] §5,
[[Overview]], `index.md`, and [[Open Questions]] with two interface questions.

## [2026-08-27] direction | 10-week implementation roadmap, three tracks

The human moved the project to implementation: two developers, static analysis and LLM
integration split between them, ten weeks (31 Aug – 6 Nov 2026), with a dashboard as a third
track and progress to be presented to an advisor. Wrote [[Roadmap]].

The organising idea is **four frozen contracts** rather than a task list: the configuration file
(C1), the **context record** (C2), the run store layout (C3), and the context request protocol
(C4). C2 is the seam between the two people and must be stable by Wednesday of week 1; C4 is
owned by the *LLM* side on the principle that the consumer should specify what it needs to ask
for, with the static side implementing the resolver behind it.

**The fixture trick unblocks parallel work.** In week 1 the LLM developer hand-builds ~20 context
records from [[Racebench]] — 10 annotated bug points, 10 planted traps — conforming to C2, and
works against those until week 8, with a mock resolver serving progressive-prompt requests from
static files. Building them by hand is also how C2's gaps surface while they are still cheap.
The same 20 records double as the feasibility probe [[Open Questions]] requires *before* the
pipeline is built, so none of the effort is throwaway.

Sequencing notes worth keeping: ground-truth infrastructure is scheduled in week 2, **before any
analysis**, because the parser certification, the counting unit, the match rule and the soundness
assumption list are what make every later number meaningful — all four are currently open
blockers. The dashboard is ordered by payback rather than by screen order, putting the read-only
candidate explorer at W4–W5 because reading `candidates.jsonl` by hand is the slow path for
debugging stage 1.

Five milestones (M1 11 Sep … M5 6 Nov). M1 and M3 are the load-bearing ones: M1 because a
negative feasibility probe changes the plan while there is time, M3 because the LLift-style
**ablation table** is the result nobody in either literature has produced for concurrency.

Recorded the schedule as **ambitious** and supplied a five-rung de-scoping ladder, ordered:
multi-file input, the real-world suite, the Z3 stage, repair, dashboard beyond the explorer.
Noted explicitly that dropping Z3 is survivable because the design stays *sound* without it — Z3
only ever discards — and that three things must not be cut at any rung: the recall gate, the
parser certification, and the assumption list.

## [2026-08-31] build | W1 Track A — contracts frozen, toolchain up, 31/31 cases to bitcode

Started implementation in `project-src/`. Everything in [[Roadmap]] W1 for Track A is done, and
the three joint days-1–3 contract items are written as schema files rather than prose.

**Contracts C1–C4 frozen** in `project-src/contracts/`, versioned `c1/1.0.0` … `c4/1.0.0`, each
with a worked example drawn from `svp_simple_001_001`. `common.defs.schema.json` holds what the
four share. Five recall decisions from the wiki are made *structural* rather than left to code:
masking is three-valued (`disabled`/`enabled`/`unknown`, with no boolean `is_masked` to reach
for); the interval property is a separate field from the point property; the solver verdict has
four values including `inconclusive` with a mandatory reason; `provenance` is required on every
context record; and there is **no `slice` field**, deliberately ([[Program Slicing]]). A sixth,
structural: C2's `fingerprint` covers only subject, class, variable and access locations, never
run id or timings, because Track B's result cache is keyed by it.

**Toolchain**: clang-14 / LLVM 14 / SVF 2.7 / Z3 4.8.12. SVF is built against the *system* LLVM
rather than its own prebuilt one — 64 MB and ten minutes instead of a multi-gigabyte download,
and it keeps the bitcode version and the analysis in step. SVF 2.7 is the release that targets
LLVM 14.

**Done-when met**: all **31/31** Racebench simple cases compile to whole-program bitcode; the
C1 file loads for all 31 (generated from the suite's own README table, not hand-written); SVF
lists their globals through a new `irqrace-probe`, which also implements
[[Dashboard Design]] R4 and R7 — it reports declared-only functions and validates the interrupt
model against the built module in both directions.

Three findings, each recorded in the wiki or in `project-src/docs/`:

1. **The Racebench README names two entry points wrongly** — `svp_simple_028_001_main` and
   `svp_simple_030_001_main`, where both files define `..._001__main` with two underscores.
   Recall-critical, not cosmetic. Added to [[Racebench]].
2. **Per-flow masking analysis drops an annotated bug point.** In `svp_simple_001_001` the main
   task masks irq 2 across the whole interval of its bug point, but `isr_1` preempts that
   interval and re-enables it. Interval masking must account for flows executing *inside* the
   interval. Written up in `project-src/docs/masking-semantics.md`; the contract now carries
   `reenabled_within_interval_by`. Added to [[Interrupt Masking and Synchronization]].
3. **`CallBase::getCalledFunction()` returns null for direct calls** to `init`, `idlerun` and
   `rand`, because `common.h` declares them K&R-style and `llvm-link` routes the call through a
   bitcast. Read naively this makes all 31 subjects look like they use function pointers, which
   for a sound analyzer means over-approximating all 31 call graphs. After stripping the casts,
   **exactly one case — `svp_simple_029_001` — uses genuine function-pointer dispatch**, and it
   is therefore the only subject that can exercise stage 1's indirect-call handling.

142 tests pass, including an end-to-end build-and-probe over all 31 subjects.
