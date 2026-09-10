---
type: source
tags: [wiki, source, llm]
sources: ["[[Reducing False Alarms (paper)]]"]
updated: 2026-08-23
status: draft
---

# AI-Enhanced Static Analysis: Reducing False Alarms Using Large Language Models

**IEEE, 2025 · clipping: [[Reducing-FP]] · PDF: `raw/Reducing-FP.pdf` · [source](https://ieeexplore.ieee.org/document/11058686)**

The **cautionary tale** of this branch, and valuable precisely because it measures the thing
everyone else glosses over: what filtering costs in recall.

## Approach

CppCheck (via SonarQube) produces security alerts. In parallel, a **fine-tuned CodeBERT
vulnerability-prediction model** classifies each function as vulnerable or clean. Only alerts
inside functions predicted vulnerable are kept; the rest are withheld from the reviewer. So
prediction chooses the functions, static analysis chooses the lines.

Note this is a *fine-tuned encoder model*, not a prompted generative LLM — a different and much
cheaper design point than the rest of this branch.

## Evaluation

Big-Vul and ReVeal: real C/C++ functions linked to CVE-fixing commits.

| Big-Vul | Precision | Recall | F1 | FPR | Inspection Ratio |
| --- | --- | --- | --- | --- | --- |
| Static analysis alone | 5.88% | **46.90%** | 10.46 | 47.07% | 50.49% |
| + LLM-based prediction | **96.20%** | 40.66% | 57.16 | 0.10% | **2.44%** |

On ReVeal the pattern repeats: recall 6.88% → 5.93%, inspection ratio 15.41% → 1.34%.

## The metric worth adopting

**Inspection Ratio** `I = (TP + FP) / (TP + FP + TN + FN)` — the proportion of the codebase a
reviewer must examine to find the actionable alerts. It measures *triage burden directly*,
which is what a recall-first tool actually needs to report: recall can be held at 100% by
construction while `I` carries the cost. Recorded in [[Precision Metrics]].

## Claims to trust and claims to check

- **Trust the honesty.** The paper states outright that alert-filtering techniques "inevitably
  introduce false negatives due to the filtering process", quantifies it, and argues the trade
  is worthwhile only "in contexts where a slight decrease in detection accuracy can be
  considered acceptable". Its own future work names the recall drop as the thing to study.
- **Check whether the trade applies here.** It does not. Precision rose 90 points, recall fell
  ~6 points absolute — a good bargain for a security-triage workflow, and a fatal one for
  [[Thesis Goal]], where the whole claim is that no real defect is dropped.
- The absolute recall is low on both sides (46.9% before filtering), so this is a study of
  *relative* effect, not of a good detector.

## Relation to other sources

The clearest statement in this wiki of the cost that [[LLM Triage]]'s drop-versus-rank rule is
designed to avoid. Contrast [[LLift (paper)]], which reaches 1.00 recall by making the LLM's
decision policy conservative rather than by making it a classifier.
