---
type: project
tags: [wiki, project, llm]
sources: ["[[LLift (paper)]]", "[[IRIS (paper)]]", "[[SkipAnalyzer (paper)]]", "[[SAST-Genius (paper)]]", "[[Reducing False Alarms (paper)]]", "[[SDRacer (paper)]]"]
updated: 2026-08-27
status: draft
---

# LLM Stage Design

The concrete design for the LLM half of [[Thesis Goal]], derived from the seven sources in
[[LLM Integration Patterns]]. The static half is in [[Pipeline Design]]; this page covers what
happens after a candidate leaves the analyzer.

Design intent is the human's; every claim about what works is cited.

## Architecture

**Two LLM roles**, both downstream of the solver. They are separate stages with separate
prompts, separate evaluations and separate failure modes — [[LLift (paper)]]'s task
decomposition applied at the level of the system, not just the conversation.

```
                                 config file (hand-written)
                                          │
                                          ▼
  source ──► static front end ──► Z3 feasibility ──► (A) triage: rank + explain
                    ▲              may discard          │   never discards
                    │              (proof only)         ▼
                    │                            (B) repair proposal
                    │                                   │
                    └──── (C) re-verify ◄───────────────┘
                          own analysis + CBMC/bmc4av
```

**The interrupt model is a hand-written configuration file**, not an inferred one. The list of
masking primitives is a closed set per platform, both benchmarks already ship the configuration
(`priority.info`, the Racebench conventions), and the recall-critical half — identifying entry
points — is a `grep` for the registration API rather than a judgement. The case is set out in
[[Specification Inference]], which is now a documented alternative rather than part of this
design. An LLM *audit* of a hand-written config remains available as a late, optional recall
check.

**Z3 feasibility runs before triage and is not optional.** It is the only component permitted to
discard candidates, because `UNSAT` is a proof. It also determines what reaches the LLM at all —
see the next section.
violation.info
**(A) Triage** — ranks and explains; **drops nothing**. See the rule below.

**(B) Repair** — proposes an interrupt-specific fix with a required witness
([[LLM-Assisted Repair]]).

**(C) Re-verification** — not an LLM stage. The tool's own analysis for a certificate and for
regressions, then [[CBMC]] or the local `bmc4av` for inconclusive cases
([[Pipeline Design]]).

## The rule that shapes everything

**A solver may drop a candidate; the LLM may not.** Stage A assigns each candidate a bucket —
*likely real* / *uncertain* / *likely infeasible* / *likely benign* — plus an explanation. The
report contains all of them, ordered. Nothing is deleted.

The evidence for this is in [[LLM Triage]]: designs where the model classifies-and-discards
measure recall losses of 6 points ([[Reducing False Alarms (paper)]]) to ~25 points
([[AdaTaint (paper)]]), while [[LLift (paper)]]'s conservative decision policy reaches 1.00
recall in its ablation. The integration point is the same in all three; only the decision policy
differs.

Consequence for reporting: the headline metric is **recall (must be 100%) plus Inspection
Ratio** — the fraction of candidates a reviewer must read before finding all real defects —
rather than precision. Inspection Ratio comes from [[Reducing False Alarms (paper)]] and is
recorded in [[Precision Metrics]].

## The context record

[[LLift (paper)]] formalizes the analyzer's handover as `SAR = ⟨v, U, F⟩` and traces 5 of its 13
false positives to *information gaps in that report*. The record here is larger because the
defect is non-local. Proposed shape, per candidate:

| Field | Content |
| --- | --- |
| `id`, `class` | candidate identifier; `race-pair` or `atomicity-triple` |
| `variable` | name, declared type, `volatile`, declaration site |
| `accesses` | for each: `R`/`W`, source range, enclosing function, **flow** (main or ISR *n*) |
| `flows` | for each involved flow: entry point, priority, how it was identified |
| `call_paths` | entry point → access, one per access, with source ranges |
| `masking` | interrupts provably disabled at each access, and **across the interval** for triples |
| `loop_context` | enclosing loop nest per access; whether `A₁` and `A₂` are the same statement |
| `enclosing_source` | the full body of each access's enclosing function, as C |
| `solver_result` | Z3's verdict and, where it exists, the satisfying assignment or the reason it was inconclusive |
| `provenance` | which facts are proven, which are assumed by the configuration file, which are unknown |

**No precomputed slice.** The record ships the cheap, always-useful layers — the accesses, the
flows, the call paths, the masking state, the enclosing functions — and the model **asks** for
anything more through progressive prompting. Deciding relevance in advance was the
slicing approach; it is now a documented alternative rather than the mechanism, for the reasons
in [[Program Slicing]]. The short version: a backward slice on a global is not small, an
incomplete one silently manufactures false negatives, and the request distribution from
progressive prompting *is* the specification of what the record should contain — so measure it
before precomputing anything.

