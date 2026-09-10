---
type: comparison
tags: [wiki, comparison, llm]
sources: ["[[LLift (paper)]]", "[[IRIS (paper)]]", "[[SkipAnalyzer (paper)]]", "[[ChatGPT for Static Analysis (paper)]]", "[[AdaTaint (paper)]]", "[[Reducing False Alarms (paper)]]", "[[SAST-Genius (paper)]]"]
updated: 2026-08-27
status: draft
---

# LLM Integration Patterns

The seven LLM-plus-static-analysis sources side by side: **where** the model is attached, what
that buys, and what it costs. Nothing here is normalized across papers — the benchmarks,
languages and defect classes are all different, and only the within-paper ablations are
comparable to anything ([[Precision Metrics]]).

## Four places an LLM can attach

| Pattern | What the LLM does | Sources |
| --- | --- | --- |
| **Specification inference** | supplies facts the analyzer needs *before* it runs | [[IRIS (paper)]], [[AdaTaint (paper)]] |
| **Triage** | decides which of the analyzer's candidates are real | all seven |
| **Detection** | finds defects itself, without an analyzer | [[SkipAnalyzer (paper)]], [[ChatGPT for Static Analysis (paper)]] |
| **Repair** | proposes and validates a fix | [[SkipAnalyzer (paper)]], [[SAST-Genius (paper)]] |

The pattern the corpus converges on is **analyzer does the whole-program reasoning, LLM does the
local judgement**. [[IRIS (paper)]] states the reason plainly: multiple studies find LLMs
ineffective at detecting vulnerabilities in real code on their own, because that requires
whole-repository reasoning. Standalone LLM detection is the weakest-performing pattern here and
is not a candidate for this project.

## The sources

| Source | Base analyzer | Model | Attach point | Headline | Recall reported? |
| --- | --- | --- | --- | --- | --- |
| [[LLift (paper)]] | UBITect (undecided cases only) | GPT-4 | triage | 50% precision on real data; **1.00 recall** in ablation | **yes, and it is the point** |
| [[IRIS (paper)]] | CodeQL | GPT-4 + 6 others | spec inference + triage | 27 → **55** of 120 detected | yes — detection rate 45.8% |
| [[SkipAnalyzer (paper)]] | Infer | GPT-4 / 3.5 | detect + triage + repair | repair Logic Rate **97.3%** | partly, vs Infer's output |
| [[ChatGPT for Static Analysis (paper)]] | Infer | GPT-4 / 3.5 | detect + triage | FP-removal precision **93.9%** / 63.3% | no — precision only |
| [[AdaTaint (paper)]] | taint analyzer | unnamed + CodeLlama | spec inference + filter | 84.3% precision | yes — **75.4%**, i.e. drops a quarter |
| [[Reducing False Alarms (paper)]] | CppCheck | fine-tuned CodeBERT | filter | precision 5.9% → **96.2%** | yes — **46.9% → 40.7%** |
| [[SAST-Genius (paper)]] | Semgrep | fine-tuned Llama 3 8B | triage + repair + exploit | precision 35.7% → **89.5%** | **no** |

Two of seven do not report recall at all, and both are the ones claiming the largest precision
gains. That is the same evaluation pathology this wiki documents in the concurrency branch
([[Synthesis]] §3) reappearing in a new literature.

## What each pattern actually buys

**Specification inference buys recall.** IRIS doubles CodeQL's detection rate, and its ablation
shows that reverting either sources or sinks to CodeQL's own specifications collapses the gain.
AdaTaint's ablation agrees in shape (recall 75.4 → 67.5 without adaptation). The obvious analogue here — inferring the **interrupt model** rather than hand-writing
[[IntRace (tool)]]'s configuration file — was **examined and rejected**. IRIS's gain comes from
an open-world problem (hundreds of unbounded third-party APIs), while interrupt masking is a
closed set per platform; both benchmarks already ship the configuration; and the recall-critical
half, identifying entry points, is a `grep`. [[Specification Inference]] carries the full
argument, and the open-world/closed-set test is worth applying before importing any other result
from this table.

**Triage buys precision, and may or may not cost recall.** This is the fork that matters. A
triage stage designed as a *classifier that drops* costs recall measurably: 6 points absolute in
Reducing False Alarms, ~25 in AdaTaint. A triage stage designed with a *conservative decision
policy* — report anything not proven safe — reached 1.00 recall in LLift's ablation. Same
integration point, opposite properties ([[LLM Triage]]).

**Repair works on easy defects.** 97.3% Logic Rate on Null Dereference, with no fine-tuning.
Whether it survives the move to interrupt-specific fixes, where the repair changes timing and
the scope depends on the defect class, is untested ([[LLM-Assisted Repair]]).

## Cross-cutting findings

- **Prompt architecture dominates.** 0.15 → 1.00 recall from structure alone, one model, one
  dataset ([[Prompt Architecture]]). Any conclusion drawn from a single-prompt experiment is a
  statement about the prompt.
- **Performance is defect-class-specific.** 93.9% versus 63.3% FP-removal precision for two bug
  types under identical conditions. Assume nothing transfers.
- **Model capability sets a floor, not the ceiling.** IRIS's triage helps large models and
  *hurts* small ones; LLift's progressive prompting and task decomposition simply did not work
  on GPT-3.5 or Bard. But IRIS's DeepSeekCoder 7B still detected 52 of 120, so the base
  integration works with modest models — it is the sophisticated prompt structures that need
  capable ones.
- **All model comparisons in this corpus are stale.** GPT-4 (2023–24), GPT-3.5, Claude 2, Bard,
  Llama 3. None of these numbers should be used to choose a model today; use them for the
  *shape* of the result, and re-measure.
- **Cost is measurable and non-trivial.** LLift: ~7,000 tokens and $0.43 per candidate at 2024
  GPT-4 pricing, 2.78 turns average. At IntRace's ~208 candidates per program that is roughly
  $90 per program for triage alone before any filtering — which is the argument for keeping a
  cheap solver stage, or a cheap ranking pre-pass, ahead of the LLM.

## What this branch does *not* provide

- **Nothing addresses concurrency.** All seven work on sequential defects: taint flow, null
  dereference, resource leaks, use-before-initialization. [[LLift (paper)]] explicitly lists
  concurrency as a case static analysis models badly, and then does not tackle it. **The
  intersection of this branch with the interrupt-concurrency branch is empty**, which is where
  [[Thesis Goal]] sits.
- **No source validates a repair by execution.** SkipAnalyzer compares against hand-written
  patches; SAST-Genius generates exploits but reports no recall. The closest thing to
  execution-grounded validation in this entire wiki remains [[SDRacer (paper)]]'s virtual
  platform, from 2020.
- **No source reports an inspection-effort metric except one.**
  [[Reducing False Alarms (paper)]]'s Inspection Ratio is the only measure of triage burden in
  the corpus, and it is the natural headline metric for a recall-first tool.

Related: [[LLM Stage Design]], [[Tool Capability Matrix]], [[Reimplementation Assessment]].
