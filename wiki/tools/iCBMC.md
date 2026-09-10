---
type: tool
tags: [wiki, tool, baseline]
sources: ["[[BMC4AV (paper)]]", "[[NIChecker (paper)]]"]
updated: 2026-08-17
status: stub
---

# iCBMC

CBMC extension for verifying low-level software with competing and nested interrupts
(Kroening, Liang, Melham, Schrammel, Tautschnig — DATE 2015 / TECS 2017). The ancestor of the
BMC line in this wiki.

- [[BMC4AV (paper)]] extends it into **iCBMC+**, adding a potential-violation identification
  front-end so it can be compared like-for-like, precisely because its CBMC-based path
  feasibility strategy is closest to BMC4AV's own.
- As a baseline, iCBMC+ finds everything but is imprecise: 20 false positives and 67.9%
  precision on Racebench 2.1; on the real-world suite, all 94 violations but **72 false
  positives** (43.4% FP rate) in 744.55 s — the paper attributes this to not exploiting key
  RF-orders ([[Memory Access Graph]]).
- Also cited by [[NIChecker (paper)]] as a comparison point and as evidence that testing-style
  approaches miss bugs as interrupt counts grow.

Status: **stub** — no primary source ingested.
