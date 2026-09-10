---
type: source
tags: [wiki, source, llm]
sources: ["[[SkipAnalyzer (paper)]]", "[[ChatGPT for Static Analysis (paper)]]"]
updated: 2026-08-23
status: solid
---

# SkipAnalyzer: A Tool for Static Code Analysis with Large Language Models

**arXiv 2310.18532 (v2) · Mohajer, Aleithan, Shiri Harzevili, Wei, Boaye Belle, Pham, Wang (York University) · clipping: [[SkipAnalyzer]] · PDF: `raw/SkipAnalyzer.pdf`**

The only source in this branch that covers **all three** stages of the loop this project needs:
detect, filter false positives, and **repair**. Its repair numbers are the strongest evidence
available that the fix-generation half of [[Thesis Goal]] is feasible.

> [!warning] Not independent of [[ChatGPT for Static Analysis (paper)]]
> Same seven authors, same institution, same subject bug types, same static analyzer (Infer),
> and an overlapping dataset. Treat the two as one body of evidence — the AIware'24 paper is
> the empirical study, this is the tool paper. Counting them as two agreeing results would be
> double-counting.

## Problem

Static bug detectors report warnings with poor precision; Infer's measured precision on the
authors' dataset is 50.9% for Null Dereference and 39.6% for Resource Leak. Triage is manual,
and repair is manual after that.

## Approach

Three independent LLM components, each a single prompt over a method-scope code snippet:

1. **Detector** — code in, warnings out. The prompt carries a specification of the bug type
   (e.g. "no null check before dereferencing") plus structured output requirements.
2. **False-positive filter** — code *and* the warning in, keep/discard out. Accepts warnings
   from Infer or from its own detector.
3. **Repair** — code and warning in, patched code out.

All components request an explanation of the decision process (zero-shot chain-of-thought), and
components 1 and 2 support zero-shot, one-shot and 3-shot prompting. Repair is zero-shot only,
because examples would exceed the token limit.

**Methodology worth copying**: 5-fold cross-validation for selecting few-shot examples, and each
few-shot set is **balanced with one true-positive and one false-positive example** to avoid
biasing the model toward one verdict.

## Evaluation

GPT-4 (8,192-token limit) and GPT-3.5-Turbo (4,097); inputs constrained to method scope because
of those limits. Dataset: Null Dereference and Resource Leak warnings from Infer over 10
open-source Java projects.

**Detection (RQ1)** — best configurations, own dataset: Null Dereference GPT-4 zero-shot
accuracy 68.37%, precision 63.76%, recall 88.93%, F1 74.27%; Resource Leak GPT-4 zero-shot
accuracy 76.95%, precision 82.73%, recall 55.11%.

**The counterintuitive result**: *zero-shot beats one-shot beats few-shot* for GPT-4 on Null
Dereference (F1 74.27 → 69.67 → 65.09). More examples made it worse. See
[[Prompt Architecture]] for why this does not contradict [[LLift (paper)]].

**False-positive removal (RQ2)** — reported as precision improvement over the underlying
detector, against baselines from Kharkar et al. (GPT-C, a feature-based logistic regression, and
DeepInferEnhance). The companion study reports precision reaching **93.88%** for Null
Dereference but only **63.33%** for Resource Leak: LLM triage quality is strongly
**bug-type-dependent**, which is a warning for anyone assuming it will transfer to a new defect
class.

**Repair (RQ3)** — two cheap, well-defined metrics: **Logic Rate** (patch matches a manually
written ground-truth fix) and **Syntax Rate** (a Java parser accepts it).

| Bug type | Model | Logic Rate | Syntax Rate |
| --- | --- | --- | --- |
| Null Dereference | GPT-4 | **97.30%** | 99.55% |
| Null Dereference | GPT-3.5-Turbo | 94.25% | 100.0% |
| Null Dereference | VulRepair (baseline) | 18.39% | — |
| Resource Leak | GPT-4 | **91.77%** | 97.77% |
| Resource Leak | VulRepair (baseline) | 12.90% | — |

No training or fine-tuning, against a fine-tuned CodeT5 baseline that needed both.

## Claims to trust and claims to check

- **Trust the repair result as an existence proof** that a prompted LLM patches simple defects
  reliably, and **trust Logic Rate / Syntax Rate** as inexpensive repair metrics
  ([[LLM-Assisted Repair]]).
- **Trust the balanced few-shot construction**; it is a real methodological point.
- **Check the transfer.** Null Dereference and Resource Leak are *local, single-flow* defects
  visible in one method. Interrupt-driven concurrency defects are non-local, involve two or
  three flows, and depend on priority and masking state that no method-scope snippet contains.
  Nothing here shows the repair numbers survive that move, and the Resource Leak numbers —
  already the harder of the two — are consistently worse.
- **Check the detection framing.** The dataset is Infer's warnings, so it contains only true and
  false positives of Infer. Recall is therefore measured against Infer's output, not against
  the bugs in the code; the companion study says as much, noting precision is the only metric
  available for Infer itself.

## Limitations and threats to validity

Method-scope inputs are a hard constraint imposed by 2023-era context windows and are the
stated cause of several missed bugs; the paper's own §VII-A example is a missed bug whose
evidence spans a lambda and a helper call. Repair correctness is judged against
hand-written patches by the authors, not by tests — there is no execution-based validation
anywhere in this paper.

## Relation to other sources

- Companion to [[ChatGPT for Static Analysis (paper)]]; do not treat as independent.
- Its three components are the three integration points tabulated in
  [[LLM Integration Patterns]], all implemented with the *simplest* possible prompt design —
  which makes the contrast with [[LLift (paper)]]'s engineered pipeline instructive.
- The only source in this branch that repairs, as [[SDRacer (paper)]] is the only one in the
  concurrency branch. Together they cover both halves of the loop.
