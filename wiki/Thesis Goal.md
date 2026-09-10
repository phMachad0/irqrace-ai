---
type: project
tags: [wiki, project]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[LLift (paper)]]", "[[IRIS (paper)]]", "[[SkipAnalyzer (paper)]]"]
updated: 2026-08-27
status: draft
---

# Thesis Goal — a race detector with an LLM in the loop

**This page states what the TCC is trying to build.** It is not derived from the sources; it
is the human's stated research direction, recorded on 2026-08-18 so that every session
working in this vault shares the same objective. Claims *about the literature* on this page
carry citations as usual; the goal itself is a directive, not a finding.

Implementation is planned in [[Roadmap]]. Read this together with [[Synthesis]] (what the field
currently does),
[[Reimplementation Assessment]] (what to build, in what order, on what stack),
[[Pipeline Design]] (the static half) and [[LLM Stage Design]] (the LLM half).

## The objective

Build a **static analysis tool that detects data races *and* atomicity violations in
interrupt-driven embedded C with no false negatives** — every actual defect appears somewhere
in the reported set, at the cost of accepting false positives — and then **close the loop with
an LLM**:

0. **Input.** A single file *or* a multi-file project — the analyzer accepts linked
   whole-program bitcode, so tasks and ISRs may be spread across a repository and defects in
   nested callees in other files are still found. The hand-written configuration file names the
   entry points, priorities and masking primitives, and it is what bounds the work: cost follows
   code reachable from those entry points, not repository size
   ([[Pipeline Design]], *Input scope and build requirements*).
1. **Static phase (sound).** Over-approximate: find every candidate defect. Precision is
   explicitly *not* the goal here. See [[Soundness and False Negatives]].
2. **Context capture.** For each candidate, serialize the evidence an LLM would need to judge
   it: the shared variable, the access triple/pair with source locations, the call stacks
   reaching each access, the enclosing ISR/task and its priority, the masking state along the
   path, the enclosing function bodies, and the solver's verdict. Anything further the model
   needs it **requests on demand** rather than receiving a precomputed slice
   ([[Program Slicing]]). This is a *first-class output of the static phase*, not an
   afterthought — the tool is meant to run on large codebases with many threads and interrupts,
   where a bare warning list is unusable.
3. **Solver, then LLM triage.** [[Path Feasibility Analysis]] runs first and discards only what
   it can *prove* impossible, removing 86.2% of what reaches it ([[IntRace (paper)]] §RQ3). The
   LLM then works on the residue — the candidates a constraint solver could not settle — and
   **ranks and explains; it does not discard** (see the decision policy below). This mirrors
   [[LLift (paper)]], where symbolic execution runs first and the LLM receives only the 40% of
   cases it abandoned.
4. **LLM repair.** Propose a fix — the repair vocabulary is interrupt-specific
   (`irq_disable`/`irq_enable`, critical-section extension, section merging), already
   enumerated by [[SDRacer (paper)]] §4, the only source in this wiki that repairs.
5. **Verification of the fix.** Re-run the analysis, and ideally a bounded model check, to
   confirm the defect is gone and nothing new appeared.

The result is a closed loop: **detect → contextualize → triage → repair → re-verify.**

**The loop is driven from a dashboard, not a command line.** Configuring a subject, editing the
interrupt model, launching a run, watching the stages, reading candidates against their source,
and accepting or rejecting a patch are all meant to be done through a UI by a developer who has
not read this wiki ([[Dashboard Design]]). That is a usability requirement, and it is also the
axis this literature actually competes on ([[Synthesis]] §5).

**The interrupt model stays a hand-written configuration file.** Having an LLM infer it — which
functions are ISRs, which mask interrupts, what the priorities are — was considered and
rejected: the masking primitives form a closed set per platform, both benchmarks already ship
the configuration, and the recall-critical half (entry points) is a `grep` rather than a
judgement. [[Specification Inference]] records the option and the case against it.

## The decision policy

The single rule that keeps the loop honest: **a solver may drop a candidate; the LLM may not.**
An `UNSAT` result is a proof of impossibility; an LLM judgement is not. So the triage stage
buckets and orders candidates and the report retains all of them.

This is not caution for its own sake — it is the difference between the two measured outcomes in
the LLM literature. Triage stages built as classifiers that discard lose recall: 6 points in
[[Reducing False Alarms (paper)]], roughly 25 in [[AdaTaint (paper)]]. [[LLift (paper)]], whose
policy reports anything not *proven* safe, reaches recall 1.00 in its ablation at the same
integration point. Details in [[LLM Triage]].

