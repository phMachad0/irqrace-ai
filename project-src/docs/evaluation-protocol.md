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
(`../racebench/2.1_remarks`, visible in its `git diff`), on the human's direction,
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
