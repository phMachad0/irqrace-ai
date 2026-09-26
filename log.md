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

## [2026-09-26] build | W1/W2 Track B — harness, prompts, scoring; fixtures blocked

Track B started on branch `track-b/llm-integration`, four weeks behind [[Roadmap]]. M1 (11 Sep)
and M2 (25 Sep) are both past. The harness is built and tested end to end against a fake model
client; the *measured* work is blocked on one thing, stated at the bottom.

**The decision policy is now a type, not a convention.** The model is never asked for a bucket.
It answers two narrow questions — *is this interleaving feasible?* and *if feasible, is it
harmful?* — and `bucket_of` derives the bucket from the pair. `likely_infeasible` is unreachable
except from an explicit infeasibility claim, and any `uncertain` on either axis yields
`uncertain`. A model cannot express low confidence by reaching for a low bucket, because the
word is not in its vocabulary. `scoring.score()` separately refuses to score a set that is not
exactly the input set, so a dropped candidate raises instead of quietly raising recall by
vanishing from the denominator.

**The ablation is five configurations, not five prompts.** The rows compose the same markdown
assets (`base.md`, `domain_rules.md`, `context_requests.md`, `self_validation.md`), so turning a
component on adds its file and changes nothing else — which is the only way the LLift-shaped
table means what it says. The config hash covers **asset contents**, so editing the domain-rule
table invalidates the result cache for every row that includes it; without that, an edited
prompt would be compared against answers produced by the previous wording.

**C4 is exercised, and its status field carries the recall rule.** `RecordBackedResolver` answers
from the candidate's own C2 record and returns `not_found`/`unsupported` for everything else —
each with the self-validation rule that applies to it, rendered *before* the payload. That is
deliberate rather than a fixture-era limitation: it exercises the rule "a definition you could
not obtain may access the shared variable" on every run, and that rule is the one deciding
whether the model invents safety from missing evidence. Request kind, depth and status are
logged per candidate — the D#2 measurement, which is the cheapest experiment in the project.

**Three findings.**

1. **The baseline row cannot use prompt caching, and this confounds the cost column.** Caching
   needs a prefix of roughly 1024 tokens. The `simple` row's system prefix is ~565 tokens and
   the full row's is ~1900, so rows 2–5 cache and row 1 silently does not. Cost per candidate is
   therefore not comparable across rows unless uncached cost is reported for all five. Recorded
   in `llm/prompts/__init__.py`.
2. **A refusal is not a verdict.** Analysed C is security-adjacent text and a safety classifier
   may decline a candidate. Scoring that as any bucket would corrupt the row, so it raises and
   the exclusion is reported.
3. **`tests/test_racebench.py` breaks at collection on any machine without the suite.** It
   parametrises at module scope from an absolute path into Track A's checkout, so `pytest tests`
   cannot run at all here. Track A's file; not touched from this branch. Workaround in the
   README.

**Blocked: the 20 fixtures, and therefore the W1 go/no-go probe.** 2 of 20 exist — the seeded
pair from Track A's contract examples, which is adversarially ideal (same subject, same `WRW`
pattern, same class; the only difference is whether a flow running inside the masked interval
re-enables the interrupt). The remaining 18 must be built from real `2.1_remarks` annotations:
inventing source locations and function bodies would poison the ground truth every number is
divided by. The suite is not on this machine.

State: 70 Track B tests, 111 passing overall (65 skipped, needing the toolchain).

## [2026-09-26] direction | LLM stage made provider-agnostic; backend seam added

Direction from the human: the LLM integration must be agnostic to the model, able to connect
any one. Recorded here because it changes an architecture decision, not just an implementation.

**MCP was proposed as the mechanism and is not one.** The Model Context Protocol standardises
how an application exposes *tools and context* to a model; it is not a provider abstraction, and
speaking MCP to Claude, GPT and a local model still needs three different clients to make the
call. What delivers model-agnosticism is a backend adapter layer, and that is what was built.
MCP does have a genuine fit in this project — **C4 is shaped exactly like an MCP tool surface**,
and exposing the resolver as an MCP server would let any MCP-capable host pull context from
irqrace without knowing our code. Considered and deferred, not rejected: it is not measured by
any number in [[Roadmap]], and the alternative of making irqrace *only* an MCP server would move
the loop into an external host and cost the scripted ablation (M3), the per-candidate cache,
majority voting and consistency — none of which any host implements.

