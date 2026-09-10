---
type: source
tags: [wiki, source, llm]
sources: ["[[AdaTaint (paper)]]"]
updated: 2026-08-23
status: draft
---

# LLM-Driven Adaptive Source–Sink Identification and False Positive Mitigation for Static Analysis

**ICCSAI 2025 (8th International Conference on Computer Information Science and AI) · clipping: [[AdaTaint]] · PDF: `raw/AdaTaint.pdf` · [source](https://dl.acm.org/doi/10.1145/3773365.3773410)**

> [!warning] Weakest evidence in this branch
> Minor venue, synthetic benchmarks, no artifact, and a results table whose baseline figures do
> not match those baselines' own papers. Read it for **ideas**, not for numbers.

## Approach

Four stages: a conventional taint analyzer produces candidate alerts; a context-extraction step
gathers API documentation, **commit history**, inline comments and usage examples; an LLM
produces updated source–sink rules *and* semantic embeddings of alerts; a downstream classifier
ranks and filters alerts.

Three ideas are worth taking:

- **Commit history as a context signal.** Security-related commit messages ("sanitize user
  input") are used to flag functions needing classification. The analogue here is mining
  race-fix commits, which [[Candidate Evaluation Subjects]] already proposes for ground truth —
  the same signal could feed the analysis itself.
- **Hybrid alert representation.** Each alert is embedded by combining an LLM embedding of the
  code snippet with *static features* — path length, presence of sanitization, control-flow
  feasibility — and a cheap classifier (logistic regression or gradient-boosted trees) ranks
  from that. This is far cheaper per candidate than an LLM call and is a plausible **first
  pass** ahead of expensive triage ([[LLM Stage Design]]).
- **Iterative feedback loop.** Developer false-positive labels are stored and used to refine the
  filter, making it project-specific over time.

Hallucination is mitigated by cross-checking across multiple prompts with **majority voting**,
the same device [[LLift (paper)]] uses. Reported cost is ~50 tokens per source–sink
classification.

## Evaluation

Juliet and SV-COMP — both **synthetic**.

| Method | Precision | Recall | F1 | FPR |
| --- | --- | --- | --- | --- |
| Static analyzer only | 62.1 | 71.3 | 66.4 | 38.7 |
| IRIS (as reported here) | 81.2 | 74.8 | 77.8 | 19.3 |
| **AdaTaint** | **84.3** | **75.4** | **79.6** | **17.5** |

Ablation: removing source–sink adaptation drops recall to 67.5; removing FP filtering raises
FPR from 17.5 to 35.7. A developer study with 12 participants reports triage time down 31% and
a trust score up from 2.7 to 4.1 on a 5-point scale.

## Claims to trust and claims to check

- **The ablation's shape is plausible** and matches [[IRIS (paper)]]'s independent finding that
  specification inference drives recall while triage drives precision.
- **Check every absolute number.** Juliet and SV-COMP are synthetic suites; the IRIS row here
  (81.2% precision) is irreconcilable with IRIS's own reported 84.82% average FDR on real
  projects, so these are re-derived on a different benchmark at best. This wiki does not treat
  the table as comparable to anything else ([[Precision Metrics]]).
- **Note what the recall column means.** AdaTaint's filter **drops** alerts and its recall is
  **75.4%** — roughly a quarter of real defects discarded by design. That is the outcome
  [[Thesis Goal]] exists to avoid, and it makes this paper a useful negative example
  ([[LLM Triage]]).

## Limitations

Error analysis attributes remaining false negatives to **context-window truncation** and
**implicit control flow** (reflection) — both of which have direct analogues here: truncated
slices, and function-pointer interrupt dispatch.

## Relation to other sources

Same integration point as [[IRIS (paper)]] ([[Specification Inference]]) with weaker evidence.
Its learned-classifier filter is the mechanism [[Reducing False Alarms (paper)]] evaluates more
honestly.
