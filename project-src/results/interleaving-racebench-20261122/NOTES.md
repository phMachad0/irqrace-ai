# `+interleaving` on Racebench, original and disguised (2026-11-22)

Does the generic row (`+interleaving`, commit `c3665e5`: the Racebench defect notion, the execution
model read from the record) do on Racebench what `+racebench` does? If so, one prompt serves both
suites. **n = 3 per arm**, `claude-cli:sonnet@low`, pool + by variable + omission retry
(`realworld-cmp2-20261121/tmp-combo.patch`), the same frozen roots as before: the original
(`runs/frozen-20261121`) and the disguised copy B (`runs-disguised-20261121/frozen`). Scored with
the native scorer (original) and `score-disguised-run.py` (disguised).

One difference in model, not in wording: Racebench's C1 configs say
`equal_priority_preemption: true`. `+racebench` overrides that in its text ("equal priority does not
preempt"); `+interleaving` follows the record, so it allows equal-priority preemption here.

## Incidents

- The first attempt failed before any call: the main checkout's venv had been recreated at 13:33
  with `python3` linked to a PlatformIO interpreter that no longer existed. The runs moved to a venv
  of their own (`../worktrees/.venv-irqrace`: pyyaml, jsonschema, pydantic 2.14, pytest; 130 triage
  tests pass on it). Attempt kept in `runs-interleaving-rb-20261122/failed-venv/`, outside git.
- Run 1 of both arms then lost large checklist groups to `claude -p` timing out at 1,200 s
  (`original-1-timeout.batch.json`, `disguised-1-timeout.batch.json`); per M1's rule both pairs were
  moved aside and re-run whole.

## Results (`likely_real`, min–max over three runs)

| | `+racebench` original | **`+interleaving` original** | `+racebench` disguised | **`+interleaving` disguised** |
| --- | --- | --- | --- | --- |
| Bug points on top (53/33) | 52–53 | 49–53 | 51–52 | 51–52 |
| **Bug points called infeasible** | 0 | **0** | **1** (`010` bug#1, 3 of 3) | **0** |
| Traps on top | 3–4 | 0–3 | 3–4 | 2–3 |
| NASAC score /106 | 94–97 | 97–98 | 90–95 | 95–98 |
| Bug points (48/38) | 47–48 | 44–48 | 46–47 | 46–47 |
| Traps (48/38) | 8–9 | 5–8 | 8–9 | 7–8 |
| Unannotated on top | 82–85 | 76–82 | 80–84 | 81–82 |
| Calls | 83–84 | 83–84 | 82–87 | 83 |
| Input tokens | 1.85–2.02 M | 1.96–2.06 M | 1.69–1.75 M | 1.75–1.86 M |
| Wall time | 259–264 s | 250–261 s | 251–257 s | 260–261 s |

`+racebench` columns: `speed-20261121/low-combo-retry` and `disguised-pipeline-20261121`.

- Original: runs 2 and 3 are 53/53 with `022` trap#1, trap#3 and `030` trap#1 on top. Run 1 put case
  022's whole variable — its four bug points and two of its traps — in `uncertain` at 0.6, a real
  answer rather than an omission; nothing was called infeasible.
- Disguised: `010` bug#1, the union whose name the disguise removes, is `uncertain` in all three runs
  instead of `likely_infeasible`; `027` bug#2 is `uncertain` once.

## Reading it

1. **One generic row serves both suites.** On Racebench, `+interleaving` scores as well as the
   row written for it (97–98 against 94–97 on the original, 95–98 against 90–95 disguised) at the
   same cost, and on the real-world suite it put all 45 entries on top (`realworld-cmp2-20261121`).
2. **The recall-veto event is gone.** No bug point is `likely_infeasible` in any of the six runs.
   The typedef rule moved the disguised union from infeasible to uncertain; it does not yet put it on
   top, so the context record stating the resolved type remains worth doing.
3. **Following the configs' equal-priority setting did not cost precision here.** Traps on top
   stayed at 0–3, no more than under `+racebench`'s override.
4. n = 3 with one run per arm repeated after timeouts; the original arm's spread (49–53) comes from
   one run's answer on case 022.
