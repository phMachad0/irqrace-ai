---
type: concept
tags: [wiki, concept]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-20
status: solid
---

# Data Race

The defect targeted by [[SDRacer (tool)]] and [[IntRace (tool)]]. Two accesses to the same
shared location, at least one a write, with no ordering between them.

In the interrupt setting the definition has to be restated in terms of preemption rather
than simultaneity, and the two sources do it slightly differently:

- **[[IntRace (paper)]]** (§2.2): events `eᵢ = (Tᵢ, Wᵢ, objᵢ, opᵢ, pᵢ)`; a race exists when
  two events from different tasks/ISRs touch the same object, at least one writes, and the
  preempting event has the higher priority.
- **[[SDRacer (paper)]]** (§2.2) adds a **hardware-state condition**: the preempting
  interrupt must be *enabled* at the moment of the first access. It explicitly calls the
  result "a variant of order violations", arguing that classical data races do not apply
  because a task and an ISR cannot touch memory simultaneously — one always precedes and is then preempted.

That extra condition is the whole ballgame for precision: a conservative detector that
ignores whether `irq2` was masked at the access point reports a race that can never fire.

**Harmfulness.** Not every race matters. [[IntRace (paper)]] adopts the Bai et al. criterion —
a race is harmful if the shared variable feeds a branch condition (`if`, `while`) or indexes
an array or pointer — and classifies 36 of its Racebench findings as harmful. It also flags
**benign races** deliberately left unsynchronized for real-time performance as a source of
its own false positives. [[SDRacer (paper)]] found all its 190 reported real races harmful.

Contrast with [[Atomicity Violation]], which needs three accesses rather than two — which is
why the two halves of this literature cannot be compared by counting defects.

**A wrinkle from the benchmark.** [[IntRace (paper)]]'s 50 "manually inserted data races" in
[[Racebench]] are close to the **48** bug points a direct parse of the annotations yields for
the 31 simple cases — and the benchmark annotates them as **triples**, not pairs. The
data-race papers are, at least on this suite, counting largely the same annotated defects the
atomicity papers count, under a different name.

That overlap is now precise rather than suggestive: all 48 bug points project onto access
pairs with at least one write, so every annotated atomicity violation *contains* races. The
converse fails — an atomicity violation can exist with no constituent race when the two local
accesses sit in separate critical sections — so the classes overlap without coinciding.
[[Pair-Triple Unification]] works this out and draws the design consequence.

Related: [[Access Interleaving Patterns]], [[Asymmetric Preemption]], [[Precision Metrics]].
