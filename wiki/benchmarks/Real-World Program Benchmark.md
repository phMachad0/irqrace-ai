---
type: benchmark
tags: [wiki, benchmark]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[IntRace (paper)]]", "[[SDRacer (paper)]]"]
updated: 2026-10-29
status: solid
---

# Real-World Program Benchmark

The second evaluation set shared by [[NIChecker (paper)]] and [[BMC4AV (paper)]]:
**18 interrupt-driven programs from six embedded software packages**, three versions each
with differing interrupt counts and priorities, from a few hundred to ~1400 LoC
(10633 LoC total). Distributed via `github.com/zhvngyuan/NIChecker`, and shipped again inside
[[BMC4AV (tool)]]'s artifact. Both copies are now local (`../NIChecker`, `../BMC4AV`).

Each program is a **single extracted `main.c`** of 157–1639 lines, accompanied by
`priority.info` (flow name to priority) and `violation.info` (the ground truth). Several are
Linux kernel drivers lifted out of the tree — `wdt_pci_*` is Alan Cox's
`drivers/watchdog/wdt_pci.c` — which is why [[Candidate Evaluation Subjects]] recommends
staying in that family for the next tier.

| Package | What it is |
| --- | --- |
| `logger1–3` | firmware of a temperature-logging device from a large industrial enterprise; interrupts for measurement and communication |
| `blink1–3` | LED pattern driven by a timer; interrupt-triggered alarm and timer-overflow tasks |
| `brake1–3` | generated from a Simulink model of a **brake-by-wire** system from Volvo Technology AB; four threads talking to four wheel-brake controllers |
| `i2c_pca_isa_1–3` | I²C bus driver |
| `i8xx_tco_1–3` | watchdog timer driver |
| `wdt_pci_1–3` | PCI watchdog driver |

## What the shipped ground truth actually says

The `violation.info` files are **identical between the NIChecker repository and the BMC4AV
artifact in 17 of 18 programs** (*corrected 2026-10-29*: this page said byte-identical;
`i8xx_tco_1` differs by a trailing `no`), so there is effectively one ground-truth document and
both teams shipped it. **The programs themselves are not identical** (see "Two copies" below).
Parsed on 2026-08-20 it contains, over the 18 programs, **45 entries marked `true violation`
and 14 marked `false violation`** — one line per shared variable, naming the pattern:

```
true violation int numberOfRecords rww
true violation int intervalCounter rww
true violation int tickCounter rww
```

Per program, against what [[BMC4AV (tool)]]'s own results file reports:

| Program | shipped ground truth | traps | BMC4AV reports |
| --- | --- | --- | --- |
| logger1 / 2 / 3 | 3 / 0 / 2 | 0 / 0 / 0 | 2 / 0 / 2 |
| blink1 / 2 / 3 | 3 / 4 / 4 | 1 / 1 / 1 | 2 / 3 / 3 |
| brake1 / 2 / 3 | 2 / 2 / 2 | 1 / 1 / 2 | 2 / 3 / 2 |
| i2c_pca_isa_1 / 2 / 3 | 1 / 2 / 3 | 2 / 1 / 1 | 1 / 4 / **8** |
| i8xx_tco_1 / 2 / 3 | 3 / 3 / 3 | 1 / 0 / 0 | 3 / 3 / 2 |
| wdt_pci_1 / 2 / 3 | 2 / 2 / 4 | 1 / 1 / 0 | **10** / **15** / **29** |
| **total** | **45** | **14** | **94** |

**The two counts are not measuring the same object.** On the small programs they agree almost
exactly. They diverge only on the large ones, and monotonically with size: `wdt_pci_3` goes
from 4 to 29. The ground-truth file records **one entry per shared variable**; BMC4AV's table
records **one entry per access-triple instance**, and a variable accessed from many sites in a
1392-line driver yields many instances.

That is a units mismatch, and it is a much simpler explanation of the 94-versus-37 gap than a
57-defect recall failure. It does not prove BMC4AV wrong — a per-instance count is a defensible
choice — but it means the headline comparison puts a per-instance numerator over a
per-variable denominator. Anyone quoting "NIChecker misses 57 of 94" should check that first.
See [[Contradictions]] #1.

**Six `true violation` entries carry the pattern `rww`** — in `logger1` (all three), `logger3`,
`i8xx_tco_3` and `wdt_pci_3`. BMC4AV excludes `(R,W,W)` by construction, so it cannot report
them; on `logger1` it reports two violations of other shapes while the shipped ground truth
lists three `rww` and nothing else.

**Equal-priority ISRs are present here too.** `wdt_pci_1`'s `priority.info` in BMC4AV's copy
gives `writer1_isr:4  writer2_isr:4  closer1_isr:2  closer2_isr:2  main:0` — two pairs of ISRs
sharing a priority level. NIChecker's copy has the same pairs with the levels swapped (writers 2,
closers 4; [[Contradictions]] #9). [[Open Questions]] had flagged this as a `svp_real_002`-only concern;
it is in the main benchmark ([[Asymmetric Preemption]]).

## Two copies, and the one this project analyses (2026-10-29)

Vendored at `project-src/bench/realworld` from NIChecker's repository (commit `40267c0`), on the
human's direction. It is the original distribution and the one `violation.info` was written for,
and its `main` keeps the real masking. Provenance is in `bench/realworld/VENDORED.md`. What differs
from BMC4AV's copy is in [[Contradictions]] #9: `main.c` in all 18, priorities in five.

What it takes to analyse it, all recorded with evidence in `bench/realworld-errata.yaml`. The
vendored files stay byte-identical to upstream:

