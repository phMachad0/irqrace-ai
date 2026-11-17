# Racebench runs — scored

Label set `53/33` (racebench 2.1_remarks as vendored (relabel 2026-10-28) + curated errata: 53 bug points, 33 traps). Case subset `bmc4av-25-noRWW` (25 cases), patterns excluded: RWW. Scorer `bench_metrics/1.0.0`.

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
| +racebench/1 | S2 | likely_real | 42/42 | 2/25 | **78**/84 | 1.000 | 0.955 | 0.71 | 45 | 0 | 201 | - | 0 | 739 / 118.0 / 726 |
| +racebench/1 | S2 | not infeasible | 42/42 | 2/25 | **78**/84 | 1.000 | 0.955 | 0.71 | 45 | 0 | 201 | - | 0 | 739 / 118.0 / 726 |
| +racebench/1 | S1 | static only | 42/42 | 8/25 | **60**/84 | 1.000 | 0.840 | 0.75 | 62 | - | - | - | - | - / 118.0 / - |
| +racebench/2 | S2 | likely_real | 42/42 | 2/25 | **78**/84 | 1.000 | 0.955 | 0.75 | 45 | 1 | 202 | - | 0 | 771 / 118.0 / 758 |
| +racebench/2 | S2 | not infeasible | 42/42 | 2/25 | **78**/84 | 1.000 | 0.955 | 0.75 | 46 | 1 | 202 | - | 0 | 771 / 118.0 / 758 |
| +racebench/2 | S1 | static only | 42/42 | 8/25 | **60**/84 | 1.000 | 0.840 | 0.75 | 62 | - | - | - | - | - / 118.0 / - |
| +racebench/3 | S2 | likely_real | 42/42 | 2/25 | **78**/84 | 1.000 | 0.955 | 0.73 | 44 | 1 | 199 | - | 1 | 739 / 118.0 / 727 |
| +racebench/3 | S2 | not infeasible | 42/42 | 2/25 | **78**/84 | 1.000 | 0.955 | 0.73 | 45 | 1 | 199 | - | 1 | 739 / 118.0 / 727 |
| +racebench/3 | S1 | static only | 42/42 | 8/25 | **60**/84 | 1.000 | 0.840 | 0.75 | 62 | - | - | - | - | - / 118.0 / - |

## Recall per access pattern (bug points detected / annotated)

| run | reported = | RWR | WWR | WRW |
| --- | --- | --- | --- | --- |
| +racebench/1 | likely_real | 27/27 | 8/8 | 7/7 |
| +racebench/1 | not infeasible | 27/27 | 8/8 | 7/7 |
| +racebench/1 | static only | 27/27 | 8/8 | 7/7 |
| +racebench/2 | likely_real | 27/27 | 8/8 | 7/7 |
| +racebench/2 | not infeasible | 27/27 | 8/8 | 7/7 |
| +racebench/2 | static only | 27/27 | 8/8 | 7/7 |
| +racebench/3 | likely_real | 27/27 | 8/8 | 7/7 |
| +racebench/3 | not infeasible | 27/27 | 8/8 | 7/7 |
| +racebench/3 | static only | 27/27 | 8/8 | 7/7 |

## Spread over independent runs (mean ± sample sd [min–max])

| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | uncertain | calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | likely_real | 3 | 42.0 ± 0.0 [42.0–42.0] | 2.0 ± 0.0 [2.0–2.0] | 78.0 ± 0.0 [78.0–78.0] | 1.000 ± 0.000 [1.000–1.000] | 0.955 ± 0.000 [0.955–0.955] | 0.73 ± 0.02 [0.71–0.75] | 44.7 ± 0.6 [44.0–45.0] | 0.7 ± 0.6 [0.0–1.0] | 201 ± 2 [199–202] |
| `+racebench` | not infeasible | 3 | 42.0 ± 0.0 [42.0–42.0] | 2.0 ± 0.0 [2.0–2.0] | 78.0 ± 0.0 [78.0–78.0] | 1.000 ± 0.000 [1.000–1.000] | 0.955 ± 0.000 [0.955–0.955] | 0.73 ± 0.02 [0.71–0.75] | 45.3 ± 0.6 [45.0–46.0] | 0.7 ± 0.6 [0.0–1.0] | 201 ± 2 [199–202] |
| `+racebench` | static only | 3 | 42.0 ± 0.0 [42.0–42.0] | 8.0 ± 0.0 [8.0–8.0] | 60.0 ± 0.0 [60.0–60.0] | 1.000 ± 0.000 [1.000–1.000] | 0.840 ± 0.000 [0.840–0.840] | 0.75 ± 0.00 [0.75–0.75] | 62.0 ± 0.0 [62.0–62.0] | - | - |

## Agreement between runs of one prompt row

Over the candidates both runs reached the LLM with and answered.

| prompt row | run A | run B | field | shared | agreement | Cohen's κ |
| --- | --- | --- | --- | --- | --- | --- |
| `+racebench` | +racebench/1 | +racebench/2 | feasibility | 112 | 0.991 | 0.973 |
| `+racebench` | +racebench/1 | +racebench/2 | bucket | 112 | 0.991 | 0.973 |
| `+racebench` | +racebench/1 | +racebench/3 | feasibility | 111 | 0.991 | 0.972 |
| `+racebench` | +racebench/1 | +racebench/3 | bucket | 111 | 0.991 | 0.972 |
| `+racebench` | +racebench/2 | +racebench/3 | feasibility | 111 | 0.982 | 0.945 |
| `+racebench` | +racebench/2 | +racebench/3 | bucket | 111 | 0.982 | 0.945 |

## Labelled items whose verdict flips across runs

None: every bug point and trap got the same bucket and feasibility in every run.

## Trap disposition

| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |
| --- | --- | --- | --- | --- | --- | --- |
| +racebench/1 | 3 | 1 | 13 | 6 | 0 | 2 |
| +racebench/2 | 3 | 1 | 13 | 6 | 0 | 2 |
| +racebench/3 | 3 | 1 | 13 | 6 | 0 | 2 |

## Bug points the LLM called infeasible (recall loss of the triage)

None.
