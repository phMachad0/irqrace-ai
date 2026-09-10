---
type: concept
tags: [wiki, concept]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-20
status: solid
---

# Atomicity Violation

The defect targeted by [[NIChecker (tool)]] and [[BMC4AV (tool)]]. A sequence of operations
expected to execute atomically is interrupted by an ISR that modifies the shared data, so
the execution is not equivalent to any serial execution (atomicity = serializability).

Three accesses are involved, not two: two from the preempted flow, one from the preempting
ISR in between. This is precisely why [[SDRacer (paper)]] argues atomicity violations "are
not applicable" to its own two-access race formulation — the two halves of this literature
count different things.

The deeper difference is not the arity but what the defect is relative to. A [[Data Race]] is
a property of the program and the machine. An atomicity violation is a property of the program
and an **intention** — that `A₁ … A₂` was meant to be indivisible — which C never states, so
every tool here guesses the atomic region as "any two accesses to the same location in one
flow". The race asks about an *instant*; the violation asks about an *interval*. See
[[Pair-Triple Unification]] for why that distinction decides whether the two analyses can be
merged.

## Patterns

Violations are enumerated as [[Access Interleaving Patterns]] over the triple. Both BMC
sources work with `(R,W,R)`, `(W,W,R)`, `(W,R,W)`. The fourth combination, `(R,W,W)`, is
where they part:

- [[NIChecker (paper)]] treats Racebench as containing **four** harmful patterns and counts
  54 violations across 31 programs.
- [[BMC4AV (paper)]] classifies `(R,W,W)` as **benign**, drops the six Racebench cases that
  contain only it, and works with 25 cases and 38 violations.

Any comparison between the two must first reconcile that choice. See [[Contradictions]] and
[[Precision Metrics]].

**The benchmarks do not support the benign reading.** `(R,W,W)` is **10 of the 48** annotated
bug points in [[Racebench]]'s simple cases, and six `true violation` entries in the
[[Real-World Program Benchmark]]'s shipped ground truth carry the pattern `rww` — including all
three violations in `logger1`. BMC4AV excludes the pattern by construction and so cannot report
any of them. For [[Thesis Goal]] the pattern must be included: excluding one is a definitional
false negative, and under the pair projection `(R,W,W)` decomposes into `(R,W)` and `(W,W)`,
two ordinary races, so it costs nothing to keep ([[Pair-Triple Unification]]).

**The benchmark sides with the three-access view.** [[Racebench]]'s own inline ground truth is
annotated as triples — `var<R#45>,<W#65>,<R#54>` — with observed shapes including `W→W→R` and
`R→W→R` ([[Racebench (documentation)]]). The suite the data-race literature evaluates on is
therefore already specifying atomicity-violation-shaped defects, which is a stronger argument
for the three-access framing than either BMC paper actually makes.

## Why detection is hard here

[[BMC4AV (paper)]]'s motivating example is instructive: a write in an ISR can be *overwritten*
by a later write in the same ISR before control returns, so the pattern that actually
manifests is `(W,W,R)` rather than the one a naive syntactic match would report. Getting the
pattern right requires knowing which write the read actually reads from — the read-from
order that BMC4AV then elevates into its [[Memory Access Graph]] guidance.

Related: [[Asymmetric Preemption]], [[Bounded Model Checking]], [[Interrupt Nesting]].
