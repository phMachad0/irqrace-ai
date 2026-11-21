# Scan measurement — the model reads the files, no static analysis (2026-11-21)

`scripts/scan-measure.py`. **n = 1 per mode**, `claude-cli:sonnet@low` (`claude-sonnet-5-5`,
`--effort low`), the same backend as the low-effort triage runs in `results/speed-20261121/`.

## What the model got

A short system prompt: the interrupt model (main task lowest, an ISR preempts lower flows when
unmasked, larger priority is higher, `disable_isr`/`enable_isr` and `-1`), the definition of an
atomicity violation (A1, B, A2 on one location, four shapes), and "report every violation you
find, as three line numbers and their access kinds; only violations you believe can happen".
No Racebench semantics, no domain rules, no self-validation, no candidate list.

Per case: the flows of its C1 config (entry function, ISR or task, priority, IRQ) — facts a
reader cannot get from the C file — the file with line numbers, and `common.h`. The file is
`2.1_remarks` with its trailing `//bug点` annotation block cut off, so the lines are the ones the
ground truth cites and the annotations are not shown. The header comment (entry points, "larger
IRQ number is higher priority", in Chinese) stays.

| Mode | Calls | What one call holds |
| --- | --- | --- |
| `per-file` | 31, four at a time | one case |
| `one-prompt` | 1 | all 31 cases, answered under their names |

Answers are structured (one JSON list of findings), scored with the project's matcher
(`irqrace.evaluation.match_subject`): a finding matches an annotation when its three lines are the
annotated ones.

## Results

| | per file | one prompt | irqrace `low-baseline` | irqrace `low-combo-retry` |
| --- | --- | --- | --- | --- |
| **53/33 labels**: bug points found | **50/53** | 48/53 | 52/53 | 53/53 |
| traps reported | 1 | 1 | 3 | 3 |
| NASAC score /106 | 97 | 93 | 95 | 97 |
| **48/38 labels**: bug points found | **48/48** | 44/48 | — | — |
| traps reported | 3 | 5 | — | — |
| NASAC score /96 | 87 | 73 | (M2, n = 3, default effort: 75) | — |
| Findings matching no annotation | 8 | 3 | 83 (`likely_real`) | 83 |
| Calls | 31 | 1 | 307 | 84 |
| Input tokens (incl. cache) | 98,575 | 33,430 | 3,499,399 | 2,024,827 |
| Output tokens | 20,315 | 11,323 | 248,746 | 113,127 |
| Wall time | 57 s | 73 s | 984 s | 263 s |

irqrace's numbers include no static-stage time (about 30 s for the 31 cases on this machine).

Missed bug points (53/33):
- per file: `001` bug#2 `WRW(43,64,44)`, `019` bug#2 `RWR(45,71,51)`, `019` bug#4 `RWR(48,69,56)`.
  **All three are bug points created by the 2026-10-28 relabel** (`bench_metrics.PRE_RELABEL_TRAPS`);
  under the original labels the scan finds every bug point.
- one prompt: `001` bug#2, `009` bug#1 `WRW(32,44,33)`, `017` bug#3 `RWW(32,39,30)` and bug#4
  `WWR(30,39,29)`, `019` bug#1 `RWR(45,71,59)`.

Traps reported (53/33): per file `022` trap#2 `RWW(55,66,56)`; one prompt `019` trap#1 `RWR(40,67,42)`.

## How far this can be trusted

- **Contamination is the first threat.** Racebench has been public on GitHub since 2019
  (`chenruibuaa/racebench`, last upstream commit 2019-12-04), with the annotation comments in
  `2.1_remarks`, and the file headers still say `racebench2.1_remarks`.
  A model that has seen the suite can recall planted bugs instead of finding them. That would also
  explain why the misses are exactly the triples whose label this project changed: the scan agrees
  with the *published* labels. Not tested here; a renamed and reordered copy of the suite would test it.
- **The cases are tiny and planted.** 60 k characters for 31 programs, one or two interrupt handlers
  each. Nothing here says how a scan behaves on a driver with thousands of lines.
- **No guarantee and nothing to check against.** The scan's 50/53 is a sample; there is no proof
  behind a missed triple, and no static fact behind a reported one. irqrace's static stages keep
  every bug point by construction (53/53, and 48/48 on the old labels), and the triage removes
  none from the report; what varies with the prompt is how many sit in `likely_real` (52–53/53 in
  the runs above).
- n = 1, one model, one effort level.
