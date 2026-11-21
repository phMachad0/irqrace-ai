# Speed experiment — global pool and triage by variable (2026-11-21)

Two temporary versions of the tool, each changing one thing, against a baseline re-run the same
day on the same machine and the same frozen root. **n = 1 per variant.** Comparison table:
`summary.md` (`scripts/compare-speed-variants.py`).

| | |
| --- | --- |
| Static stages | `runs/frozen-20261121`, commit `6de9b4c` (PR #27 + `semana-9`), Linux; 53/53 bug points, 11/33 traps, 166 records — same set as M1 |
| Row, backend | `+racebench`, `claude-cli:sonnet` (`claude-sonnet-5-5`), default effort |
| Machine | Intel i3-1115G4, 4 cores, 19 GB; nothing else running except ~3 min of a static run during baseline cases 006–008 (stopped) |
| Runs | `../worktrees/runs-speed-20261121/<variant>/+racebench/1` (outside git) |

| Variant | What changed | Code |
| --- | --- | --- |
| `baseline` | nothing: cases in series, 4 conversations per case | `tcc/t3-model-speed` at `6de9b4c` |
| `pool` | cases run 4 at a time, largest first, 1 conversation each: one pool of 4 conversations for the whole suite | `tmp-pool.patch` (`bench_batch.run_pair(case_parallel=)`, `--case-parallel`) |
| `by-variable` | one checklist conversation per shared variable (≤ 20 triples), feasibility and harmfulness still separate; cases in series, 4 conversations per case | `tmp-var.patch` (`irqrace.llm.checklist`, asset `prompts/checklist.md`, `llm triage --by-variable`) |

## Results

| | `baseline` | `pool` | `by-variable` |
| --- | --- | --- | --- |
| Bug points in `likely_real` | 53/53 | 53/53 | 53/53 |
| Bug points called infeasible | 0 | 0 | 0 |
| Traps in `likely_real` | 2 | 3 | 3 |
| Not triaged (kept `uncertain`) | 1 (refusal) | 1 (refusal) | 0 |
| NASAC score /106 | 100 | 97 | 97 |
| Inspection Ratio | 0.68 | 0.66 | 0.64 |
| Calls | 304 | 304 | **84** |
| Input tokens (incl. cache) | 3,453,796 | 3,455,050 | **1,933,473** |
| Output tokens | 278,140 | 277,782 | **125,513** |
| Sum of call latencies (s) | 3,120 | 3,335 | **1,108** |
| Wall time, triage (s) | 1,079 | 979 | 858 |
| Mean concurrency (latency sum / wall) | 2.89 | 3.41 | 1.29 |
| Annotated items in the baseline's bucket | 86/86 | 85/86 | 84/86 |

Items that changed bucket against the baseline:
- `pool` and `by-variable`: `svp_simple_009_001` `trap#1` (`W37 R47 W38`) `uncertain` → `likely_real`.
  This item is unstable in every series measured so far (M1 `+racebench+c4`: `likely_infeasible`,
  `likely_real`, `uncertain`; M3 `+effectfree`: `likely_real`), so one flip in n = 1 is not
  evidence about either change.
- `by-variable`: `svp_simple_022_001` `trap#2` (`R55 W66 W56`) `uncertain` → `likely_infeasible`.
  In the baseline it was the refused candidate (not triaged); the checklist conversation for that
  variable drew no refusal.

No checklist answer was rejected (no id answered twice or unknown) and none left an item out.

## Reading it

- **By variable cuts the model's work by about two thirds** — calls −72%, input −44%, output −55%,
  sum of latencies −64% — with recall intact and the score inside the ±3 band M1 established.
  Its wall time fell only 20%, because cases still run in series and most have one or two
  variables: mean concurrency 1.29 of 4.
- **The pool raises concurrency** (2.89 → 3.41) and wall time fell 9%. One call in case 014 stalled
  for roughly four minutes (335 s for 4 calls, against 22 s and 23 s in the other two runs), which
  is most of the pool's added latency and its tail; with n = 1 that cannot be separated from the
  pool itself.
- **The two compose.** By-variable leaves the slots idle and the pool fills them. Not measured: a
  combined run is the next measurement.
