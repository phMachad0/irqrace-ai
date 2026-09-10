---
type: source
tags: [wiki, source, documentation]
sources: ["[[Racebench (documentation)]]"]
updated: 2026-08-18
status: solid
---

# racebench repository documentation (DeepWiki export)

**DeepWiki-generated documentation for `github.com/chenruibuaa/racebench` (commit `ec1d8280`) · 25 pages · raw: `raw/racebench-deepwiki/`**

> [!warning] Provenance — read before citing
> This is **AI-generated documentation about a repository**, not a paper and not the
> benchmark authors' prose. Its reliable content is what it quotes with line references from
> `README.md`, `2.1/README.md`, `NASAC2019ProtoCompFinal.md` and the annotated test cases —
> those are trustworthy and are the basis of everything recorded in [[Racebench]].
> Its unreliable content is what it *infers*: the page on the seven defect patterns states
> plainly that "the exact enumeration is not fully detailed in the repository documentation"
> and then supplies a conceptual organization of its own, and the JSON output page derives the
> schema "based on the scoring methodology" rather than from a spec. Treat diagrams labelled
> as conceptual, and any pattern list attributed to this source, as **secondary inference**.
> When a claim matters, verify it against the repository itself.

## Why this source matters

Until now the wiki knew [[Racebench]] only through the four papers that evaluate on it, each
of which asserted a different defect count. This documentation exposes the benchmark's own
ground truth, and it settles more of the dispute in [[Contradictions]] than any of the papers
did.

## What it establishes

- **Origin**: the suite was built for the **NASAC 2019 Prototype Competition** on concurrent
  race detection, Hangzhou, 20–22 November 2019 — see
  [[NASAC 2019 Prototype Competition]]. It is a *competition* benchmark, which explains its
  design: deliberate traps, asymmetric scoring, confidential final cases.
- **Composition**: version 2.1 holds **31 simple + 2 complex cases**, with **53 bug points**
  (50 simple + 3 complex) and **38 false positive traps** (33 simple + 5 complex).
- **Ground truth is annotated as access *triples***, e.g.
  `//1.svp_simple_019_001_global_var1<R#45>,<W#65>,<R#54>` — three accesses, the middle one
  from an ISR. Recorded in [[Racebench]]; consequences in [[Atomicity Violation]] and
  [[Access Interleaving Patterns]].
- **False positives are planted deliberately** and marked `//误报点` ("false positive point").
  Precision measured on this suite is therefore trap-avoidance, not a general precision
  estimate ([[Precision Metrics]]).
- **Conventions**: `*_main` and `*isr_[N]`, shared state as `volatile int`, **higher ISR
  number = higher priority**, `enable_isr(n)` / `disable_isr(n)` acting as unlock/lock with
  `n = -1` meaning all interrupts, non-periodic interrupt timing.

## Claims to trust and claims to check

- Trust: counts, version history, naming conventions, the annotation grammar, competition
  rules and scoring — all quoted with line-level citations into the repository.
- Check: the "seven defect patterns" enumeration, which this source admits it reconstructed;
  the JSON output schema, which it infers from the scoring rules. Both are marked as such in
  [[Racebench]] and [[Open Questions]].

## Relation to other sources

Underlies the evaluations in [[IntRace (paper)]], [[NIChecker (paper)]] and
[[BMC4AV (paper)]]. It does not resolve the [[Real-World Program Benchmark]] dispute, which
concerns a different suite. It does supply the benchmark-side numbers that make the
Racebench-side counts comparable for the first time.
