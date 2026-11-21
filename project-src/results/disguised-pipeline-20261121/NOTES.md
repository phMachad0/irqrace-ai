# irqrace and the scan on the same disguised Racebench (2026-11-21)

The comparison `contamination-20261121` left open: irqrace's triage had only run on the original
names, and its triage reads names too. Here the **whole pipeline** and the scan run on the **same
disguised files**, n = 3 per arm, `claude-cli:sonnet@low`.

## The copy

`scripts/racebench-disguise.py --seed 2026 --compilable` (regenerates identically; it was not
deterministic before this commit, see below). Same disguise as `contamination-20261121` —
comments and header removed, identifiers neutral, cases `program_NN`, functions reordered so
all 258 annotated lines move — plus one prototype per function so the reordered files compile,
`common.c` without comments, and a C1 config per program (`configs/`), identical to the case's
own except the subject name, sources, flow entries and no `ground_truth` block. The copy is
outside git; `disguise-index.json` says which program is which case.

## What ran

| Arm | Code | Runs |
| --- | --- | --- |
| irqrace, original | `tmp-combo.patch` (pool + by variable + omission retry), static stages frozen in `runs/frozen-20261121` | run 1 is `speed-20261121/low-combo-retry`; runs 2, 3 here (`scores/tool-original-*`) |
| irqrace, disguised | the same, static stages frozen on the disguised configs | 3 (`tool-disguised-*`: batch, timings, case logs) |
| scan, disguised, per file / one prompt | `scripts/scan-measure.py --suite` on the same copy | 3 each (`scan-disguised-*`) |

Arms interleaved. The first attempt at irqrace disguised run 2 lost two large checklist groups
(`program_07`, `program_15`) to `claude -p` timing out after 600 s; following M1's rule for backend
incidents, the pair was moved aside (`tool-disguised-2-timeout.batch.json`) and re-run whole.

Scoring: the native scorer for the original runs; `scripts/score-disguised-run.py` for the
disguised ones, which maps every record's lines back through the copy's `line_map` and uses the
same matcher (`irqrace.evaluation.match_subject`).

## Static stages

Identical on both copies: 316 → 202 → **166** records, **53/53** bug points, 11/33 traps,
score 73. The static analysis does not depend on names, comments or function order.

## Results (min–max over three runs, `likely_real`)

| | irqrace, original | **irqrace, disguised** | scan per file, disguised | scan one prompt, disguised |
| --- | --- | --- | --- | --- |
| Bug points in `likely_real` (53/33) | 52–53 | **51–52** | 48–52 found | 46–52 found |
| Bug points kept in the report | 53 | 53 | — | — |
| Bug points called infeasible | 0 | **1** (`010` bug#1, all three runs) | — | — |
| Traps in `likely_real` | 3–4 | **3–4** | 6–10 | 3–4 |
| NASAC score /106 | 94–97 | **90–95** | 70–86 | 80–95 |
| Bug points (48/38) | 47–48 | 46–47 | 44–48 | 43–48 |
| Traps (48/38) | 8–9 | 8–9 | 10–15 | 5–7 |
| Unannotated in `likely_real` / findings | 82–85 | 80–84 | 21–30 | 6–10 |
| Calls | 83–84 | 82–87 | 31 | 1 |
| Input tokens | 1.85–2.02 M | 1.69–1.75 M | 75–79 k | 18.6 k |
| Output tokens | 108–113 k | 109–112 k | 26–28 k | 13–15 k |
| Wall time | 259–264 s | 251–257 s | 68–75 s | 83–97 s |

Traps irqrace reports on the disguised copy: `022` trap#1 and trap#3 in all runs (the two M1
found systematic), `022` trap#2 twice, `009` trap#1 twice — the same items as on the original.

## Reading it

1. **irqrace's precision does not depend on the names.** Traps in `likely_real` stay at 3–4 on
   the disguised copy, and they are the same traps. The scan's do not: 1–4 on the original
   (`contamination-20261121`) against 6–10 here per file.
2. **irqrace's triage does lean on names once, and it is a recall-veto event.** `010` bug#1 is a
   write to `.header`, a read of `.header` and a write to `.data` of a **union**. On the original
   the variable is called `global_union`, and every run puts it in `likely_real` (0.93). Disguised,
   it is `v_ridge` of type `v_juniper`, still declared `typedef union pack1` on line 2, and all
   three runs call it infeasible: "different struct fields and so different memory locations".
   The `+racebench` semantics asset states that union members overlap; the model did not apply it
   without the name. The candidate stays in the report (triage drops nothing), but in the
   `likely_infeasible` bucket. By the T3 protocol's veto, this configuration fails on the disguised
   copy. The fix belongs in the context record: the static stage knows the declared type is a
   union and could say so (`variable.declared_type` reads `volatile v_juniper` today).
3. **Against the scan, on equal terms.** irqrace keeps every bug point in the report and 51–52 at
   the top, scoring 90–95; the per-file scan finds 48–52 and scores 70–86. The one-prompt scan
   scores 80–95 with fewer traps but finds 46–52, so 1–7 bug points per run are simply absent. The
   scan costs 20–100× less input.
4. **Copy A and copy B.** `contamination-20261121` used a disguise whose names depended on Python's
   hash seed (not reproducible). Its per-file results (50–51 bug points, 6–8 traps) agree with this
   copy's (48–52, 6–10).
