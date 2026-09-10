---
type: concept
tags: [wiki, concept]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-20
status: solid
---

# Asymmetric Preemption

The structural fact that makes interrupt-driven concurrency its own research area rather
than a special case of threads. Every source in this wiki opens with some version of it.

An interrupt can preempt a task; a task can never preempt an interrupt. A higher-priority
ISR can preempt a lower-priority one; the reverse never happens. Threads, by contrast,
preempt each other symmetrically.

Three consequences the sources draw out:

- **Interrupts cannot block.** An ISR runs to completion unless a higher-priority interrupt
  preempts it ([[SDRacer (paper)]], §2.5). So the OS-level tricks used to control thread
  schedules — inserting sleeps or yields, reading thread status — have no analogue. ISR
  internal state is invisible to tasks and to other handlers, which rules out instrumentation
  as a way of observing interrupt status.
- **happens-before breaks.** Thread race detection is built on happens-before, but the
  relation computed for a task/ISR pair is not sound if an interrupt fires during its
  computation ([[SDRacer (paper)]]). This is why the interrupt literature reaches for
  patterns and priorities rather than vector clocks.
- **Concurrency control is masking, not blocking.** See
  [[Interrupt Masking and Synchronization]].

Formally, the sources agree on the shape: a program is `P = Main ∥ ISR₁ ∥ … ∥ ISRₙ`, with a
priority function over tasks. They **disagree on the direction of the priority numbering** —
[[SDRacer (paper)]] and [[IntRace (paper)]] use larger number = lower priority, while
[[BMC4AV (paper)]] uses larger number = higher priority and pins `Pri(Main) = 0`. Harmless
in isolation, a trap when transcribing formulas between papers.
**Settled 2026-08-20 from the primary artifact.** The `racebench` README states it outright —
larger priority number means higher priority — and the `priority.info` files in the
[[Real-World Program Benchmark]] agree, with `main:0` lowest. So [[BMC4AV (paper)]] matches
the benchmark and the two data-race papers' formalisms run opposite to the suite their tools
are evaluated on. Use **larger = higher** ([[Contradictions]] #3).

**Equal priorities are not an edge case.** `svp_real_002` gives two ISRs the same priority,
and so does the main real-world suite: `wdt_pci_1`'s `priority.info` reads
`writer1_isr:4  writer2_isr:4  closer1_isr:2  closer2_isr:2  main:0`. None of the four papers'
formal models discuss what happens between two flows at the same level — whether they can
preempt each other at all. A detector must decide, and the safe decision for recall is to
assume they can, unless the platform documents otherwise
([[Soundness and False Negatives]]).

Related: [[Interrupt Nesting]], [[Data Race]], [[Atomicity Violation]],
[[Lazy Sequentialization]].
