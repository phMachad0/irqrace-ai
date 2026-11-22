# Racebench runs — scored

Label set `48/38` (racebench 2.1_remarks before the 2026-10-28 relabel (five bug points back to traps; the labels every pre-relabel number and BMC4AV's re-basing use): 48 bug points, 38 traps). Case subset `all`. Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +interleaving/1 | ok | `+interleaving` | claude-cli:sonnet@low | 31 | 1 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +interleaving/1 | S2 | likely_real | 44/48 | 5/38 | **73**/96 | 0.917 | 0.898 | 0.63 | 76 | 14 | 83 | 1958384/108944 | 0 | 250 / 17.6 / 963 |
| +interleaving/1 | S2 | not infeasible | 48/48 | 8/38 | **72**/96 | 1.000 | 0.857 | 0.63 | 83 | 14 | 83 | 1958384/108944 | 0 | 250 / 17.6 / 963 |
| +interleaving/1 | S1 | static only | 48/48 | 16/38 | **48**/96 | 1.000 | 0.750 | 0.69 | 102 | - | - | - | - | - / 17.6 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +interleaving/1 | likely_real | 22/23 | 6/8 | 6/6 | 10/11 |
| +interleaving/1 | not infeasible | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1 | static only | 23/23 | 8/8 | 6/6 | 11/11 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | likely_real | 1 | 44.0 | 5.0 | 73.0 | 0.917 | 0.898 | 0.63 | 76.0 | 14.0 | 83 |
| `+interleaving` | not infeasible | 1 | 48.0 | 8.0 | 72.0 | 1.000 | 0.857 | 0.63 | 83.0 | 14.0 | 83 |
| `+interleaving` | static only | 1 | 48.0 | 16.0 | 48.0 | 1.000 | 0.750 | 0.69 | 102.0 | - | - |

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +interleaving/1 | 3 | 5 | 14 | 8 | 3 | 5 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
