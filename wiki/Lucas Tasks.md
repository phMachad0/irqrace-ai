---
type: project
tags: [wiki, project, tasks]
sources: ["[[Reported Results Across Papers]]", "[[Racebench]]", "[[Racebench Full Run 2026-10-28]]", "[[Precision Metrics]]", "[[NASAC 2019 Prototype Competition]]", "[[Contradictions]]"]
updated: 2026-11-12
status: draft
---

# Lucas Tasks — TCC backlog after the Roadmap

The [[Roadmap]]'s ten weeks ended on 6 Nov. This page holds what is left for the TCC on Lucas's
side, one section per task, numbered in the order they were set. **This page records the
human's direction, not findings.** Wherever it quotes a number about a tool or a paper, the
number cites its source. Earlier context: [[Thesis Goal]], [[LLM Stage Design]], [[Semana 8 — Integração das Trilhas A e B]].

| # | Task | Set | State |
| --- | --- | --- | --- |
| T1 | [[#T1 — Three-way comparison on Racebench]] | 2026-11-12 | planned |
| T2 | [[#T2 — Racebench 2.2, a ground truth extended with the unannotated bugs]] | 2026-11-12 | planned |
| T3 | [[#T3 — Comparative analysis of the prompts]] | 2026-11-12 | selector narrowed; variants designed, not built |
| T4 | [[#T4 — Consolidate the results into the monograph]] | 2026-11-12 | planned; depends on T1–T3 |

## Execution plan (approved 2026-11-12)

**Decisions:**
1. PR #18 merges first, and every new branch starts from `main` (`tcc/<task>-<topic>`).
2. Agents commit, push and open PRs. **Lucas always merges.**
3. Measurements use `claude-cli:sonnet`, with **n = 3 independent runs** per prompt.
4. In T2, **a human adjudicates**; agents only prepare blind dossiers, with no LLM verdict.

**Git rules:** never `Co-Authored-By` or any other Claude attribution, never commit to `main`, never
force-push, never touch `../racebench`. Any change to the vendored suite goes with a `VENDORED.md`
entry.

**Agents:** the main session runs the LLM batches itself, in series, because there is one
subscription rate limit. Code agents work in their own worktrees:
- A, measurement: `tcc/m1-measurement`;
- B, prompt variants: `tcc/t3-prompt-variants`;
- C, Racebench 2.2 preparation: `tcc/t2-racebench-2.2`;
- D, monograph: `tcc/t4-monografia`.

**Facts found while planning:**
- `llm triage --samples N` is majority voting (`"votes": samples`), not independent runs.
- `triage_store` writes into the run.
- So each (prompt, run) pair triages its own copy of one frozen static run.
- The static toolchain runs in WSL (`irqrace-wsl.cmd`).

| Milestone | Delivers | Gate: Lucas confirms before moving on |
| --- | --- | --- |
| **M0** | pending work committed into PR #18; in WSL, the test suite passes and `stage3-all` gives 53/53 and the 316 → 202 → 166 funnel | Do the funnel and the recall gate match 2026-10-28? Which `main` commit is frozen? |
| **M1** | the scorer extended (per pattern, case subsets, N runs with mean ± spread and κ, CSV and manifest); the S0 dataset; `+racebench` and `+racebench+c4` × 3 runs on one frozen static run | Which baseline wins and becomes S2? Is `likely_real` the headline? Does the ±3-point noise hold? |
| **M2** | T1: one table per baseline on its own terms, plus S0/S1/S2 on 53/33; a comparison page | Does the per-baseline framing convince? How do we present NIChecker's 54? Do we look for the artifacts to re-run BMC4AV? |
| **M3** | T3: the variants built (gate **M3a** before measuring: the wording, and which variants to run), then measured × 3 with a paired report | Does any variant beat the noise without losing a bug? Does it become the screen's default? |
| **M4** | T2: the equivalence rule, the witness template and blind dossiers (gate **M4a** before adjudicating), then the human adjudication, the 2.2 labels applied, and S1/S2 re-scored next to 2.1 | The final name, and whether to send it upstream (decided separately) |
| **M5** | T4: outdated passages fixed, the method, figures F1–F11 from versioned CSVs, results, `make final` | PDF review; the abstract's headline number; whether the original ablation is re-run |

Order: M0 → M1. After M1, M2, M3 and M4 depend on its runs. Agents B, C and D start their code
while M1 runs, and the results in M5 come after M2–M4.

---

## T1 — Three-way comparison on Racebench

**Direction (2026-11-12):** collect data from the tool to compare three systems on [[Racebench]],
using metrics that show each one's performance against the others:

| | System | What is "reported" |
| --- | --- | --- |
| **S0** | **Published results** — what the authors of the existing tools report on Racebench ([[NIChecker (tool)]], [[BMC4AV (tool)]], [[IntRace (tool)]], plus the baselines they quote) | whatever each paper reports |
| **S1** | **Our static analysis alone** — stages 1→3 ([[Pipeline Design]]) | every candidate that reaches the LLM |
| **S2** | **Ours + LLM triage** — S1 plus [[LLM Triage]] | the `likely_real` bucket (headline), with the other readings alongside |

### The central difficulty: S0 is not one number

The three columns cannot simply be placed side by side, because the papers do not agree on what
Racebench contains ([[Precision Metrics]] §"Why the numbers do not compose", [[Racebench]]
§"Reconciling the papers' counts"):

| Paper | Cases | Ground truth it assumes | Defect class |
| --- | --- | --- | --- |
| [[NIChecker (paper)]] | 31 | 54 violations — 6 more than the annotations, still unexplained | atomicity violation |
| [[BMC4AV (paper)]] | 25 (drops six `(R,W,W)`-only cases) | 38 — the annotations minus `(R,W,W)` | atomicity violation |
| [[IntRace (paper)]] | 30 (one case dropped) | 50 | data race |
| suite annotations | 31 | **53 bug points / 33 traps** since the 2026-10-28 relabel; **48 / 38** before | annotated triples |

Also: no paper scored against the relabelled 53/33, several S0 numbers are copied from other
papers rather than re-run ([[Reported Results Across Papers]]), and each was run on different
hardware. Measured against the annotations, BMC4AV's own "38/38" becomes 38 of 48 (79.2%)
([[Racebench]] §"BMC4AV's 38 is fully traceable"; [[Contradictions]] #2).

**So the comparison is done *on each paper's own terms*.** For each baseline, restrict S1 and S2
to that paper's case subset and ground-truth definition, then compare there. A row such as
"S2 vs BMC4AV on BMC4AV's 25 cases, `(R,W,W)` excluded, 48/38 labels" is like for like. A
single grand table mixing 54, 50, 38 and 53 is not. The thesis can then show one table per
baseline, plus one table of our own systems on the full suite.

### Metrics

Primary metrics come first. A metric is listed only if it can be computed for at least two of
the three systems, or if it is needed to read the ones that can.

| Metric | Definition | S0 | S1 | S2 | Why |
| --- | --- | --- | --- | --- | --- |
| **Recall** (hit rate) | bug points detected / bug points | from the paper, re-based where possible | ✓ | ✓ | the project's first-order metric ([[Thesis Goal]]) |
| **Recall per pattern** | the same, split by `RWR` / `WWR` / `WRW` / `RWW` | BMC4AV gives a per-pattern breakdown | ✓ | ✓ | shows *where* each system loses recall; BMC4AV loses all of `RWW` |
| **Traps reported** | planted false-positive markers reported / traps | from the paper (as FP) | ✓ | ✓ | trap avoidance on adversarial code ([[Precision Metrics]] item 5) |
| **Precision** | TP / (TP + traps reported) | ✓ | ✓ | ✓ | the number the field quotes; only reported next to recall |
| **NASAC score** | +2 per bug point, −3 per trap, out of the maximum | derivable only with per-case output | ✓ | ✓ | the benchmark's own scoring ([[NASAC 2019 Prototype Competition]]) |
| **Warnings (#WN)** | everything reported, unannotated candidates included | when reported | ✓ | ✓ | what a reviewer faces. Unannotated candidates are **not** false positives (direction 2026-10-28) |
| **Inspection Ratio** | share of candidates a reviewer reads before reaching every bug point | — (no ranking) | ✓ (record order) | ✓ (triage order) | the effort metric that cannot be improved by dropping candidates ([[Precision Metrics]]) |
| **Runtime** | static time, LLM time, wall clock | self-reported, other hardware | ✓ | ✓ | always shown with the hardware column |
| **LLM cost** | calls, tokens, calls per candidate | — | — | ✓ | what S2's gain costs |
| **Run-to-run variance** | spread over *n* samples; Cohen's κ between runs | — | deterministic | ✓ | a single S2 sample carries about ±3 points ([[Racebench Full Run 2026-10-28]], third run) |
| **Trap disposition** | for each trap: never generated / stage 2 / solver `unsat` / LLM infeasible / reported | — | ✓ | ✓ | shows *which stage* earns each rejection, and that the static stages drop with proofs only |

S2 is reported under its three readings, as in [[Racebench Full Run 2026-10-28]]:
`likely_real` (headline), "not called infeasible", and "everything reaching the LLM" (which is
S1). This is because the LLM ranks and never drops ([[LLM Triage]]). For the same reason, any
bug point S2 calls infeasible is reported as a recall loss *of the triage*, by name, even if the
score goes up.

### Numbers already on file (to be re-run, not quoted)

These come from 2026-10-28 runs on Track B commit `f93b5bd`. The code has changed since then
(issues #8–#17, Z3 rlimit, debug-info names, `domain_rules.md`), so **they show the shape of the
table, not its final values.**

| Labels | System | Bug points | Traps reported | Score | Source |
| --- | --- | --- | --- | --- | --- |
| 53 / 33 | S1 | 53 / 53 | 11 / 33 | 73 / 106 | [[Racebench Full Run 2026-10-28]], third run |
| 53 / 33 | S2, runs 2 and 3 | 53 / 53 | 3 and 2 / 33 | 97 and 100 / 106 | same |
| 48 / 38 | S1 | 48 / 48 | 16 / 38 | 48 / 96 | same, second run |
| 48 / 38 | S2, run 2 | 48 / 48 | 8 / 38 | 72 / 96 | same |

### Steps

1. **Freeze the configuration.** Choose one commit, one model and one prompt row: production
   `+self-validation`, with `+racebench` as a separately labelled extra row. Record all three
   in the run manifest.
2. **Run S1 + S2 on all 31 simple cases, n ≥ 3 samples, with the LLM cache cleared.** S1 comes
   out of the same run, because it is the "everything reaching the LLM" reading.
3. **Score under both label sets.** Use 53/33 for our own headline. Use 48/38, plus each paper's
   own subset and exclusions, to compare against S0.
4. **Extend `project-src/scripts/bench-triage-report.py`** so that one command produces, from a
   run store: per-system metrics, the per-pattern split, the case-subset filters (`--cases`,
   `--exclude-pattern RWW`), mean ± spread over samples, and a CSV for the thesis figures.
5. **Build S0 as data, not prose.** Put the published numbers in a versioned file under
   `project-src/bench/`, one row per (tool, reported-by, cases, ground truth, metric, value,
   re-run or copied, hardware), taken from [[Reported Results Across Papers]]. Re-base a number
   to the annotations only where the paper or its artifact gives per-case output.
6. **Optional — re-run a baseline.** BMC4AV's full source is a CBMC fork. CLAUDE.md places it
   at `../BMC4AV`, but on 2026-11-12 neither `../BMC4AV` nor `../NIChecker` was found next to
   the vault. If it can be found and built, a re-run on our machine removes both the
   copied-number and the hardware caveats for that row, and it would be the only S0 row with
   that property.
7. **File the result.** Write the tables to `wiki/comparisons/` as their own page, add the
   diary entry, update `index.md` / `log.md`, and add the chapter figure in `monografia/`.

### Decisions still open

- Which S2 reading is the headline. `likely_real` is the default above; "not infeasible" is the
  more conservative alternative.
- Whether the `+racebench` row appears in the thesis comparison at all, or only as a footnote.
  It is benchmark-specific, and it was the source of the one recall loss so far.
- How many samples (3 is the minimum for a spread; 5 if cost allows).
- Whether the two complex cases (`svp_real_001`, `svp_real_002`) join T1. No run of them is on
  file. They are where the competition's 180 s limit and its heavier scoring apply.
- How to present the NIChecker row, given its 54 against the annotations' 48.

---

## T2 — Racebench 2.2, a ground truth extended with the unannotated bugs

**Direction (2026-11-12):** the tool reports candidates that the suite's authors did not annotate
as bugs (or as traps), and on the ones the human has looked at, the tool appears to be right.
The plan is to build a **"Racebench 2.2"**: the 2.1 ground truth plus every unannotated candidate
confirmed as a real defect. The direction is that the AI-assisted pipeline is now strong enough
to find what the original annotation missed.

### What is already known

- The suite never claims its annotations are exhaustive ([[Racebench Full Run 2026-10-28]],
  second run, "Reading"). Under the scoring rule fixed on 2026-10-28, an unannotated detection is
  **not** a false positive. Today these candidates score zero either way.
- **How many there are.** In run 1, 102 unannotated candidates reached the LLM: 38 landed in
  `likely_real` and 64 in `likely_infeasible`. In run 2, without the adjacency rule, 84 landed in
  `likely_real`. That is why the Inspection Ratio rose from 0.56 to 0.72
  ([[Racebench Full Run 2026-10-28]]). Those runs used the 48/38 labels, so the counts move
  slightly under 53/33.
- **There is a precedent.** The [[Racebench#Relabel 2026-10-28|relabel of 2026-10-28]] did
  exactly this for five traps. It read each one against the README's arrival model, found a
  concrete interleaving, changed the vendored source, and recorded the change in `VENDORED.md` and
  `bench/racebench-errata.yaml`. T2 uses the same method, at a larger scale and in the other
  direction: from unlabelled to bug, not from trap to bug.

### Risk 1 — circularity

If the tool proposes the new bugs, and the tool is then scored against a gabarito that contains
them, its recall and precision on 2.2 are inflated by construction. Four rules keep 2.2 usable as
evidence:

1. **The tool proposes; it does not decide.** A candidate becomes a 2.2 bug point only with a
   **concrete interleaving witness**: the line where the interrupt arrives, the masking state
   there, the values that make every guard pass, and the observable change in A1/A2. This is the
   standard the relabel used for 001, 019 and 020. A solver `sat` result is not enough, because
   SAT means "not refuted" ([[Racebench]] §"Two traps are reachable"). The LLM's `likely_real` is
   not enough either ([[LLM Triage]]: a model's judgement does not license a ground-truth change,
   in either direction).
2. **Blind adjudication.** The person who checks a candidate does it from the source and the
   README, without seeing the LLM's verdict or reasoning. Where possible, a second person
   (Pedro) checks a sample independently, and the agreement is reported (Cohen's κ, as in the
   variance study).
3. **Rejected candidates are recorded too.** A candidate judged unreachable, or effect-free like
   022's "可能误报", gets a 2.2 trap entry or an explicit "not a defect" entry with the reason.
   Otherwise 2.2 only ever grows in the tool's favour.
4. **2.1 stays the headline for comparing against other tools.** S0 in [[#T1 — Three-way
   comparison on Racebench|T1]] was scored against 2.1 (or each paper's own reading of it). On 2.2
   the published tools have **no score at all** until someone re-runs them. Our 2.2 numbers are
   reported next to the 2.1 ones, never instead of them.

### Risk 2 — what counts as one bug

Many unannotated candidates are siblings of an annotated bug, not new bugs:

- the same lines with different access kinds (017's loop header writes and reads on line 29);
- coarser or finer triples of the same interleaving (the adjacency question, 017 against 022);
- the same pattern through another ISR, or another activation of the same one.

Before counting, T2 needs a written **equivalence rule** that says when two triples are the same
defect. The rule must be fixed *before* adjudication, and the counts must be reported both as raw
triples and as distinct defects. Without it, "2.2 adds N bugs" depends on how the triples are
split.

### Steps

1. **Freeze the candidate set.** Use the T1 run (same commit, same row), and list every
   unannotated candidate that reaches the LLM, with its bucket. Then choose: adjudicate all of
   them, or adjudicate every `likely_real` one plus a random sample of `likely_infeasible`, to
   measure how many real bugs the LLM buried.
2. **Write the equivalence rule and the witness template** (fields listed in Risk 1), and add
   them to `project-src/docs/evaluation-protocol.md`.
3. **Adjudicate**, one record per candidate, in a versioned file such as
   `project-src/bench/racebench-2.2.yaml`. Each record holds the case, the triple, the verdict
   (bug / trap / not a defect / undecided), the witness or the blocking reason, the adjudicator,
   and the date. "Undecided" stays out of both denominators and is reported as a count.
4. **Apply it to the vendored suite** as its own commit. The new annotations go in a separate
   marker or a sidecar file, so 2.1's labels can still be read unchanged. Record the change in
   `VENDORED.md`. The scorer gets a `--labels 2.1|2.2` switch.
5. **Re-score** S1 and S2 from T1 on 2.2, and report: new bug points (as triples and as distinct
   defects), what fraction of them the static stages generated (should be all, since every
   candidate comes from stage 1), and where the LLM placed them. That last number measures the
   LLM's recall on bugs nobody had labelled, which is a cleaner test than the planted traps.
6. **Write it up**: a `wiki/benchmarks/` section or page for 2.2, an entry in [[Contradictions]]
   for each annotation the suite's authors would dispute, the diary entry, and a monograph section.

### Decisions still open

- **The name.** "2.2" reads like an upstream release by the suite's maintainer. Something like
  `2.2-irqrace` or "Racebench 2.1 + extended labels" avoids implying that the authors endorsed it.
- **Whether to send it upstream** (an issue or PR to `chenruibuaa/racebench`). That is
  outward-facing, so it is a separate decision, made after adjudication.
- **Who adjudicates, and how many candidates** (all of them, or `likely_real` plus a sample).
- **Whether the two complex cases are included**, as in T1.

---

## T3 — Comparative analysis of the prompts

**Direction (2026-11-12):** keep only `+racebench` and `+racebench+c4`, the best rows so far.
Create new variants to test against them, then compare the prompts by how each one changes the
result.

### Done on 2026-11-12

The Racebench screen's prompt selector now offers only those two rows (`BENCH_PROMPTS` in
`project-src/src/irqrace/ui/benchmark_screen.py`; the test in `tests/test_desktop_modes.py`
asserts the list; 25/25 pass). **No row was deleted from `irqrace.llm.prompts`**, for three
reasons:

- both Racebench rows are built *on top of* `+self-validation`
  (`_RACEBENCH = dataclasses.replace(FULL, …)`), so that row cannot go;
- the four ablation rows are the M3 table ([[Roadmap]]), and `ablation-table.py` reads them;
- `+self-validation` / `+c4` are the prompts for real code, which do not carry the benchmark
  semantics.

They stay selectable from the CLI and the Pipeline screen. A variant under test joins
`BENCH_PROMPTS`.

### What is known about the two baselines

| Row | What it is | Measured |
| --- | --- | --- |
| `+racebench` | `+self-validation` + `racebench_semantics.md` (the interleaving is the defect; same location = same storage; the README's arrival model; harm replaced) | all 31 cases, 3 runs on 2026-10-28: 53/53, 0–3 traps, 97–102/106 on 53/33 labels; κ = 0.93 between runs 2 and 3 ([[Racebench Full Run 2026-10-28]]) |
| `+racebench+c4` | the same, plus progressive prompting: the model may ask the resolver for code (C4) | **only 8 cases**, real calls: Sonnet 3/3 bugs with 4 C4 requests, Haiku 4/6 (2 `uncertain` from backend errors) ([[Semana 8 — Integração das Trilhas A e B]] §3.21). **Never run on all 31.** |

So the first comparison is between the two baselines themselves: what C4 adds on the full suite.
Both rows are recent, and the code has changed since 2026-10-28, so `+racebench` is measured
again too.

### Variants to build

Each variant changes **one thing** relative to `+racebench`, so each difference has a single
cause. Each one is a new add-on asset or flag, plus an `EXPERIMENTAL` row and a `ROW_HELP` line.
None of them names a case or an identifier from the suite (the same rule as
`racebench_semantics.md`). Each targets something already measured:

| Row (proposed) | Change | Targets | Expected risk |
| --- | --- | --- | --- |
| `+racebench−selfval` | remove the self-validation checklist | does the checklist still help once harm is replaced? In the 2026-10-26 study it turned `benign` into `uncertain` | more traps accepted |
| `+racebench+witness` | `feasible` requires a concrete witness in the answer (arrival point, mask state there, values that pass every guard, the effect). Without one, the answer is `uncertain` | the 0.85/0.90 confidence clustering; and it produces the witnesses that [[#T2 — Racebench 2.2, a ground truth extended with the unannotated bugs\|T2]] adjudicates | bugs moving from `likely_real` to `uncertain`: a recall cost in the headline bucket |
| `+racebench+location` | B's index or pointer must be evaluated explicitly inside the judged interleaving, as a separate answer field, before feasibility | 007 trap #1, the one unstable model error (flips between samples) | a real candidate's confidence fell from 0.90 to 0.55 when a similar paragraph was tried ([[Triage Study 2026-10-26]] cause 3) |
| `+racebench+effectfree` | a remote write of the value already stored, with the local flow rewriting the location before A2, is not a defect | 022's two "可能误报" items, the last traps still accepted | **this is the adjacency rule's family**, which cost 2 bug points in run 1. It is measured to show its recall cost, not to ship |
| `+racebench+rubric` | confidence on a fixed rubric (what was shown, what was assumed) instead of a free number | the Inspection Ratio: ordering inside a bucket is coarse | none on recall; possibly more calls |

Each variant is built on `+racebench`, and its effect is then checked with C4 on only if
`+racebench+c4` wins the first comparison. That avoids doubling the matrix up front. A
**model** axis (Haiku vs Sonnet) is a different factor, not a prompt: keep it out of this table,
or run it as a separate block.

### Protocol

1. **Freeze the static side.** Run stages 1–4 once on the 31 cases at one commit, then triage
   those *same* context records under every row. Only the prompt then changes between columns.
2. **n ≥ 3 samples per row, cache cleared**, one model, recorded in the manifest.
3. **Metrics, per row** (as in [[#T1 — Three-way comparison on Racebench|T1]]): bug points in
   `likely_real` and "not infeasible" (recall), traps reported, NASAC score, Inspection Ratio,
   unannotated candidates in `likely_real`, `uncertain` count, calls and tokens per candidate,
   C4 requests, and refusals or backend errors.
4. **Paired, per item.** For each labelled item, record the row's verdict next to the baseline's,
   and list every flip by name. With 53 bugs and 33 traps, a difference of about ±3 points is
   within one row's run-to-run noise ([[Racebench Full Run 2026-10-28]]). A variant "wins" only if
   it beats that, or if it removes a named error without losing a bug point.
5. **Recall veto.** A variant that moves any bug point to `likely_infeasible` is reported as a
   recall loss, by name, whatever its score (the adjacency-rule lesson).
6. **Report**: one ablation-style table, rows × metrics, mean ± spread; the flip list; a page in
   `wiki/comparisons/`; the diary entry; and the thesis figure. Extend `ablation-table.py` or
   `bench-triage-report.py` so that one command produces it.

### Decisions still open

- Whether to build all five variants or start with two or three (`+witness` and `+location`
  have the clearest targets).
- Whether the prompt comparison runs before or after [[#T2 — Racebench 2.2, a ground truth extended with the unannotated bugs|T2]]. If after,
  "unannotated in `likely_real`" becomes a scored column.
- The model, and the number of samples (cost: about 300 calls per row per sample on the full
  suite).

---

## T4 — Consolidate the results into the monograph

**Direction (2026-11-12):** once T1–T3 are done, consolidate the data they produced and add it to
the monograph. Explain the method of each experiment, show the results, and include good
comparative charts.

### Where it lands in `monografia/`

The evaluation already has a home: `capitulos/05-desenvolvimento.tex` §"Testes e Avaliação"
(research questions, counting unit, match rule, metrics, protocol, threats). Its results
subsection is still a `\pendente{…}` inside `\ifparcial\else`, so it only shows in `final.tex`.
The method chapter (`03-metodo.tex` §"Avaliação") points to it.

**The chapter is out of date in three places**, and T4 starts by fixing them:

| Where | What it says | Now |
| --- | --- | --- |
| `05-desenvolvimento.tex` table `tab:unidades`; `02-conceitos.tex` l. 140, 365 | 48 bug points / 38 traps | 53 / 33 since the 2026-10-28 relabel. Keep 48/38 as the "as distributed" row, and add the relabel as its own step with its evidence ([[Racebench#Relabel 2026-10-28]]) |
| §"Métricas" | "on Racebench only feasibility enters the metrics"; harm is judged on the real-world suite | the `+racebench` rows replace the harm criterion with the suite's semantics. Say which reading each number uses |
| §"Perguntas de pesquisa" | four questions (static recall, triage, ablation, repair) | T1–T3 add three: comparison with the published tools, the extended ground truth, and the prompt comparison |

### Proposed structure of the results section

One subsection per research question. Each follows the same order: **setup → result (table +
figure) → reading**. The setup states the commit, model, prompt row, samples, labels (2.1, 53/33,
or 2.2) and run store.

1. **QP1 — Static recall.** The recall gate (53/53) and the funnel 316 → 202 → 166, with the
   disposition of each trap by stage. Source: T1, S1.
2. **QP2 — Triage.** S1 vs S2: traps reported, Inspection Ratio, unannotated candidates in
   `likely_real`, variance (κ). Source: T1.
3. **QP3 — Comparison with the literature.** One table per baseline, each on its own terms
   (case subset, ground truth, exclusions), with the copied-number and hardware columns. Source: T1.
4. **QP4 — Prompts.** The original ablation (if it is re-run on the current records), then the
   T3 variants: rows × metrics, mean ± spread, the list of items that flipped. Source: T3.
5. **QP5 — Extended ground truth.** How 2.2 was built (the witness standard, blind adjudication,
   the equivalence rule), what it adds, and how S1/S2 score on it **next to** 2.1. Source: T2.
6. **QP6 — Repair**, and the real-world suite, if they are measured by then; otherwise they move
   to §"Ameaças" and §"Perspectivas de continuidade" as stated gaps.
7. **Threats to validity**, updated: one sample against n samples, the prompt tuned on the suite
   it is scored on (the `+racebench` rows), the circularity of 2.2, the relabel, and hardware.

### Figures

Each one compares something. Each is generated by a script from the data, never drawn by hand,
and carries `\fonte{}` naming the run it came from.

| # | Figure | Shows | Data |
| --- | --- | --- | --- |
| F1 | **Recall × traps reported** scatter: one point per system and per published tool, with the marker showing which ground truth it was scored on | the trade-off the field optimised (precision) against ours (recall) in one image | T1 |
| F2 | **Candidate funnel**, stage by stage, as stacked bars of bug points / traps / unannotated | where the static stages remove traps with proofs, and that no bug point is lost | T1 (S1) |
| F3 | **Trap disposition**: one horizontal bar per trap, coloured by the stage that rejected it (never generated, stage 2, solver, LLM, reported) | which stage earns each rejection | T1 |
| F4 | **Recall per pattern** (`RWR`/`WWR`/`WRW`/`RWW`), grouped bars per system | BMC4AV's `RWW` blind spot against our 100% | T1 |
| F5 | **NASAC score per system**, with error bars over samples, under 2.1 and 2.2 side by side | the headline number and its noise | T1, T2 |
| F6 | **Prompt forest plot**: one row per prompt, mean ± spread for score, traps reported and IR, with a vertical line at the baseline | which variant moves what, and whether it beats the noise | T3 |
| F7 | **Flip heatmap**: labelled items × prompts, cells coloured by bucket | *which* items each prompt changes, with recall losses visible at a glance | T3 |
| F8 | **Cost × score**: LLM calls (or tokens) per candidate against score, one point per prompt | what each point of score costs, and what C4 costs | T3 |
| F9 | **Inspection Ratio per case**, box or strip plot, S1 vs S2 | review effort saved, case by case | T1 |
| F10 | **2.2 composition per case**: 2.1 bugs, new bugs, new traps, "not a defect", undecided | how much the original annotation missed, and where | T2 |
| F11 | **Where the LLM put the new bugs** (bucket distribution) | the LLM's recall on bugs nobody had labelled | T2 |

**Style rules:**
- Vector PDF in `monografia/figuras/`, labels in Portuguese, a serif font matching `lmodern`.
- A colour-blind-safe palette, with the same colour for each system in every figure, and greyscale-legible (the PDF may be printed).
- No 3D or pie charts.
- Error bars wherever there is more than one sample.
- The axis states the label set used.

**Tooling.** `matplotlib` is not in `venv/` today (2026-11-12): install it, or use `pgfplots`.
`pgfplots` is not loaded in `config/preambulo.tex`; only `tikz` is, which the pipeline diagram
already uses. Recommendation: one script, `project-src/scripts/thesis-figures.py`, that reads the
CSVs from T1–T3 (frozen under a versioned `project-src/results/` with a manifest) and writes every
figure. Rerunning it regenerates them all, and the thesis never holds a number the CSVs do not.

### Steps

1. Freeze the final runs of T1–T3, and copy their CSVs and manifests to the versioned results
   directory.
2. Fix the three outdated passages above.
3. Write the method of each experiment in §"Protocolo experimental" (T1's per-baseline
   comparability rule, T2's adjudication protocol, T3's paired design), with each new research
   question.
4. Generate F1–F11, and write §"Resultados" with one table and at least one figure per question.
5. Update §"Ameaças à validade", `06-consideracoes.tex` (conclusions, contributions, future
   work) and the abstract (`pre-textuais/resumo`, `abstract`) with the final numbers.
6. Run `make final` and check it compiles with no undefined references. Then record it in the
   wiki: an `index.md` / `log.md` entry and a diary page for the consolidation.

### Decisions still open

- Which numbers are the headline in the abstract: 2.1 with 53/33, or the comparison table.
- Whether the original ablation (M3) is re-run on the integrated records or reported as measured
  on the 20 fixtures, with that caveat.
- `matplotlib` or `pgfplots`.
