# Racebench runs — scored

Label set `53/33` (racebench 2.1_remarks as vendored (relabel 2026-10-28) + curated errata: 53 bug points, 33 traps). Case subset `all`. Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +racebench/1 | ok | `+racebench` | claude-cli:sonnet | 31 | 1 |
| +racebench/2 | ok | `+racebench` | claude-cli:sonnet | 31 | 2 |
| +racebench/3 | failed | `+racebench` | claude-cli:sonnet | 31 | 3 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | S2 | likely_real | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.68 | 83 | 0 | 304 | 3519824/296296 | 0 | 978 / 169.7 / 962 |
| +racebench/1 | S2 | not infeasible | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.68 | 83 | 0 | 304 | 3519824/296296 | 0 | 978 / 169.7 / 962 |
| +racebench/1 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |
| +racebench/2 | S2 | likely_real | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.70 | 83 | 1 | 305 | 3546360/294941 | 0 | 1016 / 169.7 / 1000 |
| +racebench/2 | S2 | not infeasible | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.70 | 84 | 1 | 305 | 3546360/294941 | 0 | 1016 / 169.7 / 1000 |
| +racebench/2 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |
| +racebench/3 | S2 | likely_real | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.67 | 82 | 1 | 302 | 3486600/295829 | 1 | 978 / 169.7 / 962 |
| +racebench/3 | S2 | not infeasible | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.67 | 83 | 1 | 302 | 3486600/295829 | 1 | 978 / 169.7 / 962 |
| +racebench/3 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +racebench/1 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/1 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/1 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/2 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/2 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/2 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/3 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/3 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/3 | static only | 27/27 | 8/8 | 7/7 | 11/11 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | likely_real | 3 | 53.0 ± 0.0 [53.0–53.0] | 2.0 ± 0.0 [2.0–2.0] | 100.0 ± 0.0 [100.0–100.0] | 1.000 ± 0.000 [1.000–1.000] | 0.964 ± 0.000 [0.964–0.964] | 0.69 ± 0.02 [0.67–0.70] | 82.7 ± 0.6 [82.0–83.0] | 0.7 ± 0.6 [0.0–1.0] | 304 ± 2 [302–305] |
| `+racebench` | not infeasible | 3 | 53.0 ± 0.0 [53.0–53.0] | 2.0 ± 0.0 [2.0–2.0] | 100.0 ± 0.0 [100.0–100.0] | 1.000 ± 0.000 [1.000–1.000] | 0.964 ± 0.000 [0.964–0.964] | 0.69 ± 0.02 [0.67–0.70] | 83.3 ± 0.6 [83.0–84.0] | 0.7 ± 0.6 [0.0–1.0] | 304 ± 2 [302–305] |
| `+racebench` | static only | 3 | 53.0 ± 0.0 [53.0–53.0] | 11.0 ± 0.0 [11.0–11.0] | 73.0 ± 0.0 [73.0–73.0] | 1.000 ± 0.000 [1.000–1.000] | 0.828 ± 0.000 [0.828–0.828] | 0.71 ± 0.00 [0.71–0.71] | 102.0 ± 0.0 [102.0–102.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | +racebench/1 | +racebench/2 | feasibility | 166 | 0.994 | 0.979 |
| `+racebench` | +racebench/1 | +racebench/2 | bucket | 166 | 0.994 | 0.979 |
| `+racebench` | +racebench/1 | +racebench/3 | feasibility | 165 | 0.994 | 0.978 |
| `+racebench` | +racebench/1 | +racebench/3 | bucket | 165 | 0.994 | 0.978 |
| `+racebench` | +racebench/2 | +racebench/3 | feasibility | 165 | 0.988 | 0.957 |
| `+racebench` | +racebench/2 | +racebench/3 | bucket | 165 | 0.988 | 0.957 |

## Labelled items whose verdict flips across runs

None: every bug point and trap got the same bucket and feasibility in every run.

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | 3 | 5 | 14 | 9 | 0 | 2 |
| +racebench/2 | 3 | 5 | 14 | 9 | 0 | 2 |
| +racebench/3 | 3 | 5 | 14 | 9 | 0 | 2 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
