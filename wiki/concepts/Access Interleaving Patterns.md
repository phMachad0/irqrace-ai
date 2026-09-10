---
type: concept
tags: [wiki, concept]
sources: ["[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[SDRacer (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-20
status: draft
---

# Access Interleaving Patterns

The cheap first filter every detector in this wiki uses: enumerate the syntactic shapes that
a defect can take, match them over shared-variable accesses, then spend real analysis effort
only on what matched.

- For [[Data Race]] detection ([[IntRace (paper)]], §3.1) a pattern is a **pair** — two
  accesses to the same shared object from different flows, at least one a write, with
  different priorities. IntRace deliberately ignores guard conditions and interrupt state at
  this stage so that nothing is missed, accepting an average of ~208 candidates per real
  program to be filtered later.
- For [[Atomicity Violation]] detection ([[NIChecker (paper)]], [[BMC4AV (paper)]]) a pattern
  is a **triple** over `{R, W}`: `(R,W,R)`, `(W,W,R)`, `(W,R,W)` — and, disputed,
  `(R,W,W)`. The first and third accesses come from the preempted flow, the middle one from
  the preempting ISR.

The pattern set is the detector's **specification of what counts as a bug**, so changing it
changes the ground truth, not just the output. BMC4AV's decision to call `(R,W,W)` benign
removes six Racebench cases from its evaluation and rebases every precision figure that
follows.

## What the benchmark itself says

[[Racebench]] annotates its ground truth as **triples**, in the grammar
`variable<R#45>,<W#65>,<R#54>` — two accesses from the preempted flow with an ISR access
between them ([[Racebench (documentation)]]). So the benchmark's own bug definition is the
three-access one, even for the suite the data-race papers evaluate on, and the observed
shapes in the annotations include `W→W→R` and `R→W→R`.

The repository grounds the suite in **seven defect patterns based on variable access order
violations**, but the enumeration is not in its documentation and the DeepWiki export
reconstructs it speculatively — so this wiki records the seven as *unrecovered*
([[Open Questions]]). Every tool here uses its own smaller set instead: two-element for the
race detectors, three or four triples for the atomicity checkers.

## Pairs and triples are not two pattern sets

Every harmful triple projects onto two adjacent access pairs, and every one of those pairs is
in the race detectors' pair set — proved in general and verified against all 48 annotated bug
points in [[Racebench]] ([[Pair-Triple Unification]]). So the pair set contains the triple set
at the matching stage, and a single front end can generate both.

It does **not** follow that the triples can be discarded. The feasibility question differs —
an instant for a pair, an interval for a triple — and an atomicity violation whose two local
accesses sit in separate critical sections has no constituent race at all. Derive both sets
from one access enumeration; never derive one from the other.

## Measured distribution

Over the 48 bug points of [[Racebench]]'s 31 simple cases: `(R,W,R)` 25, `(R,W,W)` 10,
`(W,W,R)` 7, `(W,R,W)` 6. Over [[BMC4AV (tool)]]'s 94 findings on the 18-program real-world
suite: `(W,W,R)` 75, `(R,W,R)` 18, `(W,R,W)` 1. The two benchmarks are dominated by *different*
patterns, which is worth knowing before optimizing a matcher for either.

Pattern matching alone is hopelessly imprecise — it is a syntactic over-approximation. What
separates these tools is what they do *next*: [[Path Feasibility Analysis]] with an SMT
solver ([[IntRace (tool)]]), dynamic replay on a virtual platform ([[SDRacer (tool)]]),
assertion-based [[Bounded Model Checking]] ([[NIChecker (tool)]]), or in-solver
[[Memory Access Graph]] confirmation ([[BMC4AV (tool)]]).

NIChecker's pattern handling has a practical cost worth remembering: the user must nominate
the global variable *and* the pattern, and each combination is a separate run.
