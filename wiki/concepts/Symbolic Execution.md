---
type: concept
tags: [wiki, concept]
sources: ["[[SDRacer (paper)]]"]
updated: 2026-08-17
status: draft
---

# Symbolic Execution

Used by [[SDRacer (tool)]] as its middle stage: after static analysis emits race warnings,
symbolic execution generates the **input data and interrupt schedules** needed to reach the
warning locations, and discards warnings whose path conditions conflict.

The interrupt setting complicates it in ways [[SDRacer (paper)]] spells out. Hardware
registers are not free symbolic variables: `IIR` is read-only, and its value is controlled
indirectly by the interrupt enable register `IER`, so the solver must respect the device
model to produce an input that is actually realizable. Generated inputs therefore include
both command inputs and sensor/register inputs.

Measured effect: symbolic execution removed **40.3%** of static warnings overall, ranging
from 0% to 96.6% across subjects — leaving the remainder to
[[Path Feasibility Analysis|dynamic validation]].

Relation to the BMC tools: symbolic execution and [[Bounded Model Checking]] both reduce
program semantics to SMT/SAT constraints, but BMC asks a whole-program bounded reachability
question, while SDRacer uses symbolic execution as a *test generator* whose outputs are then
replayed on real (virtual) hardware.

Related: [[Interrupt Masking and Synchronization]].
