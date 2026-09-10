---
type: moc
tags: [wiki, moc]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-18
status: solid
---

# Overview — concurrency defects in interrupt-driven embedded programs

Entry point for the wiki. The subject: how tools find (and occasionally fix) [[Data Race]]s
and [[Atomicity Violation]]s in embedded C where concurrency comes from interrupts rather
than threads. Four primary sources ingested; see [[Synthesis]] for what they collectively
say and [[Open Questions]] for what is missing.

> [!important] What this vault is for
> The literature here is background for a TCC that **builds a tool**: a sound
> (no-false-negative) static detector for both defect classes, whose candidates are triaged,
> repaired and re-verified by an LLM in a closed loop. Read [[Thesis Goal]] before advising on
> anything, [[Reimplementation Assessment]] for the build plan and stack, and
> [[Pipeline Design]] for how each borrowed technique applies.
>
> **The artifacts are local**, one directory above the vault: `../racebench`, `../NIChecker`,
> `../BMC4AV` (full source). Check a claim against them before repeating it from a paper.

## The shape of the field

Interrupt concurrency is not thread concurrency: preemption is asymmetric, interrupts cannot
block, synchronization is masking rather than locking, and firing depends on hardware state.
Read [[Asymmetric Preemption]] first — every source starts there, and every method choice
downstream follows from it.

**Two branches, and they have never met.** The concurrency branch below is one; the second is
seven sources on **LLM-assisted static analysis**, all of which work on *sequential* defects.
Nothing in either branch addresses LLM-assisted analysis of interrupt concurrency, which is
where [[Thesis Goal]] sits. Map of the second branch: [[LLM Integration Patterns]].

Two defect classes, two literatures that rarely meet:

- **[[Data Race]]** (two accesses) — [[SDRacer (tool)]], [[IntRace (tool)]], [[Rchecker]]
- **[[Atomicity Violation]]** (three accesses) — [[NIChecker (tool)]], [[BMC4AV (tool)]],
  [[intAtom]], [[CPA4AV]]

Three method families:

1. **Execution-grounded** — force interrupts on a virtual platform: [[SDRacer (tool)]].
2. **Static + solver** — pattern match, then discharge path constraints:
   [[IntRace (tool)]], via [[Path Feasibility Analysis]].
3. **Bounded verification** — [[Bounded Model Checking]] over a transformed program:
   [[NIChecker (tool)]] via [[Lazy Sequentialization]], [[BMC4AV (tool)]] via a
   [[Memory Access Graph]].

Everything in family 2 and 3 is a variation on one move: **turn the concurrent program into
a sequential one and ask a reachability question**. What differs is how much interrupt
semantics survives the transformation.

## Sources

| Paper | Year | Tool | Defect | Method |
| --- | --- | --- | --- | --- |
| [[SDRacer (paper)]] | 2020 | [[SDRacer (tool)]] | data race | static + symbolic + dynamic, **with repair** |
| [[IntRace (paper)]] | 2024 | [[IntRace (tool)]] | data race | staged static + Z3 |
| [[NIChecker (paper)]] | 2024/25 | [[NIChecker (tool)]] | atomicity | lazy sequentialization + CBMC |
| [[BMC4AV (paper)]] | 2026 (preprint) | [[BMC4AV (tool)]] | atomicity | BMC + guided memory access graph |
| [[Racebench (documentation)]] | 2019 repo, 2026 export | — | benchmark | the suite's own ground truth, conventions and competition origin |

### LLM-assisted static analysis

| Paper | Year | Attach point | Why it matters here |
| --- | --- | --- | --- |
| [[LLift (paper)]] | 2024, OOPSLA | triage of undecided cases | **the architectural template**; ablation moves recall 0.15 → 1.00 |
| [[IRIS (paper)]] | 2024–25 | specification inference + triage | LLM supplies what the analyzer needs; 27 → 55 detections |
| [[SkipAnalyzer (paper)]] | 2023 | detect + triage + repair | the only LLM source that repairs; Logic Rate 97.3% |
| [[ChatGPT for Static Analysis (paper)]] | 2024, AIware | detect + triage | prompt-template mechanics; 93.9% vs 63.3% by bug type |
| [[AdaTaint (paper)]] | 2025 | spec inference + learned filter | ideas yes, numbers no; recall 75.4% |
| [[Reducing False Alarms (paper)]] | 2025 | learned filter | the cautionary tale; measures the recall cost of filtering |
| [[SAST-Genius (paper)]] | 2025 preprint | triage + repair + exploit | orchestration-layer pattern; prompt-injection risk |

## Concepts

**Domain**: [[Asymmetric Preemption]] · [[Interrupt Nesting]] ·
[[Interrupt Masking and Synchronization]] · [[Data Race]] · [[Atomicity Violation]] ·
[[Access Interleaving Patterns]]

**Method**: [[Symbolic Execution]] · [[Path Feasibility Analysis]] ·
[[Bounded Model Checking]] · [[Lazy Sequentialization]] · [[Loop Abstraction]] ·
[[Memory Access Graph]] · [[Program Slicing]]

**LLM integration**: [[Prompt Architecture]] · [[LLM Triage]] · [[Specification Inference]] ·
[[LLM-Assisted Repair]]

**Evaluation**: [[Precision Metrics]] · [[Soundness and False Negatives]] · [[Racebench]] ·
[[Real-World Program Benchmark]] · [[Candidate Evaluation Subjects]] ·
[[NASAC 2019 Prototype Competition]]

## Cross-cutting

- [[Tool Capability Matrix]] — who does what, side by side
- [[Reported Results Across Papers]] — every headline number with its caveats
- [[Contradictions]] — the six open conflicts, including the 37-vs-94 dispute
- [[Reimplementation Assessment]] — what to study first, what to build, on what stack, and
  what is actually obtainable
- [[LLM Integration Patterns]] — the seven LLM sources by attach point, with what each costs

## This project

- [[Thesis Goal]] — the closed-loop detector this vault exists to support
- [[Pipeline Design]] — the static half: the techniques, and what each becomes here
- [[LLM Stage Design]] — the LLM half: architecture, context record, prompts, evaluation
- [[Dashboard Design]] — the UI: architecture and requirements, end to end
- [[Roadmap]] — 10-week implementation plan, three parallel tracks, milestones
- [[Pair-Triple Unification]] — can races and atomicity violations be one analysis?
- [[Soundness and False Negatives]] — where recall is lost, and the rule every filter must obey
- [[Candidate Evaluation Subjects]] — where to find real code with known, fixed defects

## Baselines without primary sources

[[intAtom]] · [[CPA4AV]] · [[Rchecker]] · [[iCBMC]] · [[CBMC]] · [[Lazy-CSeq]] ·
[[Supporting Infrastructure]]

## Maintenance

[[index]] catalogs every page with a one-line summary; [[log]] records what was ingested,
asked and linted, and when. Conventions and workflows live in `CLAUDE.md` at the vault root —
ingest, query and lint procedures, page templates, and the domain rules about ground-truth
counting that keep [[Precision Metrics]] honest.
