---
type: concept
tags: [wiki, concept]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-23
status: draft
---

# Soundness and False Negatives

Where recall is lost in interrupt-race analysis, and what a detector aiming at zero false
negatives ([[Thesis Goal]]) has to do about each. [[Precision Metrics]] covers how the field
*measures* this; this page covers where the misses actually come from.

## The one design rule

Every stage after pattern matching is a filter, and **a filter may drop a candidate only when
the candidate is provably impossible**. "Cannot prove it is real" must keep the candidate;
only "can prove it cannot happen" may discard it. Every tool in this wiki violates this
somewhere, and every violation is a false-negative source.

This is the inverse of the field's instinct. The [[NASAC 2019 Prototype Competition]] scored a
false positive at −3 against +2 for a detection, and that scoring function propagated into a
literature that reports 100% precision alongside unmeasured recall ([[Synthesis]] §4b). A
recall-first tool is deliberately swimming against that current, and should say so.

## Catalogue of false-negative sources

### 1. Under-approximate aliasing and indirect control flow
Shared-resource identification is the root of the whole pipeline: a memory location missed
here is invisible to every later stage. [[IntRace (tool)]] populates its pool with globals and
pointer-typed parameters via inter-procedural alias analysis ([[IntRace (paper)]] §3.1);
[[SDRacer (tool)]] uses alias sets. **May-alias over-approximation is mandatory**; any
must-alias or field-insensitive shortcut trades recall for speed. Embedded C compounds this
with function-pointer ISR vector tables, where an imprecise call graph silently removes whole
handlers from consideration.

### 2. Filters that assume synchronization they cannot see
[[Interrupt Masking and Synchronization]] in real embedded code is frequently ad-hoc —
writes to hardware registers, project-specific enable/disable wrappers. [[IntRace (paper)]]
concedes this and asks the **user for a configuration file** naming the implicit operations.
That file is a recall hazard in both directions: an unlisted mechanism costs precision, but a
*wrongly* listed one makes the tool believe an interrupt is masked and drop a real race. The
safe default is to treat unrecognized register manipulation as *not* masking.

### 3. Bounds
[[Bounded Model Checking]] answers "no counterexample within unwind bound `u` and round bound
`r`", never "no defect" ([[Contradictions]] #4). [[NIChecker (paper)]] shows how sharp this is:
some Racebench cases need the loop unfolded **10,000 times** before the bug appears, and
[[CPA4AV]] times out or runs out of memory on exactly those three cases. [[Loop Abstraction]]
is the mitigation — over-approximate the loop *before* unwinding so deep bugs surface at a
small bound — and it is the single most recall-relevant technique in the corpus.
[[IntRace (tool)]] has no equivalent and asks the user for a loop depth instead.

