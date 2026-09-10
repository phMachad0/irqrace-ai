---
type: concept
tags: [wiki, concept, llm]
sources: ["[[LLift (paper)]]", "[[IRIS (paper)]]", "[[SkipAnalyzer (paper)]]", "[[ChatGPT for Static Analysis (paper)]]", "[[AdaTaint (paper)]]"]
updated: 2026-08-23
status: draft
---

# Prompt Architecture

How an LLM stage is *structured*, as distinct from what it is asked. The evidence in this wiki
says this is the dominant variable — larger than model choice, and far larger than wording.

## The result that settles it

[[LLift (paper)]]'s ablation, on one dataset with one model, isolating four components:

| Configuration | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Simple prompt — "check this code for UBI bugs" | 0.12 | **0.15** | 0.13 |
| PGA | 0.26 | 0.38 | 0.31 |
| PGA + PP | 0.21 | 0.46 | 0.29 |
| PGA + PP + SV | 0.33 | 0.85 | 0.48 |
| PGA + PP + TD | 0.55 | 0.46 | 0.50 |
| **PGA + PP + TD + SV** | **0.87** | **1.00** | **0.93** |

Asking the question directly recovers 15% of the defects. The same model, same data, structured
pipeline: 100%. Any claim that "an LLM cannot do this" from a single-prompt experiment is
measuring the prompt, not the model.

Note also that components **interact**: PP alone *lowers* precision (0.26 → 0.21) and only pays
off once TD and SV are present. Ablating one at a time would have led to dropping it.

## The four components

**Domain-rule teaching by few-shot in-context learning.** LLift's PGA teaches the model what a
*post-constraint* is — a concept it does not reliably apply unprompted — with a small table of
code patterns (check-before-use, failure-check, and their loop and switch variants). Sensitivity
to those patterns alone eliminates over 70% of non-bug cases.

**Progressive prompting.** Rather than pre-loading every callee's body, let the model **ask**.
LLift instructs: *"If you encounter uncertainty due to a lack of function definitions, tell me
your need and I'll supply them"*, and teaches a fixed request format —
`[{"type":"function_def","name":"some_func"}]` — which the harness parses, resolves against the
source tree, and answers. Iterate until the model stops asking or the harness cannot answer.
Average 2.78 turns, maximum 8.

This is why precomputed slicing is not in the design: the question of how much context to
include is answered by **not deciding in advance**, and the model pulls what it needs
([[Program Slicing]]). Logging what it asks for is the cheapest way to learn what a context
record actually requires.

**Task decomposition.** Split the workflow into separate conversations, each of several turns,
passing results forward. In LLift's ablation TD contributes the largest precision gain and was
the only component that prevented context-window overflow.

**Self-validation.** Ask the model to review its own answer against explicit if-then rules
(*"when {case}, you should {action}"*) that add no new information — they restate invariants.
This produced the largest recall gain in the ablation, 0.46 → 1.00 in combination with TD.

Critically, LLift's self-validation rules are **biased toward recall**: it emphasises that
*"may_init is always a safe choice when you meet uncertain functions and code"*, explicitly
trading precision for soundness. That is the mechanism by which an LLM stage can be made
conservative, and it is directly reusable ([[LLM Triage]]).

## Mechanics that recur across sources

- **Chain-of-thought everywhere.** Every source in this branch requests an explanation of the
  reasoning; [[SkipAnalyzer (paper)]] and [[ChatGPT for Static Analysis (paper)]] call it
  zero-shot CoT and use it in all components.
- **Natural language first, JSON second.** LLift found that demanding JSON directly "interrupts
  the thought progression", and so asks for reasoning in English, then converts in a follow-up
  turn. [[IRIS (paper)]] achieves the same effect within one response by ordering the schema so
  the **explanation precedes the verdict**.
- **Delimiters around inputs.** `####` marking the code snippet, so the model knows exactly what
  it is analysing ([[ChatGPT for Static Analysis (paper)]]).
- **Batching** for cheap, repetitive classification, with batch size as a tunable
  hyper-parameter ([[IRIS (paper)]]).
- **Majority voting** across repeated runs to damp stochasticity ([[LLift (paper)]],
  [[AdaTaint (paper)]]).
- **Project-level context helps.** Including README and API documentation measurably improved
  IRIS's labelling accuracy.
- **Avoid negations.** LLift reports the model occasionally reading *"don't do X"* as *"do X"*,
  and writes every instruction affirmatively.
- **Source code, not IR.** LLift analyses C source rather than LLVM IR: fewer tokens, and
  identifier names carry meaning a model can use.

## When few-shot hurts

[[SkipAnalyzer (paper)]] finds the opposite of LLift on its face — GPT-4 zero-shot beats
one-shot beats 3-shot for Null Dereference detection (F1 74.27 → 69.67 → 65.09). The two are
reconcilable, and the distinction matters:

- LLift uses few-shot to **teach a rule the model does not know** (what a post-constraint is and
  how to apply it). That is knowledge transfer, and it works.
- SkipAnalyzer uses few-shot to **show examples of the task** the model already understands.
  That mostly consumes context and can anchor the model on the examples' surface features.

The rule of thumb: spend examples on a domain concept, not on demonstrating the obvious. And
when examples are used for a judgement task, **balance them** — SkipAnalyzer includes one
true-positive and one false-positive per few-shot set specifically to avoid biasing the verdict.

## Consistency is a separate axis from accuracy

LLift measures whether two runs of the same case agree, and reports that TD and SV improve
agreement independently of improving accuracy. For a research tool that must produce a
reproducible evaluation, consistency deserves its own measurement — an unstable verdict is not
usable as a result even when it is often right ([[LLM Stage Design]]).

Related: [[LLM Triage]], [[Specification Inference]], [[LLM-Assisted Repair]],
[[LLM Integration Patterns]].
