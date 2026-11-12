# Evaluation protocol — counting unit and match rule

Both decisions were open blockers in [[Open Questions]] and were taken on
**2026-09-10**. Every recall number this project reports divides by the first and
is computed with the second, so they are recorded here, implemented in
`src/irqrace/evaluation.py`, and echoed into every run manifest. A number quoted
without them is not quotable ([[Precision Metrics]]).

## Decision 1 — counting unit: per-triple-instance

**One annotated triple is one defect.** The 31 Racebench simple cases carry
**53 bug points and 33 planted traps** since 2026-10-28, and carried **48 and 38**
before (see "Relabel, 2026-10-28" below). Every number dated before that day
divides by 48/38.

The corpus mixes units without naming them: the shipped `violation.info` counts
per variable (45 entries) while [[BMC4AV (paper)]]'s tables count per
access-triple-instance (94), and most cross-paper comparisons quietly depend on
which ([[Contradictions]] #1). Measured on this suite, the three candidate units
give:

| Unit | Bug points | Traps | before 2026-10-28 |
| --- | --- | --- | --- |
| **per-triple-instance** | **53** | **33** | 48 / 38 |
| per (case, variable) | 35 | 25 | 33 / 29 |
| per case (cases with at least one) | 31 | 22 | 31 / — |

Per-triple-instance is the finest grain available, so it is the hardest to
inflate; it is what BMC4AV counts, so cross-paper comparison survives; and the
coarser units actively hide structure — `svp_simple_017_001` carries four
distinct bug points on one variable, and `svp_simple_022_001` four on another.

## Decision 2 — match rule

> A reported candidate **matches** an annotated triple when it is in the same
> subject, concerns the same shared location, and its ordered access lines
> `(A₁, B, A₂)` equal the annotation's corrected lines.

Three things that rule deliberately does **not** do:

**It does not require the access kinds to agree.** Two measurements justify this.
First, the ordered line triple is already a unique key: `(case, lines)`
distinguishes all 86 annotations with zero collisions, and no trap shares a line
triple with a bug point — so adding kinds buys no discrimination. Second, **20
annotated accesses name a line that both reads and writes the variable**
(`for (x = 0; x < N; x++)`, `x = x + 1`). Requiring kind equality would turn each
of those into a coin flip about which of the two the detector chose to report.
Kind agreement is computed and reported, so systematic disagreement surfaces
rather than hiding; it is just not part of the match.

**It does not require the variable *name* to agree.** The annotations name the
location at source level, which is sometimes an alias: `*p` and `*u` for a local
pointer, `*ptr_var` in `svp_simple_025_001`, `global_array[1]`, `tm_blocks[36]`,
`global_union.header`. Those are not errors — they are what the location is
called at that point — and resolving them is exactly the job of the may-alias
analysis. So names are normalised to a base identifier and checked against the
candidate's name *and* its alias set, and a mismatch is reported rather than
fatal. 12 annotations depend on this.

**Triple against triple.** Racebench's ground truth is triple-shaped, and so is
every candidate ([[Triples Only]]): a match compares the ordered line triple of
the candidate with that of the annotation.

## Decision 3 — match against corrected annotations

Matching is against `bench/racebench-errata.yaml` applied to the parsed
annotations, not against the shipped text.

This is not a convenience. `svp_simple_019_001`'s annotations name lines that
contain no access at all — its bug point's ISR write is annotated at line 65,
which is `idlerun();`, while the write is at line 71. **An exact match against
the shipped text scores 0 on that bug point no matter how good the analyzer is**,
and would mis-score its three traps as well.

The errata holds 12 corrections: six line-number fixes (five in 019, one
off-by-one in 001) and six access-kind fixes across 002, 016, 017 and 022. Each
entry quotes the annotation as written, gives the corrected triple, states a
confidence (`certain` for eleven, `likely` for one) and carries its evidence.
**No correction changes a count**: the errata corrects lines and kinds only. What
changes is the shape distribution, and both are reported. (Since 2026-10-28 the
errata holds 6 corrections: the six line fixes for 001 and 019 moved into the
suite's source with the relabel below.)

## Relabel, 2026-10-28 — the one change of counts

Five planted traps were relabelled as bug points **in the suite's own source**
(then `../racebench/2.1_remarks`, uncommitted there; since 2026-10-29 vendored at
`bench/racebench`, where the change is a commit of its own), on the human's direction,
after each was hand-checked as reachable under the suite's README ("an interrupt
may preempt the main program or a lower-level interrupt whenever it is enabled,
at an indeterminate moment, position and number of times"):

| Case | Was | Now | Why |
| --- | --- | --- | --- |
| 001 | trap 1 `global_var <W#43><R#63><W#44>` | bug 2, read on line 64 | `isr_1` may fire before `disable_isr(2)`, or start again with irq 2 unmasked |
| 019 | traps 2, 3, 4 (line-drifted) | bugs 2, 3, 4, lines of the file | 2: valid only for the `2.1` copy; 3, 4: reachable through the gap between two critical sections in both copies |
| 020 | trap 1 `global_var <R#37><W#44><R#40>` | bug 3 | reachable with two `isr_1` activations |

Counts: **48 → 53 bug points, 38 → 33 traps.** Recall gate after stage 3:
53/53. The evidence: `bench/racebench-errata.yaml` (note `relabel_2026_10_28`),
wiki `Racebench Full Run 2026-10-28` ("Verdict on every disputed item"),
`Contradictions` #7 and #8. 022's two "可能误报" (possible false positive) items
were not relabelled: reachable but effect-free, and hedged by their annotator.

The competition rules quote 53 bug points and 38 false-positive markers for the
whole suite, 50 and 33 for the simple cases; this project's 53/33 for the simple
cases coincides with neither by design.

Applying the errata is fail-fast: an entry that no longer matches the file raises
rather than being skipped, because a silently inapplicable errata means the suite
moved underneath every number measured against it.

## What is reported

| Number | Definition | Gate |
| --- | --- | --- |
| **Recall** | bug points matched / 53 (48 before 2026-10-28) | **must be 100%** |
| Candidates reported | total, per subject and overall | no gate — report without embarrassment |
| Trap reporting rate | traps matched / 33 (38 before 2026-10-28) | **no gate at stage 1** (see below) |
| Kind agreement | matches whose access kinds also agree | diagnostic |
| Alias-resolved matches | matches where the variable name differed | diagnostic |
| **Inspection Ratio** | fraction of the ordered list read before every bug point is found | the headline precision-side metric |

**A trap reported by the static phase is correct behaviour, not a failure.** The
static phase is deliberately over-approximate and ignores guard conditions and
interrupt state so that nothing is missed ([[Pipeline Design]], stage 1). Traps
are what the solver and then the LLM stage are there to sort out, so trap
rejection only becomes a meaningful score after those stages exist. Reporting
most traps at stage 1 is the expected result (30/33 since the relabel).

**Inspection Ratio is undefined when a bug point was missed**, and the code
returns nothing rather than a flattering number. An Inspection Ratio computed
over an incomplete detection describes how quickly a reviewer finds the defects
that were found, which is not the quantity anyone wants.

---

## DRAFT — Racebench 2.2: equivalence rule, witness, adjudication

> **Status: DRAFT for gate M4a (prepared 2026-11-12). Not in force.** Nothing below is
> applied until Lucas approves it, and no triple is adjudicated before that. The name
> "2.2" is provisional ("2.2-irqrace" is the alternative: wiki `Lucas Tasks`, T2).

**What 2.2 is.** *2.1* is the ground truth above: the suite's annotations, the errata, the
relabel of 2026-10-28 — 53 bug points and 33 traps. *2.2* is 2.1 plus every entry of
`bench/racebench-2.2.yaml` whose verdict is `bug` (a bug point) or `trap`. The label file is a
sidecar: it never edits the suite, and 2.1 is read unchanged next to it.
`irqrace.labels_ext.ground_truth("2.1" | "2.2")` returns either, so the scorer can gain
`--labels 2.1|2.2` with one call.

### Rule E — when two reported triples are the same defect

Three units, always reported side by side:

| Unit | What it is | 2.1 |
| --- | --- | --- |
| **record** | one context record (candidate id). Records differ in access kinds, columns, flows, call paths | — |
| **triple** | the match rule's key: case, location, ordered lines (A1, B, A2). The unit of Decisions 1 and 2 | 53 bugs, 33 traps |
| **defect** | an equivalence class of triples under rule E | 35 bugs, 27 traps |

> **Rule E.** Two triples *t* and *u* are **siblings** when they are in the same case, on the
> same shared location (their normalised names intersect: name and alias set, as in Decision 2),
> and one of these holds, comparing sites as (file, line), where an annotation's site is in the
> case file:
>
> - **E1 — same lines.** A1, B and A2 are on the same three lines. They differ only in access
>   kinds (017's loop header writes and reads on line 29), columns, or the flow or call path
>   through which a line is reached. E1 is exactly the match rule's key, so E1 classes *are*
>   triples.
> - **E2 — another interrupting access.** Same A1 line and same A2 line; B on another line. The
>   same interrupted pair broken by another ISR (027's `isr_1` at 41 and `isr_2` at 45), or by
>   another statement of the same ISR. A second *activation* of an ISR does not make a new triple
>   at all: a triple does not record which activation reached B.
> - **E3 — finer or coarser.** Same B line, and the two A1–A2 pairs share an endpoint line (A1 or
>   A2 of one is A1 or A2 of the other). A coarser triple and the finer ones it is made of: 019's
>   (45, 71, 59) with (45, 71, 51) and (51, 71, 59); 017's four loop triples; 022's chain.
>
> A **defect** is a connected component of the sibling relation (transitive closure), computed
> over **the triples being counted and no others**: a triple judged not a bug does not bridge
> two bug triples into one defect. Bug triples are classed among bug triples, trap triples among
> trap triples. A **new defect** of 2.2 is a bug class with no 2.1 bug point in it; a 2.2 bug
> triple that joins a class holding a 2.1 bug point adds a triple, not a defect.

What the rule does **not** use: reachability, masking, guards, the solver's result, the LLM's
buckets. It is decided from case, location and lines alone, so it can be fixed before any
adjudication and recomputed mechanically from the label file (`irqrace.labels_ext.defect_classes`,
`label_counts`; the rule string `EQUIVALENCE_RULE` is echoed with every count).

**Calibration on 2.1 (measured, not chosen).** Applied to the suite's own labels, rule E turns
53 bug triples into **35 defects** and 33 trap triples into **27**. That is deliberately coarser
than the suite's own counting, which lists 027's two ISRs, 019's coarse and fine triples and
017's four loop triples as separate bug points; that is why the triple count stays the unit
comparable with 2.1 and BMC4AV, and the defect count is reported next to it, never instead.
Applied to bugs and traps together, **12 of the classes mix a bug point with a planted trap**
(001, 002, 003, 005, 006, 007, 022, 026–030): the suite plants traps *as* siblings of its bug
points. So rule E is a counting rule, not a verdict rule — siblings may have different verdicts,
and **every triple is adjudicated on its own**.

### The witness

A triple becomes a 2.2 bug point only with a **concrete interleaving witness** under the README
model — the standard the 2026-10-28 relabel used for 001, 019 and 020 (wiki `Racebench Full Run
2026-10-28`, "Verdict on every disputed item"). A solver `sat` is not a witness (SAT means "not
refuted"), and an LLM bucket is not one either. One record per triple in
`bench/racebench-2.2.yaml`:

| Field | Content |
| --- | --- |
| `case` | the subject, e.g. `svp_simple_017_001` |
| `variable` | the shared location, as the annotations name it |
| `triple` | A1, B, A2 in that order, each with `kind` (read/write), `line`, `flow` (and `file` when not the case file) |
| `candidate_ids` | the tool's records on these lines (informational) |
| `witness.arrival_point` | where B's flow arrives: the function and the two statements of the interrupted flow it lands between |
| `witness.masking_at_arrival` | the masking state of B's interrupt there, and *why* it is unmasked (which `enable_isr`, on which path, which earlier activation) |
| `witness.guard_values` | the values that make every guard on A1, B and A2 pass, and how they get there |
| `witness.effect` | the observable change in A1/A2 — the value read or left differs from every serial order — and the shape (RWR / WWR / RWW / WRW) |
| `verdict` | `bug` · `trap` · `not-a-defect` · `undecided` |
| `blocking_reason` | required unless `bug`: what makes it unreachable, effect-free, or undecidable |
| `adjudicator`, `date` | who decided, and when |
| `second_check` | `done` (yes/no); if yes, the second adjudicator, their verdict and date |
| `notes` | free text |

The four verdicts:

- **bug** — a witness exists; all four witness fields filled. Joins the bug points.
- **trap** — no interleaving exists: B's interrupt is masked at every arrival point, B's flow
  cannot preempt there, the guards cannot all pass, or A1, B and A2 do not touch one location.
  Joins the traps, so reporting it costs the tool as a planted trap does.
- **not-a-defect** — the interleaving occurs but changes nothing observable (022's "可能误报"
  kind: the ISR writes the value already there, or the task overwrites it on every path before
  any use). Out of both denominators by default and reported as a count; whether it should
  count as a trap, as 022's two do in 2.1, is open at M4a (`not_a_defect_as_trap`).
- **undecided** — cannot be settled from the source and the README. Out of both denominators,
  reported as a count.

### Procedure

1. **Freeze the candidate set** from the T1 run (one commit, one row): every context record whose
   ordered line triple matches no 2.1 annotation (`scripts/racebench-dossiers.py`). This is
   narrower than the scorer's "candidates matching no annotation", which also counts records on
   an annotated line triple with other access kinds (E1 siblings of an annotation, which 2.2
   cannot label). On the static run `runs/m0-check-20261112` (31 cases, 166 records reaching the
   LLM): the scorer's count is 102; the frozen set is **96 records on 91 triples, in 31 groups**;
   20 of the groups hold a 2.1 bug point, 11 do not.
2. **Fix rule E and this template** at gate M4a, before step 4. A change afterwards means
   re-counting everything and saying so.
3. **Select**: either `--all`, or every `likely_real` triple plus a seeded random sample of the
   rest (`--likely-real-plus-sample K --seed S`), which measures how many real bugs the LLM put
   in a lower bucket. The selection is the only step that reads buckets; it writes them only to
   `selection.csv`, which the adjudicator does not open. `--all` never opens `llm/`.
4. **Blind dossiers**, one per group: the case, the triples, the variable, the flows and
   priorities, the static masking facts and the solver's result labelled as tool output, the
   numbered source of every function involved, the README's arrival rules, and a blank witness
   form per triple. No bucket, LLM verdict, confidence or reasoning — a test enforces it. Ordered
   by case and line, never by triage rank; in sample mode, siblings that were not drawn are left
   out, since listing them would reveal their bucket.
5. **Adjudicate** each triple from the dossier alone, and record every outcome, rejections
   included, in `bench/racebench-2.2.yaml` (the loader rejects a `bug` without a full witness and
   any other verdict without a blocking reason). Otherwise 2.2 could only grow in the tool's
   favour.
6. **Second adjudicator.** Pedro checks a sample independently, blind to the LLM *and* to the
   first verdict. Agreement is Cohen's κ over the four verdicts and over bug / not bug
   (`labels_ext.second_check_agreement`); disagreements are discussed, the resolution goes in
   `notes`, and both verdicts stay on the record.
7. **Report 2.1 always next to 2.2**, as triples and as defects, with the count of
   `not-a-defect` and `undecided`. The published tools have no 2.2 score until someone re-runs
   them, so 2.1 remains the headline for any comparison with them.
