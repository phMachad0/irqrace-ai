---
type: concept
tags: [wiki, concept]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-17
status: solid
---

# Bounded Model Checking

Search for a bug in all executions whose length is bounded by some integer `u`, by encoding
the bounded program as a formula and handing it to a SAT/SMT solver. The method behind
[[NIChecker (tool)]], [[BMC4AV (tool)]], [[Rchecker]] and [[iCBMC]] — all of them built on
[[CBMC]].

**Why this literature likes it.** BMC produces a **counterexample**, so a warning comes with
an execution the engineer can inspect. Static analysis produces a location and leaves manual
triage to the user, which [[NIChecker (paper)]] identifies as the practical barrier to
adoption.

**Why it hurts.** The state space grows exponentially with `u`. Some [[Racebench]] cases need
a loop unfolded **10,000 times** before the bug appears; [[CPA4AV]] times out or runs out of
memory on exactly those. Two responses appear in this wiki:

- **[[Loop Abstraction]]** — shrink the `u` you need.
- **Encoding and state-space reduction** — slicing and preemption-point reduction in
  NIChecker (up to 42.2% speed-up); the in-solver [[Memory Access Graph]] in BMC4AV, whose
  ablation attributes 45.97 s → 21.12 s and 739.74 MB → 567.21 MB to the graph alone.

**Bounded means bounded.** Any "no false negatives" claim from a BMC tool is relative to `u`,
the ISR-execution bound, and the round bound `r`. It is not a proof of absence. This is worth
stating explicitly whenever these tools are compared with the sound-by-construction claims of
static analysis — see [[Precision Metrics]].

The other half of the wiki avoids BMC entirely: [[IntRace (tool)]] solves only local path
constraints, and [[SDRacer (tool)]] executes.

Related: [[Lazy Sequentialization]], [[Atomicity Violation]].
