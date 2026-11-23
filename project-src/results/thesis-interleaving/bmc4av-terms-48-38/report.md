# Racebench runs — scored

Label set `48/38` (racebench 2.1_remarks before the 2026-10-28 relabel (five bug points back to traps; the labels every pre-relabel number and BMC4AV's re-basing use): 48 bug points, 38 traps). Case subset `cases=25;exclude=RWW` (25 cases), patterns excluded: RWW. Scorer `bench_metrics/1.0.0`.

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
| +interleaving/1@1 | S2 | likely_real | 34/37 | 5/30 | **53**/74 | 0.919 | 0.872 | 0.68 | 38 | 12 | 69 | - | 0 | 811 / 15.2 / 805 |
| +interleaving/1@1 | S2 | not infeasible | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.68 | 45 | 12 | 69 | - | 0 | 811 / 15.2 / 805 |
| +interleaving/1@1 | S1 | static only | 37/37 | 13/30 | **35**/74 | 1.000 | 0.740 | 0.71 | 62 | - | - | - | - | - / 15.2 / - |
| +interleaving/1@2 | S2 | likely_real | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.67 | 43 | 2 | 70 | - | 0 | 844 / 15.2 / 837 |
| +interleaving/1@2 | S2 | not infeasible | 37/37 | 8/30 | **50**/74 | 1.000 | 0.822 | 0.67 | 44 | 2 | 70 | - | 0 | 844 / 15.2 / 837 |
| +interleaving/1@2 | S1 | static only | 37/37 | 13/30 | **35**/74 | 1.000 | 0.740 | 0.71 | 62 | - | - | - | - | - / 15.2 / - |
| +interleaving/1@3 | S2 | likely_real | 37/37 | 7/30 | **53**/74 | 1.000 | 0.841 | 0.69 | 44 | 1 | 70 | - | 0 | 819 / 15.2 / 812 |
| +interleaving/1@3 | S2 | not infeasible | 37/37 | 8/30 | **50**/74 | 1.000 | 0.822 | 0.69 | 44 | 1 | 70 | - | 0 | 819 / 15.2 / 812 |
| +interleaving/1@3 | S1 | static only | 37/37 | 13/30 | **35**/74 | 1.000 | 0.740 | 0.71 | 62 | - | - | - | - | - / 15.2 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW |
| --- | --- | --- | --- | --- |
| +interleaving/1@1 | likely_real | 22/23 | 6/8 | 6/6 |
| +interleaving/1@1 | not infeasible | 23/23 | 8/8 | 6/6 |
| +interleaving/1@1 | static only | 23/23 | 8/8 | 6/6 |
| +interleaving/1@2 | likely_real | 23/23 | 8/8 | 6/6 |
| +interleaving/1@2 | not infeasible | 23/23 | 8/8 | 6/6 |
| +interleaving/1@2 | static only | 23/23 | 8/8 | 6/6 |
| +interleaving/1@3 | likely_real | 23/23 | 8/8 | 6/6 |
| +interleaving/1@3 | not infeasible | 23/23 | 8/8 | 6/6 |
| +interleaving/1@3 | static only | 23/23 | 8/8 | 6/6 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | likely_real | 3 | 36.0 ± 1.7 [34.0–37.0] | 6.3 ± 1.2 [5.0–7.0] | 53.0 ± 0.0 [53.0–53.0] | 0.973 ± 0.047 [0.919–1.000] | 0.851 ± 0.018 [0.841–0.872] | 0.68 ± 0.01 [0.67–0.69] | 41.7 ± 3.2 [38.0–44.0] | 5.0 ± 6.1 [1.0–12.0] | 70 ± 1 [69–70] |
| `+interleaving` | not infeasible | 3 | 37.0 ± 0.0 [37.0–37.0] | 7.7 ± 0.6 [7.0–8.0] | 51.0 ± 1.7 [50.0–53.0] | 1.000 ± 0.000 [1.000–1.000] | 0.828 ± 0.011 [0.822–0.841] | 0.68 ± 0.01 [0.67–0.69] | 44.3 ± 0.6 [44.0–45.0] | 5.0 ± 6.1 [1.0–12.0] | 70 ± 1 [69–70] |
| `+interleaving` | static only | 3 | 37.0 ± 0.0 [37.0–37.0] | 13.0 ± 0.0 [13.0–13.0] | 35.0 ± 0.0 [35.0–35.0] | 1.000 ± 0.000 [1.000–1.000] | 0.740 ± 0.000 [0.740–0.740] | 0.71 ± 0.00 [0.71–0.71] | 62.0 ± 0.0 [62.0–62.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@2 | feasibility | 112 | 0.884 | 0.725 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@2 | bucket | 112 | 0.884 | 0.725 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@3 | feasibility | 112 | 0.875 | 0.700 |
| `+interleaving` | +interleaving/1@1 | +interleaving/1@3 | bucket | 112 | 0.875 | 0.700 |
| `+interleaving` | +interleaving/1@2 | +interleaving/1@3 | feasibility | 112 | 0.991 | 0.974 |
| `+interleaving` | +interleaving/1@2 | +interleaving/1@3 | bucket | 112 | 0.991 | 0.974 |

## Labelled items whose verdict flips across runs

| prompt row | case | item | triple | field | per run |
| --- | --- | --- | --- | --- | --- |
| `+interleaving` | 009 | trap#1 | W37 R47 W38 | bucket | +interleaving/1@1: likely_infeasible, +interleaving/1@2: uncertain, +interleaving/1@3: uncertain |
| `+interleaving` | 009 | trap#1 | W37 R47 W38 | feasibility | +interleaving/1@1: infeasible, +interleaving/1@2: uncertain, +interleaving/1@3: uncertain |
| `+interleaving` | 022 | bug#1 | W32 W66 R55 | bucket | +interleaving/1@1: uncertain, +interleaving/1@2: likely_real, +interleaving/1@3: likely_real |
| `+interleaving` | 022 | bug#1 | W32 W66 R55 | feasibility | +interleaving/1@1: uncertain, +interleaving/1@2: feasible, +interleaving/1@3: feasible |
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
| +interleaving/1@1 | 3 | 1 | 13 | 6 | 2 | 5 |
| +interleaving/1@2 | 3 | 1 | 13 | 5 | 1 | 7 |
| +interleaving/1@3 | 3 | 1 | 13 | 5 | 1 | 7 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
