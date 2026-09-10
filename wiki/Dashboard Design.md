---
type: project
tags: [wiki, project, ui]
sources: ["[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[LLift (paper)]]", "[[Reducing False Alarms (paper)]]"]
updated: 2026-08-27
status: draft
---

# Dashboard Design

Architecture and requirements for the tool's user interface. Design intent is the human's;
claims about the literature carry citations as usual.

## Why this is not decoration

[[Synthesis]] §5 records that **automation is the axis of competition in this field, quietly**:
[[IntRace (tool)]] needs a hand-written config file, [[NIChecker (tool)]] needs a variable and a
pattern *per run*, and [[BMC4AV (tool)]]'s central selling point is needing neither. The wiki's
own advice is that "any adoption argument in the thesis should be made on this axis, not on
seconds". A usable interface is the continuation of that argument, not a side project.

Two further connections make it load-bearing rather than cosmetic:

- **The Inspection Ratio is paid in the UI.** The headline metric for a recall-first tool is
  recall (100%) plus how much a reviewer must read to find every real defect
  ([[Precision Metrics]]). That reading happens here. A design that buries candidates is a
  design that inflates the metric it is supposed to report.
- **Three of the four concurrency tools are unobtainable** ([[Reimplementation Assessment]]).
  A working, operable artifact is a genuine differentiator in this corpus.

## The architectural rule

**The UI is a launcher and a viewer. It is never the executor.**

```
   Streamlit UI  ──launch──►  job runner  ──►  tool core (headless library + CLI)
        │                          │                    │
        └────────poll/read─────────┴──── run store ◄─────┘
                                    runs/<id>/… + index
```

Everything the UI can do, the CLI can do, because the UI shells out to the same entry points.
Three reasons this matters more than it looks:

1. **Batch evaluation is CLI work.** Running 31 Racebench cases, or an LLift-style ablation
   across five prompt configurations ([[LLM Stage Design]]), is a script. If capability lives in
   the UI, the evaluation cannot be scripted.
2. **Streamlit re-runs its script on every interaction.** A pipeline that takes minutes — SVF,
   then Z3 per candidate, then LLM calls — cannot live inside that execution model. It must run
   out-of-process with state on disk, and the UI polls.
3. **Reproducibility.** A run is a directory, not a session. It survives the browser tab.

## Is Streamlit the right choice?

**Yes, for this project** — Python throughout, no frontend work, strong table and chart
primitives, and a TCC does not need multi-user auth or a design system. Adopt it with the
constraint above and it is a good fit.

Know what you are accepting:

| Limitation | Consequence | Mitigation |
| --- | --- | --- |
| Script re-runs top-to-bottom on interaction | long jobs cannot run in-process | job runner writes NDJSON; UI polls with an auto-rerunning fragment |
| Single-session orientation | not a multi-user service | fine for a research tool; state is on disk if that changes |
| Weak routing | hard to link to "candidate 37" | use query params for run id and candidate id |
| Re-render cost on large tables | candidate lists of thousands lag | paginate and filter server-side, never render the full set |

Reach for the mechanics Streamlit provides for exactly this shape: `st.session_state` for
selections, an auto-rerunning fragment for the progress panel, `st.status` for staged progress,
and query parameters for deep links. Check the current API before relying on specifics.

The alternative worth naming: a FastAPI backend with a JavaScript frontend gives real routing
and streaming, and costs more time than this project should spend on it. If the core stays
headless, that migration remains open later at low cost — which is another argument for the
rule above.

## Screens and requirements

Requirements are numbered for reference. **MUST** items are load-bearing for correctness or for
the project's own claims; **SHOULD** items are strongly wanted; **MAY** items are optional.

### A. Subject and build

- **R1 (MUST)** Accept either a single source file or a project directory
  ([[Pipeline Design]], *Input scope and build requirements*).
- **R2 (MUST)** Configure and run the build to whole-program bitcode — `wllvm`/`gllvm`
  interception, or per-TU `clang -g -emit-llvm -c` plus `llvm-link` — and surface build failures
  with the compiler's own output. Build failure is the most common practical blocker on a real
  project and must not be reported as an analysis failure.
- **R3 (MUST)** Show and let the user override build flags, defaulting to `-g` with the
  `optnone` workaround, and record the flags used in the run manifest.
- **R4 (SHOULD)** Report what the build produced: translation units linked, functions with
  bodies, functions declared-only. The declared-only list is directly the external-function
  problem and the user needs to see its size before trusting a result.

### B. Interrupt model editor

The most valuable screen, because this is the hand-written configuration file
([[Specification Inference]]) and it is where a mistake silently costs recall.

