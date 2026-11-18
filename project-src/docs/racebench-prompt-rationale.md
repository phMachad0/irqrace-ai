# Rationale for `racebench_semantics.md`

Provenance key used below:

- **Doc** = the DeepWiki export in `racebench-deepwiki/` (machine-generated *about* the suite).
- **Cited** = the doc states it with a reference into the suite's own files (README, `common.*`, a
  case file with line numbers), and the reference actually supports it.
- **Doc-inferred** = the doc states it, but with no citation, or with a citation that does not
  support it (the export often attaches a README line range to a claim the README never makes).
- **Derived** = not stated by the doc; generalised by me from annotation data the doc quotes with
  line citations, and/or from the suite directly. These are marked so they can be reviewed first.
- **Verified** = checked by me against `racebench/` (README.md, `2.1/README.md`,
  `2.1_remarks/README.md`, `2.1/common.{c,h}`, `NASAC2019ProtoCompFinal.md`, and the
  `2.1_remarks/svp_simple_*` sources and their annotations). File:line refs are to those files.

Translations of the Chinese READMEs are mine.

---

## 1. Rules in the asset, one by one

### 1.1 Precedence preamble
Not a Racebench rule; it implements the task's instruction to state which rule wins. Conflicts are
listed in section 3.

### 1.2 "Only single-variable access-order violations count" (and multi-variable out of scope)
- Doc: `3-Benchmark-Architecture.md` › Architectural Constraints › Analysis Scope ("Focus is on
  single-variable access patterns / Multi-variable atomicity requirements are not tested", cites
  `2.1/README.md` L3); `4.1-Simple-Test-Cases-Overview.md` › Limitations and Scope (same citation).
- **Cited.** Verified: `2.1/README.md` L3 and `2.1_remarks/README.md` L3 say the set applies only to
  testing single-variable access-order patterns. Root `README.md` L14 calls the annotated defects
  "BUGs that violate variable access order".

### 1.3 Triple shape: A1, A2 in one flow, B from another flow, same location
- Doc: `4.2-Annotated-Test-Cases-(2.1_remarks).md` › Bug Point Annotations, › Operation Semantics;
  `4.1.1` › Ground Truth Annotation Format. Every annotation the docs quote is three accesses, middle
  one remote (cited per case, e.g. 019 L73-74, 022 L69-72, 007 L52, 015 L42, 005 L48).
- **Cited** (the annotation data). The doc's gloss "first operation: access in main execution
  context" (4.2 › Operation Semantics) is **doc-inferred and wrong**: in case 014 all three are in
  ISRs (A1/A2 in the priority-1 ISR, B in the priority-3 ISR), which the doc itself shows in 4.1.3.
  The asset therefore says "one flow / another flow", matching `base.md`.

### 1.4 The four shapes and what goes wrong in each
- Doc: shapes appear only through cited annotations: W-W-R (`4.1.1` 007; `4.1.4` 021 race 2),
  R-W-R (`4.1.1` 015; `4.1.2` 024, 023 race 1; `4.1.3` 013, 014, 003; `4.2` 022), W-R-W (`4.1.1` 005),
  R-W-W (`4.1.2` 026, 023 race 2; `4.1.4` 021 race 1). The per-shape effects ("ISR update is lost",
  "two reads see different values", "ISR may read a transient intermediate value") are the doc's
  prose in 4.1.1/4.1.4, consistent with the code they cite.
- **Cited** for the four shapes. **Derived** for "no other shape is a defect": the doc never says
  it. Support: serializability (a remote write between two local writes is equivalent to a serial
  order), and the wiki's measured shape table (`wiki/benchmarks/Racebench.md`: after errata every
  bug point is one of the four; the two W-W-W annotations are traps).
- Not used: `3.1-Seven-Defect-Patterns.md` (its own diagram is a reconstruction; it says the
  enumeration "is not fully detailed in the repository documentation"), and the "Read-Read-Write" /
  "Write-Write" rows of `4-Test-Case-Structure.md` › Access Pattern Types (doc-inferred; no annotation
  has those shapes).

