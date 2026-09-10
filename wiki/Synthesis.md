---
type: synthesis
tags: [wiki, synthesis]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-27
status: draft
---

# Synthesis — what the four sources collectively say

The evolving thesis. Rewritten on every ingest; claims here must be traceable to a source
page. Current state: four sources, 2020–2026.

## 1. The field is defined by one structural fact

Every source opens by arguing that thread techniques do not transfer, and they converge on
the same reasons ([[Asymmetric Preemption]]): interrupts preempt asymmetrically, cannot
block, are controlled by masking rather than locking, and fire only in particular hardware
states. The consequence is technical, not rhetorical — happens-before, the foundation of
thread race detection, is unsound here, so the whole field falls back on **pattern matching
plus a filter** ([[Access Interleaving Patterns]]).

## 2. Everyone has the same architecture; the fight is over the filter

Cheap over-approximate matching produces hundreds of candidates per program — IntRace
measures ~208 per real program — and every tool's identity is what it does next:

| Filter | Tool | Cost |
| --- | --- | --- |
| replay on a virtual platform | [[SDRacer (tool)]] | needs a simulatable target |
| SMT path constraints | [[IntRace (tool)]] | 69.7% of runtime |
| assertions + sequentialized BMC | [[NIChecker (tool)]] | user must name variable + pattern |
| in-solver graph confirmation | [[BMC4AV (tool)]] | preprint-stage evidence |

The historical drift is from **execution toward verification**: ground truth from a real run
(2020) → constraint solving (2024) → whole-program bounded proof (2024–2026). Each step buys
scalability and loses contact with real hardware behaviour.

## 3. Precision is solved on paper; recall is not

Three of the four tools report zero or near-zero false positives on their own benchmarks.
Precision is no longer the frontier. **Recall is**, and it is measured badly: "no false
negatives" means manual inspection in the older papers and bounded absence in the newer ones
([[Precision Metrics]]). [[BMC4AV (paper)]]'s claim that [[NIChecker (tool)]] missed 57 of 94
violations — while reporting 100% precision — is the sharpest illustration available that
this literature's evaluation practice can hide a factor-of-two error ([[Contradictions]]).

## 4. Benchmarks are shared; ground truth is not

The whole field evaluates on [[Racebench]] and one 18-program [[Real-World Program Benchmark]],
which should make results comparable. It does not: the papers assume 38, 50, 54 or 94
defects on the same code, depending on defect class and on whether `(R,W,W)` counts. Almost
every cross-paper number in circulation is therefore uncomparable, and the papers themselves
are more candid about this than their headline abstracts suggest.

Ingesting the benchmark's own documentation ([[Racebench (documentation)]]) anchors one end
of this: Racebench 2.1 contains **53 bug points and 38 planted false-positive traps**, with
50 and 33 of them in the 31 simple cases. [[IntRace (paper)]]'s count matches exactly;
[[NIChecker (paper)]]'s exceeds it by four without explanation; [[BMC4AV (paper)]]'s derives
from NIChecker's rather than from the annotations. And the annotations are **access triples**,
so the shared benchmark specifies atomicity-violation-shaped defects even for the papers that
call them data races — which puts the field's organizing distinction in question
([[Contradictions]] #5).

## 4b. The evaluation culture was set by a competition

Racebench was built for the [[NASAC 2019 Prototype Competition]], where a false positive cost
−3 and a detection earned +2, and where 38 traps were planted deliberately. That scoring
function — precision rewarded, recall priced at zero — propagated into a literature that now
routinely reports 100% precision alongside unmeasured recall. Naming this is probably the
sharpest critical move available to a thesis on this corpus.

## 5. Automation is the axis of competition, quietly

Each generation attacks the previous one's manual burden as much as its numbers: IntRace
still needs a **config file** for ad-hoc masking; NIChecker needs a **variable and pattern per
run**; BMC4AV's central selling point is that it needs neither. Any adoption argument in the
thesis should be made on this axis, not on seconds — which is the reason this project treats a
dashboard as part of the contribution rather than as packaging ([[Dashboard Design]]).

## 6. Repair died with the oldest tool

[[SDRacer (tool)]] (2020) detects, validates *and* repairs, with measured overhead. Nothing
since repairs anything. The verification turn kept precision and lost the fix — an obvious
gap, and a natural framing for original work ([[Open Questions]]).

## Working thesis statement (draft)

> Detection of concurrency defects in interrupt-driven programs has converged on a common
> pipeline — pattern matching over shared accesses, followed by a progressively more
> expensive feasibility filter — and has largely solved precision on the community
> benchmarks. What remains open is recall under honest ground truth, evaluation practice that
> permits genuine cross-tool comparison, unification of the data-race and atomicity-violation
> analyses, and automated repair, which has been absent since 2020.

*Revise this on every ingest.*

## 7. Where this project enters

The four gaps the statement above names — recall, comparability, unification, repair — are
exactly the four the tool described in [[Thesis Goal]] targets, which is why that framing is
worth keeping sharp. Three of them are addressed by the same architectural decision: build a
deliberately over-approximating front end covering **both** defect classes' patterns, and move
the judgement work (is this feasible? is it benign? how should it be fixed?) into an LLM stage
downstream, where it can be inspected rather than buried in a solver. See
[[Soundness and False Negatives]] for what "over-approximating" has to mean concretely, and
[[Reimplementation Assessment]] for which source supplies which piece.

### The second literature, and the empty intersection

Seven sources on **LLM-assisted static analysis** were ingested on 2026-08-23
([[LLM Integration Patterns]]). They converge on a division of labour that fits this project
exactly — the analyzer does the whole-program reasoning, the LLM does the local judgement — and
[[IRIS (paper)]] states the reason: LLMs are ineffective at detecting defects in real code
alone, because that needs whole-repository reasoning.

Three of their findings change the design rather than decorate it. **Prompt architecture
dominates**: [[LLift (paper)]]'s ablation moves recall from 0.15 to 1.00 on one model and one
dataset, purely by structuring the interaction ([[Prompt Architecture]]). **Filtering costs
recall unless the decision policy is conservative**: 6 points in
[[Reducing False Alarms (paper)]], ~25 in [[AdaTaint (paper)]], against 1.00 recall for LLift's
report-unless-proven-safe policy ([[LLM Triage]]). And **the LLM can attach before the analyzer,
not only after it** — [[IRIS (paper)]] doubles CodeQL's detection rate by inferring the
specifications it was missing. That last pattern turns out **not** to transfer: it depends on an
open-world specification problem, and the interrupt model is a closed set per platform that both
benchmarks already ship ([[Specification Inference]]). Which is itself a finding worth keeping —
results from this branch import only when the condition that produced them holds.

But all seven work on **sequential** defects. Nothing in either literature applies LLM
assistance to interrupt concurrency, and LLift explicitly names concurrency as something static
analysis models badly before setting it aside. The intersection is empty, and that is where
[[Thesis Goal]] sits — which is a stronger novelty claim than any single gap listed above.

Worth noting too that the same evaluation pathology recurs: two of the seven report no recall at
all, and they are the two claiming the largest precision gains ([[Precision Metrics]]).

The one gap this does *not* automatically close is comparability. Since both benchmarks'
ground truth is disputed ([[Contradictions]] #1, #2) and both are now known to be obtainable,
re-counting one package by hand is both a prerequisite for any honest recall number here and,
on its own, an original result ([[Open Questions]]).