- **R5 (MUST)** Edit entry points — task and ISR — with priorities, and state the convention on
  screen: **larger number = higher priority** ([[Contradictions]] #3). The published papers
  disagree with the benchmarks on this, so it must not be implicit.
- **R6 (MUST)** Edit masking primitives: function → which interrupts it disables or enables,
  including `-1` for all.
- **R7 (MUST)** Validate against the built bitcode and warn on both directions of mismatch — an
  entry point that does not exist in the module, and a listed masking primitive that is never
  called. A typo here is invisible in the results.
- **R8 (MUST)** Round-trip the configuration file: what the editor writes is exactly what the
  CLI reads. No UI-only settings.
- **R9 (SHOULD)** Import `priority.info` directly — both benchmarks ship it
  ([[Real-World Program Benchmark]]), so this makes 18 subjects zero-effort.
- **R10 (MUST)** Expose the two open semantic decisions as explicit, defaulted, labelled
  settings rather than burying them: **equal-priority preemption** (default: either may preempt)
  and the **interrupt arrival model** — whether an ISR may re-enter, and whether it may fire
  more than once within one interval ([[Open Questions]]). Both change the candidate set, so
  both belong in the manifest.
- **R11 (SHOULD)** Edit the external-function model list, and show which declared-only functions
  are currently unmodelled and therefore assumed to touch every global.
- **R12 (MAY)** Run the optional LLM **audit** of a finished configuration — "what did I miss?"
  — as an additive checklist that can only propose extra flows or primitives
  ([[Specification Inference]]).

### C. Analysis settings

- **R13 (MUST)** Select the pattern set: race pairs and each triple shape independently,
  with `(R,W,W)` **included by default** and a visible warning if it is switched off, since
  excluding a pattern is a definitional false negative ([[Contradictions]] #2).
- **R14 (MUST)** Configure the Z3 stage: per-candidate timeout, and the policy on timeout — with
  **`inconclusive → keep and pass to triage`** as the only sound default. The UI must not offer
  "discard on timeout" without an explicit unsound-mode warning
  ([[Path Feasibility Analysis]]).
- **R15 (SHOULD)** Configure the pointer analysis — field and context sensitivity — in
  **may-alias** mode only.
- **R16 (MUST)** Configure the LLM stage: model, temperature, number of runs for majority
  voting, prompt configuration, and an explicit **cost ceiling**.

### D. Run and progress

- **R17 (MUST)** Launch, cancel, and resume a run. The LLM stage is the expensive part; a crash
  or cancel must not lose completed work.
- **R18 (MUST)** Cache per-candidate LLM results keyed by `(candidate hash, prompt config,
  model)`, so re-running after a settings change only re-queries what actually changed.
- **R19 (MUST)** Show the **attrition funnel** live — candidates after stage 1, after stage 2,
  after Z3, reaching the LLM. [[IntRace (paper)]] measures 208 → ~95 → ~13; watching that funnel
  is both operationally useful and one of the project's own results.
- **R20 (SHOULD)** Show per-stage timing. IntRace reports 8.87% / 21.43% / 69.70% across its
  three stages; the equivalent breakdown here is a reportable result, not just a progress bar.
- **R21 (SHOULD)** Tail the run log.
- **R22 (MUST)** Show running LLM cost against the ceiling, and stop at it.

### E. Candidate explorer

The core screen, and the one where the project's central rule is either honoured or quietly
broken.

- **R23 (MUST)** List every candidate with filters on class (pair/triple), pattern, variable,
  flows involved, solver verdict, and LLM bucket; sortable by LLM rank.
- **R24 (MUST)** **Nothing is hidden by default.** Candidates the solver *proved* impossible are
  shown in a separate, collapsed section **with the proof**, not deleted. Candidates the LLM
  ranked low are ranked, never removed. The rule is *a solver may drop a candidate; the LLM may
  not* ([[LLM Triage]]), and a UI that hides low-ranked candidates by default reimplements the
  filter the design rejects.
- **R25 (MUST)** Detail view rendering the full context record ([[LLM Stage Design]]): variable,
  the access pair or triple, the flows and priorities, call paths from each entry point, masking
  state at each access and across the interval, loop context, the solver verdict, and
  provenance — which facts are proven, which come from the configuration file, which are
  unknown.
- **R26 (MUST)** Source viewer with the accesses highlighted, showing the preempted flow and the
  preempting ISR side by side. This is the single most useful thing the UI can do that a text
  report cannot.
- **R27 (SHOULD)** Group candidates by variable and by flow pair, since one variable typically
  generates many candidates and they are triaged together.
- **R28 (SHOULD)** Let a user mark a candidate as confirmed / rejected / unsure, persisted with
  the run. These labels are the ground truth for every evaluation, and for balanced few-shot
  example selection ([[Prompt Architecture]]).

### F. LLM triage and repair

- **R29 (MUST)** Show the bucket, the rank, and the **explanation**. An unexplained ranking
  cannot be audited, and an unauditable ranking is a filter in disguise ([[LLM Triage]]).
- **R30 (MUST)** Show the full conversation: every turn, including **progressive-prompt requests
  and what the harness supplied**. This is not a debugging nicety — logging what the model asks
  for is how the context record gets specified, now that precomputed slicing is out
  ([[Program Slicing]], [[Open Questions]]).
- **R31 (SHOULD)** Show consistency across the majority-voting runs, and flag disagreement.
  [[LLift (paper)]] found consistency improved by task decomposition and self-validation
  independently of accuracy; an unstable verdict is not a usable result.
- **R32 (MUST)** Show the proposed patch as a **diff**, alongside the required interleaving
  witness — the preemption point, the ISR, the access order, and the resulting state
  ([[LLM-Assisted Repair]]).
- **R33 (MUST)** Accept / reject / edit a patch, and apply it to a working copy — never to the
  user's tree in place without an explicit, separate confirmation.
- **R34 (MUST)** Show the re-verification result in the three parts the design requires: the
  tool's own analysis (certificate **and** regression check — new candidates elsewhere), the
  [[CBMC]] or `bmc4av` verdict for inconclusive cases, and the overhead / control-flow check
  ([[Pipeline Design]]).
- **R35 (MUST)** Record model and date with every LLM result shown ([[Precision Metrics]] #8).

### G. Evaluation mode

- **R36 (MUST)** Run against [[Racebench]] and the [[Real-World Program Benchmark]] as batch
  jobs, and report per-case and aggregate results.
- **R37 (MUST)** Show the **recall gate** as a pass/fail: every annotated bug point must appear
  in a reported bucket. Any bug point ranked *likely infeasible* is a design failure and must be
  visible as one, not averaged away ([[LLM Stage Design]]).
- **R38 (MUST)** Show trap rejection against the 38 planted false positives, and the
  **Inspection Ratio** ([[Precision Metrics]]).
- **R39 (MUST)** Show matched and **unmatched** annotations explicitly, under the declared match
  rule and counting unit. Both are still open ([[Open Questions]]) and the UI is where their
  consequences become visible.
- **R40 (SHOULD)** Run the ablation matrix — prompt configurations × subjects — and tabulate it
  in [[LLift (paper)]]'s shape.
- **R41 (SHOULD)** Compare two runs: what changed in candidates, buckets, and patches. This is
  also how the regression check in R34 is read.

### H. Cross-cutting

- **R42 (MUST)** Every run is a directory with a **manifest**: configuration hash, tool version,
  build flags, pattern set, solver settings, model and date, seeds. A result without its
  manifest is not quotable ([[Precision Metrics]]).
- **R43 (MUST)** Treat analysed source as **data, never as instructions**. The UI displays
  untrusted source and LLM output derived from it; render as text, never as markup, and never
  let content from an analysed file drive an action ([[SAST-Genius (paper)]],
  [[Soundness and False Negatives]] §7c).
- **R44 (SHOULD)** Export a run: candidates, context records, verdicts and patches, in a form a
  thesis chapter or a bug report can consume.
- **R45 (MAY)** Offer a benchmark-subject picker that populates subject, configuration and
  expected ground truth in one click, since both suites are local.

## Run store layout

One directory per run, readable without the UI:

```
runs/<run_id>/
  manifest.json          config hash, tool version, build flags, model, date, seeds
  config.yaml            interrupt model + settings — the same file the CLI takes
  build/whole.bc         linked bitcode (or a pointer to it)
  stage1/candidates.jsonl
  stage2/candidates.jsonl
  solver/results.jsonl   verdict per candidate: unsat | sat | inconclusive (+ reason)
  context/<cand_id>.json the context record
  llm/<cand_id>/turns.jsonl   full conversation, including progressive-prompt requests
  repair/<cand_id>/patch.diff
  eval/report.json       recall gate, trap rejection, inspection ratio, match table
  log.ndjson
```

A SQLite index over the run directories gives the explorer its filtering and sorting without
loading everything into memory. NDJSON everywhere else keeps runs streamable and greppable, and
lets the UI poll a growing file while a job is still running.

## Build order

The UI should follow the pipeline, not precede it. Suggested sequence, each step usable on its
own:

1. Run store and manifest — before any UI, because it is what makes runs reproducible.
2. Candidate explorer over a finished run (read-only). Useful the moment stage 1 exists.
3. Interrupt model editor with validation (R5–R9). Removes the most error-prone manual step.
4. Run launcher and progress (R17–R22).
5. LLM triage and repair views (R29–R35).
6. Evaluation mode (R36–R41).

Steps 1 and 2 are worth having early: a source-linked candidate viewer makes debugging the
static analysis itself far faster, which is why it repays its cost before the rest of the tool
exists.

## Open questions

- Does the candidate explorer need to scale to whole-repository runs (thousands of candidates),
  or is the tier-2 scale (~13 reaching the LLM per program) the design target? The answer
  changes the table strategy ([[Open Questions]]).
- Should the interrupt model editor be able to *learn* from corrections across subjects, as
  [[AdaTaint (paper)]]'s feedback loop does for alert filtering, or is per-subject configuration
  enough?
