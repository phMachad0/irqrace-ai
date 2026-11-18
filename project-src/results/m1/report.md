# Racebench runs — scored

Label set `53/33` (racebench 2.1_remarks as vendored (relabel 2026-10-28) + curated errata: 53 bug points, 33 traps). Case subset `all`. Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +racebench+c4/1 | ok | `+racebench+c4` | claude-cli:sonnet | 31 | 1 |
| +racebench+c4/2 | ok | `+racebench+c4` | claude-cli:sonnet | 31 | 2 |
| +racebench+c4/3 | ok | `+racebench+c4` | claude-cli:sonnet | 31 | 3 |
| +racebench/1 | ok | `+racebench` | claude-cli:sonnet | 31 | 1 |
| +racebench/2 | ok | `+racebench` | claude-cli:sonnet | 31 | 2 |
| +racebench/3 | failed | `+racebench` | claude-cli:sonnet | 31 | 3 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +racebench+c4/1 | S2 | likely_real | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.65 | 84 | 0 | 615 | 7241918/614327 | 0 | 1976 / 169.7 / 1958 |
| +racebench+c4/1 | S2 | not infeasible | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.65 | 84 | 0 | 615 | 7241918/614327 | 0 | 1976 / 169.7 / 1958 |
| +racebench+c4/1 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |
| +racebench+c4/2 | S2 | likely_real | 53/53 | 3/33 | **97**/106 | 1.000 | 0.946 | 0.69 | 84 | 2 | 619 | 7293219/623849 | 0 | 1992 / 169.7 / 1977 |
| +racebench+c4/2 | S2 | not infeasible | 53/53 | 4/33 | **94**/106 | 1.000 | 0.930 | 0.69 | 85 | 2 | 619 | 7293219/623849 | 0 | 1992 / 169.7 / 1977 |
| +racebench+c4/2 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |
| +racebench+c4/3 | S2 | likely_real | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.69 | 85 | 3 | 623 | 7374177/618860 | 0 | 2092 / 169.7 / 2068 |
| +racebench+c4/3 | S2 | not infeasible | 53/53 | 3/33 | **97**/106 | 1.000 | 0.946 | 0.69 | 87 | 3 | 623 | 7374177/618860 | 0 | 2092 / 169.7 / 2068 |
| +racebench+c4/3 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |
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
| +racebench+c4/1 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/1 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/1 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/2 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/2 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/2 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/3 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/3 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+c4/3 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
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
| `+racebench+c4` | likely_real | 3 | 53.0 ± 0.0 [53.0–53.0] | 2.3 ± 0.6 [2.0–3.0] | 99.0 ± 1.7 [97.0–100.0] | 1.000 ± 0.000 [1.000–1.000] | 0.958 ± 0.010 [0.946–0.964] | 0.68 ± 0.02 [0.65–0.69] | 84.3 ± 0.6 [84.0–85.0] | 1.7 ± 1.5 [0.0–3.0] | 619 ± 4 [615–623] |
| `+racebench+c4` | not infeasible | 3 | 53.0 ± 0.0 [53.0–53.0] | 3.0 ± 1.0 [2.0–4.0] | 97.0 ± 3.0 [94.0–100.0] | 1.000 ± 0.000 [1.000–1.000] | 0.947 ± 0.017 [0.930–0.964] | 0.68 ± 0.02 [0.65–0.69] | 85.3 ± 1.5 [84.0–87.0] | 1.7 ± 1.5 [0.0–3.0] | 619 ± 4 [615–623] |
| `+racebench+c4` | static only | 3 | 53.0 ± 0.0 [53.0–53.0] | 11.0 ± 0.0 [11.0–11.0] | 73.0 ± 0.0 [73.0–73.0] | 1.000 ± 0.000 [1.000–1.000] | 0.828 ± 0.000 [0.828–0.828] | 0.71 ± 0.00 [0.71–0.71] | 102.0 ± 0.0 [102.0–102.0] | - | - |
| `+racebench` | likely_real | 3 | 53.0 ± 0.0 [53.0–53.0] | 2.0 ± 0.0 [2.0–2.0] | 100.0 ± 0.0 [100.0–100.0] | 1.000 ± 0.000 [1.000–1.000] | 0.964 ± 0.000 [0.964–0.964] | 0.69 ± 0.02 [0.67–0.70] | 82.7 ± 0.6 [82.0–83.0] | 0.7 ± 0.6 [0.0–1.0] | 304 ± 2 [302–305] |
| `+racebench` | not infeasible | 3 | 53.0 ± 0.0 [53.0–53.0] | 2.0 ± 0.0 [2.0–2.0] | 100.0 ± 0.0 [100.0–100.0] | 1.000 ± 0.000 [1.000–1.000] | 0.964 ± 0.000 [0.964–0.964] | 0.69 ± 0.02 [0.67–0.70] | 83.3 ± 0.6 [83.0–84.0] | 0.7 ± 0.6 [0.0–1.0] | 304 ± 2 [302–305] |
| `+racebench` | static only | 3 | 53.0 ± 0.0 [53.0–53.0] | 11.0 ± 0.0 [11.0–11.0] | 73.0 ± 0.0 [73.0–73.0] | 1.000 ± 0.000 [1.000–1.000] | 0.828 ± 0.000 [0.828–0.828] | 0.71 ± 0.00 [0.71–0.71] | 102.0 ± 0.0 [102.0–102.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+racebench+c4` | +racebench+c4/1 | +racebench+c4/2 | feasibility | 166 | 0.976 | 0.911 |
| `+racebench+c4` | +racebench+c4/1 | +racebench+c4/2 | bucket | 166 | 0.976 | 0.911 |
| `+racebench+c4` | +racebench+c4/1 | +racebench+c4/3 | feasibility | 166 | 0.970 | 0.889 |
| `+racebench+c4` | +racebench+c4/1 | +racebench+c4/3 | bucket | 166 | 0.970 | 0.889 |
| `+racebench+c4` | +racebench+c4/2 | +racebench+c4/3 | feasibility | 166 | 0.976 | 0.910 |
| `+racebench+c4` | +racebench+c4/2 | +racebench+c4/3 | bucket | 166 | 0.976 | 0.910 |
| `+racebench` | +racebench/1 | +racebench/2 | feasibility | 166 | 0.994 | 0.979 |
| `+racebench` | +racebench/1 | +racebench/2 | bucket | 166 | 0.994 | 0.979 |
| `+racebench` | +racebench/1 | +racebench/3 | feasibility | 165 | 0.994 | 0.978 |
| `+racebench` | +racebench/1 | +racebench/3 | bucket | 165 | 0.994 | 0.978 |
| `+racebench` | +racebench/2 | +racebench/3 | feasibility | 165 | 0.988 | 0.957 |
| `+racebench` | +racebench/2 | +racebench/3 | bucket | 165 | 0.988 | 0.957 |

## Labelled items whose verdict flips across runs

| prompt row | case | item | triple | field | per run |
| --- | --- | --- | --- | --- | --- |
| `+racebench+c4` | 007 | trap#1 | W32 W50 R34 | bucket | +racebench+c4/1: likely_infeasible, +racebench+c4/2: uncertain, +racebench+c4/3: likely_infeasible |
| `+racebench+c4` | 007 | trap#1 | W32 W50 R34 | feasibility | +racebench+c4/1: infeasible, +racebench+c4/2: uncertain, +racebench+c4/3: infeasible |
| `+racebench+c4` | 009 | trap#1 | W37 R47 W38 | bucket | +racebench+c4/1: likely_infeasible, +racebench+c4/2: likely_real, +racebench+c4/3: uncertain |
| `+racebench+c4` | 009 | trap#1 | W37 R47 W38 | feasibility | +racebench+c4/1: infeasible, +racebench+c4/2: feasible, +racebench+c4/3: uncertain |

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +racebench+c4/1 | 3 | 5 | 14 | 9 | 0 | 2 |
| +racebench+c4/2 | 3 | 5 | 14 | 7 | 1 | 3 |
| +racebench+c4/3 | 3 | 5 | 14 | 8 | 1 | 2 |
| +racebench/1 | 3 | 5 | 14 | 9 | 0 | 2 |
| +racebench/2 | 3 | 5 | 14 | 9 | 0 | 2 |
| +racebench/3 | 3 | 5 | 14 | 9 | 0 | 2 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
