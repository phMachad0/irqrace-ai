# Racebench runs — scored

Label set `53/33` (racebench 2.1_remarks as vendored (relabel 2026-10-28) + curated errata: 53 bug points, 33 traps). Case subset `all`. Scorer `bench_metrics/1.0.0`.

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
| +interleaving/1@1 | S2 | likely_real | 49/53 | 0/33 | **98**/106 | 0.925 | 1.000 | 0.65 | 76 | 14 | 83 | 1958384/108944 | 0 | 250 / 17.6 / 963 |
| +interleaving/1@1 | S2 | not infeasible | 53/53 | 3/33 | **97**/106 | 1.000 | 0.946 | 0.65 | 83 | 14 | 83 | 1958384/108944 | 0 | 250 / 17.6 / 963 |
| +interleaving/1@1 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 17.6 / - |
| +interleaving/1@2 | S2 | likely_real | 53/53 | 3/33 | **97**/106 | 1.000 | 0.946 | 0.64 | 81 | 2 | 84 | 2001688/113096 | 0 | 261 / 17.6 / 1007 |
| +interleaving/1@2 | S2 | not infeasible | 53/53 | 4/33 | **94**/106 | 1.000 | 0.930 | 0.64 | 82 | 2 | 84 | 2001688/113096 | 0 | 261 / 17.6 / 1007 |
| +interleaving/1@2 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 17.6 / - |
| +interleaving/1@3 | S2 | likely_real | 53/53 | 3/33 | **97**/106 | 1.000 | 0.946 | 0.65 | 82 | 1 | 84 | 2057025/111883 | 0 | 252 / 17.6 / 970 |
| +interleaving/1@3 | S2 | not infeasible | 53/53 | 4/33 | **94**/106 | 1.000 | 0.930 | 0.65 | 82 | 1 | 84 | 2057025/111883 | 0 | 252 / 17.6 / 970 |
| +interleaving/1@3 | S1 | static only | 53/53 | 11/33 | **73**/106 | 1.000 | 0.828 | 0.71 | 102 | - | - | - | - | - / 17.6 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | likely_real | 26/27 | 6/8 | 7/7 | 10/11 |
| +interleaving/1@1 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +interleaving/1@1 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
| +interleaving/1@2 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +interleaving/1@2 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +interleaving/1@2 | static only | 27/27 | 8/8 | 7/7 | 11/11 |
| +interleaving/1@3 | likely_real | 27/27 | 8/8 | 7/7 | 11/11 |
| +interleaving/1@3 | not infeasible | 27/27 | 8/8 | 7/7 | 11/11 |
| +interleaving/1@3 | static only | 27/27 | 8/8 | 7/7 | 11/11 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | likely_real | 3 | 51.7 ± 2.3 [49.0–53.0] | 2.0 ± 1.7 [0.0–3.0] | 97.3 ± 0.6 [97.0–98.0] | 0.975 ± 0.044 [0.925–1.000] | 0.964 ± 0.031 [0.946–1.000] | 0.65 ± 0.01 [0.64–0.65] | 79.7 ± 3.2 [76.0–82.0] | 5.7 ± 7.2 [1.0–14.0] | 84 ± 1 [83–84] |
| `+interleaving` | not infeasible | 3 | 53.0 ± 0.0 [53.0–53.0] | 3.7 ± 0.6 [3.0–4.0] | 95.0 ± 1.7 [94.0–97.0] | 1.000 ± 0.000 [1.000–1.000] | 0.935 ± 0.010 [0.930–0.946] | 0.65 ± 0.01 [0.64–0.65] | 82.3 ± 0.6 [82.0–83.0] | 5.7 ± 7.2 [1.0–14.0] | 84 ± 1 [83–84] |
| `+interleaving` | static only | 3 | 53.0 ± 0.0 [53.0–53.0] | 11.0 ± 0.0 [11.0–11.0] | 73.0 ± 0.0 [73.0–73.0] | 1.000 ± 0.000 [1.000–1.000] | 0.828 ± 0.000 [0.828–0.828] | 0.71 ± 0.00 [0.71–0.71] | 102.0 ± 0.0 [102.0–102.0] | - | - |

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
| +interleaving/1@1 | 3 | 5 | 14 | 8 | 3 | 0 |
| +interleaving/1@2 | 3 | 5 | 14 | 7 | 1 | 3 |
| +interleaving/1@3 | 3 | 5 | 14 | 7 | 1 | 3 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
