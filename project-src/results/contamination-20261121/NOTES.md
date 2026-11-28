# Contamination test — the scan on a disguised copy of Racebench (2026-11-21)

Question ([[Open Questions]], 2026-11-21): did the LLM-only scan of `scan-measure-20261121` do well
because the model remembers Racebench? Racebench has been public on GitHub since 2019, with its
answers in the `2.1_remarks` comments.

**n = 3 per arm**, `claude-cli:sonnet@low` (`claude-sonnet-5-5`), the same prompt and scorer as
`scan-measure-20261121` (`scripts/scan-measure.py`). The first original run of each mode is the
one in `scan-measure-20261121`; runs 2 and 3 are here. Arms were interleaved (disguised 1,
disguised 2, original 2, disguised 3, original 3), all on the same day.

## The disguised copy

`scripts/racebench-disguise.py --seed 2026` (the copy itself is not in git; `disguise-index.json`
lists which program is which case). **Correction, same day:** this first copy ("copy A") was not
reproducible after all — the order in which names were assigned depended on Python's hash seed.
The script is deterministic since the next commit; `disguised-pipeline-20261121` reruns the scan on
the deterministic copy B, with results that agree with these.

- the header comment (suite name, company, dates, the Chinese notes), every other comment and the
  trailing answer block are removed; `common.h` loses its comments too;
- every `svp_simple_NNN_NNN_<name>` identifier becomes a neutral one per case (`v_timber`,
  `fn_cedar`, `irq_lantern`, `task_anchor`), and the cases become `program_NN` in shuffled order;
- the top-level function definitions are reordered, so every line moves. All 258 annotated
  access lines moved; a `line_map` maps each new line back, and findings are scored against the
  original annotations with the same matcher. No occurrence of `svp`, `racebench`, `sunwise`,
  `bug`, `误报` or `说明` is left in any file.

The flows (entry, ISR or task, priority, IRQ) are given under the new names, as before.

## A direct recall probe

`scan-measure.py recall`: no source at all, only "what are the annotated bug points of
`svp_simple_NNN_001.c` in Racebench 2.1_remarks?", one call per case. **31 of 31 answers were
empty.** A model that declines is not proof of no memory, but no line triple came back.

## Results (min–max over three runs)

| | original, per file | **disguised, per file** | original, one prompt | **disguised, one prompt** |
| --- | --- | --- | --- | --- |
| Bug points, 53/33 | 49–51 (mean 50.0) | **50–51 (50.7)** | 48–51 (49.7) | **44–49 (46.0)** |
| Traps reported, 53/33 | 1–4 (2.0) | **6–8 (7.3)** | 0–1 (0.7) | **2–6 (4.3)** |
| NASAC score /106 | 86–99 (94.0) | **76–84 (79.3)** | 93–100 (97.3) | **75–82 (79.0)** |
| Bug points, 48/38 | 46–48 | 47 | 44–47 | 40–44 |
| Traps reported, 48/38 | 3–7 | 10–12 | 4–5 | 6–11 |
| Findings matching no annotation | 6–8 | 20–26 | 3–11 | 7–17 |
| Input tokens | 94–99 k | 74–81 k | 33 k | 17–35 k |
| Output tokens | 19.7–20.3 k | 27.0–28.0 k | 11.3–13.4 k | 10.7–14.0 k |
| Wall time | 57–59 s | 73–74 s | 73–87 s | 67–147 s |

What was missed and reported across the three per-file runs:
- original: missed `001` bug#2 (3×), `019` bug#4 (2×), `008` bug#1 (2×), `019` bug#2, `009` bug#1;
  traps `022` trap#2 (3×), `005` trap#1, `005` trap#2, `013` trap#1.
- disguised: missed `019` bug#2 (2×), `001` bug#2, `020` bug#3, `021` bug#3, `017` bug#3, `031` bug#1;
  traps in **every** run: `004` trap#1 and trap#2, `005` trap#1 and trap#2, `022` trap#2,
  `030` trap#1; once each: `007` trap#2, `014` trap#1, `019` trap#1, `028` trap#1.

## Reading it

1. **Finding the bugs does not depend on recognising the suite.** Per file, the disguised copy
   gives the same recall as the original (50–51 against 49–51 of 53), and the recall probe returns
   nothing. On one prompt for all 31 files recall drops by about four bug points.
2. **Rejecting the traps does.** The disguised copy reports 3–4× as many planted false positives
   (7.3 against 2.0 per file, 4.3 against 0.7 in one prompt) and three times as many findings
   matching no annotation. Six traps are reported in all three disguised runs and in none or one of
   the original ones. The scan's near-perfect precision on the original was not a property of
   reading the code alone.
3. **Which cue it was is not separated.** The disguise changes three things at once: names
   (`condition6`, `global_flag`, `isr_1` against `v_*`), comments and the header, and the order of
   the functions. Memory of the suite is one explanation; meaningful identifiers are another. The
   cases where the traps appear (`004`, `005`, `030`) have no inline comments, so names and order
   remain.
4. **Correction to `scan-measure-20261121`.** Its NOTES read the per-file misses (all three bug
   points of the relabel, in that single run) as the signature of memorisation. Over three runs
   the original arm also misses `008` bug#1 and `009` bug#1, and the disguised arm finds the
   relabelled bug points about as often. That reading does not hold.
5. **Against the tool, with a caveat that cuts the same way.** On the disguised copy the scan
   scores 76–84, against irqrace's 97 with pool + by variable at the same effort (`speed-20261121`,
   `low-combo-retry`). But that irqrace run read the **original** names and comments: its static
   stages do not depend on them, its triage does, so the tool's trap count on the disguised copy is
   unmeasured and may rise too. Running the full pipeline on the disguised copy (it needs C1
   configs for the new names, and the reordered files to still compile) is the comparison that
   would settle it — done in `disguised-pipeline-20261121`: irqrace's traps stay at 3–4. Recall is the part that does not need it: the static stages keep every bug
   point whatever the names, while the scan misses 2–3 per run with no proof behind any miss. The
   scan stays far cheaper: 74–81 k input tokens against 2.0 M.