The `provenance` field is not bookkeeping. A model shown incomplete evidence will confidently
declare a candidate infeasible, and that miss is invisible afterwards. Marking partial evidence
*as* partial is the cheap defence; letting the model ask for more is the real one.

`solver_result` matters because triage now runs **after** Z3, on candidates the solver could not
decide. Telling the model what the solver established, and where it gave up, is exactly the
handover [[LLift (paper)]] formalizes — and the gap it traces 5 of its 13 false positives to.

## Prompt design

Follow [[Prompt Architecture]]. The four LLift components map as follows.

**D#1 — teach the domain rule by few-shot in-context learning.** LLift's insight is that the
model does not natively apply *post-constraints*, so it is taught with a table of code patterns.
The equivalent concept here is **when a preemption is actually possible**, and the model's prior
is actively wrong: trained largely on thread concurrency, it will reach for locks and
happens-before, neither of which holds under [[Asymmetric Preemption]]. The teaching set should
be a table of interrupt patterns with their verdicts:

| Pattern | Verdict to teach |
| --- | --- |
| both local accesses inside **one** critical section covering the interval | infeasible — the planted-trap shape in [[Racebench]] |
| each local access in its **own** critical section, gap between them unprotected | **still a real atomicity violation** — no race, but the ISR fits in the gap ([[Pair-Triple Unification]]) |
| preempting flow has **lower or equal** priority | no preemption *if strictly lower*; **equal priority is unresolved** — treat as possible |
| interrupt not yet enabled at this point in the flow | infeasible only if disabled on **every** path reaching it |
| the same statement inside a loop as both `A₁` and `A₂` | a valid triple — `svp_simple_029_001` annotates exactly this |
| ISR re-enables a lower-priority interrupt inside itself | masking is dynamic; `svp_simple_003_001_isr_1` does this |
| shared variable feeds a branch, or indexes an array or pointer | harmful rather than benign (Bai et al. criterion, via [[IntRace (paper)]]) |

