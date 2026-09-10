---
type: tool
tags: [wiki, tool, baseline]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[IntRace (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-18
status: draft
---

# intAtom

Static [[Atomicity Violation]] detector for interrupt-driven programs, based on data-flow
analysis of path feasibility between consecutive accesses in each preempted task. Full
reference, via [[BMC4AV (paper)]]'s bibliography: C. Li, **R. Chen**, B. Wang, T. Yu, D. Gao,
M. Yang, "Precise and efficient atomicity violation detection for interrupt-driven programs
via staged path pruning", ISSTA 2022, pp. 506–518. No page of its own paper in this wiki yet —
everything here is second-hand.

Note the co-author: R. Chen also maintains [[Racebench]] and co-authors
[[NIChecker (paper)]] ([[NASAC 2019 Prototype Competition]]).

- Identifies candidate violations by [[Access Interleaving Patterns]], then prunes modularly
  by building a symbol digest and selecting representative preemption points
  ([[IntRace (paper)]], §5).
- **Criticized by** [[BMC4AV (paper)]] for lacking precise reachability analysis, so it
  cannot handle non-deterministic interleavings across priority levels.
- **Not open source**; both [[NIChecker (paper)]] and [[BMC4AV (paper)]] report failing to
  obtain an executable and therefore reusing published numbers.

Reported on [[Racebench]]: finds all violations in both comparisons, with 6 false positives
and 86.4% precision in BMC4AV's 25-case subset; NIChecker likewise reports intAtom finding
everything but with a higher FP rate than itself.

> Worth acquiring the intAtom paper — it is the most-cited static baseline in this corpus and
> the only one both BMC papers agree finds every violation. Listed in [[Open Questions]].
