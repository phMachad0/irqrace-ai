---
type: concept
tags: [wiki, concept]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-31
status: draft
---

# Interrupt Masking and Synchronization

Interrupt-driven programs have no mutexes. Concurrency control means preventing the
interrupt from firing at all — masking it — rather than blocking a flow that is already
running. A detector that does not model masking reports races that hardware would never
allow.

**In the benchmark.** [[Racebench]] provides `disable_isr(n)` / `enable_isr(n)` as explicit
lock/unlock primitives, with `n = -1` meaning all interrupts ([[Racebench (documentation)]]).
Several of its planted false positives are regions that *are* correctly protected by these
calls, so a detector that ignores masking is penalized by construction.

**Standard APIs.** `disable_irq_all()`, `disable_irq(n)`, `disable_irq_nosync(n)`,
`enable_irq(n)` — recognizable by static analysis ([[IntRace (paper)]], §3.2).

**The hard part: ad-hoc mechanisms.** Embedded code masks interrupts by writing bits to
device registers, suspending the scheduler, or setting flag variables. [[SDRacer (paper)]]'s
motivating example turns on exactly this: `serial_out` disables `irq2_handler` by flagging an
interrupt bit at hardware level through a `flags` variable, and a conservative analyzer that
misses it reports a false race on `xmit->tail`. The paper's term for this is that hardware
states and operations must be *known*, not inferred.

Each tool's answer:

- [[IntRace (tool)]] recognizes the standard APIs and asks the user for a **configuration
  file** naming the implicit ones (API name, code location, operation type), then does a
  depth-first traversal recording each interrupt's state as 1 (enabled, preemptible) or 0.
  Missing implicit operations is one of the two acknowledged causes of its residual false
  positives.
- [[NIChecker (tool)]] encodes masking into the **invocation conditions** of the sequentialized
  program, alongside priority.
- [[SDRacer (tool)]] observes real hardware state on a virtual platform, which sidesteps the
  modelling problem at the cost of needing a simulator for the target.
- [[Rchecker]] uses an **Interrupt Mask List (IML)**.

That "user must supply a config file" step is a recurring, under-reported usability cost in
this literature and a fair thing to criticize in a thesis.

## Masking established in one flow can be undone by another

Found 2026-08-31 while hand-building the first context records for the implementation
(`project-src/docs/masking-semantics.md`, `log.md`). It is a recall trap that survives even after
the "masked on every path" rule is applied correctly, because it is about the *wrong flow*.

`svp_simple_001_001` masks interrupt 2 in its main task at line 28 and never re-enables it there.
Its annotated bug point is the triple `<W#32>, <R#55>, <W#35>`, with both writes in the main task
and the read in `isr_2`. On the main task's own control-flow graph, interrupt 2 is masked at
every point of the interval `[32, 35]` on every path — so a masking analysis that walks only the
flow containing `A₁` and `A₂` concludes the interleaving is impossible and discards **an
annotated bug point**.

What it misses is that `isr_1` is still enabled, may preempt the main task inside that interval,
and calls `enable_isr(2)`; `isr_2` then preempts `isr_1` in turn. The masking that looked like a
proof is not one. The corrected rule has two clauses:

> Interrupt *n* is masked throughout `[A₁, A₂]` only if **(a)** *n* is masked at every point of
> every path from `A₁` to `A₂` in the local flow, **and** **(b)** no flow that may itself execute
> within that interval re-enables *n*.

Clause (b) is transitive and has to be computed to a fixpoint, starting from "every flow may run"
and tightening — never from "nothing may run" and loosening, which would report a proof before it
has one. This generalizes the pattern [[LLM Stage Design]] lists as *"ISR re-enables a
lower-priority interrupt inside itself"*: here the re-enabled interrupt has **higher** priority,
and the consequence is stronger, because the fact being invalidated was established in a
different flow.

The planted false positive immediately below it in the same file is the mirror image —
`isr_1`'s two writes at lines 43 and 44 with `isr_2`'s read between them, where interrupt 2 stays
masked until line 46, *after* both writes. The two candidates differ only in where the interval
sits relative to that one line, so an implementation that gets one right and the other wrong is
guessing rather than modelling the interval property.

Related: [[Asymmetric Preemption]], [[Path Feasibility Analysis]], [[Interrupt Nesting]].
