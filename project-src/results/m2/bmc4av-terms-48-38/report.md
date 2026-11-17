# Racebench runs — scored

Label set `48/38` (racebench 2.1_remarks before the 2026-10-28 relabel (five bug points back to traps; the labels every pre-relabel number and BMC4AV's re-basing use): 48 bug points, 38 traps). Case subset `bmc4av-25-noRWW` (25 cases), patterns excluded: RWW. Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +racebench/1 | ok | `+racebench` | claude-cli:sonnet | 25 | 1 |
| +racebench/2 | ok | `+racebench` | claude-cli:sonnet | 25 | 2 |
| +racebench/3 | failed | `+racebench` | claude-cli:sonnet | 25 | 3 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | S2 | likely_real | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.67 | 45 | 0 | 201 | - | 0 | 739 / 118.0 / 726 |
| +racebench/1 | S2 | not infeasible | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.67 | 45 | 0 | 201 | - | 0 | 739 / 118.0 / 726 |
| +racebench/1 | S1 | static only | 37/37 | 13/30 | **35**/74 | 1.000 | 0.740 | 0.71 | 62 | - | - | - | - | - / 118.0 / - |
| +racebench/2 | S2 | likely_real | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.74 | 45 | 1 | 202 | - | 0 | 771 / 118.0 / 758 |
| +racebench/2 | S2 | not infeasible | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.74 | 46 | 1 | 202 | - | 0 | 771 / 118.0 / 758 |
| +racebench/2 | S1 | static only | 37/37 | 13/30 | **35**/74 | 1.000 | 0.740 | 0.71 | 62 | - | - | - | - | - / 118.0 / - |
| +racebench/3 | S2 | likely_real | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.72 | 44 | 1 | 199 | - | 1 | 739 / 118.0 / 727 |
| +racebench/3 | S2 | not infeasible | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.72 | 45 | 1 | 199 | - | 1 | 739 / 118.0 / 727 |
| +racebench/3 | S1 | static only | 37/37 | 13/30 | **35**/74 | 1.000 | 0.740 | 0.71 | 62 | - | - | - | - | - / 118.0 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW |
| --- | --- | --- | --- | --- |
| +racebench/1 | likely_real | 23/23 | 8/8 | 6/6 |
| +racebench/1 | not infeasible | 23/23 | 8/8 | 6/6 |
| +racebench/1 | static only | 23/23 | 8/8 | 6/6 |
| +racebench/2 | likely_real | 23/23 | 8/8 | 6/6 |
| +racebench/2 | not infeasible | 23/23 | 8/8 | 6/6 |
| +racebench/2 | static only | 23/23 | 8/8 | 6/6 |
| +racebench/3 | likely_real | 23/23 | 8/8 | 6/6 |
| +racebench/3 | not infeasible | 23/23 | 8/8 | 6/6 |
| +racebench/3 | static only | 23/23 | 8/8 | 6/6 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | likely_real | 3 | 37.0 ± 0.0 [37.0–37.0] | 7.0 ± 0.0 [7.0–7.0] | 53.0 ± 0.0 [53.0–53.0] | 1.000 ± 0.000 [1.000–1.000] | 0.841 ± 0.000 [0.841–0.841] | 0.71 ± 0.04 [0.67–0.74] | 44.7 ± 0.6 [44.0–45.0] | 0.7 ± 0.6 [0.0–1.0] | 201 ± 2 [199–202] |
| `+racebench` | not infeasible | 3 | 37.0 ± 0.0 [37.0–37.0] | 7.0 ± 0.0 [7.0–7.0] | 53.0 ± 0.0 [53.0–53.0] | 1.000 ± 0.000 [1.000–1.000] | 0.841 ± 0.000 [0.841–0.841] | 0.71 ± 0.04 [0.67–0.74] | 45.3 ± 0.6 [45.0–46.0] | 0.7 ± 0.6 [0.0–1.0] | 201 ± 2 [199–202] |
| `+racebench` | static only | 3 | 37.0 ± 0.0 [37.0–37.0] | 13.0 ± 0.0 [13.0–13.0] | 35.0 ± 0.0 [35.0–35.0] | 1.000 ± 0.000 [1.000–1.000] | 0.740 ± 0.000 [0.740–0.740] | 0.71 ± 0.00 [0.71–0.71] | 62.0 ± 0.0 [62.0–62.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | +racebench/1 | +racebench/2 | feasibility | 112 | 0.991 | 0.973 |
| `+racebench` | +racebench/1 | +racebench/2 | bucket | 112 | 0.991 | 0.973 |
| `+racebench` | +racebench/1 | +racebench/3 | feasibility | 111 | 0.991 | 0.972 |
| `+racebench` | +racebench/1 | +racebench/3 | bucket | 111 | 0.991 | 0.972 |
| `+racebench` | +racebench/2 | +racebench/3 | feasibility | 111 | 0.982 | 0.945 |
| `+racebench` | +racebench/2 | +racebench/3 | bucket | 111 | 0.982 | 0.945 |

## Labelled items whose verdict flips across runs

None: every bug point and trap got the same bucket and feasibility in every run.

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | 3 | 1 | 13 | 6 | 0 | 7 |
| +racebench/2 | 3 | 1 | 13 | 6 | 0 | 7 |
| +racebench/3 | 3 | 1 | 13 | 6 | 0 | 7 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