**Why this is more than portability.** [[LLift (paper)]]'s central claim is that prompt
architecture dominates model choice — its ablation moves recall 0.15 → 1.00 with one model. A
harness welded to one SDK can cite that; one with a backend seam can *test* it on interrupt
concurrency, which no source in either branch has done. Holding the prompt fixed and sweeping
the model is now a scripted experiment. It also gives the ablation an honest floor: if a local
7B with the full prompt architecture beats a frontier model with the simple prompt, that is a
far stronger result than any single-model table.

`provider:model` is both the selector and the identity, so a number cannot be reported without
saying what produced it ([[Precision Metrics]] #8, which the multi-provider setting makes
sharper — the model name alone is no longer unique). Three adapters: `anthropic` via the
official SDK, `openai` covering every OpenAI-compatible endpoint, `ollama` for local. The two
generic adapters speak plain HTTP from the standard library — depending on one vendor's SDK to
reach a local vLLM server would be backwards, and it means the ablation is reproducible against
a local model with nothing installed beyond the repository.

**Three cross-provider differences are recorded rather than smoothed over**, because each lands
in a number:

1. **Structured-output tier.** Providers range from an enforced JSON Schema to nothing. Which
   tier served an answer is stored on the verdict itself (`produced_by.structured_mode`). A row
   answered through `prompted_json` is not the same experiment as one answered through
   `native_schema`; finding that out afterwards would invalidate a comparison instead of
   explaining it.
2. **Prompt caching is Anthropic-only here.** Cost per candidate is therefore not comparable
   across backends, which is a caveat on a table rather than a bug — but only if `Capabilities`
   says so, which it now does, in the CLI and next to the row.
3. **Unpriced is not free.** A backend that did not know its rates yields `cost_usd() is None`,
   and `Spend` refuses to produce a per-candidate figure from a partial total. A silent 0.00
   would put a local model in the same column as a cloud one.

The seam does **not** retry or repair a bad answer into a good one: a backend that cannot produce
a parseable verdict raises, and the candidate is reported as an exclusion. Inventing a verdict to
keep a sweep running is how a recall number becomes fiction.

State: 139 passing (65 skipped, needing the toolchain), of which 98 are Track B. Still blocked on
the 18 remaining fixtures and therefore on the W1 go/no-go probe.

## [2026-09-26] build | Track B — racebench acquired; tolerant annotation reader certifies 48/38

Racebench cloned to `../racebench` per this file's convention, 539K, unmodified. Proceeding
without Track A by agreement; the ownership overlap below needs reconciling later.

**Both W1 findings verify against the source.** The suite README names `svp_simple_028_001_main`
and `svp_simple_030_001_main`; both files define `..._001__main` with two underscores. And the
`svp_simple_001_001` bug point is exactly `<W#32>,<R#55>,<W#35>`, with `isr_1` setting the flag
at line 41 and re-enabling irq 2 at line 46 — the interval puncture [[Interrupt Masking and
Synchronization]] records. The README also settles [[Contradictions]] #3 in its own words:
「优先级数字越大，优先级越高」, larger number is higher priority.

**A tolerant annotation reader now independently reproduces 48 bug points and 38 traps**
(`project-src/src/irqrace/llm/annotations.py`). That is [[Roadmap]] W2's "done when", reached
from Track B's side because no fixture can be built without it. Two notes on getting there:

- The wiki's prediction that *"a strict parser silently returns 28 bug points instead of 48"*
  **reproduced exactly** — my first reader returned 28. Independent confirmation of a claim
  that was previously only asserted.
- Reaching 48 needed two fixes beyond the four documented grammars. `svp_simple_022_001`'s
  four headerless entries must default to *bug points*; requiring a header costs exactly those
  four and yields 44, silently. And `svp_simple_013_001` writes its access type in lower case,
  `<w#66>`, which is not in the wiki's catalogue. Both added to [[Racebench]].

