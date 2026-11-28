# Racebench runs — scored

Label set `48/38` (racebench 2.1_remarks before the 2026-10-28 relabel (five bug points back to traps; the labels every pre-relabel number and BMC4AV's re-basing use): 48 bug points, 38 traps). Case subset `bmc4av-25` (25 cases). Scorer `bench_metrics/1.0.0`.

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
| +racebench/1 | S2 | likely_real | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.67 | 49 | 0 | 220 | 2547973/216525 | 0 | 739 / 118.0 / 726 |
| +racebench/1 | S2 | not infeasible | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.67 | 49 | 0 | 220 | 2547973/216525 | 0 | 739 / 118.0 / 726 |
| +racebench/1 | S1 | static only | 41/41 | 14/31 | **40**/82 | 1.000 | 0.745 | 0.71 | 68 | - | - | - | - | - / 118.0 / - |
| +racebench/2 | S2 | likely_real | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.74 | 49 | 1 | 221 | 2574570/214023 | 0 | 771 / 118.0 / 758 |
| +racebench/2 | S2 | not infeasible | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.74 | 50 | 1 | 221 | 2574570/214023 | 0 | 771 / 118.0 / 758 |
| +racebench/2 | S1 | static only | 41/41 | 14/31 | **40**/82 | 1.000 | 0.745 | 0.71 | 68 | - | - | - | - | - / 118.0 / - |
| +racebench/3 | S2 | likely_real | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.71 | 48 | 1 | 218 | 2514707/215418 | 1 | 739 / 118.0 / 727 |
| +racebench/3 | S2 | not infeasible | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.71 | 49 | 1 | 218 | 2514707/215418 | 1 | 739 / 118.0 / 727 |
| +racebench/3 | S1 | static only | 41/41 | 14/31 | **40**/82 | 1.000 | 0.745 | 0.71 | 68 | - | - | - | - | - / 118.0 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +racebench/1 | likely_real | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/1 | not infeasible | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/1 | static only | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/2 | likely_real | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/2 | not infeasible | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/2 | static only | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/3 | likely_real | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/3 | not infeasible | 23/23 | 8/8 | 6/6 | 4/4 |
| +racebench/3 | static only | 23/23 | 8/8 | 6/6 | 4/4 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | likely_real | 3 | 41.0 ± 0.0 [41.0–41.0] | 7.0 ± 0.0 [7.0–7.0] | 61.0 ± 0.0 [61.0–61.0] | 1.000 ± 0.000 [1.000–1.000] | 0.854 ± 0.000 [0.854–0.854] | 0.71 ± 0.03 [0.67–0.74] | 48.7 ± 0.6 [48.0–49.0] | 0.7 ± 0.6 [0.0–1.0] | 220 ± 2 [218–221] |
| `+racebench` | not infeasible | 3 | 41.0 ± 0.0 [41.0–41.0] | 7.0 ± 0.0 [7.0–7.0] | 61.0 ± 0.0 [61.0–61.0] | 1.000 ± 0.000 [1.000–1.000] | 0.854 ± 0.000 [0.854–0.854] | 0.71 ± 0.03 [0.67–0.74] | 49.3 ± 0.6 [49.0–50.0] | 0.7 ± 0.6 [0.0–1.0] | 220 ± 2 [218–221] |
| `+racebench` | static only | 3 | 41.0 ± 0.0 [41.0–41.0] | 14.0 ± 0.0 [14.0–14.0] | 40.0 ± 0.0 [40.0–40.0] | 1.000 ± 0.000 [1.000–1.000] | 0.745 ± 0.000 [0.745–0.745] | 0.71 ± 0.00 [0.71–0.71] | 68.0 ± 0.0 [68.0–68.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | +racebench/1 | +racebench/2 | feasibility | 123 | 0.992 | 0.976 |
| `+racebench` | +racebench/1 | +racebench/2 | bucket | 123 | 0.992 | 0.976 |
| `+racebench` | +racebench/1 | +racebench/3 | feasibility | 122 | 0.992 | 0.975 |
| `+racebench` | +racebench/1 | +racebench/3 | bucket | 122 | 0.992 | 0.975 |
| `+racebench` | +racebench/2 | +racebench/3 | feasibility | 122 | 0.984 | 0.951 |
| `+racebench` | +racebench/2 | +racebench/3 | bucket | 122 | 0.984 | 0.951 |

## Labelled items whose verdict flips across runs

None: every bug point and trap got the same bucket and feasibility in every run.

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | 3 | 1 | 13 | 7 | 0 | 7 |
| +racebench/2 | 3 | 1 | 13 | 7 | 0 | 7 |
| +racebench/3 | 3 | 1 | 13 | 7 | 0 | 7 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