| Problem | Programs | Handled by |
| --- | --- | --- |
| `priority.info` names `task_measure`, the function is `task_measure_isr`, and `main` is not listed | all | generator: entry `<name>_isr`, `main` a task at priority 0 |
| `EINVAL`, `NULL` undeclared (the extraction dropped the includes) | `i8xx_tco_*`, `wdt_pci_1/3` | `-D` in the C1 build |
| `wdt_ctr_port` undeclared; `wdtpci_lock0`, a typo for `wdtpci_lock` | `wdt_pci_*` | `-D` |
| `return NULL;` in all eight `void` ISRs | `wdt_pci_3` | `-Wno-error=return-type` |
| ground truth unlabelled, naming variables absent from the program | `logger2` | read as zero entries, which is the 45/14 count above |
| per-instance lines copied from `blink1` without the shift from an inserted ISR. B is `121W` on a line that only reads | `blink2` (4 entries), `blink3` (2) | line errata, `likely`, with alternatives where the source does not say which write |

**The ground truth's grain is mixed.** 31 of the 45 bug entries are per *variable and pattern*
(`true violation int numberOfRecords rww`). The 14 `blink` entries are per *instance*, with lines.
The harness (`irqrace realworld run`) matches each at its own grain, so a per-variable entry is
satisfied by any candidate on that variable with that pattern. That is weaker than Racebench's
line match and is said wherever the number is quoted.

## Runs of this project's pipeline

**Official run, 2026-10-30.** NIChecker's copy, line errata and the three priority corrections applied
(`bench/realworld-errata.yaml`):

| | |
| --- | --- |
| Funnel | 1980 → 1037 → **972** reaching the LLM (54 per program) |
| Stage 2 | 505 dropped by priority, 438 by no-path |
| Solver | 846 `sat`, 126 `inconclusive`, 65 `unsat` |
| **Recall gate** | **45/45, PASS** |
| Traps reaching the LLM | 9/14 |

The solver's split is not reproducible across runs: its 10 s timeout is wall-clock, and `brake3`
went from 3 `unsat` / 49 `inconclusive` to 0 / 73 under machine load. Recall is unaffected,
since `inconclusive` is kept.

972 triples are 280 distinct intervals (variable, A₁, A₂, pattern) and 119 (variable, pattern)
pairs, which is the ground truth's grain. 65 of those pairs are on variables the ground truth
does not annotate, such as `expect_close` in the watchdog drivers. Precision cannot be computed
against a non-exhaustive ground truth. Turning off equal-priority preemption, which
[[NIChecker (paper)]] says its semantics forbid, cuts stage 2 by 44% but loses 2 annotated
violations in `i8xx_tco_1`. The ground truth itself relies on it. Diary:
[[Semana 9 — O Benchmark de Programas Reais]] §3.9.

**First run, 2026-10-29.** NIChecker's copy, line errata applied, priorities as shipped:

| | |
| --- | --- |
| Funnel | 1980 → 1005 → **941** reaching the LLM (52.3 per program) |
| Stage 2 | 537 dropped by priority, 438 by no-path |
| Solver | 842 `sat`, 99 `inconclusive` (94 of them in `brake2`/`brake3`, at the 10 s timeout), 64 `unsat` |
| Recall gate, NIChecker's priorities | **40/45**: misses in `logger3`, `wdt_pci_1`, `wdt_pci_2` |
| Recall gate, BMC4AV's priorities for the five disputed programs | **45/45** |
| Traps reaching the LLM | 7/14 |

The five misses are not detector failures. Under NIChecker's own priorities and its stated
convention, the annotated violations are unreachable, and stage 2 proves it correctly
([[Contradictions]] #9). Which `priority.info` to treat as canonical for those programs is an
open decision.

For scale: [[Racebench]]'s 31 cases send 166 candidates to the LLM. Here 941 do. The per-variable
grain of most entries means the gate is a weaker statement than Racebench's per-line one.

## The disputed ground truth, as the papers state it

| | [[NIChecker (paper)]] | [[BMC4AV (paper)]] |
| --- | --- | --- |
| Violations assumed present | 47 detected (on its "Benchmark 2$" variant); 37 after `(R,W,W)` removal by BMC4AV's accounting | **94** |
| NIChecker's result | 47 found, **0 FP**, 158.71 s, 4270.82 MB | 37 found, 0 FP, **57 FN**, hit rate **39.4%**, 262.39 s |
| BMC4AV's result | — | 94/94, 0 FP, 21.12 s, 567.21 MB |
| [[iCBMC]]+ | — | 94 found but 72 FP (56.3% precision), 744.55 s |
| [[CPA4AV]] | — | 36 TP, 3 FP, several T.O./O.O.M. |

BMC4AV's argument: NIChecker's 37 violations were **manually injected by NIChecker's own
authors**, and since the tool only inspects user-nominated variables and patterns, the other
57 naturally occurring violations were never looked for. See [[Contradictions]].

Note that neither 37 nor 47 matches the 45 entries in the shipped ground truth either, so
NIChecker's published figure is close to its own artifact but not identical to it. Three
numbers — 45, 47 and 94 — now describe the same 18 programs.

## Note on IntRace and SDRacer

They use *different* real-world sets and different defect classes, so their numbers do not
belong in the table above:

- [[IntRace (paper)]]: 9 industrial programs — `mv643xx_eth.c`, `short`, `shortprint`, three
  from the China Academy of Space Technology, three from Sung's suite — 118 data races,
  9 FP.
- [[SDRacer (paper)]]: 11 subjects including `module1`, `i2c-pca-isa` and `shortprint`,
  190 races.

`i2c`-family and `shortprint` programs appear on both sides of the literature, which makes
them the most promising place to look for a genuinely cross-comparable case study.
