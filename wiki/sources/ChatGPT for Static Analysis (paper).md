---
type: source
tags: [wiki, source, llm]
sources: ["[[ChatGPT for Static Analysis (paper)]]", "[[SkipAnalyzer (paper)]]"]
updated: 2026-08-23
status: draft
---

# Effectiveness of ChatGPT for Static Analysis: How Far Are We?

**AIware 2024 (1st ACM International Conference on AI-Powered Software), Porto de Galinhas · Mohajer, Aleithan, Shiri Harzevili, Wei, Boaye Belle, Pham, Wang (York University) · clipping: [[Static-Chatgpt]] · PDF: `raw/Static-Chatgpt.pdf` · [source](https://doi.org/10.1145/3664646.3664777)**

The empirical study behind [[SkipAnalyzer (paper)]] — same authors, same bug types, same
analyzer. Read it for the **prompt-template mechanics** and the honest metric discussion rather
than for a separate result.

## Problem and setup

Two static-analysis tasks — bug detection and false-positive warning removal — for two bug
types, Null Dereference and Resource Leak, gathered with Infer from 10 open-source projects:
**222 Null Dereference and 46 Resource Leak instances**.

## Findings

- Detection: accuracy/precision up to 68.37% / 63.76% (Null Dereference) and 76.95% / 82.73%
  (Resource Leak), improving Infer's precision by 12.86 and 43.13 points respectively.
- False-positive removal: precision up to **93.88%** for Null Dereference but **63.33%** for
  Resource Leak.

The gap between the two bug types is the finding worth carrying: the same prompts, the same
model and the same analyzer produce a 30-point precision difference purely from the defect
class. Assuming LLM triage transfers to a *new* defect class is not supported by this evidence
([[LLM Triage]]).

## Prompt-template mechanics

The most reusable part of the paper, and it is concrete:

- Prompt templates give **detailed descriptions and context for each bug type**, including the
  criteria that classify a defect as that type.
- **Delimiters mark the inputs** — `####` around the code snippet — "ensuring that the LLM
  focuses solely on this section".
- Every template ends with two elements: a request to **explain the decision process**, and a
  directive to emit output in a **specified format** (JSON) for parsing.
- Few-shot uses K = 3, chosen because more examples breach the token limit — a budget decision,
  not a tuned optimum.

## Claims to trust and claims to check

- Trust the prompt-template structure; it is stated precisely enough to reimplement.
- **Check the metric framing, which the paper itself flags**: because the dataset consists of
  Infer's warnings, "precision is the only metric available for evaluating Infer" — recall and
  accuracy for the baseline are not computable. Any comparison here is a precision comparison,
  and the study says so.

## Relation to other sources

Companion to [[SkipAnalyzer (paper)]]; the two share a dataset and should be counted once.
Its bug-type sensitivity is the empirical counterweight to [[LLift (paper)]]'s optimism, and
its zero-shot-beats-few-shot pattern is analysed in [[Prompt Architecture]].
