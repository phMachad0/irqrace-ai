---
type: tool
tags: [wiki, tool, baseline]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-17
status: draft
---

# CBMC

The C Bounded Model Checker — the shared substrate of nearly every verification tool in this
wiki, and therefore a shared source of both capability and limitation.

Used by:

- [[NIChecker (tool)]] — v5.6, as the verification backend for its sequentialized programs.
- [[BMC4AV (tool)]] — as front-end, with MiniSat as the solving backend and a
  [[Memory Access Graph]] maintained alongside it.
- [[Rchecker]] and [[iCBMC]] — as the base of their respective analyses.

Because the tools share CBMC, differences between them are differences in **encoding and
guidance**, not in raw solving power. [[BMC4AV (paper)]] makes this explicit: one of its
criticisms of NIChecker is that "the original CBMC encoding is not optimized", and its
iCBMC+ baseline exists to hold the CBMC-based strategy constant while varying the guidance.

Inherits the usual BMC caveat: results hold only up to the unwind bound `u` — see
[[Bounded Model Checking]] and [[Loop Abstraction]].
