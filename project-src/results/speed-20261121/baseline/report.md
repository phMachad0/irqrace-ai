# Racebench runs — scored

Label set `53/33` (racebench 2.1_remarks as vendored (relabel 2026-10-28) + curated errata: 53 bug points, 33 traps). Case subset `all`. Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +racebench/1 | failed | `+racebench` | claude-cli:sonnet | 31 | 1 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | S2 | likely_real | 53/53 | 2/33 | **100**/106 | 1.000 | 0.964 | 0.68 | 83 | 2 | 304 | 3453796/278140 | 1 | 1079 / 17.6 / 1072 |
| +racebench/1 | S2 | not infeasible | 53/53 | 4/33 | **94**/106 | 1.000 | 0.930 | 0.68 | 83 | 2 | 304 | 3453796/278140 | 1 | 1079 / 17.6 / 1072 |
| +racebench/1 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 17.6 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +racebench/1 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/1 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +racebench/1 | static only | 27/27 | 8/8 | 7/7 | 11/11 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | likely_real | 1 | 53.0 | 2.0 | 100.0 | 1.000 | 0.964 | 0.68 | 83.0 | 2.0 | 304 |
| `+racebench` | not infeasible | 1 | 53.0 | 4.0 | 94.0 | 1.000 | 0.930 | 0.68 | 83.0 | 2.0 | 304 |
| `+racebench` | static only | 1 | 53.0 | 11.0 | 73.0 | 1.000 | 0.828 | 0.71 | 102.0 | - | - |

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | 3 | 5 | 14 | 7 | 2 | 2 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
