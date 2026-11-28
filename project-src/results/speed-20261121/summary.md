| | `baseline` | `pool` | `by-variable` | `low-baseline` | `low-combo` | `low-combo-retry` |
| --- | --- | --- | --- | --- | --- | --- |
| Bug points in `likely_real` | 53/53 | 53/53 | 53/53 | 52/53 | 47/53 | 53/53 |
| Bug points called infeasible | 0 | 0 | 0 | 0 | 0 | 0 |
| Traps in `likely_real` | 2 | 3 | 3 | 3 | 0 | 3 |
| Uncertain (not triaged) | 1 | 1 | 0 | 0 | 16 | 0 |
| NASAC score /106 | 100 | 97 | 97 | 95 | 94 | 97 |
| Inspection Ratio | 0.68 | 0.66 | 0.64 | 0.68 | 0.64 | 0.65 |
| Calls | 304 | 304 | 84 | 307 | 83 | 84 |
| Input tokens (incl. cache) | 3,453,796 | 3,455,050 | 1,933,473 | 3,499,399 | 1,966,515 | 2,024,827 |
| Output tokens | 278,140 | 277,782 | 125,513 | 248,746 | 110,130 | 113,127 |
| Sum of call latencies (s) | 3,120 | 3,335 | 1,108 | 2,862 | 986 | 1,015 |
| Wall time, triage (s) | 1,079 | 979 | 858 | 984 | 257 | 263 |
| Mean concurrency | 2.89 | 3.41 | 1.29 | 2.91 | 3.83 | 3.86 |
| Items with the baseline's bucket | 86/86 | 85/86 | 84/86 | 82/86 | 77/86 | 84/86 |

**`pool` vs `baseline`: 1 annotated item(s) changed bucket.**
- svp_simple_009_001 trap#1 (trap, W37 R47 W38): uncertain -> likely_real

**`by-variable` vs `baseline`: 2 annotated item(s) changed bucket.**
- svp_simple_009_001 trap#1 (trap, W37 R47 W38): uncertain -> likely_real
- svp_simple_022_001 trap#2 (trap, R55 W66 W56): uncertain -> likely_infeasible

**`low-baseline` vs `baseline`: 4 annotated item(s) changed bucket.**
- svp_simple_007_001 trap#1 (trap, W32 W50 R34): likely_infeasible -> likely_real
- svp_simple_009_001 trap#1 (trap, W37 R47 W38): uncertain -> likely_infeasible
- svp_simple_022_001 trap#2 (trap, R55 W66 W56): uncertain -> likely_infeasible
- svp_simple_024_001 bug#1 (bug, R56 W63 R57): likely_real -> uncertain

**`low-combo` vs `baseline`: 9 annotated item(s) changed bucket.**
- svp_simple_019_001 bug#1 (bug, R45 W71 R59): likely_real -> uncertain
- svp_simple_019_001 bug#3 (bug, R51 W71 R59): likely_real -> uncertain
- svp_simple_022_001 bug#1 (bug, W32 W66 R55): likely_real -> uncertain
- svp_simple_022_001 bug#2 (bug, R55 W66 W58): likely_real -> uncertain
- svp_simple_022_001 bug#3 (bug, W58 W66 R63): likely_real -> uncertain
- svp_simple_022_001 bug#4 (bug, R63 W66 R39): likely_real -> uncertain
- svp_simple_022_001 trap#1 (trap, W32 W66 R39): likely_real -> uncertain
- svp_simple_022_001 trap#2 (trap, R55 W66 W56): uncertain -> likely_infeasible
- svp_simple_022_001 trap#3 (trap, R55 W66 R63): likely_real -> uncertain

**`low-combo-retry` vs `baseline`: 2 annotated item(s) changed bucket.**
- svp_simple_009_001 trap#1 (trap, W37 R47 W38): uncertain -> likely_real
- svp_simple_022_001 trap#2 (trap, R55 W66 W56): uncertain -> likely_infeasible

