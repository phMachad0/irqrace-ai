# Racebench runs — scored

Label set `48/38` (racebench 2.1_remarks before the 2026-10-28 relabel (five bug points back to traps; the labels every pre-relabel number and BMC4AV's re-basing use): 48 bug points, 38 traps). Case subset `all`. Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | ok | `+interleaving` | claude-cli:sonnet@low | 31 | 1 |
| +interleaving/1@2 | ok | `+interleaving` | claude-cli:sonnet@low | 31 | 1 |
| +interleaving/1@3 | ok | `+interleaving` | claude-cli:sonnet@low | 31 | 1 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | S2 | likely_real | 44/48 | 5/38 | **73**/96 | 0.917 | 0.898 | 0.63 | 76 | 14 | 83 | 1958384/108944 | 0 | 250 / 17.6 / 963 |
| +interleaving/1@1 | S2 | not infeasible | 48/48 | 8/38 | **72**/96 | 1.000 | 0.857 | 0.63 | 83 | 14 | 83 | 1958384/108944 | 0 | 250 / 17.6 / 963 |
| +interleaving/1@1 | S1 | static only | 48/48 | 16/38 | **48**/96 | 1.000 | 0.750 | 0.69 | 102 | - | - | - | - | - / 17.6 / - |
| +interleaving/1@2 | S2 | likely_real | 48/48 | 8/38 | **72**/96 | 1.000 | 0.857 | 0.63 | 81 | 2 | 84 | 2001688/113096 | 0 | 261 / 17.6 / 1007 |
| +interleaving/1@2 | S2 | not infeasible | 48/48 | 9/38 | **69**/96 | 1.000 | 0.842 | 0.63 | 82 | 2 | 84 | 2001688/113096 | 0 | 261 / 17.6 / 1007 |
| +interleaving/1@2 | S1 | static only | 48/48 | 16/38 | **48**/96 | 1.000 | 0.750 | 0.69 | 102 | - | - | - | - | - / 17.6 / - |
| +interleaving/1@3 | S2 | likely_real | 48/48 | 8/38 | **72**/96 | 1.000 | 0.857 | 0.64 | 82 | 1 | 84 | 2057025/111883 | 0 | 252 / 17.6 / 970 |
| +interleaving/1@3 | S2 | not infeasible | 48/48 | 9/38 | **69**/96 | 1.000 | 0.842 | 0.64 | 82 | 1 | 84 | 2057025/111883 | 0 | 252 / 17.6 / 970 |
| +interleaving/1@3 | S1 | static only | 48/48 | 16/38 | **48**/96 | 1.000 | 0.750 | 0.69 | 102 | - | - | - | - | - / 17.6 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | likely_real | 22/23 | 6/8 | 6/6 | 10/11 |
| +interleaving/1@1 | not infeasible | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1@1 | static only | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1@2 | likely_real | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1@2 | not infeasible | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1@2 | static only | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1@3 | likely_real | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1@3 | not infeasible | 23/23 | 8/8 | 6/6 | 11/11 |
| +interleaving/1@3 | static only | 23/23 | 8/8 | 6/6 | 11/11 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | likely_real | 3 | 46.7 ± 2.3 [44.0–48.0] | 7.0 ± 1.7 [5.0–8.0] | 72.3 ± 0.6 [72.0–73.0] | 0.972 ± 0.048 [0.917–1.000] | 0.871 ± 0.024 [0.857–0.898] | 0.64 ± 0.01 [0.63–0.64] | 79.7 ± 3.2 [76.0–82.0] | 5.7 ± 7.2 [1.0–14.0] | 84 ± 1 [83–84] |
| `+interleaving` | not infeasible | 3 | 48.0 ± 0.0 [48.0–48.0] | 8.7 ± 0.6 [8.0–9.0] | 70.0 ± 1.7 [69.0–72.0] | 1.000 ± 0.000 [1.000–1.000] | 0.847 ± 0.009 [0.842–0.857] | 0.64 ± 0.01 [0.63–0.64] | 82.3 ± 0.6 [82.0–83.0] | 5.7 ± 7.2 [1.0–14.0] | 84 ± 1 [83–84] |
| `+interleaving` | static only | 3 | 48.0 ± 0.0 [48.0–48.0] | 16.0 ± 0.0 [16.0–16.0] | 48.0 ± 0.0 [48.0–48.0] | 1.000 ± 0.000 [1.000–1.000] | 0.750 ± 0.000 [0.750–0.750] | 0.69 ± 0.00 [0.69–0.69] | 102.0 ± 0.0 [102.0–102.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@2 | feasibility | 166 | 0.904 | 0.725 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@2 | bucket | 166 | 0.904 | 0.725 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@3 | feasibility | 166 | 0.898 | 0.705 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@3 | bucket | 166 | 0.898 | 0.705 |
| `+interleaving` | +interleaving/1@2 | +interleaving/1@3 | feasibility | 166 | 0.994 | 0.979 |
| `+interleaving` | +interleaving/1@2 | +interleaving/1@3 | bucket | 166 | 0.994 | 0.979 |

## Labelled items whose verdict flips across runs

| prompt row | case | item | triple | field | per run |
| --- | --- | --- | --- | --- | --- |
| `+interleaving` | 009 | trap#1 | W37 R47 W38 | bucket | +interleaving/1@1: likely_infeasible, +interleaving/1@2: uncertain, +interleaving/1@3: uncertain |
| `+interleaving` | 009 | trap#1 | W37 R47 W38 | feasibility | +interleaving/1@1: infeasible, +interleaving/1@2: uncertain, +interleaving/1@3: uncertain |
| `+interleaving` | 022 | bug#1 | W32 W66 R55 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 022 | bug#1 | W32 W66 R55 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: feasible, +interleaving/1@3: feasible |
| `+interleaving` | 022 | bug#2 | R55 W66 W58 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 022 | bug#2 | R55 W66 W58 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: feasible, +interleaving/1@3: feasible |
| `+interleaving` | 022 | bug#3 | W58 W66 R63 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 022 | bug#3 | W58 W66 R63 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: feasible, +interleaving/1@3: feasible |
| `+interleaving` | 022 | bug#4 | R63 W66 R39 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 022 | bug#4 | R63 W66 R39 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: feasible, +interleaving/1@3: feasible |
| `+interleaving` | 022 | trap#1 | W32 W66 R39 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 022 | trap#1 | W32 W66 R39 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: feasible, +interleaving/1@3: feasible |
| `+interleaving` | 022 | trap#3 | R55 W66 R63 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 022 | trap#3 | R55 W66 R63 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: feasible, +interleaving/1@3: feasible |
| `+interleaving` | 028 | trap#1 | R29 W49 W30 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_infeasible, +interleaving/1@3: likely_infeasible |
| `+interleaving` | 028 | trap#1 | R29 W49 W30 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: infeasible, +interleaving/1@3: infeasible |
| `+interleaving` | 030 | trap#1 | R29 W52 W30 | bucket | +interleaving/1@1: likely_infeasible, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 030 | trap#1 | R29 W52 W30 | feasibility | +interleaving/1@1: infeasible, +interleaving/1@2: feasible, +interleaving/1@3: feasible |

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | 3 | 5 | 14 | 8 | 3 | 5 |
| +interleaving/1@2 | 3 | 5 | 14 | 7 | 1 | 8 |
| +interleaving/1@3 | 3 | 5 | 14 | 7 | 1 | 8 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
