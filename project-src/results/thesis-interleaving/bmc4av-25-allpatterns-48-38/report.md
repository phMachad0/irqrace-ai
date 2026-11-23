# Racebench runs — scored

Label set `48/38` (racebench 2.1_remarks before the 2026-10-28 relabel (five bug points back to traps; the labels every pre-relabel number and BMC4AV's re-basing use): 48 bug points, 38 traps). Case subset `cases=25` (25 cases). Scorer `bench_metrics/1.0.0`.

NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.

## Runs

| run | status | prompt row | backend | cases | sample |
| --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | ok | `+interleaving` | claude-cli:sonnet@low | 25 | 1 |
| +interleaving/1@2 | ok | `+interleaving` | claude-cli:sonnet@low | 25 | 1 |
| +interleaving/1@3 | ok | `+interleaving` | claude-cli:sonnet@low | 25 | 1 |

## Scores per run

| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | S2 | likely_real | 37/41 | 5/31 | **59**/82 | 0.902 | 0.881 | 0.67 | 42 | 13 | 71 | 1517288/88955 | 0 | 811 / 15.2 / 805 |
| +interleaving/1@1 | S2 | not infeasible | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.67 | 49 | 13 | 71 | 1517288/88955 | 0 | 811 / 15.2 / 805 |
| +interleaving/1@1 | S1 | static only | 41/41 | 14/31 | **40**/82 | 1.000 | 0.745 | 0.71 | 68 | - | - | - | - | - / 15.2 / - |
| +interleaving/1@2 | S2 | likely_real | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.67 | 47 | 2 | 72 | 1524468/91009 | 0 | 844 / 15.2 / 837 |
| +interleaving/1@2 | S2 | not infeasible | 41/41 | 8/31 | **58**/82 | 1.000 | 0.837 | 0.67 | 48 | 2 | 72 | 1524468/91009 | 0 | 844 / 15.2 / 837 |
| +interleaving/1@2 | S1 | static only | 41/41 | 14/31 | **40**/82 | 1.000 | 0.745 | 0.71 | 68 | - | - | - | - | - / 15.2 / - |
| +interleaving/1@3 | S2 | likely_real | 41/41 | 7/31 | **61**/82 | 1.000 | 0.854 | 0.69 | 48 | 1 | 72 | 1550086/90823 | 0 | 819 / 15.2 / 812 |
| +interleaving/1@3 | S2 | not infeasible | 41/41 | 8/31 | **58**/82 | 1.000 | 0.837 | 0.69 | 48 | 1 | 72 | 1550086/90823 | 0 | 819 / 15.2 / 812 |
| +interleaving/1@3 | S1 | static only | 41/41 | 14/31 | **40**/82 | 1.000 | 0.745 | 0.71 | 68 | - | - | - | - | - / 15.2 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW | RWW |
| --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | likely_real | 22/23 | 6/8 | 6/6 | 3/4 |
| +interleaving/1@1 | not infeasible | 23/23 | 8/8 | 6/6 | 4/4 |
| +interleaving/1@1 | static only | 23/23 | 8/8 | 6/6 | 4/4 |
| +interleaving/1@2 | likely_real | 23/23 | 8/8 | 6/6 | 4/4 |
| +interleaving/1@2 | not infeasible | 23/23 | 8/8 | 6/6 | 4/4 |
| +interleaving/1@2 | static only | 23/23 | 8/8 | 6/6 | 4/4 |
| +interleaving/1@3 | likely_real | 23/23 | 8/8 | 6/6 | 4/4 |
| +interleaving/1@3 | not infeasible | 23/23 | 8/8 | 6/6 | 4/4 |
| +interleaving/1@3 | static only | 23/23 | 8/8 | 6/6 | 4/4 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | likely_real | 3 | 39.7 ± 2.3 [37.0–41.0] | 6.3 ± 1.2 [5.0–7.0] | 60.3 ± 1.2 [59.0–61.0] | 0.967 ± 0.056 [0.902–1.000] | 0.863 ± 0.015 [0.854–0.881] | 0.68 ± 0.01 [0.67–0.69] | 45.7 ± 3.2 [42.0–48.0] | 5.3 ± 6.7 [1.0–13.0] | 72 ± 1 [71–72] |
| `+interleaving` | not infeasible | 3 | 41.0 ± 0.0 [41.0–41.0] | 7.7 ± 0.6 [7.0–8.0] | 59.0 ± 1.7 [58.0–61.0] | 1.000 ± 0.000 [1.000–1.000] | 0.843 ± 0.010 [0.837–0.854] | 0.68 ± 0.01 [0.67–0.69] | 48.3 ± 0.6 [48.0–49.0] | 5.3 ± 6.7 [1.0–13.0] | 72 ± 1 [71–72] |
| `+interleaving` | static only | 3 | 41.0 ± 0.0 [41.0–41.0] | 14.0 ± 0.0 [14.0–14.0] | 40.0 ± 0.0 [40.0–40.0] | 1.000 ± 0.000 [1.000–1.000] | 0.745 ± 0.000 [0.745–0.745] | 0.71 ± 0.00 [0.71–0.71] | 68.0 ± 0.0 [68.0–68.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@2 | feasibility | 123 | 0.886 | 0.733 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@2 | bucket | 123 | 0.886 | 0.733 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@3 | feasibility | 123 | 0.878 | 0.711 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@3 | bucket | 123 | 0.878 | 0.711 |
| `+interleaving` | +interleaving/1@2 | +interleaving/1@3 | feasibility | 123 | 0.992 | 0.977 |
| `+interleaving` | +interleaving/1@2 | +interleaving/1@3 | bucket | 123 | 0.992 | 0.977 |

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

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +interleaving/1@1 | 3 | 1 | 13 | 7 | 2 | 5 |
| +interleaving/1@2 | 3 | 1 | 13 | 6 | 1 | 7 |
| +interleaving/1@3 | 3 | 1 | 13 | 6 | 1 | 7 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