Also state the priority convention explicitly — **larger number = higher priority**
([[Contradictions]] #3) — since the published papers disagree with the benchmark and the model
has read the papers.

**D#2 — progressive prompting.** Let the model request what it lacks, in a fixed parseable
format, and answer from the source tree. **This is the context-retrieval mechanism**, replacing
precomputed slicing: rather than guessing how much to include, ship the cheap layers and let the
model pull the rest ([[Program Slicing]]). Requests worth supporting: a function definition, the
full body of an ISR, the masking state at an arbitrary line, the definition of a macro, and all
other accesses to a given variable.

Instrument this from day one. **Logging what the model asks for, how often, and how deep is the
cheapest experiment in the project** — it measures the true context requirement directly, and it
is the evidence that decides whether precomputed context is ever needed.

**D#3 — task decomposition.** Separate conversations for: (i) is this interleaving *feasible*?
(ii) if feasible, is it *harmful*? (iii) what is the fix? Feasibility is a program-semantics
question and harmfulness is an intent question; merging them is how "benign" quietly becomes
"infeasible". Ask for reasoning in prose first, then convert to JSON in a following turn — or at
minimum order the schema so the explanation precedes the verdict ([[IRIS (paper)]]).

**D#4 — self-validation with recall-biased rules.** LLift's rules add no information; they
restate invariants, and they lean explicitly toward the safe answer. The equivalents here:

- *When the masking state along any path is unknown, treat the interrupt as enabled.*
- *When you cannot obtain a function's definition, assume it may access the shared variable.*
- *When two flows have equal priority, assume either may preempt the other.*
- *"Uncertain" is always a safe verdict; it costs a reviewer one candidate, while "infeasible"
  may hide a defect.*

**Mechanics**: chain-of-thought in every prompt; delimiters around the code
([[ChatGPT for Static Analysis (paper)]]); affirmative phrasing, no negations; source C rather
than LLVM IR; majority voting across runs for the final bucket.

**Where few-shot pays and where it does not**: use examples to teach the interrupt patterns
above (LLift's use), not to demonstrate the task itself — [[SkipAnalyzer (paper)]] found
zero-shot beating 3-shot when examples only showed the task. If examples of *verdicts* are used,
balance real defects against traps.

## Z3 first, then the LLM

The solver stage is **fixed in the pipeline**, ahead of triage, for three reasons that compound.

**Soundness.** Z3 is the only component allowed to discard, because `UNSAT` is a proof of
impossibility and nothing the LLM produces is ([[Path Feasibility Analysis]]). Removing it would
leave the pipeline with no sound filter at all, and the LLM would be forced into a role the
design forbids.

**Cost.** [[IntRace (paper)]] measures the solver eliminating **86.2%** of what reaches it. At
~208 candidates per program that is roughly 208 → 95 after the cheap concurrency filter → ~13
reaching the LLM. At [[LLift (paper)]]'s ~$0.43 per candidate the difference is about **$90 per
program versus about $6** — the solver stage pays for itself many times over, and it is the
reason per-program triage is affordable at all.

**Precedent.** This is exactly LLift's architecture: UBITect's symbolic execution runs first and
the LLM receives only the cases it *could not decide*. LLift is not a replacement for the solver;
it is what happens at the solver's limit. The same holds here, and it is why the solver's verdict
belongs in the context record.

Two consequences worth stating. First, the LLM sees a **biased sample** — by construction, the
hardest candidates, the ones a constraint solver could not settle. Evaluation must reflect that:
triage measured on all 86 Racebench candidates is a different experiment from triage measured on
the residue after Z3, and the second is the one that matches deployment. Second, an
**inconclusive** solver result (timeout, unsupported construct) must be distinguished from
`SAT`, and both must reach the LLM — collapsing them loses exactly the information LLift exists
to exploit.

A cheap ranking pass remains available on top, for ordering rather than filtering:
[[AdaTaint (paper)]] combines an embedding with static features (path length, masking present,
control-flow feasibility). Since it drops nothing it is compatible with the rule above, but at
~13 candidates per program it is not needed for cost — only if tier-3 subjects turn out much
larger.

[[IRIS (paper)]]'s pruning trick also applies directly: when the model rejects a candidate, ask
**which element** made it infeasible. "This variable is never written by an ISR" or "this
interrupt can never be enabled here" generalizes to every other candidate involving it.

## Testing and evaluation

**[[Racebench]] is an unusually good triage benchmark, by accident.** It contains **48
annotated bug points and 38 deliberately planted false-positive traps** in the 31 simple cases —
86 labelled candidates, adversarially constructed, several of them correctly protected by
`disable_isr`/`enable_isr` ([[NASAC 2019 Prototype Competition]]). That is a purpose-built test
for exactly this stage, and it is local.

Proposed evaluation, in order:

1. **Recall gate.** Every one of the 48 bug points must survive triage in a reported bucket.
   Any bug point ranked *likely infeasible* is a design failure, not a tuning issue — and is
   reportable as such.
2. **Trap rejection.** Of the 38 planted traps, how many are correctly bucketed low? This is the
   precision measure, and unlike precision it cannot be gamed by dropping candidates.
3. **Inspection Ratio** on the combined set, and on the [[Real-World Program Benchmark]] where
   `violation.info` supplies 45 true entries and 14 traps.
4. **Consistency.** Run each candidate *n* times and report agreement between runs.
   [[LLift (paper)]] found task decomposition and self-validation improved consistency
   independently of accuracy; an unstable verdict is not a usable result.
5. **An LLift-style ablation** — simple prompt → +domain rules → +progressive → +decomposition
   → +self-validation. This is the single most valuable experiment available, because it is the
   one result the concurrency branch has no equivalent of, and LLift's own table gives a
   directly comparable shape.
6. **Solver versus LLM on the same candidate set.** Now a *characterisation* experiment rather
   than an either/or: the solver stays in the pipeline, so the question is where the two agree,
   where the LLM adds value on the solver's residue, and whether the LLM ever contradicts a
   proof (which would be a prompt or context-record defect, and is worth catching early).
7. **Repair**: Syntax Rate by parser, Logic Rate against hand-written fixes
   ([[SkipAnalyzer (paper)]]), then the overhead and control-flow check
   ([[SDRacer (paper)]]), then re-verification.

**Report the model and date with every number.** Every model comparison in this corpus is
already stale ([[LLM Integration Patterns]]), and this one will be too.

## Risks

- **Context-record gaps become model errors.** LLift traced 5 of 13 false positives to gaps in
  the handover; [[AdaTaint (paper)]] attributes false negatives to context truncation. Mitigated
  by progressive prompting and the `provenance` field.
- **Nothing in the LLM branch has been tested on concurrency.** All seven sources address
  sequential defects, and triage quality varies by 30 precision points between two *sequential*
  bug types ([[ChatGPT for Static Analysis (paper)]]). Assume nothing transfers; measure on
  Racebench early, before building on it.
- **Prompt injection through analysed code.** The analysis reads untrusted source, comments
  included, and puts it in a prompt. A comment can attempt to instruct the triage model to
  dismiss a defect ([[SAST-Genius (paper)]]). Analysed code is data, never instructions — and a
  candidate dismissed on the strength of a comment is a deliberately induced false negative.
- **Benignity judgements becoming unexamined assumptions.** [[BMC4AV (paper)]] asserts `(R,W,W)`
  is benign without argument, and the wiki treats that as a defect. An LLM making the same call
  case-by-case must state a criterion that is written down and testable, or the project has
  reproduced the problem it set out to fix ([[Open Questions]]).
