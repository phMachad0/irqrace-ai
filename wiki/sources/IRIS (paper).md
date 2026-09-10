---
type: source
tags: [wiki, source, llm]
sources: ["[[IRIS (paper)]]"]
updated: 2026-08-23
status: solid
---

# IRIS: LLM-Assisted Static Analysis for Detecting Security Vulnerabilities

**arXiv 2405.17238 (v3) · clipping: [[IRIS]] · PDF: `raw/IRIS.pdf` · [source](https://arxiv.org/abs/2405.17238)**

> [!note] Provenance
> The clipping is the arXiv HTML and carries **no venue and no author list**; the extraction
> dropped the author block. Confirm publication status before citing it as peer reviewed.
> **The tool is open source** — `github.com/iris-sast/iris` — which makes it one of the few
> obtainable artifacts anywhere in this wiki.

Self-described as a **neuro-symbolic** approach. The source that puts the LLM at a *different*
integration point from everyone else: not
filtering the analyzer's output, but **supplying the specifications the analyzer needs to run**
([[Specification Inference]]). For [[Thesis Goal]] that is the more interesting idea, because
the equivalent missing specification here is the interrupt model itself.

## Problem

Static taint analysis needs source and sink specifications. Real projects call third-party APIs
whose roles are unknown, so CodeQL's hand-written specification set misses most real
vulnerabilities. Two challenges are named: **identifying taint specifications** for a project,
and **eliminating false-positive paths**.

## Approach

Four stages:

1. **Candidate extraction** — CodeQL enumerates external APIs invoked by the project and public
   internal APIs, with metadata: method name, type signature, enclosing package and class, and
   JavaDoc.
2. **LLM specification inference** — the LLM labels each candidate as source, sink,
   taint-propagator or sanitizer. Specifications are a 3-tuple `⟨T, F, R⟩` (node type, API
   descriptor, role). APIs are **batched** into one prompt (batch size is a tunable
   hyper-parameter), answered as JSON; 3-shot prompting for external APIs, zero-shot for
   internal ones. Including the repository README and JavaDoc measurably improves accuracy —
   "helps the LLM understand the high-level purpose and usage of the codebase".
3. **Detection** — a specialized CodeQL query runs with the inferred specifications instead of
   CodeQL's built-in ones, producing unsanitized source-to-sink paths.
4. **Contextual triage** — an LLM classifies each path as true or false positive.

**Two prompt details worth stealing.** The triage prompt gives CWE information, full code for
the source and sink nodes, and only file name plus line for intermediate steps, truncating long
paths to a subset of nodes. The JSON schema **puts the explanation before the verdict**, because
"presenting the judgment after the reasoning process is known to yield better results". And when
the verdict is *false*, the LLM is asked **which element** — source or sink — is spurious, so
every other path through that element can be pruned without further LLM calls.

## Evaluation

**CWE-Bench-Java**, a dataset the paper had to build: 120 real Java vulnerabilities with CVE
metadata, fix commit, vulnerable version, a build script, and **the validated program locations
involved in the fix**. A vulnerability counts as detected if any reported path passes through a
patched location. Models: GPT-4, GPT-3.5, Llama-3 8B/70B, Qwen-2.5-Coder 32B, Gemma-2 27B,
DeepSeekCoder 7B. Baselines: CodeQL 2.15.3, Infer, SpotBugs, Snyk.

| Method | #Detected /120 | Detection rate | Avg FDR | Avg F1 |
| --- | --- | --- | --- | --- |
| CodeQL | 27 | 22.50% | 90.03% | 0.076 |
| IRIS + GPT-4 | **55** | **45.83%** | **84.82%** | **0.177** |
| IRIS + Llama-3 70B | 54 | 45.00% | 90.96% | 0.113 |
| IRIS + DeepSeekCoder 7B | 52 | 43.33% | 95.40% | 0.062 |
| Infer / SpotBugs / Snyk | 0 / 4 / 23 | — | — | — |

It also found **4 previously unknown vulnerabilities** in current versions of 30 Java projects,
verified as undetectable by CodeQL alone.

**Ablations**: replacing either LLM-inferred sources *or* sinks with CodeQL's own drastically
reduces recall — both halves are necessary. Contextual triage helps precision **only for
capable models**; GPT-4, GPT-3.5 and Llama-3 70B improve, smaller models get worse, because
"smaller models are more likely to respond with *vulnerable*".

## Claims to trust and claims to check

- **Trust the framing**: doubling CodeQL's detection rate by inferring specifications is a large
  effect at a stage nobody else in this wiki touches.
- **Trust CWE-Bench-Java's construction method.** Mining fixed CVEs for the patched locations
  is exactly the tier-3 methodology [[Candidate Evaluation Subjects]] proposes, executed
  carefully — the criteria (metadata, compilable, real-world, validated locations) transfer
  directly.
- **Check the precision story.** Average FDR remains **84.82%** — roughly six false alerts for
  every true one. The paper is honest that this is an upper bound (a manual sample of 50 alarms
  suggested ~46%), but IRIS is emphatically not a precise tool. It buys recall.
- **Check the small-model triage result** before assuming an LLM filter helps: below some
  capability threshold it actively hurts.

## Limitations and threats to validity

Java only, four CWE classes, and CWE-78 (OS command injection) remains hard for every
configuration because the patterns involve gadget chains and external side effects. The paper
concedes the limits of static analysis for those and defers dynamic approaches. Its related-work
section also records that multiple studies find LLMs ineffective at detecting vulnerabilities in
real code *on their own*, reinforcing that whole-program reasoning must come from the analyzer.

## Relation to other sources

- The specification-inference idea is the one to adapt here: the analogue of an unknown taint
  source is an **unrecognized ISR registration or masking primitive**, which is IntRace's
  user-written configuration file and a documented recall hole
  ([[Soundness and False Negatives]] §2, [[Specification Inference]]).
- [[AdaTaint (paper)]] pursues the same idea with a weaker evaluation; [[SAST-Genius (paper)]]
  cites IRIS as its main comparison.
- Contrast with [[LLift (paper)]], which leaves the analyzer alone and works only on its
  undecided output.
