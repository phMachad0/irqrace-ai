---
type: benchmark
tags: [wiki, benchmark]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[IntRace (paper)]]", "[[SDRacer (paper)]]"]
updated: 2026-08-20
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

The `violation.info` files are **byte-identical between the NIChecker repository and the
BMC4AV artifact**, so there is exactly one ground-truth document and both teams shipped it.
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

**Equal-priority ISRs are present here too.** `wdt_pci_1`'s `priority.info` gives
`writer1_isr:4  writer2_isr:4  closer1_isr:2  closer2_isr:2  main:0` — two pairs of ISRs
sharing a priority level. [[Open Questions]] had flagged this as a `svp_real_002`-only concern;
it is in the main benchmark ([[Asymmetric Preemption]]).

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
