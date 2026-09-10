---
type: tool
tags: [wiki, tool, baseline]
sources: ["[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-18
status: draft
---

# Rchecker

CBMC-based [[Data Race]] detector for interrupt-driven programs (H. Feng, L. Yin, W. Lin,
X. Zhao, W. Dong, QRS-C 2020), which handles synchronization through an **Interrupt Mask
List (IML)** describing where interrupts are masked. Known here only through citations.

**Origin**: Feng, Yin and Dong competed at the [[NASAC 2019 Prototype Competition]] as Team 3
with a tool called **Verian** ("verification-enhanced interrupt data access conflict analysis
tool"), a year before the Rchecker paper. Rchecker is that competition entry grown up, which
also explains why it was evaluated only on [[Racebench]].

- **Baseline for** [[IntRace (paper)]], which reports reducing false positives by 73.2%
  relative to it — using Rchecker's *published* numbers, since the implementation is
  unavailable and the authors' re-implementation attempt was set aside to keep the data
  faithful.
- **Criticized for**: scalability limits ([[NIChecker (paper)]]) and for not considering
  implicit dependencies between tasks and ISRs or handling [[Interrupt Nesting]] well
  ([[IntRace (paper)]]).
- One Racebench case could not be analyzed by Rchecker at all, so IntRace excluded it from
  both sides of the comparison.

The IML idea is the interesting part for the thesis: it is an early, explicit attempt to give
a checker a model of [[Interrupt Masking and Synchronization]] instead of inferring it.
