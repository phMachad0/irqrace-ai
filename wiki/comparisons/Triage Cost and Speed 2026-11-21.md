---
type: comparison
tags: [wiki, comparison, t3, cost]
sources: ["[[Racebench Comparison 2026-11-16]]", "[[Racebench]]", "[[LLM Triage]]", "[[Lucas Tasks]]"]
updated: 2026-11-21
status: draft
---

# Triage cost and speed, 2026-11-19 to 2026-11-21

What the [[LLM Triage]] stage costs on [[Racebench]], and four ways to cut it: a smaller model, a
lower effort level, scheduling the calls differently, and asking about several candidates at once.
It ends with the baseline the tool has to justify itself against: a model that just reads the
files. Every number is this project's own run, on one machine (Intel i3-1115G4, 4 cores), with
`claude-cli` on Pedro's subscription, the `+racebench` row and the 53/33 labels, and **n = 1 per
variant** unless stated. The protocol's n = 3 ([[Lucas Tasks]], decision 3) is not met anywhere on
this page, so a difference of one item is noise until repeated; M1 measured a ±3-point band on the
NASAC score ([[Racebench Comparison 2026-11-16]]).

Data: `project-src/results/speed-pilot-20261119/`, `speed-20261121/`, `scan-estimate-20261121/`,
`scan-measure-20261121/`, each with a `NOTES.md`. The temporary versions measured here are kept
as patches in `speed-20261121/`, not merged.

## Where the time goes (M1)

From the per-case spend lines of M1 (`results/m1/tokens-per-case.csv`), one `+racebench` run is
304 calls for 166 candidates, about 11.6 k input and 975 output tokens per call, and 978–1,016 s of
wall time with four conversations per case. The sum of call latencies is about 2,810 s, so on
average 2.9 of the 4 slots were busy: cases run one after another, and most have fewer than four
candidates.

## Model and effort (pilot, 2026-11-19)

| | M1 (default effort, n = 3) | Sonnet, low effort | Haiku (`claude-haiku-5-5`) |
| --- | --- | --- | --- |
| Bug points in `likely_real` | 53/53 | 52/53 | 47/53 |
| NASAC score /106 | 100 | 98 | 88 |
| Output tokens per call | ≈975 | 754 | 2,608 |
| Wall time | ≈978 s | 943 s | 1,584 s |

Neither was faster in a way that matters. Haiku wrote 2.7× more per call, failed the CLI's
structured output on 11 candidates (5 of them bug points, kept `uncertain`) and called one bug
point benign. The raw runs were lost with the session's `/tmp` scratchpad; the numbers were
transcribed before the loss. A low-effort baseline was re-run on 2026-11-21 (below) and agrees.

## Scheduling and grouping (2026-11-21)

| | baseline | pool | by variable | low-effort baseline | pool + by variable, low effort |
| --- | --- | --- | --- | --- | --- |
| Bug points in `likely_real` | 53/53 | 53/53 | 53/53 | 52/53 | 53/53 |
| Bug points called infeasible | 0 | 0 | 0 | 0 | 0 |
| Traps in `likely_real` | 2 | 3 | 3 | 3 | 3 |
| NASAC score /106 | 100 | 97 | 97 | 95 | 97 |
| Inspection Ratio | 0.68 | 0.66 | 0.64 | 0.68 | 0.65 |
| Calls | 304 | 304 | 84 | 307 | 84 |
| Input tokens | 3.45 M | 3.46 M | 1.93 M | 3.50 M | 2.02 M |
| Output tokens | 278 k | 278 k | 126 k | 249 k | 113 k |
| Wall time | 1,079 s | 979 s | 858 s | 984 s | **263 s** |
| Mean concurrency (of 4) | 2.89 | 3.41 | 1.29 | 2.91 | 3.86 |

- **Pool.** The runner starts cases four at a time, largest first, with one conversation each, so
  four conversations serve the whole suite. Concurrency rose and wall time fell 9%; one call
  stalled for about four minutes and set the tail.