The reader does not match a grammar. It finds bracket groups and pulls a type letter and a
number out of each independently, so field order, the `#`, the separator and letter case all
stop mattering and the four grammars collapse into one rule. It recovers from every catalogued
error — doubled bracket, missing closing bracket, missing `#` — rather than skipping the entry.

**New finding: `svp_simple_019_001` is annotated against the other copy of the suite.** All
five of its annotations — one bug point, four traps — resolve cleanly against
`racebench/2.1/svp_simple_019/` and not against the `2.1_remarks` file they are written in,
where they point at `idlerun();`, a bare `{`, and blank lines. The annotated copy is 72 lines
of code to the plain copy's 66: the `if` bodies were braced during a reformat and the line
references were never updated. Checked across the suite, **019 is the only case affected**;
the other 30 verify identically against both copies. Both facts are fixed as tests.

This closes part of an open blocker rather than just adding a caveat. **Exact-line matching
between a reported candidate and an annotated bug point is now ruled out empirically** — it
loses one bug point and four traps on 019 alone, 2% of recall and 10.5% of trap rejection, in
the direction that makes a tool look worse than it is. [[Open Questions]] updated: a window
around the nearest access to the named variable absorbs this and the `svp_simple_001_001`
`<R#63>` off-by-one; only the width is left to decide.

Also recorded: **five cases annotate a global while the annotated line reaches it through a
pointer or parameter** — 009, 011, 012, 024, 025. Not defects; the set of cases that *require*
alias reasoning, which is worth knowing before any name-based matching.

**Ownership overlap to reconcile with Track A.** The canonical ground-truth parser is Track A's
W2 deliverable and must stay so — it owns the counting unit and the match rule, neither of which
this reader defines. When it lands, the two counts must be reconciled and this one should lose
its independent count. Track B also could not use `tests/conftest.py` or `cli.py`, both of which
hardcode an absolute path into Track A's checkout; `annotations.locate_suite()` looks in the
documented `../racebench` and honours `IRQRACE_RACEBENCH`. Track A's files were not touched from
this branch.

State: 163 passing (65 skipped, needing the toolchain), of which 122 are Track B. Fixtures still
2/20 — the reader was the prerequisite, and building the remaining 18 is next.

## [2026-09-26] build | Track B — the 20 fixtures exist; W1 complete except the probe

[[Roadmap]] W1's fixture set is done: **10 bug points and 10 traps**, across 11 subjects,
spanning all four access patterns the suite uses. The feasibility probe is one command away and
is not run only because this machine has no API credentials.

**Generated, but the analysis in them is hand-written.** `llm/fixture_specs.py` carries, per
fixture, the masking state at each access and across the interval, whether the remote flow can
preempt, and the reasoning; `llm/fixture_builder.py` takes the rest from the source. That keeps
the Roadmap's intent — hand-building is how schema gaps are found — while removing the part
that is transcription. `scripts/build-fixtures.py --check` fails if the files are stale.

Selection is by coverage rather than convenience, which the annotation reader made possible:
interrupt nesting (ISR preempts ISR), pointer aliasing, function-pointer dispatch with
three-frame call paths, arrays, multi-line expressions, and **six adversarial pairs** — one
subject contributing a bug point and a trap that differ in exactly one fact.
`svp_simple_003_001`'s pair shares variable, flows, local accesses *and masking*, parting only
on whether the remote write sits in a reachable branch.

**Traps come in more shapes than the design anticipated.** Only two of the ten are the "critical
section covers the interval" shape the D#1 table leads with. The rest are unreachable guards
(three), disjoint array elements (two), a pointer the remote flow reassigned before reading, a
ternary that evaluates one of its two textual occurrences, and a loop body whose guard is
satisfiable exactly once. That last one is the sharpest thing in the set: it has the same shape
as D#1 row 5, *"the same statement inside a loop as both A1 and A2"*, which the table calls a
valid triple — and `svp_simple_006_001`'s guard `(i + j) == 6 && i < j` has one solution over
`i, j` in `[0, 5)`, so the statement executes once. A prompt that applies the rule by shape
fails it. [[LLM Stage Design]]'s D#1 table should gain a row for this.

