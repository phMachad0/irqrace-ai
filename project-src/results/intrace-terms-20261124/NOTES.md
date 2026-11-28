# The static stages on the Racebench copy IntRace analysed (2026-11-24)

Pedro's question: how does irqrace's static phase (S1: stages 1–3, everything that reaches the
model) do against IntRace, on the Racebench version IntRace used? S1 only; no model was called.

## Which version IntRace used

IntRace (J. Supercomputing 2024) cites `github.com/chenruibuaa/racebench` and names no version or
directory. Its Table 3 gives, per case, the size in lines, `#ISR`, `#Race` and its own and
Rchecker's results, numbered 1–30 without case names (`match.py` holds the transcription from
`pdftotext -layout raw/IntRace.pdf`). Matching (size, #ISR) against every file:

- **The directory is `2.1`** — whose files self-identify as `racebench2.0`
  ([[Racebench]], "The directory named 2.1 holds racebench 2.0"). 29 of 30 rows match a `2.1`
  file exactly (line count with the unterminated last line counted); against `2.1_remarks`, whose
  files carry the annotations and are longer, only 5 rows match any file, by coincidence of size;
  `2.0/` holds only 10 cases. The paper's own two examples agree: No.3 is
  `svp_simple_007_001` (51 lines, its `<W#38>,<W#47>` and `line_40`) and No.8 is `004` (69).
  Upstream's last commit is 2019-12-04 (`ec1d828`), so any download for a 2024 paper is the
  vendored import `3d77421`.
- **Rows to cases** are unique except No.4 (`001` or `018`, both 65 lines, 2 ISRs; `#Race` 3
  makes it `018`) and Nos.19/24 (`006`/`010`, identical on every column; the order does not
  matter).
- **No.13 matches no file**: 72 lines, 1 ISR, 1 race. No file of 72 lines and one ISR exists in
  any upstream commit. The two cases left over are `001` (65 lines, **2** ISRs) and `019` (66
  lines, 1 ISR), both with one annotated bug point. By the ISR count No.13 is `019`, so the
  case excluded "because Rchecker errored on it" is **most likely `svp_simple_001_001`** — an
  inference, not a fact; the monograph currently says the excluded case is not identified.
- **IntRace's ground truth is the distributed annotations plus two.** Per case, `#Race` equals
  the 48/38 bug points everywhere except `009` (2 against 1) and `017` (5 against 4). Over 30
  cases that is 47 + 2 = **49**, the table's sum; with `001` it is the 50 the paper quotes. Why
  those two cases count one more is not stated.
- **The paper's table does not add up**: its rows sum to 53 detected and 4 false positives, its
  Sum row says 54 and 5, and the text says 5. The headline "detection rate of 90.7%" is 49/54,
  i.e. **precision** (TP over reported), not recall; recall is claimed as 100% by manual
  inspection.

## What ran

- Commit `2829a9b` (branch `tcc/t2-protocol-review`), static binaries from `analysis/build`, the machine of the
  monograph's runs. `irqrace pipeline --through context` on 31 configs (`configs/`): the
  production C1 files with `source_root` pointed at **pristine `2.1/`** (`git archive 3d77421`,
  so without the 006 source patch) and, for `028` and `030`, the entry point
  `..._001_main` — the `__main` double underscore exists only in `2.1_remarks`. 25.5 s wall for
  the 31 cases. Runs kept outside git in `../worktrees/intrace-cmp/runs-2.1`.
- **Scoring** (`score_21.py`): the project's 48/38 label set (`bench_metrics`, with the errata),
  annotations moved from `2.1_remarks` lines to `2.1` lines by a diff of the two files, then
  matched with `evaluation.match_subject` (exact line triple). Same-size changed blocks are mapped
  positionally — checked by hand: in `017`, `026`, `027`, `028`, `030` the annotated line is the
  same write with another expression (`x++` in remarks, `x = 12` in 2.1). `019` is rewritten
  between the copies (in 2.1 `reader4`/`reader5` are read under the mask); its lines 51, 56, 59
  map by hand to 49, 53, 54. After that no annotation lacks a counterpart.
- Not scored against IntRace's own 49: it is a count per case, not a list.

## Results (S1, 48/38 annotations moved to 2.1)

| | IntRace (its paper) | S1 on 2.1, 30 cases without `001` | S1 on 2.1, 31 cases |
| --- | --- | --- | --- |
| Ground truth | 49 races | 47 bug points, 36 traps | 48, 38 |
| Found | 49 (claimed, manual inspection) | **46/47** | 47/48 |
| Reported | 54 (rows: 53) | 152 triples (139 distinct access pairs) | 158 |
| Annotated traps reported | — | 15/36 | 16/38 |
| False positives | 5 (rows: 4), by the authors' judgement | — (unannotated reports: 91) | — |
| Funnel stage 1 → 2 → 3 | ~208 per *real* program (RQ2); not given for Racebench | 286 → 186 → 152 | 300 → 196 → 158 |

Excluding `019` instead of `001`: 46/47 found, 13/34 traps, 151 reported.

**The one bug point lost is `svp_simple_006_001` (R33, W52, R35), and the loss is correct.** In
pristine `2.1` the inner loop reads `for (int j = 0; i < 5; j++)`: once `i == 0` it never exits,
so A2 (line 35, under `i == 4`) is dead code. Z3 answers `unsat` (2.4 M resource units, 0.6 s).
This is the bug the 2026-10-22 source patch fixed in the vendored copy (`racebench-errata.yaml`).
IntRace counts a true race in this case; as a pair (R33 in main, W52 in the ISR) it is one —
the triple is what is impossible. Same divergence as the defect-class difference, made concrete.

**Against the version irqrace normally runs** (`2.1_remarks`, patched; monograph Table QP3 and
Fig. F2): 48/48 on 48/38 with 16 traps, funnel 316 → 202 → 166. On `2.1` the funnel is smaller
(300 → 196 → 158) and the trap count the same; the only recall difference is `006`.

## Reading it

- On IntRace's version and case set, S1 finds every annotated bug point that is reachable in
  that version (46 of 47; the 47th is dead code there).
- S1 reports about three times as many items as IntRace (152 triples against 54). That is the
  design — S1 over-approximates and leaves precision to triage — but it means S1 alone does not
  match IntRace's precision. The comparable figure would be S2 on this copy, not run.
- Nothing here licenses "S1 beats IntRace": the defect classes differ (pairs vs triples), the
  ground truths differ (49 vs 47, unexplained +1 in `009` and `017`), IntRace's false positives
  are its authors' judgement over a list that is not published, and its table is internally
  inconsistent.

## S2 on the same copy (2026-11-24/25)

Pedro asked for the triage too. The final configuration of the monograph: row `+interleaving`,
triage by variable, a pool of 4 calls across cases (`--case-parallel 4 --workers 1`),
`claude-cli:sonnet@low`, `IRQRACE_CLAUDE_TIMEOUT=1200`, three runs, commit `2829a9b` (the first
measurement with the integrated `--by-variable` and `--case-parallel`). Frozen root:
`../worktrees/intrace-cmp/runs-2.1` (the S1 runs above). Scored by `score_s2.py`: the
`likely_real` bucket against the same moved 48/38 annotations.

### Incidents

Five attempts lost cases to `claude -p` hanging until the 1,200 s timeout, always on the first
large checklist calls a run starts (`017`, `022`, `027`, `031`; `007` lost 11 of 12 candidates),
while every other case answered in 10–106 s:

| attempt (UTC start) | failing cases |
| --- | --- |
| 11-24 23:13 | 007, 031 |
| 11-24 23:34 / 23:55 / 11-25 00:15 (`--samples 3`) | 017, 027, 031 · 017, 031 · 007, 022, 031 |
| 11-25 00:47 (run 3, second try) | 022 |

Not reproduced in isolation: at 00:36 UTC case 031 alone answered in 28 s, and the four largest
cases launched at once answered in 31–60 s (`triage-failed/probe-20261124`). The same 111 k-
character prompt for 031 answered in 25 s on 2026-11-22. Taken as an intermittent backend stall,
not a property of the code; per protocol each failed pair was set aside whole
(`../worktrees/intrace-cmp/triage-failed/`, outside git) and repeated. The kept runs started at
00:38, 00:42 and 01:07 UTC.

### Results (48/38 moved to 2.1, IntRace's 30 cases)

| | IntRace (its paper) | S1 | S2, run 1 | S2, run 2 | S2, run 3 |
| --- | --- | --- | --- | --- | --- |
| Found | 49/49 (claimed) | 46/47 | 46/47 | 46/47 | 46/47 |
| Bug points called infeasible | — | — | 0 | 0 | 0 |
| Reported | 54 | 152 | 126 | 130 | 126 |
| Annotated traps reported | — | 15/36 | 5 | 7 | 5 |
| Reported, not annotated | 5 FP (authors' judgement) | 91 | 75 | 77 | 75 |
| Calls | — | — | 84 | 83 | 83 |
| Input tokens | — | — | 1.81 M | 1.85 M | 1.76 M |
| Output tokens | — | — | 106 k | 108 k | 103 k |
| Wall time (triage) | — | 25.5 s (31 cases, static) | 253 s | 252 s | 248 s |

Input = uncached + cache read + cache write, from the `spend:` lines. Over all 31 cases: 47/48
found in every run, 6–8 traps on top.

- **The missing bug point is the same in S1 and S2**: `006`, dead code in this copy, refuted by Z3
  before triage. The triage lost nothing and called no bug point infeasible.
- **Traps on top (runs 1 and 3)**: `019` (R49 W65 R54) and (R48 W63 R53), `020` (R37 W44 R40),
  `022` (W32 W66 R39) and (R55 W66 R63). The first three are among the five the 2026-10-28
  relabel turned into bug points as reachable under the suite's README (for `019` the errata says
  traps 3 and 4 are reachable "in both copies"; trap 2, (R45 W65 R49), the one valid only in
  `2.1`, stayed off the top in every run). The two of `022` are the annotator's own "可能误报"
  (possible false positive), reachable but effect-free ([[Racebench]]; the question of
  2026-11-23 on the final runs). Run 2 adds `009` (W37 R47 W38) and `022` (R55 W66 R56).
- **Against IntRace**: same recall on the reachable bug points, but S2 still reports about 2.4
  times as many items (126 against 54). S2 lists every triple on a variable the model judges
  harmful, several per annotated defect; IntRace reports about one race per annotated defect.
  Its 5 false positives are its authors' judgement over a list that is not published; S2's 75
  unannotated items on top are not judged here (on `2.1_remarks` the median run left 76–82 such
  items, monograph QP2).

## What S2 puts on top, read by hand (2026-11-25)

Pedro asked whether the traps S2 keeps on top are really false, whether IntRace's 5 false
positives are the suite's traps, and what the unannotated items on top are. Read against the
`2.1` sources; the dump is `dump_top.py` (run 1, IntRace's 30 cases).

**Criterion.** A triple (A1, B, A2) is a real atomicity violation when B can run between A1 and
A2 and A1's flow does not write the variable between A1 and A2 on every path. An own write in
between breaks the relation between A1 and A2: the interleaving happens, but the violation is
another triple (the dominance filter of `Open Questions`). An own *read* in between does not break
it; such a triple is a non-adjacent variant of an adjacent one.

### Traps on top (7 distinct over the three runs)

| case | triple | runs | verdict |
| --- | --- | --- | --- |
| 019 | `condition3` R48 W63 R53 | 3/3 | **real**: the ISR is enabled on lines 50–52, between the two reads, which disagree |
| 019 | `var1` R49 W65 R54 | 3/3 | **real**: same window; R54 only runs after the ISR cleared `condition3` |
| 020 | `var` R37 W44 R40 | 3/3 | **real** with two `isr_1` activations (the first enables `isr_2`, which changes `para`; the second writes `var` before R40) |
| 022 | W32 W66 R39 | 3/3 | **false**: main writes `var1` on line 56 or 58 between A1 and A2 on every path |
| 022 | R55 W66 R63 | 3/3 | **false**: same |
| 022 | R55 W66 W56 (annotated "R56") | 1/3 | **real**: the twin of bug 2 (R55 W66 W58) on the other branch; the annotation has the access kind wrong |
| 009 | `*m` W37 R47 W38 | 1/3 | **false**: the ISR points `m` at its own local (line 46) before reading (47), so it never reads main's variable |

The three real ones are among the five the 2026-10-28 relabel made bug points; the two false ones
on every run are the annotator's own "可能误报". Median run: 5 traps on top, 3 real, 2 false.

### IntRace's 5 false positives are almost certainly the suite's traps

- The paper's two examples are traps: `<R#50>,<W#68>` in No.8 (`004`) is trap 2
  (`R50 W68 R52`); the `i != 2` branch of No.3 (`007`, lines 40 and 47) is trap 2
  (`W40 W47 R42`).
- IntRace reports more than the ground truth only in `002`, `007`, `008`, `013` (one item each),
  and all four carry traps. The suite has no other reference for "false".
- S2 put none of those cases' traps on top in any run (S1 let one through in `004`, `007`, `013`).
- Some of those traps are false only as triples. As pairs — IntRace's defect class — they are
  races: in `008` the ISR writes `array[4]`, which main reads on line 48; in `002`, W44 against
  R37 on `[9999]`; in `007`, W50 against R34 on `array[1]`. Counting them as false positives is
  itself debatable under IntRace's own definition.

### The 75 unannotated items on top (run 1)

| class | items | what they are |
| --- | --- | --- |
| real, missing from the ground truth | 12 | `007` `global_var` R32 W49 R34 (the index changes between the array write and read); `009` `m` R37 W46 R38 and W35 W46 R37 (main writes through a pointer the ISR aimed at its own stack — worse than the annotated bug); `009` `local_var1` W26 R44 W32; `011` `u` W33 R43 W35; `017` R30 W39 W30 (lost update on `gv++`), W29 W39 R29 (the loop skips 0–49), R32 W39 R30; `019` W37 W65 R45 (line 37 exists only in `2.1`; the annotations were written for `2.1_remarks`, which deleted it); `027`, `028`, `030` ISR 2 preempted by ISR 3 inside its `+=`, between `init()` and `disable_isr(-1)` |
| real variants | 18 | the interleaving of an adjacent triple with own reads between A1 and A2 (`016` ×3, `017` ×6, `031` ×3, one each in `007`, `009`, `018`, `019`, `022`, `023`) |
| initialisation write (debatable) | 28 | A1 is `x = rand()` in an `init` function; the ISR writes after `init()` enables interrupts and main reads. Same shape as `022` bug 1 (W32 W66 R55), but the program does not depend on the value it drew (`021` ×2, `023` ×2, `025`, `026` ×3, `027` ×5, `028` ×5, `029`, `030` ×5, `031` ×4) |
| false | 14 | 11 dominated by an own write between A1 and A2 (`017` ×5, `022` ×5, `009` ×1); 2 where B reads what its own ISR just wrote (`017` R41 right after W39, and main cannot run inside the ISR); 1 impossible (`021` R65 W79 R65: line 65 runs once, with `ichan == 0`) |
| possible only in theory | 3 | `007` `array`: need three or more ISR activations and index 2; the ISR always writes the same value, or A2 does not depend on A1 |

As data races (pairs) almost none of the 75 is false: every one involves a concurrent pair with
a write.

### Reading it

- S2's precision on this copy is far better than "75 unannotated" suggests: the ground truth is
  not exhaustive and holds 12 real new violations, one more severe than the annotated defect.
- 13 of the 14 false items have causes a sound static filter would remove with proof: 11 by
  dominance, 2 by "B preceded by its own flow's write, which A's flow cannot interrupt" — both on
  the pending list (handoff 2026-11-23). The `021` one is a path condition (`ichan`) the solver did
  not refute.
- One false trap (`009` `*m`) needs recognising that the pointer was redirected before the read.
- This is one reader's classification, not a second ground truth; it is not scored.
