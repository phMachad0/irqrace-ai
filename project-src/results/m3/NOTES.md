# M3 (T3) — the two prompt-variant runs Lucas completed, scored 2026-11-21

Lucas ran the T3 variants on 2026-11-17 and shared the raw runs (`runs_lucas/m3-20261117/`), but
did not score them. They were scored here, unchanged, with
`scripts/bench-triage-report.py <pair> ... --results results/m3`. Per-case tokens are in
`tokens-per-case.csv` (`scripts/spend-per-case.py`).

**This is not gate M3.** n = 1 per row, against the protocol's n = 3, and only two of the five
variants finished.

| | |
| --- | --- |
| Static stages | `runs/frozen-20261115` (Lucas, commit `a639158`): the same frozen root as M1 |
| Triaged with | commit `a4a1ff7` (`tcc/t3-measure`), `claude-cli:sonnet`, 4 conversations per case |
| Labels | 53/33 |

## What ran

| Row | Pairs | Outcome |
| --- | --- | --- |
| `+racebench+rubric` | 1 | ok, 2026-11-17 03:33–03:52 UTC |
| `+racebench+effectfree` | 1 | ok, 2026-11-17 07:53 UTC (one earlier attempt lost to the rate limit, moved aside) |
| `+racebench-selfval` | 0 | **13 attempts, all failed** on the subscription's rate limit between 05:18 and 14:42 UTC (`runs_lucas/m3-20261117-failed/`). Every case exits 1 in the later attempts: a retry loop running into the 5-hour window |
| `+racebench+witness`, `+racebench+location` | 0 | never started |

## Results (`likely_real`, n = 1), next to M1's baseline

| | M1 `+racebench` (n = 3) | `+rubric` | `+effectfree` |
| --- | --- | --- | --- |
| Bug points | 53/53 | 53/53 | 53/53 |
| Bug points called infeasible | 0 | 0 | 0 |
| Traps in `likely_real` | 2, 2, 2 | 2 | **1** |
| NASAC score /106 | 100 | 100 | **103** |
| Precision | 0.964 | 0.964 | 0.981 |
| Inspection Ratio | 0.69 ± 0.02 | 0.65 | 0.68 |
| Calls | 302–305 | 307 | 305 |
| Input tokens (incl. cache) | 3.49–3.55 M | 3.74 M | 3.56 M |
| Output tokens | 295–296 k | 384 k | 353 k |
| Sum of call latencies | 2,809–2,866 s | 3,371 s | 3,260 s |
| Wall time | 978–1,016 s | 1,172 s | 1,140 s |

Which traps:
- `+rubric` keeps case 022's `trap#1` and `trap#3`, the two systematic ones of M1.
- `+effectfree` removes both 022 traps — the ones it was written for — but reports one M1 never
  `+racebench` never put in `likely_real`: `svp_simple_009_001` `trap#1` (`W37 R47 W38`, WRW,
  feasible, conf 0.72). In M1 it was `likely_infeasible` in all three `+racebench` runs, and in
  `+racebench+c4` it went `likely_infeasible`, `likely_real`, `uncertain`: an unstable item. With
  n = 1 this is one draw; it is the item to watch in the n = 3 runs.

The effect-free rule exists to measure its recall cost ([[Lucas Tasks]] T3). On this run the cost
is zero: no bug point left `likely_real`. That is one run, not the measurement.
