# Racebench runs — scored

Label set `53/33` (racebench 2.1_remarks as vendored (relabel 2026-10-28) + curated errata: 53 bug points, 33 traps). Case subset `all`. Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +racebench+rubric/1 | ok | `+racebench+rubric` | claude-cli:sonnet | 31 | 1 |
| +racebench+effectfree/1 | ok | `+racebench+effectfree` | claude-cli:sonnet | 31 | 1 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +racebench+rubric/1 | S2 | likely_real | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.65 | 83 | 3 | 307 | 3736620/383688 | 0 | 1172 / 169.7 / 1154 |
| +racebench+rubric/1 | S2 | not infeasible | 53/53 | 3/33 | **97**/106 | 1.000 | 0.946 | 0.65 | 85 | 3 | 307 | 3736620/383688 | 0 | 1172 / 169.7 / 1154 |
| +racebench+rubric/1 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |
| +racebench+effectfree/1 | S2 | likely_real | 53/53 | 1/33 | **103**/106 | 1.000 | 0.981 | 0.68 | 81 | 1 | 305 | 3564564/352526 | 0 | 1140 / 169.7 / 1123 |
| +racebench+effectfree/1 | S2 | not infeasible | 53/53 | 3/33 | **97**/106 | 1.000 | 0.946 | 0.68 | 83 | 1 | 305 | 3564564/352526 | 0 | 1140 / 169.7 / 1123 |
| +racebench+effectfree/1 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 169.7 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +racebench+rubric/1 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+rubric/1 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+rubric/1 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+effectfree/1 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+effectfree/1 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench+effectfree/1 | static only | 27/27 | 8/8 | 7/7 | 11/11 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+racebench+rubric` | likely_real | 1 | 53.0 | 2.0 | 100.0 | 1.000 | 0.964 | 0.65 | 83.0 | 3.0 | 307 |
| `+racebench+rubric` | not infeasible | 1 | 53.0 | 3.0 | 97.0 | 1.000 | 0.946 | 0.65 | 85.0 | 3.0 | 307 |
| `+racebench+rubric` | static only | 1 | 53.0 | 11.0 | 73.0 | 1.000 | 0.828 | 0.71 | 102.0 | - | - |
| `+racebench+effectfree` | likely_real | 1 | 53.0 | 1.0 | 103.0 | 1.000 | 0.981 | 0.68 | 81.0 | 1.0 | 305 |
| `+racebench+effectfree` | not infeasible | 1 | 53.0 | 3.0 | 97.0 | 1.000 | 0.946 | 0.68 | 83.0 | 1.0 | 305 |
| `+racebench+effectfree` | static only | 1 | 53.0 | 11.0 | 73.0 | 1.000 | 0.828 | 0.71 | 102.0 | - | - |

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +racebench+rubric/1 | 3 | 5 | 14 | 8 | 1 | 2 |
| +racebench+effectfree/1 | 3 | 5 | 14 | 8 | 2 | 1 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