**Three defects found by strengthening one test.** The label-leak test — the record must not
carry the answer — caught, in order: my own provenance entry naming the annotation's section;
my note explaining *why* `svp_simple_016_001` bug point 3 was chosen over bug point 1; and then
**Track A's `contracts/examples/c2-trap.json`, whose provenance says "This is the planted-trap
shape: ONE critical section covering the whole interval."** A real stage 2 does not know whether
a candidate is annotated, so any record saying so is not indistinguishable from emitter output —
and rendered into a prompt it hands the model the verdict. Track A's file was not touched; the
two `svp_simple_001_001` candidates are now generated from their annotations like the rest, so
the fixture set no longer depends on it. **Pedro should fix that example.**

**A silent-success hole in the recall gate, reached in practice.** Running the ablation with no
SDK installed excluded all 20 candidates, scored the empty set, and exited **0** — recall over
nothing is 1.0. `Score.gate_passed` now requires that bug points were actually scored, and the
runner treats a row that measured nothing as a failure. This is the failure mode the whole
decision policy exists to prevent, and it was in our own harness.

Also: `scripts/run-ablation.py` runs one row or all five and prints recall, trap rejection,
Inspection Ratio, consistency and cost, with the backend's caveats beside them. A candidate the
backend refuses is excluded and reported, never scored.

State: 168 passing (65 skipped, needing the toolchain). W1 for Track B is complete bar the
probe; the go/no-go needs `ANTHROPIC_API_KEY`, or any OpenAI-compatible endpoint, or a local
model through Ollama — the backend seam means the probe can run on whichever is cheapest.

## [2026-09-26] build | Track B — repair stage, majority voting, IRIS grouping, C4 distribution

Everything buildable without model access is now built. [[Roadmap]] W6 and W7 have code; W1–W6
still have **no measured numbers**, and will not until a backend exists.

**W7 — repair.** `llm/repair.py`, with the witness required and stated *before* the patch:
firing flow, preemption point, access order, and the state that differs from every serial
execution. [[SAST-Genius (paper)]]'s reusable idea is that an artifact can be checked where a
verdict cannot, and `witness_problems()` checks it mechanically against the record — the named
flow must exist, must be the one the analysis says preempts, and the order must put the remote
access between the local pair. The vocabulary is a closed enum, so a model reaching for a mutex
cannot express it; there is no second thread to block and an ISR cannot wait.

**Logic Rate is scored on effect, not text** — strategy, interrupts masked, region covered —
because two correct patches can be written differently and a diff comparison would score
formatting. Coverage compares as "at least", since widening beyond the interval is conservative;
it is `latency_note` that has to justify the widening. `mask_interval` and `extend_section` are
accepted for one another.

**Ten hand-written reference fixes** in `llm/repair_references.py`, each carrying its reasoning
and, where there is one, the plausible wrong answer. Three are worth naming:

- `svp_simple_001_001` — masking irq 2 is a **no-op**: it is already masked at line 28, and the
  defect exists because isr_1 re-enables it from inside the interval. The fix must mask irq 1
  too. The wrong answer looks right and changes nothing.
- `svp_simple_017_001` — A1 and A2 are one statement in two iterations, so the interval is a
  loop iteration, not a point. Masking the annotated line alone protects nothing.
- `svp_simple_029_001` — the accesses are in `GetTmData`/`SetTmData`, which *both* flows call;
  the interval is in the caller. Fixing where the accesses are would mask the ISR's own path and
  leave the read-modify-write interruptible.

`svp_simple_005_001` is the latency case: the correct fix spans the tail of a
`MAX_LENGTH x MAX_LENGTH` loop, so it is right and probably unusable — which is
[[SDRacer (paper)]]'s 2-of-11 overhead finding reproduced in a fixture.

**Syntax Rate returns `None` when no checker can run**, never a pass. Same discipline as the
recall gate: an unmeasured 100% is the failure mode, not the absence of a number.