The reporting consequence is that the headline metric is **recall (which must be 100%) together
with Inspection Ratio** — how much of the candidate set a reviewer must read to find every real
defect — rather than precision ([[Precision Metrics]]).

## Why this is not already done

Three gaps in the corpus line up with this design, each one already recorded in the wiki:

- **Nothing detects both defect classes in one pass** ([[Tool Capability Matrix]]), although
  the pipelines share their first two stages. The [[Racebench]] annotations are three-access
  triples even for the suite the data-race papers evaluate on
  ([[Racebench (documentation)]]), which suggests the split is partly vocabulary
  ([[Contradictions]] #5).
- **Recall is the open frontier, and it is measured badly** ([[Synthesis]] §3). Three of four
  tools report ~zero false positives; "no false negatives" means manual inspection in the
  older papers and bounded absence in the newer ones ([[Precision Metrics]]). A tool built
  *for* recall, with an explicit soundness argument, is aimed at the gap the literature
  actually has.
- **Repair died in 2020** ([[Synthesis]] §6). [[SDRacer (tool)]] detects, validates and
  repairs; nothing since repairs anything.

The LLM stage is also aimed at a specific, documented weakness rather than at "adding AI":
IntRace's two acknowledged false-positive causes are (1) implicit interrupt operations that go
through hardware state and cannot be recognized without a user-written configuration file, and
(2) **benign** races left unsynchronized deliberately ([[IntRace (paper)]], limitations). Both
are judgement problems over source-level intent, which is what an LLM is plausibly good at and
a constraint solver is not.

- **The two literatures have never met.** Seven LLM-plus-static-analysis sources are now in this
  wiki and **all seven address sequential defects** — taint flow, null dereference, resource
  leaks, use-before-initialization ([[LLM Integration Patterns]]). [[LLift (paper)]] names
  concurrency as a case static analysis models badly and then does not tackle it. The
  intersection of the two branches is empty, and that intersection is where this project sits.

## What the LLM literature says the design must get right

Three findings from [[LLM Integration Patterns]] that change how the stage is built:

1. **Prompt architecture dominates outcome.** [[LLift (paper)]]'s ablation moves recall from
   **0.15 to 1.00** on one dataset with one model, purely by structuring the interaction —
   domain-rule teaching, letting the model request missing definitions, decomposing the task,
   and self-validation against recall-biased rules ([[Prompt Architecture]]). Treating the
   prompt as a finishing touch would be the largest available mistake.
2. **Nothing transfers by assumption.** Identical prompts and model give 93.9% versus 63.3%
   false-positive-removal precision on two *sequential* bug types
   ([[ChatGPT for Static Analysis (paper)]]). Interrupt concurrency is further from both than
   they are from each other, so the stage must be measured on [[Racebench]] before anything is
   built on top of it.
3. **The benchmark is already a triage test set.** Racebench's 31 simple cases carry 48
   annotated bug points *and* 38 deliberately planted false-positive traps — 86 adversarial
   labelled candidates. Recall against the bug points and rejection rate against the traps are
   exactly the two numbers this stage needs ([[LLM Stage Design]]).

## Benchmarks and validation targets

- **[[Racebench]]** — 33 aerospace-derived C programs, 53 annotated bug points and 38
  *planted* false-positive traps. Obtainable: `github.com/chenruibuaa/racebench`. Used by all
  four sources.
- **[[Real-World Program Benchmark]]** — the 18 programs from six packages used by
  [[NIChecker (paper)]] and re-counted by [[BMC4AV (paper)]]. Obtainable:
  `github.com/zhvngyuan/NIChecker` (Apache-2.0 — benchmarks and results only; the tool source
  is withheld, see [[Reimplementation Assessment]]).
- **Real large-scale interrupt-driven open source** — still to be selected; see
  [[Open Questions]].

Because both community benchmarks come with contested ground truth, any recall number this
project reports must state which count it divides by ([[Contradictions]] #1, #2).

## What "no false negatives" can honestly mean

Unconditional zero-FN is not attainable for C with pointers, function-pointer interrupt
vector tables, and hardware-dependent control flow. What *is* attainable, and defensible in a
thesis, is **soundness relative to an explicitly stated abstraction**: a documented list of
the assumptions under which no defect is missed, plus evidence that each filter drops a
candidate only when it is provably impossible. [[Soundness and False Negatives]] maintains
that list and catalogs where each of the four tools loses recall.

Stating this openly is itself a contribution here, given [[Contradictions]] #4 — the corpus's
"no false negatives" claims rest on incompatible and largely unexamined evidence.
