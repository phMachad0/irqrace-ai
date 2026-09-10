---
type: tool
tags: [wiki, tool, baseline]
sources: ["[[NIChecker (paper)]]"]
updated: 2026-08-17
status: draft
---

# Lazy-CSeq

Lazy sequentialization tool for multi-threaded C (Inverso et al.), built on the CSeq
framework; gold medallist in the SV-COMP "Concurrency Safety" category. The direct ancestor
of [[NIChecker (tool)]], which is built on v2.1 and reuses its *inline* and *unwind* modules.

Its efficiency comes from combining laziness with context-bounded analysis: explore reachable
states only, rather than the whole state space.

**Why it cannot be used directly on interrupt code** ([[NIChecker (paper)]], §1) — the three
differences that define this research area:

1. preemption is asymmetric for interrupts, symmetric for threads;
2. interrupts can be masked, threads cannot;
3. interrupts cannot block, threads can.

NIChecker's contribution is essentially the *instrument* module rewritten so that invocation
conditions encode priority and masking. See [[Lazy Sequentialization]] and
[[Asymmetric Preemption]].
