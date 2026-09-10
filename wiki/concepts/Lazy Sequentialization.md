---
type: concept
tags: [wiki, concept]
sources: ["[[NIChecker (paper)]]"]
updated: 2026-08-17
status: solid
---

# Lazy Sequentialization

Translate a concurrent program into a **nondeterministic sequential** program that simulates
its executions, then verify the sequential program with an ordinary model checker. "Lazy"
means only reachable states are explored, rather than the full state space — the property
that made [[Lazy-CSeq]] win SV-COMP concurrency-safety gold.

[[NIChecker (paper)]] adapts it from threads to interrupts. The resulting sequential program
(SP) has a main driver plus one entry function per ISR, run **round-robin**; in each round
the driver calls each interrupt simulation function whose **invocation conditions** hold.
Those conditions are where the interrupt semantics live:

- **priority** — only a higher-priority ISR may preempt;
- **masking** — a disabled interrupt cannot be invoked
  ([[Interrupt Masking and Synchronization]]);
- **atomic top priority** — the highest-priority function has no context switches inside it,
  so it cannot be preempted.

Thread sequentializers cannot be reused unmodified, for the three reasons
[[Asymmetric Preemption]] records: threads preempt symmetrically, cannot be masked, and can
block.

**Cost profile.** In NIChecker most of the runtime is *generating* the SP (3–12 s per
real-world program, 158.71 s total) rather than solving it (34.12 s of CBMC time) — the
opposite of what one expects from a BMC tool, and a useful data point when arguing about
where the bottleneck in this approach really is.

NIChecker proves **bounded correctness** of the translation, the only formal correctness
argument among the four sources. [[BMC4AV (tool)]] takes a different route entirely: no
sequentialization, order relations maintained as a [[Memory Access Graph]] inside the solver.

Related: [[Bounded Model Checking]], [[Interrupt Nesting]].
