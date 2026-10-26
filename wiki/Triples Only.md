---
type: project
tags: [wiki, project, decision]
sources: ["[[Thesis Goal]]", "[[Pair-Triple Unification]]", "[[Racebench]]", "[[Soundness Assumptions]]"]
updated: 2026-10-24
status: solid
---

# Triples Only

**Direction (Pedro, 2026-10-24).** The tool generates, filters and reports **one candidate
class: the atomicity-violation triple** `(A₁, B, A₂)` — A₁ and A₂ in one flow, B in another, on
one shared location, in one of the four unserializable shapes. The two-access **race pair**
`(A, B)`, which stages 1–3 had derived alongside the triples since W3–W4, is removed from the
code, the contracts and the project documentation.

This page is the one place in the project layer that describes the pair. The literature pages
still describe what the papers do — [[IntRace (paper)]] and [[SDRacer (paper)]] are pair
detectors, and [[Data Race]] and [[Pair-Triple Unification]] are about pairs — because that is
what the sources say. The historical records (`log.md`, the 2026-10-23 meeting notes in
`wiki/reunioes/`) keep describing what was done and presented at the time.

## What was removed

The pair was **two accesses to one shared location, in two different flows, at least one a
write**. It was judged by the *point property* — may B's flow run while A's flow is at A, or the
reverse — where a triple is judged by the *interval property* over `[A₁, A₂]`. The pipeline
derived both from one access set and judged them independently, following
[[Pair-Triple Unification]]; neither was ever derived from the other.

On Racebench the pair never counted toward the recall gate: the ground truth is annotated as
triples, and pairs were scored only as a separate "pair coverage" number.

## What it measures — not why it was decided

| | with pairs (W6–W7) | triples only |
| --- | --- | --- |
| stage 1 candidates | 566 (316 triples + 250 pairs) | **316** |
| after stage 2 | 436 (202 + 234) | **202** |
| reaching the LLM | 383 (166 + 217) | **166**, 5.4 per subject |
| recall gate | 48/48 | **48/48** |
| traps reaching the LLM | 16/38 | **16/38** |

Pairs were 57% of what reached the LLM, so the triage bill falls by the same share.

**Regression check.** Every triple result was compared, subject by subject, against a snapshot of
the last run before the change: the same candidate ids, the same stage-2 decisions and masking
states, the same solver verdicts, the same matches against the ground truth — **zero differences
across the 31 cases**. The Inspection Ratio rises (0.34 → 0.84 after stage 3) only because its
denominator shrinks: triples were already listed first.

## What it costs in recall

*Recall outranks precision* in this project, so the cost is stated: a defect that needs only one
access in each flow — an ISR write that a single unprotected read in the main task can tear or
overwrite, with no second access in the main task to make an interval — is **no longer a
candidate at all**. That is out of scope by decision, not refuted by proof, and it is now an
entry in [[Soundness Assumptions]] (H1e) so that the no-false-negatives claim of [[Thesis Goal]]
is stated for the class it covers.

It also changes what can be compared: the race-detection papers report pairs, so their numbers no
longer have a counterpart here ([[Reported Results Across Papers]]).

## What changed in the contracts

| Contract | Change | Version |
| --- | --- | --- |
| C1 | `analysis.candidate_classes` removed | `c1/1.0.0` → **`c1/2.0.0`** |
| C2 | `class` is the constant `atomicity-triple`; exactly three accesses; `pattern` one of `RWR`, `RWW`, `WWR`, `WRW`; `loop_context.a1_a2_same_statement` a boolean | `c2/1.0.0` → **`c2/2.0.0`** |
| C3 | the drop record's `class` narrowed the same way; the manifest and the layout unchanged | `c3/1.0.0` |
| C4 | unchanged | `c4/1.0.0` |

**The fingerprint is unchanged**, so every triple keeps its candidate id and Track B's result cache,
keyed by fingerprint, stays valid for triples. Tool version `0.1.0` → `0.2.0`.

## Track B

Track B's branch still produces and consumes pairs (fixtures, UI, repair, scripts). The refactor
there is tracked in GitHub issue
[phMachad0/irqrace-ai#1](https://github.com/phMachad0/irqrace-ai/issues/1).

Related: [[Thesis Goal]], [[Pipeline Design]], [[Soundness Assumptions]], [[Roadmap]].
