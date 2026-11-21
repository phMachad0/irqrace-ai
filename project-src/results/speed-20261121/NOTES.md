# Speed experiment — global pool and triage by variable (2026-11-21)

Temporary versions of the tool, each changing one thing (the second batch combines two), against a baseline re-run the same
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
- **The two compose.** By-variable leaves the slots idle and the pool fills them: measured in the
  second batch below.

## Second batch: Sonnet at low effort, pool + by variable combined (same day)

Pedro's direction (2026-11-21): continue with `sonnet@low`. Three more runs on the same frozen
root, n = 1 each, `claude-cli:sonnet@low`:

| Variant | What changed | Code |
| --- | --- | --- |
| `low-baseline` | the baseline at low effort | `tcc/t3-model-speed` (`88550d2`, effort suffix) |
| `low-combo` | by variable **and** the pool (4 cases at a time, 1 conversation each) | `tmp-combo.patch` without its last hunk |
| `low-combo-retry` | the same, and an item a checklist answer leaves out is asked on its own, once | `tmp-combo.patch` |

| | `baseline` (default effort) | `low-baseline` | `low-combo` | `low-combo-retry` |
| --- | --- | --- | --- | --- |
| Bug points in `likely_real` | 53/53 | 52/53 | 47/53 | **53/53** |
| Bug points called infeasible | 0 | 0 | 0 | 0 |
| Traps in `likely_real` | 2 | 3 | 0 | 3 |
| Not triaged (kept `uncertain`) | 1 | 0 | **16** | 0 |
| NASAC score /106 | 100 | 95 | 94 | 97 |
| Inspection Ratio | 0.68 | 0.68 | 0.64 | 0.65 |
| Calls | 304 | 307 | 83 | 84 |
| Input tokens (incl. cache) | 3,453,796 | 3,499,399 | 1,966,515 | 2,024,827 |
| Output tokens | 278,140 | 248,746 | 110,130 | 113,127 |
| Sum of call latencies (s) | 3,120 | 2,862 | 986 | 1,015 |
| Wall time, triage (s) | 1,079 | 984 | 257 | **263** |
| Mean concurrency | 2.89 | 2.91 | 3.83 | 3.86 |

- **Low effort alone changes little**: output −11%, wall −9%; one bug point (`024` bug#1) went
  `uncertain`, and `007` trap#1 rose to `likely_real`.
- **`low-combo` found a failure of the checklist.** For `svp_simple_022_001` (15 triples on one
  variable) the feasibility answer stated three shared findings and then answered **one** item of 15;
  for `019` it answered 2 of 4. The completeness check did its job — the 16 left out stayed in the
  report as `uncertain` with the reason, none was dropped — but 6 bug points left `likely_real`, and
  the 0 traps is an artefact of the omissions (022's traps were among them). The default-effort
  by-variable run answered every item, so low effort is the likely cause; the two are not separated.
- **`low-combo-retry` adds the fix**: an omitted item is asked in its own conversation, as the baseline
  does. In this run the model answered every item, so the retry never fired (84 calls, 84 requests in
  the spend lines): the fix is in place but untested on a real omission.
- **The combination is about 4× faster than the baseline** (1,079 → 263 s), with 41% less input and
  59% less output, recall intact, and the score inside M1's ±3 band.

Caveat on the retry: an omitted item that is the group's lead would have its checklist transcript
overwritten by its own conversation (`llm/<lead>/turns.jsonl`), which undercounts `llm_calls`; the
spend lines are unaffected. Not hit in this run.