### 4. Requiring the user to name the target
[[NIChecker (tool)]] must be told **which global variable and which pattern** to check, one
run per combination ([[NIChecker (paper)]] §5). This is the mechanism [[BMC4AV (paper)]]
blames for the disputed 57 missed violations: a tool that only inspects what it was pointed at
cannot find what nobody nominated. Whatever else is true of that dispute
([[Contradictions]] #1), the structural point stands — **any manual targeting step is a recall
ceiling**, and it is invisible to a precision metric.

### 5. Narrowing the pattern set
The pattern set *is* the bug specification ([[Access Interleaving Patterns]]), so excluding a
pattern is a definitional false negative. [[BMC4AV (paper)]] classifies `(R,W,W)` as benign
and drops six Racebench cases on that basis, asserted rather than argued
([[Contradictions]] #2). A zero-FN detector must carry the **union** of all patterns any
source uses — the three-access triples `(R,W,R)`, `(W,W,R)`, `(W,R,W)`, `(R,W,W)`, and the
two-access race pairs — and mark benignity as a downstream judgement, never as an input
filter.

### 5b. Collapsing triples into pairs
Projecting atomicity violations onto their constituent access pairs is sound at the *matching*
stage but not after a masking filter: two accesses each protected by their own critical
section admit no race, while an ISR can still land in the gap between them. Detecting only
pairs therefore loses exactly those violations. Derive pairs and triples separately from one
access set, and give each its own feasibility query — instant for pairs, interval for triples
([[Pair-Triple Unification]]).

### 6. Uncovered concurrency shapes
- **Equal-priority ISRs.** `svp_real_002` in [[Racebench]] gives two ISRs the same priority,
  and so does `wdt_pci_1` in the [[Real-World Program Benchmark]] (`writer1_isr:4`,
  `writer2_isr:4`). No formal model in any of the four papers covers the case. Assume
  same-level flows *can* interleave unless the platform says otherwise.
- **[[Interrupt Nesting]].** [[SDRacer (tool)]] explicitly *excludes* reentrant interrupts —
  a documented, deliberate recall gap.
- **Priority direction.** The two data-race papers state a numbering convention opposite to
  the benchmark they run on ([[Contradictions]] #3). An inverted comparison in a
  priority-ordering filter drops exactly the real preemptions.

### 7. Execution-grounded validation
[[SDRacer (tool)]]'s final filter is replay on Simics: a race requiring a hardware state the
simulator does not model is unreachable and therefore unreported. [[IntRace (paper)]] makes
this criticism directly. Any dynamic confirmation stage converts modelling gaps into silent
false negatives, which is a reason to keep such a stage *advisory* rather than authoritative.

### 7b. Measuring recall against an unparseable ground truth
[[Racebench]]'s annotations use four incompatible grammars and contain several typos. A strict
parser reads **28** bug points where a tolerant one reads **48** — a 42% undercount that
produces no error and inflates apparent recall, because the denominator shrinks. Any automated
evaluation harness is itself a false-negative source until its parser is validated against a
manual count.

### 7c. The LLM stage, if it is allowed to discard
An LLM judgement is not a proof, so a triage stage that deletes candidates is an unsound filter
by construction. The cost is measured: recall 46.90% → 40.66% in
[[Reducing False Alarms (paper)]], 75.4% in [[AdaTaint (paper)]]. The alternative is a
conservative decision policy — report anything not *proven* safe — which reached recall 1.00 in
[[LLift (paper)]]'s ablation at the same integration point ([[LLM Triage]]).

Three subtler variants, all of which produce misses that look like model errors:

- **Context gaps become confident verdicts.** A model shown incomplete evidence will declare a
  candidate infeasible and give a plausible reason. LLift traced 5 of its 13 false positives to
  gaps in the report handed over by the analyzer; the same gap in the other direction is a false
  negative nobody can see. Defences: let the model request what it lacks, and mark partial
  evidence as partial ([[LLM Stage Design]]).
- **Inferred specifications that narrow.** This project writes the interrupt model by hand
  precisely to avoid it: a wrongly *inferred* masking primitive makes the analyzer believe an
  interrupt is disabled — §2 again, with an automated source. If any inference is ever added it
  must only widen on doubt ([[Specification Inference]]).
- **Prompt injection through analysed code.** The analysis reads untrusted source including
  comments and places it in a prompt; a comment can attempt to instruct the triage model to
  dismiss a defect ([[SAST-Genius (paper)]]). Analysed code is data, never instructions.

### 8. The evidence behind the claim
[[SDRacer (paper)]] and [[IntRace (paper)]] rest "no false negatives" on **manual
inspection** of suites the authors selected. [[BMC4AV (paper)]]'s re-count — 94 violations
where 37 were reported — is the corpus's own demonstration that this method can be wrong by a
factor of two, whatever one concludes about who is right. Recall claims should state their
evidence type.

## Practical consequence for this project

Soundness is a property of a *stated abstraction*, not an absolute. The deliverable is a
written list of assumptions — pointer model, call-graph construction for indirect calls,
recognized masking primitives, treatment of loops, ISR arrival model, priority semantics —
under which no defect is missed, with each filter's drop condition proved or argued against
that list. Everything not on the list is a known unsoundness, declared rather than discovered
by a later paper.
