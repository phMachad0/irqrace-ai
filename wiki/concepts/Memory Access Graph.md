---
type: concept
tags: [wiki, concept]
sources: ["[[BMC4AV (paper)]]"]
updated: 2026-08-17
status: solid
---

# Memory Access Graph

BMC4AV's central construct: a graph of memory events whose edges are the ordering relations
between them — **RF** (read-from), **WS** (write serialization), **FR** (from-read) — built
*inside the solver*, on the fly, instead of being encoded as constraints up front.

The pipeline in [[BMC4AV (paper)]]:

1. Symbolically encode the program (SSA + symbolic memory events) and derive the possible
   orderings across priorities.
2. Identify **potential** violations by pattern match, and extract for each one the **key
   partial orders** — the RF relations that would have to hold for it to be real.
3. Initialize a MAG and extend it under **RF-guidance**, inferring WS and FR edges via
   inference rules rather than generating order constraints for them. When the graph is
   stable and acyclic, the candidate is **confirmed** as a real violation.

The name of the paper — "From Potential to Confirmed" — is exactly this move.

**What the ablation attributes to each half** (Table 3, 18 real-world programs):

| Variant | What is removed | Result |
| --- | --- | --- |
| BMC4AV | — | 94/94 violations, 21.12 s, 567.21 MB |
| BMC4AV-NRF | RF-guidance | 63 false negatives; 258 key RF-edges vs 94 |
| BMC4AV-ARF | guidance (all RF-edges considered) | no false negatives but 368.17 s |
| BMC4AV-NG | the graph itself | same precision, 45.97 s and 739.74 MB |

Read together: **guidance buys precision, the graph buys efficiency**. That separation is the
most defensible claim in the paper, because it is one team, one machine, one benchmark — no
cross-paper number copying involved.

Related: [[Bounded Model Checking]], [[Atomicity Violation]], [[Lazy Sequentialization]].
