| | `baseline` | `pool` | `by-variable` |
| --- | --- | --- | --- |
| Bug points in `likely_real` | 53/53 | 53/53 | 53/53 |
| Bug points called infeasible | 0 | 0 | 0 |
| Traps in `likely_real` | 2 | 3 | 3 |
| Uncertain (not triaged) | 1 | 1 | 0 |
| NASAC score /106 | 100 | 97 | 97 |
| Inspection Ratio | 0.68 | 0.66 | 0.64 |
| Calls | 304 | 304 | 84 |
| Input tokens (incl. cache) | 3,453,796 | 3,455,050 | 1,933,473 |
| Output tokens | 278,140 | 277,782 | 125,513 |
| Sum of call latencies (s) | 3,120 | 3,335 | 1,108 |
| Wall time, triage (s) | 1,079 | 979 | 858 |
| Mean concurrency | 2.89 | 3.41 | 1.29 |
| Items with the baseline's bucket | 86/86 | 85/86 | 84/86 |

**`pool` vs `baseline`: 1 annotated item(s) changed bucket.**
- svp_simple_009_001 trap#1 (trap, W37 R47 W38): uncertain -> likely_real

**`by-variable` vs `baseline`: 2 annotated item(s) changed bucket.**
- svp_simple_009_001 trap#1 (trap, W37 R47 W38): uncertain -> likely_real
- svp_simple_022_001 trap#2 (trap, R55 W66 W56): uncertain -> likely_infeasible