### 1.5 "The interleaving is the defect; effect need not be observable" (dead readers count)
- Doc: never stated as a rule. The cited bug annotations it quotes all have readers whose value is
  never used: `4-Test-Case-Structure.md` quotes 007's A2 as a read into a local ("reader1 = ...[2]",
  cited L52); `4.1.1` 005 has the ISR reading into a local (cited L46); `4.2` 019's reads go into
  locals (cited L73-74).
- **Derived** from cited data. Verified against the suite: the read-side locals are never used in
  005 (ISR local), 007, 013, 014, 016, 019, 001 (ISR locals), 006, 009, 010, 012 — every one of these
  is the read access of an annotated bug point. Matches the project's prior decision
  (`project-src/src/irqrace/llm/scoring.py`, `scoring_bucket` docstring, "option C").
- "Code that looks deliberate" — derived: the suite's bug points are deliberately planted, so intent
  can never be a benignity argument under this ground truth.

### 1.6 Same location = same storage (elements, fields, unions, pointers, `volatile`)
- Doc: `6-Tool-Developer-Guide.md` › Pitfall 3 (array indices are "different variables") —
  **doc-inferred** (cites `2.1/README.md` L9-16, which says nothing about indices);
  `4.1.4` › Array Element Independence ("precise tools should distinguish...") — **doc-inferred**;
  `4.1.4` › Pointer Aliasing (009: p and q alias a local; m retargeted by the ISR) — **cited** (009
  L19-48); `4.1.2` › Pattern 2 (024: array accessed through a parameter, annotated as the global's
  element) — **cited** (024 L54-67).
- **Verified** in the suite:
  - elements: 007 bug uses the branch that writes element 2 and its trap the branch that writes a
    different element; 007's other trap has the index re-read after the ISR changes it; 001 trap 2
    has B read an element A2 never writes;
  - fields: 010 bug is on a union (members overlap) and its trap the same accesses on a struct;
  - pointers: 009 bug is two writes through two aliasing pointers to a *local of the main flow*, with
    the ISR reading through one of them; 009 trap has the ISR retarget the pointer before reading;
    024/025 access the global through a pointer parameter; 012 through a local pointer;
  - `volatile`: 012's bug-point variable is a plain `int`; 013/014 guard flags are non-volatile.
    The doc's repeated claim that all shared variables are `volatile` (`1-Home`, `3`, `4`, `6.1`
    › Volatile Qualification, the last citing only "implied by" README L7) is **doc-inferred and
    contradicted**.
- "Evaluate indices and pointers within the interleaving" — derived from 007 trap 1 and 009 trap.

### 1.7 A1 and A2 must be adjacent (subsumed triples are not counted)

