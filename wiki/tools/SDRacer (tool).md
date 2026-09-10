---
type: tool
tags: [wiki, tool]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]"]
updated: 2026-08-17
status: solid
---

# SDRacer (tool)

**Static and Dynamic race detection** — detects, validates *and repairs* [[Data Race]]s in
interrupt-driven C. Paper: [[SDRacer (paper)]].

- **Family**: hybrid static + [[Symbolic Execution]] + dynamic simulation.
- **Built on**: a virtual platform (Simics) for execution control; see
  [[Supporting Infrastructure]].
- **Target**: race conditions between a task/ISR and a higher-priority ISR, hardware-state
  aware. Reentrant interrupts excluded.
- **Input**: C source of the interrupt-driven program, plus a simulatable target platform.
- **Unique capability**: **repair**. Emits `irq_disable(n)`/`irq_enable(n)` pairs, lock
  insertion, or critical-section extension, merging adjacent critical sections to keep the
  operation count low.
- **Availability**: not evaluated as a baseline by any later source in this wiki.

**Reported results** ([[SDRacer (paper)]], §5): 190 races on 11 subjects; symbolic execution
removes 40.3% of static warnings, dynamic validation a further 36.7%; repair overhead <0.09
on 9 of 11 programs, notably worse on `module1` and `i2c-pca-isa`.

**How others see it.** [[IntRace (paper)]] cites SDRacer approvingly as a hybrid framework
but argues simulation cannot exercise all implementations, so false negatives remain possible
and the dynamic environment is too costly for large industrial software. Neither BMC source
compares against it — different defect class ([[Atomicity Violation]] vs [[Data Race]]).
