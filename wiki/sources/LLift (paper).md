---
type: source
tags: [wiki, source, llm]
sources: ["[[LLift (paper)]]"]
updated: 2026-08-23
status: solid
---

# Enhancing Static Analysis for Practical Bug Detection: An LLM-Integrated Approach

**PACMPL / OOPSLA 2024 · UC Riverside · clipping: [[LLift]] · PDF: `raw/LLift.pdf` · [source](https://dl.acm.org/doi/10.1145/3649828)**

The most important source in the LLM branch of this wiki, and the closest structural match to
[[Thesis Goal]]: a soundness-oriented static analyzer produces candidates it cannot decide, and
an LLM decides them. Peer reviewed at a top venue, evaluated on the Linux kernel, with an
ablation that quantifies every prompt-design decision.

## Problem

UBITect detects Use-Before-Initialization bugs in the Linux kernel with a two-stage pipeline:
a path-insensitive static analysis that **strives for soundness** and emits ~140,000 potential
bugs, then symbolic execution to filter them. Symbolic execution completes only 60% of cases;
**53,000 (40%) are abandoned to timeout (10 min) or memory limits (2 GB)**.

That is precisely the dilemma this project faces. Report all the undecided cases and drown the
user; discard them and lose real bugs. The paper names two underlying causes, and both apply
here:

- **Inherent knowledge boundary** — analyses must model functions and language features by
  hand and cannot model everything. The recurring Linux cases it lists are assembly, hardware
  behaviours, callback functions, and **concurrency**.
- **Exhaustive path exploration** — path-sensitive reasoning explodes.

## Approach

**Post-Constraint Guided Path Analysis.** Rather than explore all paths, focus on the
*post-constraint* `C_post`: the condition guarding the suspicious use. If `C_post` conflicts
with the path constraints or with the outcome under which an initializer is skipped, that path
is pruned and the variable is `must_init`. Sensitivity to return-value checks alone eliminates
**over 70%** of non-bug cases in the Linux kernel.

**The static analysis report is a formal tuple.** `SAR = ⟨v, U, F⟩` — suspicious variable, its
use, the enclosing function. The LLM stage consumes that structure, not prose.

**A conservative decision policy.** `Δ` reports a potential bug for anything **not** proven
`must_init`. The paper states plainly that this over-approximates and costs precision. It is
the rule of [[Soundness and False Negatives]] applied at the LLM boundary.

**Four prompt-design components**, each answering a named failure ([[Prompt Architecture]]):
`D#1` post-constraint guidance via few-shot in-context learning, `D#2` progressive prompt — the
LLM asks for function definitions on demand in a fixed JSON format and the harness supplies
them, `D#3` task decomposition into separate conversations and turns, `D#4` self-validation
against explicit if-then rules. Plus chain-of-thought in every prompt, majority voting across
runs, and **source code rather than LLVM IR** — cheaper in tokens and richer in identifier
semantics.

## Evaluation

GPT-4 (`gpt-4-0613`), temperature 1.0, `max_token` 1024. Implementation is ~1,000 lines of
Python and seven prompts totalling ~2,000 tokens.

- **Rnd-300** (300 of the 53,000 undecided cases): 10 positives reported, 5 true — **50%
  precision**, and **no real bugs missed** on manual inspection.
- Extended to 1,000 cases: 26 positives, 13 true; **4 confirmed as real bugs by the Linux
  community**, the rest judged "bugs only in theory" because they require hardware error
  conditions.
- **Recall against a known oracle**: of the 52 bugs UBITect's symbolic execution verified,
  LLift identifies **every one**.
- Against UBITect alone: reporting all Rnd-300 cases gives precision 0.02; discarding them
  gives recall 0. LLift converts an unusable trade-off into a usable one.
- **Cost**: ~7,000 tokens and **$0.43 per candidate** (GPT-4, 2024 pricing); 2.78 turns on
  average, maximum 8. About 50 human hours to establish ground truth.
- **Generality**: also run on Nginx and EDK II. On Nginx it correctly clears all 11 UBITect
  reports as `must_init`.

### The ablation — the most useful table in this branch

Measured on Cmp-40 (13 positives, 27 negatives):

| Configuration | Precision | Recall | F1 |
| --- | --- | --- | --- |
| Simple prompt ("check this code for UBI bugs") | 0.12 | **0.15** | 0.13 |
| PGA (post-constraint guidance) | 0.26 | 0.38 | 0.31 |
| PGA + PP (progressive prompt) | 0.21 | 0.46 | 0.29 |
| PGA + PP + SV (self-validation) | 0.33 | 0.85 | 0.48 |
| PGA + PP + TD (task decomposition) | 0.55 | 0.46 | 0.50 |
| **PGA + PP + TD + SV (full)** | **0.87** | **1.00** | **0.93** |

Naively asking the model finds **15%** of the bugs; the engineered pipeline finds **100%**.
Prompt architecture is not a finishing touch in this problem — it is the difference between a
useless tool and a working one. TD and SV also improve **consistency** (whether two runs agree)
and TD alone prevented every context-window overflow.

**Model comparison** on 9 straightforward bugs: GPT-4 9/9, GPT-3.5 89%, Claude 2 67%, Bard 67%.
Bard and GPT-3.5 could not use progressive prompting or task decomposition at all and had to be
run with PGA only.

## Claims to trust and claims to check

- **Trust the ablation.** Single team, single model, one dataset, components isolated cleanly.
  The best available evidence that prompt structure dominates outcome.
- **Trust the conservative decision policy** as a design pattern: recall-first discipline,
  implemented and measured.
- **Check the recall claim's scope.** "No missing bugs" rests on manual inspection of 300 cases
  plus the 52-bug UBITect oracle — stronger than this corpus's norm ([[Precision Metrics]]),
  but still manual inspection over a sample, and the 53,000 undecided cases have no ground
  truth at all.
- **The model comparison is obsolete.** Claude 2 and Bard are 2023-era models; those numbers
  say nothing about current models and must not be used to choose one.

## Limitations and threats to validity

13 false positives traced to *incomplete constraint extraction* (4), *information gaps in the
SAR handed over by UBITect* (5), and *missing runtime information* (4). Four cases exceeded the
context window while the progressive prompt walked into callees. The paper is candid that the
LLM cannot recover information the static analysis failed to put in the report — a direct
argument for making the context record rich ([[LLM Stage Design]]).

## Relation to other sources

- The template for this project's architecture; [[LLM Stage Design]] follows its shape.
- Same integration point as [[SkipAnalyzer (paper)]]'s FP filter and [[IRIS (paper)]]'s
  contextual triage, but with far more design effort and a much better result
  ([[LLM Integration Patterns]]).
- Its "knowledge boundary" argument names **concurrency** as a case static analysis models
  badly — the subject of this entire wiki.
