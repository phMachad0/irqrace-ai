---
type: concept
tags: [wiki, concept]
sources: ["[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[SDRacer (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-20
status: draft
---

# Pair-Triple Unification

Whether [[Data Race]] detection (two accesses) and [[Atomicity Violation]] detection (three
accesses) can be run as one analysis. This is the central design question for
[[Thesis Goal]], since nothing in the corpus detects both classes in one pass
([[Tool Capability Matrix]]).

The proposal under evaluation: **project every atomicity-violation triple onto its
constituent access pairs, detect at the pair level, and treat the two defect classes as one.**

## What actually distinguishes the two defects

Not the number of accesses — that is a symptom. The real difference is what the defect is
*relative to*:

- A **data race** is a property of two accesses and the machine: same location, at least one
  write, no ordering between them. It is decidable from the program and the priority/masking
  model alone.
- An **atomicity violation** is a property of three accesses and an **intention**: the
  programmer meant `A₁ … A₂` in the preempted flow to be indivisible, and a remote access `B`
  landed in between, making the execution equivalent to no serial execution. Nothing in C
  states that intention, which is why every tool in the corpus *guesses* the atomic region —
  in practice, "any two accesses to the same location in the same flow".

So the triple is not a race plus an extra access. It is a claim about an **interval**
`[A₁, A₂]`, where the race is a claim about an **instant**. That distinction turns out to
decide whether the unification is sound.

## The containment argument holds — at stage 1

Write a triple as `(A₁, B, A₂)` with `A₁, A₂` in the preempted flow and `B` in the preempting
ISR. Project it onto its two adjacent pairs `(A₁, B)` and `(B, A₂)`. For all four patterns:

| Triple    | pairs it projects onto | both in IntRace's pair set? |
| --------- | ---------------------- | --------------------------- |
| `(R,W,R)` | `(R,W)`, `(W,R)`       | yes                         |
| `(W,W,R)` | `(W,W)`, `(W,R)`       | yes                         |
| `(W,R,W)` | `(W,R)`, `(R,W)`       | yes                         |
| `(R,W,W)` | `(R,W)`, `(W,W)`       | yes                         |

[[IntRace (paper)]]'s Table 1 pair set is `(W₁,W₂)`, `(W₁,R₂)`, `(R₁,W₂)` — every pair over
the same location, across flows, containing at least one write. Every adjacent pair of every
harmful triple contains at least one write, because in each of the four patterns the middle
access conflicts with at least one neighbour and in fact with both. **So the pair set
strictly contains the triple set, and pair-level matching cannot miss an atomicity violation
that triple-level matching would find.**

### Confirmed against the benchmark's own ground truth

Parsed from `racebench/2.1_remarks` on 2026-08-20 (see [[Racebench]] for the corrected
counts and the parser caveats): **48 annotated bug points across the 31 simple cases, and
48 of 48 project onto write-bearing pairs.** Shape distribution and projection:

| Bug-point shape | Count | | Projected adjacent pair | Count |
| --- | --- | --- | --- | --- |
| `(R,W,R)` | 25 | | `(R,W)` | 41 |
| `(R,W,W)` | 10 | | `(W,R)` | 38 |
| `(W,W,R)` | 7 | | `(W,W)` | 17 |
| `(W,R,W)` | 6 | | *no-write pairs* | **0** |

The single apparent `(R,R)` projection came from one mistyped annotation, not from a real
defect: `svp_simple_016_001` bug point 1 is written `<W#24>,<R#33>,<R#25>`, but line 33 is
`global_var1 = 0x09;` — a write. Corrected, it is `(W,W,R)`. So on the community benchmark the
containment is not merely provable but observed with no exceptions.

**This also dissolves the `(R,W,W)` dispute at detection time.** `(R,W,W)` projects onto
`(R,W)` and `(W,W)`, both unambiguous races, so a pair-level detector reports those 10 bug
points whether or not one agrees with [[BMC4AV (paper)]] that the pattern is benign
([[Contradictions]] #2). Benignity becomes a downstream judgement, which is exactly where
[[Soundness and False Negatives]] says it belongs.

## Where the proposal breaks: the interval, not the instant

The containment argument covers **stage 1**, pure syntactic matching. It does **not** survive
stage 2, and this is the part worth being careful about.

Consider a preempted flow that protects each access individually but not the span between
them:

```c
void task(void) {
    disable_isr(1);  a = shared;   enable_isr(1);   /* A1 */
    /* ... interrupts enabled here ... */
    disable_isr(1);  shared = a+1; enable_isr(1);   /* A2 */
}
void isr_1(void) { shared = 0; }                    /* B  */
```

There is **no data race**: `B` cannot interleave with `A₁`, and cannot interleave with `A₂` —
both pairs are provably impossible, and a correct masking filter
([[Interrupt Masking and Synchronization]]) will discard both. But `B` *can* execute in the gap between the two
critical sections, so `(A₁, B, A₂)` is a real atomicity violation.

A pair-level detector with a sound stage-2 filter therefore reports **nothing** here. The
false negative is created by the filter, not by the pattern matching — precisely the failure
mode [[Soundness and False Negatives]] is about, and a demonstration that the two defect
classes are *not* interchangeable however the benchmark happens to annotate them.

The reason is structural: the feasibility question for a pair is *"can B execute at the
instant of A?"*, and for a triple it is *"can B execute anywhere in the interval
[A₁, A₂]?"*. The interval question is strictly weaker — satisfiable in strictly more cases —
so answering the pair question and inferring the triple answer loses defects.

## The recommendation

Unify the **front end**, keep **both candidate sets**, and never derive one from the other.

1. **One shared front end.** Shared-location identification, access enumeration, flow and
   priority model, masking model, call graph — all of this is common to both defect classes
   and is where the real engineering cost lives. This is the genuine unification, and it is
   what makes a single-pass tool worth building.
2. **Two derivations from the same access set.**
   - *Pairs*: every cross-flow, same-location pair with at least one write.
   - *Triples*: every remote access `B` against every ordered pair `(A₁, A₂)` of same-location
     accesses in one flow such that `B` can occur in `[A₁, A₂]`.
   Enumerate triples **directly**, not by combining confirmed pairs.
3. **Filter each with its own feasibility query** — instant-feasibility for pairs,
   interval-feasibility for triples. A candidate is dropped only when its own query proves it
   impossible.
4. **Group before reporting.** A pair that also participates in a triple is reported with the
   triple attached, because the *repair scope differs*: a race is fixed by protecting an
   access; an atomicity violation is fixed by making `[A₁, A₂]` atomic — [[SDRacer (paper)]]'s
   "extend an existing critical section" rather than its "insert `irq_disable`/`irq_enable`".
   An LLM handed only the pair will propose the wrong edit.

The net effect is what the original proposal wanted — more candidates, nothing discarded, one
analysis covering both classes — without the recall hole, and with report shapes that carry
the information the repair stage needs.

## Consequences for measurement

Reporting at pair granularity makes the numbers incomparable to the literature, which counts
triples. One triple yields up to two pairs, and one pair can belong to several triples — the
25 `(R,W,R)` bug points above collapse onto far fewer distinct pairs. So recall against
[[Racebench]] must be measured **after** triple reconstruction, mapping back to the annotated
bug points; pair counts are an internal diagnostic, not a comparable result
([[Precision Metrics]]).

## What this settles

[[Contradictions]] #5 asked whether the benchmark measures races or atomicity violations. The
answer is now precise: the annotations are triples, every triple contains races, so both
literatures are looking at overlapping evidence — but the defect classes remain distinct,
because the split-critical-section case above is an atomicity violation containing no race at
all. The overlap is real and the identification is false.

Related: [[Access Interleaving Patterns]], [[Path Feasibility Analysis]], [[Pipeline Design]].
