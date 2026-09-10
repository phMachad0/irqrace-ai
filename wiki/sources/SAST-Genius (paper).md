---
type: source
tags: [wiki, source, llm]
sources: ["[[SAST-Genius (paper)]]"]
updated: 2026-08-23
status: draft
---

# LLM-Driven SAST-Genius: A Hybrid Static Analysis Framework for Comprehensive and Actionable Security

**Preprint / technical report, 2025-11 · Vaibhav Agrawal (Google), Kiarash Ahi (Virelya Intelligence Research Labs) · clipping: [[SAST-Genius]] · PDF: `raw/SAST-Genius.pdf`**

> [!warning] Preprint, and the clipping is out of order
> Not peer reviewed. The source PDF's two-column layout extracts with sections in the wrong
> sequence — the contributions list and Section II precede the abstract and Section I in
> `Clippings/SAST-Genius.md`. Section headings inside the paper are also inconsistent
> (Section VI's heading appears inside Section V). Verify anything quoted against the PDF.

## Approach

A two-stage pipeline: Semgrep 1.97.0 as the deterministic core, then a **fine-tuned Llama 3 8B**
performing triage, exploit validation and remediation. Distinctive against the rest of this
branch in three ways:

- **Fine-tuning a small model** rather than prompting a large one. The LLM is trained on
  Semgrep's intermediate representation.
- **The orchestration-layer pattern.** The framework sits *between* the SAST scan and the final
  action. A middleware script intercepts raw SAST output, fetches the cross-file function
  definitions and taint flow the alert refers to, and converts it into a **structured JSON
  prompt**. This is the same architectural shape [[LLM Stage Design]] adopts, described from
  the deployment side.
- **Exploit generation as validation.** Rather than asking the model whether an alert is real,
  ask it to produce a proof-of-concept — a verdict backed by an artifact that can be checked
  independently. The analogue here is asking for a concrete interleaving witness rather than a
  yes/no ([[LLM-Assisted Repair]]).

## Evaluation

25 GitHub projects, ~250K LoC, against a ground-truth set of 170 vulnerabilities.

| | Precision | F1 |
| --- | --- | --- |
| Semgrep alone | 35.7% | 48.3% |
| GPT-4 alone | 65.5% | — |
| SAST-Genius | **89.5%** | — |

False positives fall from 225 to 20 (~91% reduction) and reported triage time by 91%.

## Claims to trust and claims to check

- **Trust the architectural patterns** — orchestration layer, structured JSON prompts built by
  fetching cross-file context, exploit-based validation, fine-tuning a small model. These are
  design ideas that stand independently of the measurements.
- **Check everything quantitative.** Preprint, no artifact, no ablation, and recall is not
  reported at all — only precision and false-positive counts, so there is no way to tell what
  the 225 → 20 reduction cost in missed vulnerabilities. Given
  [[Reducing False Alarms (paper)]], that omission is the important one.

## The security consideration nobody else raises

Its Section V flags **prompt injection and data poisoning** as risks inherent to putting an LLM
in a security pipeline. This deserves attention here and is easy to overlook: the analysis reads
*untrusted source code* — including comments — and places it in a prompt. A comment in an
analysed file can attempt to instruct the triage model to dismiss a defect. Any triage stage
must treat analysed code as data, never as instructions, and a defect dismissed on the strength
of a comment is a false negative introduced deliberately. Recorded in
[[Soundness and False Negatives]].

## Relation to other sources

Cites [[IRIS (paper)]] as its main point of comparison and positions itself as the first
end-to-end hybrid framework. Overlaps [[SkipAnalyzer (paper)]] in scope — detect, triage,
repair — with a fine-tuned rather than prompted model.