**W6 — voting, with the tie-break as the design decision.** `vote()` collapses n runs by modal
bucket and resolves ties toward the bucket **earlier in inspection order**. Resolving downward
would reintroduce through the voting layer exactly the recall loss the decision policy forbids
at the verdict layer. The winning run's own explanation is kept rather than a synthesis.

**W6 — [[IRIS (paper)]]'s pruning, inverted.** IRIS asks which element is spurious and removes
every candidate involving it. This design may not remove anything, so
`blocking_element_groups()` uses the same signal the other way: candidates sharing a blocking
element are reported as a group, because a reviewer who checks one has checked all of them.
Inspection Ratio improves, recall is untouched. That is the only pruning the rule permits.

**W4 — the request distribution.** `request_distribution()` reports kind, depth, status,
answered and not-found rates, and **which C4 kinds were never asked for** — a kind nobody
requests is a candidate for removal at the next version bump. A test asserts the declared kind
set still matches the C4 schema, so the "never requested" list cannot be measured against a
stale enum. This is the measurement the Roadmap calls the cheapest experiment in the project,
and the one that decides whether precomputed context is ever needed.

**Cost of the blocker, now quantified.** Measuring the rendered prompts: the W1 probe is 10
requests and the full five-row ablation 240. At Anthropic list prices the probe is **$0.35** on
Opus 5 and the whole ablation **$10.25** ($2.05 on Haiku 4.5). The Roadmap's >$30-by-W5 trigger
was well calibrated: n=3 voting across all five rows lands at ~$31, exactly on it, and the
mitigation it prescribes puts the run at ~$17. The blocker was never cost or hardware — there is
simply no key, and it has held M1 since 11 September.

State: 202 passing (65 skipped, needing the toolchain). Nothing measured.

## [2026-09-26] build | Track B — first live run; three interoperability defects in the adapter

A Groq key arrived, so the harness met a real endpoint for the first time. It found three
defects in ten minutes that no amount of fake-backend testing would have found. All three are
fixed with tests; all three are worth recording because each looked like a different problem
than it was.

**1. No User-Agent — read as an auth failure.** `urllib` sends `Python-urllib/3.x` when the
caller sets nothing, and that string is on CDN block lists: Groq's edge answered **403 with
Cloudflare error 1010** while accepting the byte-identical request from curl. Diagnosing it
needed a curl comparison with a spoofed UA, because the status code points at credentials. The
adapter now names itself. Every HTTP client should.

**2. The cache key was not a legal filename.** Backend specs legitimately contain path
characters — `openai:openai/gpt-oss-120b` has both a colon and a slash — and the key went
straight into a filename. On Windows the slash silently became a directory and the colon an
invalid argument. Slugged now, **plus a hash of the original spec**, because two specs can slug
alike and a cache collision would serve one model's verdict as another's. Only visible with a
real model id; the fake backend's `fake:v1` is filename-safe, which is exactly why the bug
survived 200 tests.

**3. No retry on 429, so a rate limit looked like a wall of failures.** Groq's free tier meters
**8,000 tokens per minute** and one context record costs 3,400–5,200, so the run hit the limit
after two candidates and reported eighteen exclusions. Nothing was wrong; the harness was
impatient. Backoff now reads the delay from `retry-after`, else from the provider's message
("try again in 25.5s"), else a fallback — **plus one second**, because waiting the exact stated
time lands on the boundary and is refused again. Capped, so an exhausted quota ends a run
rather than hanging it.

The last one has a measurement consequence worth stating before any number is quoted: at ~2
candidates per minute a single 20-fixture row takes about ten minutes on this tier, and the
five-row ablation would take hours. Groq answers the go/no-go; it is not where M3 gets measured.

Note also that this endpoint does not honour `response_format: json_schema` — the adapter
latches to `prompted_json` and every verdict records that it did. A row served that way is not
comparable with one served by an enforced schema, which is why `structured_mode` is on the
record rather than in a footnote.

## [2026-09-26] result | M1 — the feasibility probe answered: GO

