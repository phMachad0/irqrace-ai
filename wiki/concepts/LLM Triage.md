---
type: concept
tags: [wiki, concept, llm]
sources: ["[[LLift (paper)]]", "[[IRIS (paper)]]", "[[SkipAnalyzer (paper)]]", "[[ChatGPT for Static Analysis (paper)]]", "[[Reducing False Alarms (paper)]]", "[[AdaTaint (paper)]]"]
updated: 2026-08-23
status: draft
---

# LLM Triage

Using a language model to decide which of a static analyzer's candidates are real. The most
common LLM integration point in the literature, the one [[Thesis Goal]] depends on, and the one
where a design mistake costs recall invisibly.

## The rule

**A solver may drop a candidate; the LLM may not.** An `UNSAT` result is a proof of
impossibility, which is what [[Soundness and False Negatives]] requires of a filter. An LLM's
judgement is not a proof. So the LLM stage **ranks, explains and buckets**; every candidate
stays in the report ([[Pipeline Design]]).

This is not a philosophical preference. It is the difference between the two outcomes measured
in this branch.

## The two outcomes

**[[Reducing False Alarms (paper)]] — the filter that drops.** A fine-tuned model classifies
functions as vulnerable, and alerts in functions predicted clean are withheld. On Big-Vul:
precision 5.88% → 96.20%, inspection ratio 50.49% → 2.44%, and **recall 46.90% → 40.66%**. The
paper is admirably direct that such techniques "inevitably introduce false negatives due to the
filtering process" and that the trade is defensible only where losing detections is acceptable.
[[AdaTaint (paper)]]'s learned filter lands in the same place, at 75.4% recall.

**[[LLift (paper)]] — the conservative decision policy.** Anything not *proven* safe is reported.
Precision is 50% on real data and the ablation's full configuration reaches **recall 1.00**. The
LLM still makes a judgement; what differs is the direction it errs in, which is fixed by
prompt-level rules that say so explicitly — *"may_init is always a safe choice when you meet
uncertain functions"*.

The lesson is that "LLM triage" describes two different designs with opposite recall
properties, and papers rarely distinguish them. What matters is the **decision policy**, not
the model.

## Practical design points from the corpus

**Ask which element is spurious, not just whether.** [[IRIS (paper)]] has the model name whether
the *source* or the *sink* is the false one when it rejects a path, then prunes every other path
through that element without further calls. The analogue here: if the model judges a candidate
infeasible because a particular variable is never shared, or a particular ISR can never be
enabled at that point, that verdict generalizes to every candidate involving it — a large saving
when one program yields ~208 candidates.

**Triage quality is bug-type-dependent, and the gap is large.**
[[ChatGPT for Static Analysis (paper)]] reports false-positive-removal precision of **93.88%**
for Null Dereference and **63.33%** for Resource Leak — same model, same prompts, same analyzer.
There is no basis for assuming performance transfers to a defect class the model has not been
tested on, and interrupt-driven concurrency defects are further from both of those than they are
from each other.

**Below a capability threshold, triage makes things worse.** [[IRIS (paper)]]'s ablation finds
contextual analysis improves precision for GPT-4, GPT-3.5 and Llama-3 70B but *degrades* it for
smaller models, which "are more likely to respond with vulnerable". For a recall-first tool that
particular failure is the safe direction — but it means a small local model cannot be assumed to
be a cheap substitute.

**A cheap pre-pass may be better than an LLM call per candidate.**
[[AdaTaint (paper)]] scores alerts by combining an LLM embedding of the code with static features
— path length, sanitization present, control-flow feasibility — and ranks with logistic
regression or gradient-boosted trees. As a *ranking* stage that never drops anything, this is
compatible with the rule above and far cheaper than full triage at ~$0.43 per candidate.

**Explanations are part of the output, not decoration.** Every source requests reasoning, and for
a recall-first tool the explanation is what makes a low-ranked candidate auditable. A ranking
without a reason cannot be checked, and an unchecked ranking is a filter in disguise.

## The failure mode to watch

An LLM told an interleaving "looks infeasible" on the strength of an **incomplete context
record** will confidently say so, and the resulting miss is attributed to the model rather than
to the evidence that omitted the relevant path. That is a false negative laundered through
context capture, and it is the main reason this project retrieves context on demand rather than
precomputing a slice ([[Program Slicing]]). Two defences: make the model *ask* for what it lacks
([[Prompt Architecture]]'s progressive prompt), and label partial evidence as partial in the
prompt.

Related: [[Prompt Architecture]], [[LLM Integration Patterns]], [[Precision Metrics]],
[[LLM Stage Design]].