> **Removed 2026-10-28.** The first full 31-case run (wiki: Racebench Full Run 2026-10-28) showed
> the rule contradicted by the suite itself: 017's annotated bug points include non-adjacent
> triples (a loop condition re-reads the variable between A1 and A2), and the rule made the model
> call two of them infeasible. Its net effect on the score was +2, bought with recall. The
> derivation below is kept as the record of why it was tried.
- Doc: `4.2` › Example from svp_simple_022_001 quotes the four bug points and three "可能误报" traps
  with line citations (022 L69-77) — **cited data**. Its explanation ("function call structure and
  execution order guarantee that certain accesses cannot interleave") is **doc-inferred** and does
  not explain the labels.
- **Derived**, moderate confidence. In 022 the bug points are exactly the adjacent pairs of the main
  flow's access chain on the variable, and traps 1 and 3 are the pairs with another access of the
  same flow in between on every path (trap 2 is a dead branch). The "on every path" qualifier is
  supported by 021 bug 3 (`4.1.4` › Race 3, cited): its A1→A2 interval contains a local write only
  when the guard is true, and it is a bug point. Non-adjacent pairs in 016 and 018 are unannotated
  (neither bug nor trap), consistent with the rule. Case 019 neither confirms nor refutes it (its
  annotations are stale against the shipped file, see the wiki). The project's triage study
  independently identified these as "subsumed triples"
  (`wiki/comparisons/Triage Study 2026-10-26.md`, cause 5).
- This rule makes the model answer `infeasible` for an interleaving that can occur physically. See
  conflict 3.3.

### 1.8 Every evaluated occurrence is an access (conditions, RMW, by-value arguments, callees)
- Doc: two reads in one compound condition — `4.1.1` › Example 2 (015, cited L30-31, L42);
  read-modify-write as two accesses usable as A1 and A2 — `4.1.2` › Race 2 (023, cited L34, L41-42);
  by-value argument read at the call and the sequence continuing in the callee — `4.1.2` › Race 1
  (023, cited L24-34). **Cited**, verified (`2.1_remarks` 023 bugs 1 and 2; 025 is the same through
  a pointer; 016 has three reads in one expression with two bug points between consecutive ones;
  017 has the loop's own condition read twice across iterations).
- "B may be in an ISR's callee" — **derived from the suite** (018: the priority-2 ISR writes through
  a helper function and that write is a bug point's B). The doc does not cover 018.
- "Unevaluated operand" (used in the traps list) — **derived from the suite**: 015's trap is a
  conditional expression naming the variable in both branches. Already covered by `domain_rules.md`.

### 1.9 Arrival model: preempts main or strictly lower ISRs, any moment/position/count, not periodic, nesting
- Doc: `3.3-Test-Case-Conventions.md` › Interrupt Timing Model, `3` › Preemption Rules,
  `4.1` › Interrupt Timing Model (adds "Nesting: Nested interrupts possible based on priority
  levels"), `6.1` › Interrupt Timing Model — all cite `2.1/README.md` L10.
- **Cited**, verified: `2.1/README.md` L10 (and `2.1_remarks/README.md` L10) — test cases do not
  consider interrupt periodicity; an interrupt may, when interrupts are allowed, interrupt the main
  program or a lower-level interrupt; the moment, position and number of times are indeterminate.
  Nesting verified on 014 (the priority-3 ISR lands between two reads of the priority-1 ISR).
  "Zero times" is my reading of "indeterminate number".

### 1.10 Equal priority does not preempt
- Doc: `3.3` › Priority Rules table ("Same isr_num: Implementation-defined (typically
  non-preempting)", cites root README L13, which does not say this) — **doc-inferred**; `4.3` ›
  Test Case 2 ("These ISRs cannot preempt each other", cites `2.1/README.md` L62, which is only a
  table row) — **doc-inferred**.
- **Derived** from the literal README text: L10 names only "the main program or a lower-level
  interrupt" as preemptible. **Not verifiable** on public code: the only equal-priority
  configuration is the withheld real case 2 (`2.1/README.md` L62). Low practical impact on the 31
  simple cases (none has equal priorities). See conflict 3.2.

### 1.11 Priority = configured, larger is higher; masking takes the interrupt number
- Doc: `3.3` › Interrupt Priority System and the svp_real_002 note; `6.1` › Priority Number Mapping.
- **Cited**, verified: `2.1/README.md` L15 (larger number, higher priority), root `README.md` L13
  (larger isr_num, higher priority), `2.1/README.md` L14 (the interrupt number is what the on/off
  functions take), L21-62 (entry / number / priority columns; L62 has number 2 at priority 1).
  The priority direction duplicates `domain_rules.md`; it is folded into one clause, not restated.

### 1.12 Initialisation unmasks every interrupt; state before it unstated
- Doc: `1-Home`, `3`, `4` list `init()` only as an "initialization routine"; `4.1.1` › Detection
  Requirements says ISRs can run "at any point during main execution after the init() call"
  (**doc-inferred**, uncited); `6-Tool-Developer-Guide.md` › Pitfall 4 says the opposite, that init
  leaves interrupts disabled and accesses before the first enable are "typically safe"
  (**doc-inferred and contradicted**).
- **Verified from the suite, not from the doc**: `2.1/common.c` (and `2.1_remarks/common.c`) define
  init as a single call enabling all interrupts. Nothing in the suite states the state before it.
  "Use the record's masking state there" defers to the analyzer's configured initial state (the
  project uses all-enabled, `project-src/docs/masking-semantics.md`).

### 1.13 Masking: per number, all-form, global, persistent, ISRs may unmask higher-priority ISRs
- Doc: `3.3` › ISR Control Functions and `6.1` › Interrupt Control Functions (cite `2.1/README.md`
  L14) — **cited**; "only that ISR" — `6` › Selective Blocking (cites L10-11, not about masking →
  doc-inferred, but it follows from per-number masking); global/persistent and cascades — `4.1.3` ›
  Dynamic ISR Control ("ISR N cannot preempt any context until re-enabled"), › Pattern 1/2
  (cascading enables, cited 013 L50/L60, 014 L34/L52), and the 014 remark that tools "must not
  assume that disable_isr() provides permanent protection" — **cited**.
- Verified: `2.1/README.md` L14 (enable/disable may be regarded as unlock/lock on an interrupt
  number; the special value masks/unmasks all). Cascades verified on 013 (ISR1 unmasks 2, ISR2
  unmasks 3), 014 (ISR2 re-unmasks 3 that ISR1 masked), 027 (bug B sits in an ISR unmasked by
  another ISR), 001. "Survives the return of the flow" is **derived** (global lock-like state; the
  project's Soundness Assumption F7); the suite's labels do not distinguish it from nesting.
- Deliberately not stated: whether masking nests/counts (the doc's "nested disable/enable calls must
  be handled correctly", `3` › Interrupt Control Semantics, is doc-inferred and undocumented).

### 1.14 Idle/delay calls are not synchronisation; random and hardware values unconstrained
- Idle: `4.1.3` › Dynamic ISR Control ("idlerun(): create interrupt opportunity") and
  `4-Test-Case-Structure.md` (ISR "Activation Trigger: call to idlerun()") are **doc-inferred and
  wrong**: `2.1/common.c` defines it as an empty bounded loop, and README L10 lets interrupts arrive
  at any position. Verified: the bug points of 015, 016, 023 and 025 need a preemption inside an interval of the
  interrupted flow that contains no idle call (and the ISRs of 023 and 025 contain none at all).
  Stated in the asset because the doc's reading would mislead a model.
- Random/hardware: `1-Home`, `3` › Layer 3 ("rand(): random number generation for conditional
  branches", cites `common.h`) — cited; `2.1/common.h` only declares it external. Verified: 007's bug
  point requires a random value to equal a specific constant; 021/031 read a memory-mapped register in
  the ISR (`4.1.4` › ISR Hardware Update Pattern, cited L78-81).

### 1.15 Planted false positives — what they test
- That they exist and are planted: `2.2`, `5`, `5.1` cite `NASAC2019ProtoCompFinal.md` L41-47 —
  **cited**, verified (L41: 53 planted bug points and 38 planted false-positive points; only these are
  scored). `2.1_remarks/README.md` L5 calls both "pre-planted". "Meant to test precision" is the
  doc's (inferred but uncontroversial) reading.
- Categories in the asset:
  - critical section over the whole interval / lower-priority remote / guard never true / runs once /
    operand never evaluated: already in `domain_rules.md`; listed by reference only. Verified on
    003 and 027 (masking; `4.1.3` › False Positive Avoidance cites 003 L33-45), 005/006/022 (never-true
    guard), 006 (statement that runs once), 015 (unevaluated operand).
  - different element/field/object; non-adjacent: see 1.6 and 1.7.
  - exclusive guards on fixed values: `4.2` cites 019 trap 1 but explains it only as "conditional
    logic prevents simultaneous access" (doc-inferred). **Derived and verified**: 019 trap 1 (main sets
    the tested values before both guards; the ISR does not write them). The "unless a flow that may
    run between can change them" qualifier comes from 020 trap 1, which is reachable because a
    cascaded ISR rewrites the tested value (wiki, `Racebench.md` › Two traps are reachable).
  - ISR unmasked only by a flow that first disables its access: `4.1.3` › False Positive Avoidance
    cites 013 L43-45 and 014 L43-45, but its explanation ("reads occur before ISR3 is enabled") is
    doc-inferred and incomplete — the ISR *can* be re-unmasked during those reads via the cascade.
    **Derived and verified**: in 013 and 014 the only path that unmasks the writer first clears the
    flag guarding its write, and nothing sets it back. The project's triage study found the same
    class in 004, 028, 030.

### 1.16 Ambiguity: arrival model over apparent intent; show-it-or-uncertain
- The doc offers no guidance on ambiguity. The first sentence is **derived** from README L10
  (indeterminate moment and count) plus `init` enabling everything (1.12). It deliberately follows
  the README over the trap labels where they disagree (see 3.5). The second sentence restates the
  existing `uncertain` policy (`self_validation.md` rule 4, `base.md`).

### 1.17 Harmfulness: any feasible four-shape interleaving is harmful
- **Derived** from 1.4 and 1.5: the benchmark's ground truth labels program facts (the interleaving
  exists), not consequences. Verified as in 1.5. Conflict: see 3.1.

---

## 2. Deliberately left out

From the doc:

| Doc content | Where | Why left out |
| --- | --- | --- |
| The "seven defect patterns" taxonomy and diagram | `3.1` | The doc admits the enumeration is not in the repository and reconstructs it. |
| Scoring weights, "precision over recall" advice, confidence thresholds | `2.2`, `5`, `5.1`, `6.2` › Best Practices | Competition scoring, not program semantics; and contrary to the project's recall policy. |
| init disables interrupts; accesses before the first enable are safe | `6` › Pitfall 4 | Contradicted by `2.1/common.c`. |
| idlerun is the interrupt trigger / opportunity | `4`, `4.1.3` | Contradicted by `common.c` and README L10 (stated the other way round in the asset). |
| All shared variables are `volatile` | `1`, `3`, `4`, `6`, `6.1` | Contradicted by case 012 (stated the other way round in the asset). |
| Equal priority "implementation-defined" | `3.3` | Replaced by the literal README reading (1.10). |
| Nested disable/enable counting | `3` | Undocumented in the suite. |
| Hardware dereference is "an atomic read" | `4.1.4` | Doc-inferred, irrelevant to triples. |
| "Read-Read-Write", "Write-Write" race types | `4` | Doc-inferred; no annotation has those shapes. |
| "First operation is in main" | `4.2` | Wrong (case 014). |
| Annotation syntax, ±2-line matching tolerance, parsing advice | `4.2`, `6`, `6.3` | Forbidden by the brief (no annotation markers), and evaluation-harness matters. |
| JSON output schema | `6`, `6.2` | Invented by the doc ("conceptual"); irrelevant to triage. |
| Real-case descriptions ("likely handles CAN messages", etc.) | `4.3` | Speculative; the cases are withheld. |
| Bug/trap counts 50/33 | several | Not semantics; the measured counts are 48/38 (wiki). |
| Case names, line numbers, variable names, examples | everywhere | Forbidden by the brief. |

From the suite (found while verifying, not in the doc):

- **The labels' narrower arrival model.** At least two traps (001 trap 1, 020 trap 1) are reachable
  only if an ISR fires before the main flow's first masking call or fires more than once; the
  annotators evidently assumed it would not. Encoding that would raise trap agreement but contradicts
  README L10, the project's Soundness Assumptions F7/F8 and `docs/masking-semantics.md`. Left out;
  the asset's Ambiguity section points the other way. Expect the model to call those traps feasible.
- **Writes before initialisation.** Some cases write a shared variable before the initialisation call
  and read it after; such triples are never annotated either way, so nothing can be inferred.
- **W-W-W.** Two annotations become W-W-W traps after the project's errata; only the general "no other
  shape" sentence covers them.
- **Case 019.** Its annotations were written against the other copy of the file (wiki, `Racebench.md`);
  nothing was generalised from its labels.

---

## 3. Conflicts with irqrace's existing prompt assets

The asset declares precedence explicitly for each of these.

1. **Harmfulness criterion** (`domain_rules.md` › Harmfulness: harmful only if the variable feeds a
   branch, index or pointer; otherwise name a reason or answer `uncertain`). Under Racebench a value
   read into a dead local is still the defect. The asset replaces the criterion. It does not change
   scoring: `scoring.py` already ignores harm on Racebench (option C); this makes the *reported*
   bucket agree with that view.
2. **Equal priority** (`domain_rules.md` table row "equal priority: possible", and
   `self_validation.md` rule 3 "either may preempt"). The README's literal reading is that they do not
   nest. The asset replaces both for this benchmark. Recall risk if the asset is ever used outside
   Racebench, and the reading itself is uncertain (1.10).
3. **Definition of feasibility** (`base.md` and `client.FEASIBILITY_TASK`: "can the reported
   interleaving actually occur"). The adjacency rule makes the model answer `infeasible` for an
   interleaving that can physically occur, because the benchmark does not count it. That moves such
   candidates to `likely_infeasible` (still reported — the bucket is derived, nothing is dropped), but
   it is a definitional change, and `FeasibilityAnswer.blocking_element`'s description does not list
   "intervening access" among its examples. The asset says it "narrows the feasibility question".
4. **`domain_rules.md` row "An ISR re-enables a lower-priority interrupt inside itself".** Not a
   contradiction but too narrow: in this suite ISRs typically unmask *higher*-priority ISRs. The asset
   says "any interrupt, including a higher-priority one" (the triage study flagged the same wording).
5. **Trap labels vs. the README arrival model.** Not a conflict with the prompt assets but with the
   ground truth: the asset sides with the README (and with `base.md`'s masking-field semantics and
   Soundness Assumption F8). Disputed traps will score as accepted.
6. **Composition.** `prompts/__init__.py` has no flag for an extra asset; using this one needs a new
   `PromptConfig` field (or a variant row) so the asset enters `assets()` and therefore the config
   hash. If it is appended *after* `self_validation.md`, its "this replaces self-validation rule 3"
   clause reads correctly; if it is used in a row without `domain_rules.md`, the references to "the
   domain rules" dangle harmlessly (the trap list restates their categories in brief).

## 4. Points of residual uncertainty

- Adjacency (1.7) rests on one case with a full chain (022) plus consistency checks; it is the rule
  most likely to be an annotation habit rather than an intended semantic.
- Equal-priority non-preemption (1.10) is a literal reading of one clause and unverifiable on public
  cases.
- Persistence of an ISR's unmask after it returns (1.13) is consistent with every label but not
  distinguished by any.
- "Zero activations" and "state before initialisation" are readings of what the README leaves open.

---

## 5. Experimental variants (T3, 2026-11-12)

Five rows for the prompt comparison of `wiki/Lucas Tasks.md` § T3. Each is `+racebench` with
**exactly one change**, so a measured difference between a variant and `+racebench` has one
cause. None of them has been measured; the hypotheses below are what a measurement should test.

**Composition.** A variant that changes how feasibility is argued must not reach the harmfulness
prompt, or the harm answers become a second cause. `PromptConfig.stage_extra` adds an asset to
one question only; `extra` (used by `+racebench` itself and by the rubric) adds it to both. Every
add-on is rendered after `racebench_semantics.md`, so an add-on that overrides one of its rules
says so and is read last, as the semantics asset does with the earlier sections. The baselines'
hashes are pinned in `tests/test_llm_prompt_variants.py`; no existing asset was edited.

**The schema is unchanged.** Contract C2 (`FeasibilityAnswer`, `HarmfulnessAnswer`) has no
witness, location or rubric field. The variants that need one write it into `reasoning` under a
fixed heading (`Witness:`, `Location:`, `Rubric:`), which a scorer can find but the schema does
not enforce. A missing heading is therefore not a protocol violation; it has to be counted from
the text.

Measurement rules that apply to every row (§ T3 Protocol): a frozen static run, n = 3, paired
per item against `+racebench`, about ±3 points of run-to-run noise
(`wiki/comparisons/Racebench Full Run 2026-10-28.md`, third run), and a recall veto on any bug
point moved to `likely_infeasible`.

### 5.1 `+racebench-selfval` — the self-validation checklists removed

- **Change:** `self_validation=False`. This drops `self_validation.md` from the feasibility prompt
  and `harm_validation.md` from the harmfulness prompt: the flag gates both. The second was already
  declared replaced by the semantics asset's Harmfulness section, so in practice the change is the
  feasibility checklist plus a harm checklist the model was told to set aside.
- **Target:** whether the checklist still earns its place. In the 2026-10-26 study it turned
  correct `benign` answers into `uncertain` (`wiki/comparisons/Triage Study 2026-10-26.md`,
  cause 3); it has since been confined to feasibility, and the semantics asset overrides its
  rule 3 (equal priority). What remains are rules 1, 2 and 4: unknown masking is enabled, an
  unavailable body may access the variable, `uncertain` over `infeasible` without a named
  blocking element.
- **Expected risk:** more traps accepted is the risk the wiki states; the larger one is recall.
  Rule 4 is the sentence that leans the model away from `infeasible`; without it, a bug point may
  be called infeasible on a weak argument. Watch `likely_infeasible` on bug points by name.
- **Hypothesis:** on Racebench, with the record now complete (study follow-up), the checklist adds
  little: `uncertain` counts fall slightly and no bug point moves to `likely_infeasible`. If one
  does, the checklist is doing real work and stays.

### 5.2 `+racebench+witness` — `feasible` needs a written witness

- **Change:** `racebench_witness.md`, feasibility only. It sharpens the semantics asset's
  Ambiguity rule ("if you can show the interleaving...") into four items written in the
  reasoning: the arrival point (and every activation or nested preemption the execution needs),
  the masking state there and the statements that leave it so, the values that pass every guard
  and fix every index or pointer, and the effect at the three accesses. Without all four, the
  answer is `uncertain`, never `infeasible`.
- **Wording choices.** Item 4 asks for the effect *at the accesses* (the values A1 and A2 disagree
  on, the write that is lost), not a downstream use, because the semantics asset says the effect
  need not be observable. Multiple activations are named explicitly because two of the relabelled
  former traps (001 #1, 020 #1) need an activation before the first masking call or a second
  activation (`wiki/benchmarks/Racebench.md`, relabel 2026-10-28). A solver `sat` is not accepted
  as a witness on its own, matching `base.md`'s reading of `unconstrained`.
- **Target:** the confidence clustering on 0.85/0.90 (Triage Study, Results), by making `feasible`
  cost an argument; and the witnesses T2's adjudication needs (§ T2 Risk 1 uses the same four
  fields). The output is in the format of T2's witness template, but the adjudicator must not see
  it (T2 rule 2, blind adjudication).
- **Expected risk:** bug points moving from `likely_real` to `uncertain` when the model cannot or
  does not write all four items: a recall cost in the headline bucket, not a veto (`uncertain` is
  still reported). Longer answers, more tokens per call.
- **Hypothesis:** traps accepted because the model reached for `feasible` without a concrete
  execution (007 #1, unstable) fall to `uncertain` or `infeasible`; bug points keep `feasible`
  because their witnesses exist in the code. Success: no bug point leaves `likely_real`, and at
  least one named error disappears across the three runs.

### 5.3 `+racebench+location` — the location settled first

- **Change:** `racebench_location.md`, feasibility only. The reasoning opens with a `Location:`
  paragraph: the storage each of A1, B and A2 touches, every index and pointer evaluated at the
  moment that access executes in the judged interleaving, then one of `same storage`, `different
  storage on every path` (a blocking element), or `cannot pin down` (treated as shared).
- **Target:** 007 trap #1, the one unstable model error: the ISR increments the index before
  writing and A2 re-reads it, so the three accesses are not on one element; it was `feasible` in
  run 2 and `infeasible` in run 3 (`Racebench Full Run 2026-10-28`, verdict table and variance).
  The asset names both mechanisms that error depends on: stores the remote flow makes before B,
  and stores it made that A2's re-evaluation then sees.
- **Departure from the wiki's proposal:** T3 asks for "a separate answer field". C2 stays
  unchanged, so the paragraph lives in `reasoning` (see Composition). It adds no rule:
  `domain_rules.md` already has the different-location row and `base.md` the one-location
  definition; the variant only fixes the *order* of reasoning.
- **Expected risk:** in the study's counterfactual, a similar paragraph turned the 007 trap
  `infeasible` but lowered a real candidate's confidence from 0.90 to 0.55 (Triage Study,
  cause 3). The asset adds one sentence against that ("`same storage` settles the question and is
  no reason for doubt"); whether it holds is part of the measurement. A model that over-applies
  "different storage" to an index it cannot pin down would cost recall; the asset routes that
  case to "shared".
- **Hypothesis:** 007 #1 is `infeasible` in all three runs; bug points' feasibility is unchanged
  and their mean feasibility confidence falls by less than 0.05.

### 5.4 `+racebench+effectfree` — measured for its recall cost only

- **Change:** `racebench_effectfree.md`, harmfulness only. A remote write that stores the value the
  location already holds, with the local flow writing the location again between A1 and A2 on
  every path, is `benign`, named in `criterion_matched`. It overrides two semantics-asset rules,
  "its effect need not be observable" and "`benign` only for a shape outside the four", and says so.
- **Target:** 022 traps #1 and #3, the annotator-hedged "可能误报" items and the last traps still
  accepted in runs 2 and 3 (`Racebench Full Run 2026-10-28`, verdict table: "neither" is wrong).
- **Why harmfulness and not feasibility.** The interleaving does occur in those traps. Asking it as
  `infeasible` would redefine feasibility, which is what made the adjacency rule unsafe (§ 1.7,
  conflict 3.3). As a harm rule, the reported bucket is `likely_benign`, the feasibility verdict
  stays a statement about reachability, and the feasibility prompt is byte-identical to
  `+racebench`'s. Two consequences for the measurement: the recall veto (`likely_infeasible`)
  cannot fire by construction, so the cost must be read on the `likely_real` reading and listed
  by name; and under the "harm not scored" view (`scoring.scoring_bucket(harm_scored=False)`,
  option C) the variant has no effect at all. `bench-triage-report.py` scores the reported bucket,
  where it does.
- **Expected risk:** it is the adjacency rule's family (an effect-based exclusion), which cost two
  bug points in 017 in run 1. The two conditions together are narrower than adjacency, but the
  first ("the value already held") is easy to argue wrongly for a flag set to a constant that is
  usually, but not always, already set. **Its ROW_HELP says "só para medir, não usar"**; it is not
  a candidate for the screen's default or for the thesis's headline row.
- **Hypothesis:** both 022 traps move to `likely_benign` (+6), and at least one bug point moves with
  them, which would confirm that effect-based rules cost recall on this suite even in narrow form.

### 5.5 `+racebench+rubric` — confidence from a fixed rubric

- **Change:** `racebench_rubric.md`, both questions (the report's rank key takes the lower of the
  two confidences, so both must follow the same scale). Each fact the verdict rests on is sorted as
  *shown* (by the record, including `proven` writers and `assumed_from_config` facts), *defaulted*
  (a safe default the prompt states), or *assumed*; the weakest sets the level, and each level maps
  to one number: A 0.95, B 0.85, C 0.75, D 0.60, and for `uncertain` E 0.45 (one missing fact) or
  F 0.30 (several). The level is written in a final `Rubric:` line.
- **Schema:** the numeric `confidence` field stays (C2 unchanged); the rubric only fixes how the
  number is chosen, and the `Rubric:` line lets a scorer check the mapping after the run.
- **Target:** the Inspection Ratio. Confidences cluster on 0.85/0.90 (Triage Study, Results), so
  the order inside a bucket is close to arbitrary; IR rose from 0.56 to 0.72 when the adjacency
  rule left (`Racebench Full Run 2026-10-28`, second run), mostly from unannotated candidates in
  `likely_real` whose order the confidence does not resolve.
- **Expected risk:** none on recall, since confidence never changes a bucket. Possibly more tokens.
  The levels may still collapse onto A if most answers rest only on shown facts, which would itself
  be a finding: the record is complete enough that confidence carries no signal.
- **Hypothesis:** bug points rest on shown facts more often than accepted traps and unannotated
  candidates, so within `likely_real` they rank first and the mean IR falls below `+racebench`'s by
  more than the run-to-run spread. Verdicts should match `+racebench`'s on almost every item.
