---
type: source
tags: [wiki, source]
sources: ["[[NIChecker (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-18
status: solid
---

# Bounded Verification of Atomicity Violations for Interrupt-Driven Programs via Lazy Sequentialization

**ACM TOSEM 34(3), 2025 · Y. Zhang, L. Qu, Y. Wu, L. Wu, T. Yu, R. Chen, W. Kong (author list via [[BMC4AV (paper)]]'s bibliography — the clipping carries no byline) · clipping: [[NIChecker]] · PDF: `raw/NIChecker.pdf` · [source](https://dl.acm.org/doi/10.1145/3705311)**

Brings the multi-threaded verification stack to interrupt-driven code by *sequentializing*
the program and handing it to a model checker. Introduces the tool [[NIChecker (tool)]].
Its name is "Nested-Interrupt-Checker": [[Interrupt Nesting]] is the headline capability.

## Problem

Two challenges, stated as the paper's motivation:

1. Efficient static analysis produces too many false positives, because it discards path
   conditions and variable information for speed.
2. **Loops with large or unknown bounds** wreck [[Bounded Model Checking]]: BMC finds bugs
   in executions bounded by `u`, and the state space explodes as `u` grows. Some Racebench
   cases need the loop unfolded **10,000 times** before the bug appears.

[[Lazy-CSeq]], the state-of-the-art lazy sequentializer for threads, cannot be pointed at
interrupt code directly, for three reasons the paper enumerates: preemption is asymmetric,
interrupts can be masked, and interrupts cannot block ([[Asymmetric Preemption]]).

## Approach

1. **BIDP generation** — preprocess the C program into a *bounded interrupt-driven program*:
   bound each ISR's executions, inline calls, unwind loops to `u`. [[Loop Abstraction]] is
   applied *before* unwinding, replacing intractable loops with over-approximated versions,
   so deep bugs surface at a smaller bound.
2. **SP generation via [[Lazy Sequentialization]]** — translate the BIDP into a
   nondeterministic sequential C program: a main driver plus one entry function per ISR,
   executed round-robin. *Invocation conditions* encode interrupt priority and masking, and
   the highest-priority function runs atomically because no context switches are placed
   inside it. This is where the interrupt semantics actually live.
3. **Atomicity violation verification** — for a global variable and a chosen
   [[Access Interleaving Patterns|pattern]], auxiliary code is injected so the violation
   becomes an assertion, and [[CBMC]] discharges it. **The user supplies the variable and the
   pattern** — one run per (variable, pattern) combination.
4. **Optimizations** — LA, **slicing** (on a slicing criterion for the target global), and
   **preemption point reduction (PPR)**, which removes preemption points whose global-variable
   dependencies make them redundant.

The paper also proves **bounded correctness** of the translation (§6.1) — the only formal
correctness argument among the four sources.

## Evaluation

Built on Lazy-CSeq v2.1 with CBMC v5.6 as backend. Machine: Intel Xeon Silver 4215 (8 cores), 128 GB RAM, Ubuntu 20 — the most powerful setup in this corpus.

- **[[Racebench]] (Benchmark 1)**: 31 programs, **54 manual atomicity violations** — four
  more than the **50 bug points the benchmark itself annotates** for those cases
  ([[Racebench (documentation)]]), with no derivation given; see [[Contradictions]] —
  1–3 ISRs and up to three priority levels per case. NIChecker reports the **highest
  precision at 96.4%** among the compared tools; both it and [[intAtom]] find every
  violation, but NIChecker's false-positive rate is lower. Only 14 cases could be compared
  against [[CPA4AV]], which does not support the other 17 and additionally failed (timeout
  or out-of-memory) on the three cases needing an unwind bound of 10,000.
  The two false positives both involve pointers or structures, which NIChecker models coarsely.
- **[[Real-World Program Benchmark]] (Benchmark 2, 18 programs from six packages —
  logger, blink, brake, i2c, i8xx_tco, wdt_pci)**: **47 real atomicity violations in
  158.71 s with no false positives**, CBMC backend time 34.12 s, 4270.82 MB total memory.
  Most of the runtime is sequentialization (3–12 s per program), not solving.
- **Optimizations** (RQ3): slicing and PPR give up to **42.2% speed-up** in verification
  runtime. RQ1/RQ2 used only basic LazySeq and LA, which sufficed to find everything.

Baselines Rchecker and intAtom could not be obtained; their numbers come from their own
papers, on different hardware. The paper states this plainly.

## Claims to trust and claims to check

- Trust: the lazy-sequentialization construction and the bounded-correctness proof — the
  contribution that survives regardless of benchmark disputes.
- Trust: the LA result, i.e. that bounded tools without loop abstraction simply cannot reach
  deep bugs. [[CPA4AV]]'s failures on the 10,000-unwind cases are direct evidence.
- **Check hard**: the "47 violations, no false positives" on the real-world suite. That is
  *precision*, and [[BMC4AV (paper)]] later argues the recall behind it is 39.4%, with 57
  violations missed. See [[Contradictions]].

## Limitations and threats to validity

The paper's own limitations section concedes coarse handling of compound data types. The
larger practical limitation is the one BMC4AV attacks: NIChecker must be **told which global
variable and which pattern to look for**, so it is not fully automatic, and its
assertion-insertion strategy can miss violations when the auxiliary code lands in the wrong
place in a large program.

## Provenance note

Co-author R. Chen maintains [[Racebench]] and co-authors [[intAtom]], the baseline NIChecker
reports as its closest competitor ([[NASAC 2019 Prototype Competition]]). Not disqualifying,
but relevant when weighing both this paper's benchmark counts and [[BMC4AV (paper)]]'s
challenge to them.

## Relation to other sources

- Direct target of [[BMC4AV (paper)]], which uses NIChecker as its main baseline, reuses its
  benchmark and its loop-abstraction strategy, and disputes its recall.
- Same problem as [[IntRace (paper)]] via the opposite method: model checking rather than
  staged static filtering — and atomicity violations rather than data races.
- Descends from [[Lazy-CSeq]] and [[CBMC]] rather than from the interrupt-testing lineage of
  [[SDRacer (paper)]].
