---
type: concept
tags: [wiki, concept]
sources: ["[[NIChecker (paper)]]", "[[IntRace (paper)]]", "[[SDRacer (paper)]]"]
updated: 2026-08-17
status: draft
---

# Interrupt Nesting

An ISR preempted by a higher-priority ISR, which may itself be preempted, and so on. Nesting
multiplies the interleavings a detector must consider and is the single feature that most
cleanly separates the tools in this wiki.

- **[[NIChecker (tool)]]** is named for it ("Nested-Interrupt-Checker"). Nesting is handled
  natively by the *invocation conditions* of [[Lazy Sequentialization]]: an ISR simulation
  function may run in a round only if priority and masking permit, and the highest-priority
  function executes atomically because no context switches are placed inside it.
- **[[IntRace (tool)]]** handles nesting with a step-by-step **inside-out sequential
  conversion** during its concurrency-relationship stage, and borrows interleaving semantics
  from IntAbs (Sung et al.).
- **[[SDRacer (tool)]]** explicitly **excludes reentrant interrupts** (an interrupt
  preempting itself), calling them uncommon and used only in special situations.

The practical consequence for the thesis: claims of the form "tool X handles interrupts" are
not comparable unless the nesting depth and the reentrancy assumption are stated.

Related: [[Asymmetric Preemption]], [[Interrupt Masking and Synchronization]].