- **By variable.** One conversation per shared variable (at most 20 triples), with the shared
  fields and source bodies rendered once and one verdict per candidate id; feasibility and
  harmfulness stay separate calls (D#3). The prompt asset and the reasoning behind it are in
  `tmp-var.patch` (`prompts/checklist.md`, `irqrace/llm/checklist.py`). Calls fell 72%, input 44%,
  output 55%. Wall time fell only 20%, because cases still ran in series.
- **Together, at low effort**: 4.1× faster than the baseline with recall intact.

**A failure the completeness check caught.** In the first combined low-effort run, the
feasibility answer for `svp_simple_022_001` (15 triples on one variable) stated three shared
findings and then answered **one** item; `019`'s answered 2 of 4. Every omitted triple stayed in
the report as `uncertain` with the reason, which is the design ([[Soundness Assumptions]] H3), but
six bug points left `likely_real`. The fix — an omitted item is asked in its own conversation — is
in the run reported above; that run answered every item, so the retry has not yet fired on a real
omission. The default-effort checklist run never omitted, so the low effort level is the likely
cause.

## The scan: ask the model to read the files

The baseline any LLM-assisted analyzer has to beat: no static analysis, the model reads each file
and lists the atomicity violations as line triples (`scripts/scan-measure.py`). The prompt is
deliberately simple: the interrupt model, the four shapes, the flows and priorities from the C1
config, the numbered source (annotation block cut off) and `common.h`. Sonnet at low effort, as the
low-effort triage runs.

| | scan, per file | scan, one prompt for 31 files | irqrace, pool + by variable (low) |
| --- | --- | --- | --- |
| Bug points (53/33) | 50/53 | 48/53 | 53/53 |
| Traps reported (53/33) | 1 | 1 | 3 |
| NASAC score /106 | 97 | 93 | 97 |
| Bug points (48/38, the published labels) | **48/48** | 44/48 | 48/48 (M2, default effort) |
| Traps reported (48/38) | 3 | 5 | 7 (M2) |
| Findings matching no annotation | 8 | 3 | 83 in `likely_real` |
| Calls | 31 | 1 | 84 |
| Input tokens | 99 k | 33 k | 2.02 M |
| Output tokens | 20 k | 11 k | 113 k |
| Wall time | 57 s | 73 s | 263 s (+ ≈30 s static) |

On the original files the scan looked competitive at a twentieth of the input, and in that one
run its three misses were all bug points this project created in the 2026-10-28 relabel
([[Contradictions]] #7, #8). That reading did not survive the contamination test below.

### Contamination test (n = 3 per arm)

A disguised copy (`scripts/racebench-disguise.py`, seed 2026): every comment and the header gone,
every `svp_simple_*` identifier renamed to a neutral word, cases renamed `program_NN`, and the
functions reordered so all 258 annotated lines move; findings are mapped back line by line and
scored with the same matcher. A second probe asked for each case's bug points by name alone, with
no source: **31 of 31 answers were empty** (`results/contamination-20261121/`).

| Min–max over 3 runs | original, per file | disguised, per file | original, one prompt | disguised, one prompt |
| --- | --- | --- | --- | --- |
| Bug points (53/33) | 49–51 | **50–51** | 48–51 | 44–49 |
| Traps reported | 1–4 | **6–8** | 0–1 | 2–6 |
| NASAC score /106 | 86–99 | **76–84** | 93–100 | 75–82 |
| Findings matching no annotation | 6–8 | 20–26 | 3–11 | 7–17 |
| Input / output tokens | 94–99 k / 20 k | 74–81 k / 27–28 k | 33 k / 11–13 k | 17–35 k / 11–14 k |

- **Recall survives the disguise; precision does not.** Per file the scan still finds 50–51 of 53
  bug points, but it reports 3–4× as many planted traps, six of them in every disguised run. Over
  three runs the original arm's misses also include non-relabel bug points (`008`, `009`), so the
  "it agrees with the published labels" signature was one draw.
- **The cue is not separated.** Names, comments and function order changed together; memory of the
  suite and meaningful identifiers (`condition6`, `global_flag`) both explain the original's low
  trap count.
- **The comparison with irqrace is not yet like for like.** irqrace's 97 came from the original
  names, and its triage reads names too; its static recall does not. Running the full pipeline on
  the disguised copy is the next measurement.

**Other limits of the scan comparison.**
- **Scale.** 60 k characters for 31 programs with one or two handlers each. The estimate for the
  18 real-world programs (`scan-estimate-20261121`, characters calibrated on M1's prompts) has the
  scan at 0.15–0.22 M input tokens against 9–29 M for triage, but they are extracted programs of
  280 k characters in total, not repositories.
- **Guarantees.** The scan's recall is a sample with nothing behind a miss. irqrace's static stages
  keep every bug point by construction and the triage removes none ([[Thesis Goal]]).

The thesis can use the scan honestly as the cost floor of a pure-LLM approach: on the disguised
copy it keeps most of the recall (2–3 bug points missed per run, with nothing behind a miss) and
loses the precision.

## Lucas's T3 runs, scored here

Two of the five T3 variants ran on 2026-11-17 and were never scored (`results/m3/`, n = 1):
`+racebench+rubric` 53/53, 2 traps, score 100; `+racebench+effectfree` 53/53, **1 trap, score
103**. It removes case 022's two systematic traps and reports `009` trap#1 instead, an item that
flips in every series measured. `-selfval` failed 13 times on the rate limit; `+witness` and
`+location` never ran. Not gate M3.

## Open

- A free, non-Anthropic model on the same rows: `gpt-oss-120b` through Groq's free tier, already
  supported by the `openai:` backend (`ablation-groq.json` is an earlier run on the 20 fixtures).
  The free tier's daily token limits are unknown here; grouping by variable halves what a run needs.
- Compacting `provenance.entries` (about 7.8 k characters per real-world record, 75% of a checklist
  item) before the checklist is tried on real code, where it currently costs more input than the
  per-interval grouping.
- n = 3 for the combined low-effort configuration before it becomes a default.
