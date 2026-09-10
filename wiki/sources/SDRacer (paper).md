---
type: source
tags: [wiki, source]
sources: ["[[SDRacer (paper)]]"]
updated: 2026-08-17
status: solid
---

# Automatic Detection, Validation, and Repair of Race Conditions in Interrupt-Driven Embedded Software

**IEEE (TSE) · 2020 · clipping: [[SDRacer]] · PDF: `raw/SDRacer.pdf` · [source](https://ieeexplore.ieee.org/document/9072666)**

The earliest of the four sources in this wiki, and the only one that closes the loop from
detection all the way to **repair**. Introduces the tool [[SDRacer (tool)]].

## Problem

Thread-level race detectors do not transfer to interrupt-driven code. The paper gives five
reasons, and they are the clearest statement of the problem in the whole corpus (§2.5):
interrupts cannot block and run to completion; preemption is asymmetric rather than
symmetric ([[Asymmetric Preemption]]); concurrency control is *disabling* an interrupt
rather than blocking on a lock ([[Interrupt Masking and Synchronization]]); interrupt
occurrence depends on hardware state, so a detector unaware of registers reports races that
cannot fire; and repair requires interrupt-specific synchronization, not lock insertion.

The paper's [[Data Race]] definition is explicitly a *variant of order violations*: a race is
reported when a task or ISR is preempted after a shared memory access by a higher-priority
ISR that manipulates the same location. Classical data races and
[[Atomicity Violation]]s in the three-access sense are argued not to apply, since a memory
location cannot be accessed simultaneously by a task and an ISR.

## Approach

Four stages, each narrowing the previous stage's output:

1. **Static analysis** — identify shared resources (with alias sets) and interrupt
   enable/disable operations, then emit unordered static race warnings `<(T,L,A), (T,L,A)>`.
2. **Guided [[Symbolic Execution]]** — generate input data and interrupt interleavings that
   reach the warning locations; infeasible pairs (conflicting path conditions between two
   ISRs) are dropped here as false positives.
3. **Dynamic validation on a virtual platform** — replay inputs on Simics, force interrupts
   to fire at the candidate racing points by manipulating memory and buses directly, and keep
   only the pairs that can actually be interleaved.
4. **Repair suggestions** — insert `irq_disable(n)` / `irq_enable(n)` around the offending
   access, add locks, or extend an existing critical section; merge adjacent critical
   sections to avoid redundant operations.

The virtual platform is what distinguishes this work: it delivers the controllability
(force an interrupt at an arbitrary instruction) that neither static analysis nor
thread-level scheduling control can provide.

## Evaluation

Nine embedded benchmarks (11 subjects in the results table, including `shortprint`, `module1`
and `i2c-pca-isa`). Headline numbers (§5):

- **190 races detected** in total; on `shortprint`, none.
- Symbolic execution removed **40.3%** of static warnings overall (0–96.6% per subject);
  dynamic validation removed a further **36.7%** (0–100%).
- Manual inspection found **all reported real races harmful and no false negatives**.
- Repairs introduced few new operations and cost **<0.09 overhead on 9 of 11 programs**;
  `module1` and `i2c-pca-isa` were markedly worse because disabling interrupts changed the
  main task's control flow.
- End-to-end time: "typically a few minutes".

## Claims to trust and claims to check

- Trust: the staged false-positive reduction percentages, which are measured internally
  and consistently defined.
- Check: "no false negatives" rests on **manual inspection**, the same weak ground later
  used by [[IntRace (paper)]]. [[BMC4AV (paper)]] shows how badly that assumption can fail
  when it recounted the real-world suite and found 57 defects [[NIChecker (tool)]] had
  missed.
- Check: the 190-race total is not comparable to any other count in this wiki — different
  subjects, different defect definition ([[Precision Metrics]]).

## Limitations and threats to validity

Detection is bounded by what the virtual platform can simulate; races requiring hardware
states Simics does not model are invisible. Repair may extend critical sections enough to
create timing violations, which the paper acknowledges but does not verify against
deadlines. As [[IntRace (paper)]] observes, simulation cannot exercise all implementations,
so false negatives are possible in principle.

## Relation to other sources

- Shares the staged-filtering shape with [[IntRace (paper)]] — both narrow static warnings
  through progressively more expensive analysis — but SDRacer's final filter is *dynamic
  execution* while IntRace's is *constraint solving*. See [[Path Feasibility Analysis]].
- Sits opposite [[NIChecker (paper)]] and [[BMC4AV (paper)]], which give up execution
  entirely for [[Bounded Model Checking]].
- The only source here that repairs defects rather than only reporting them.
