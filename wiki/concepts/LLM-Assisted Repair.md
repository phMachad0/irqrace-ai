---
type: concept
tags: [wiki, concept, llm]
sources: ["[[SkipAnalyzer (paper)]]", "[[SAST-Genius (paper)]]", "[[SDRacer (paper)]]"]
updated: 2026-08-23
status: draft
---

# LLM-Assisted Repair

Generating and validating a fix from a confirmed defect report. The last two stages of
[[Thesis Goal]]'s loop, and the point where the LLM branch of this wiki meets the concurrency
branch — [[SDRacer (paper)]] is the only concurrency source that repairs, and
[[SkipAnalyzer (paper)]] is the only LLM source that does.

## What is established

[[SkipAnalyzer (paper)]] feeds a true-positive code snippet plus its warning to GPT-4, zero-shot,
and gets back a patch. Against hand-written ground-truth fixes:

| Bug type | Logic Rate | Syntax Rate |
| --- | --- | --- |
| Null Dereference (GPT-4) | 97.30% | 99.55% |
| Resource Leak (GPT-4) | 91.77% | 97.77% |
| VulRepair (fine-tuned CodeT5 baseline) | 12.90–18.39% | — |

No training and no fine-tuning, against a baseline that required both. As an existence proof
that prompted repair works, this is strong.

## Two cheap metrics worth adopting

- **Syntax Rate** — a parser accepts the patch. Mechanical, and it catches the most common
  failure without human effort.
- **Logic Rate** — the patch matches a manually written ground-truth fix.

Neither requires a test suite, which matters because this domain rarely has one.
[[SkipAnalyzer (paper)]]'s own limitation is instructive: it has **no execution-based
validation at all**, so "logically correct" means "an author agreed with it".

## Why the numbers will not transfer unchanged

Null Dereference and Resource Leak are **local, single-flow** defects whose evidence fits in one
method. An interrupt-driven concurrency defect is none of those things:

- The evidence spans **two or three flows** and depends on priority and masking state that no
  method-scope snippet contains.
- The repair vocabulary is interrupt-specific — [[SDRacer (paper)]] §4 enumerates it:
  `irq_disable(n)`/`irq_enable(n)` around the access, lock insertion, **extending an existing
  critical section**, and **merging adjacent critical sections** to avoid redundant operations.
- The **repair scope depends on the defect class**. A race is fixed by protecting an access; an
  atomicity violation is fixed by making the whole interval `[A₁, A₂]` atomic. A model given
  only a racing pair will propose the wrong edit ([[Pair-Triple Unification]]).
- Even a *correct* fix can be wrong. SDRacer measured repair overhead below 0.09 on 9 of 11
  subjects but markedly worse on two, because disabling interrupts changed the main task's
  control flow. In interrupt code an extended critical section is a latency change, and latency
  is a correctness property. Nothing in the LLM branch checks anything like this.

## Validation: ask for an artifact, not a verdict

[[SAST-Genius (paper)]]'s most reusable idea is that its LLM does not merely classify an alert —
it generates a **proof-of-concept exploit**. A verdict backed by an artifact can be checked
mechanically; a verdict alone cannot.

The analogue here is to require a **concrete interleaving witness**: the specific preemption
point, the ISR that fires, the order of the three accesses, and the resulting value or state
that differs from every serial execution. That is checkable — against the masking analysis,
and by encoding it as an assertion for [[CBMC]] or the local `bmc4av`
([[Pipeline Design]]) — and it converts the model's confidence into evidence.

The full validation chain for an applied fix is set out in [[Pipeline Design]]: re-run the
tool's own analysis for a certificate and for regressions, resolve inconclusive cases with a
bounded model checker, then check overhead and control flow in SDRacer's style.

Related: [[LLM Triage]], [[Prompt Architecture]], [[LLM Stage Design]].