The [[Roadmap]] W1 go/no-go, fifteen days late and answered. **Positive.**

**Setup.** 20 fixtures (10 annotated bug points, 10 planted traps), `openai/gpt-oss-120b` via
Groq, 2026-09-26. The **simple-prompt baseline** — no domain rules, no progressive prompting,
no decomposition, no self-validation. Output was schema-enforced (`native_schema`), so this
number carries no structured-output caveat. 17 requests, 57,199 in / 13,014 out, 483s wall
(rate-limited, not compute).

| | |
| --- | --- |
| **recall gate** | **PASS — 9/9 bug points survived triage** |
| trap rejection | 80.0% (8/10) |
| Inspection Ratio | 63.2% |
| protocol violations | 4/19 |

**What this settles.** ``wiki/LLM Stage Design.md``'s stated risk was that *nothing in the LLM
branch has been tested on concurrency* and that triage quality varies 30 precision points
between two merely *sequential* bug types, so nothing should be assumed to transfer. At this
integration point it does transfer, and the baseline is already at the ceiling on recall.

The adversarial pairs are the part worth believing, because they cannot be passed by shape:

- `svp_simple_017_001` (same statement in a loop, **valid** triple) → `likely_real`, and
  `svp_simple_006_001` (same shape, guard satisfiable **once**) → `likely_infeasible`. The
  model separated them **without the D#1 rule in the prompt** — the baseline row does not
  include `domain_rules.md`, and that distinction was only added to the table after the fixture
  work found it.
- `svp_simple_001_001`: bug point with the interval punctured by `isr_1` → `likely_real`;
  trap with the section intact → `likely_infeasible`.
- `svp_simple_003_001`: one bug point and two traps, the traps differing from it only in
  masking and in branch reachability. All three correct.

**Three qualifications, none fatal.**

1. **Two real bug points landed in `likely_benign`** (003, 005), and the model was right to:
   those cases read into dead locals. That is the harmfulness-criterion conflict recorded above
   and in [[LLM Stage Design]] — a specification problem, not a model failure, and it makes the
   recall gate's wording inadequate as it stands.
2. **The one genuine false positive is the hardest trap in the set.** `svp_simple_029_001`'s
   trap → `likely_real`: the model missed that lines 73 and 74 pass `tm_para` and `tm_para + 1`,
   so the two reads at line 80 touch elements 36 and 37. Interprocedural **call-site
   sensitivity** is where the baseline fails, and it is precisely what progressive prompting
   should fix — the model could have asked for the call paths. That makes it a prediction the
   ablation can test rather than only a defect.
3. **One candidate was excluded, not scored.** `svp_simple_009_001`'s bug point failed JSON
   generation: the model emitted `"confidence": 0. nine`. Schema enforcement caught it; the
   harness reported the exclusion instead of scoring it. Recall is therefore 9/9, not 10/10.

**The headroom problem, stated before the ablation runs.** [[LLift (paper)]]'s ablation moves
recall 0.15 → 1.00; ours starts at 1.00. There is nothing for the remaining four rows to
improve on the headline metric, so **the ablation's dependent variable has to be Inspection
Ratio and trap rejection, not recall**. A flat recall column is a result and should be reported
as one: it says that at this integration point, with a 2026 model and a decision policy that is
conservative by construction, prompt architecture matters less than LLift measured. The 63.2%
Inspection Ratio and the 029 miss are where the rows can move.

**Two more harness defects, both found by real data.** The IRIS-style grouping produced **zero
groups**: blocking elements are free text, and "A1 write is dead code (guard i == MAX_LENGTH + 1
is unsatisfiable)" and "A2 write is dead code because its guard is unsatisfiable" are the same
reason in different words. Propagation needs a constrained `blocking_element_kind` alongside the
prose; not changed mid-experiment, since altering the response schema would make the rows
incomparable. And the cache key covered the prompt assets but **not the response schema** —
adding a field to the verdict changes the experiment as much as editing a prompt does, and a
stale hit would have hidden it. Fixed, with a test.

State: 221 passing. First measured numbers in the project.
