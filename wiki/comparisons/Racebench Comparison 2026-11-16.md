---
type: comparison
tags: [wiki, comparison, t1]
sources: ["[[BMC4AV (paper)]]", "[[NIChecker (paper)]]", "[[IntRace (paper)]]", "[[Racebench]]", "[[Reported Results Across Papers]]", "[[Contradictions]]"]
updated: 2026-11-16
status: draft
---

# Racebench comparison, 2026-11-16 (T1)

The three-way comparison set in [[Lucas Tasks]] T1:
- **S0**: what the published tools report;
- **S1**: irqrace's static stages alone;
- **S2**: irqrace with [[LLM Triage]], `+racebench` row, `likely_real` reading (gate M1, 2026-11-16).

Following T1's rule, every comparison is made **on the baseline paper's own terms** (case subset,
ground truth, defect class), one table per baseline. There is no grand table, because the papers
do not agree on what Racebench contains ([[Precision Metrics]], [[Racebench]]).

**Provenance.**
- S1/S2 are this project's runs, re-run: the static stages frozen from `a639158`, three
  independent triages with `claude-cli:sonnet`, on an AMD Ryzen 5 3600X with 16 GB (WSL for the
  static stages).
- Every S0 number is self-reported by its paper, on other hardware, and some are copied from a
  third paper. Each row is tagged as `run` (the paper ran it itself), `copied` (taken from another
  paper) or `rebased`. Source data: `project-src/bench/published-results.yaml`.
- Scored output: `project-src/results/m1/` (both prompt rows) and `project-src/results/m2/` (S2
  only, one directory per view below).

S2 had **zero spread** over its three runs in every view below (sd 0 on bug points, traps and
score), so each S2 cell is one number.

## 1. Our systems on the full suite (headline)

31 cases, **53 bug points / 33 traps** (the labels since the 2026-10-28 relabel, [[Racebench]]).
No baseline has published on these labels, so this table has no S0 column.

| | Bug points | Traps reported | NASAC score | Precision | Inspection Ratio | LLM calls |
| --- | --- | --- | --- | --- | --- | --- |
| **S1** static | 53/53 | 11/33 | 73/106 | 0.828 | 0.71 | — |
| **S2** + LLM | **53/53** | **2/33** | **100/106** | **0.964** | 0.69 ± 0.02 | 304 ± 2 |

- Recall per pattern is 27/27 RWR, 8/8 WWR, 7/7 WRW and 11/11 RWW, for S1 and S2 alike. The triage
  called no bug point infeasible in any run.
- The two surviving traps are the same in every run, both in `svp_simple_022_001`: `trap#1`
  `W32 W66 R39` and `trap#3` `R55 W66 R63`. They are systematic, not noise, and are the T3 target.
- Trap disposition (S2): 3 never generated, 5 dropped in stage 2, 14 `unsat` in the solver, 9 called
  infeasible by the LLM, 2 reported. Of the 31 traps not reported, **19 are dropped by a proof**
  (stage 2 or solver `unsat`) before the LLM sees them, 3 never become candidates, and 9 are the
  LLM's ranking. The LLM's 9 stay in the report, as `likely_infeasible`.

## 2. Against BMC4AV, on BMC4AV's terms

[[BMC4AV (paper)]] evaluates **25 cases** (it drops 025–030 as `(R,W,W)`-only), excludes `(R,W,W)`
as benign, and uses the pre-relabel labels. It reports **38/38 detected, 0 false positives,
6.35 s** (`run`, Xeon E5-2620).

| View | System | Bug points | Traps reported | Precision |
| --- | --- | --- | --- | --- |
| 25 cases, RWW excluded, 48/38 | BMC4AV (S0) | 38/38 | 0 | 1.000 |
| | S1 | 37/37 | 13 | 0.740 |
| | S2 | **37/37** | 7 | 0.841 |
| 25 cases, RWW excluded, **53/33** | S1 | 42/42 | 8 | 0.840 |
| | S2 | **42/42** | **2** | **0.955** |
| 31 cases, all patterns, 48/38 (re-based) | BMC4AV | **38/48 (79.2%)** | — | — |
| | S2 | 48/48 | 7 | 0.873 |

How to read it:

- **37 against 38 is a pattern-classification difference, not a missed bug.** The project's errata
  correct the access kind of `svp_simple_022_001` bug 2 (lines 55/66/58). As written, the annotation
  reads `(R,W,R)`. Corrected, it reads `(R,W,W)` (`bench/racebench-errata.yaml`, access-kind). BMC4AV
  counts it as `(R,W,R)`, so it is inside its 38. Excluding `(R,W,W)` by the corrected kind removes
  it from our subset, which leaves 37. S1 and S2 detect it anyway: they find all 41 bug points of the
  25 cases, every pattern included. On BMC4AV's own classification, then, S1 and S2 are 38/38 too.
  Recorded as [[Contradictions]] #9.
- **The 7 "traps" S2 reports under 48/38 include the five triples the relabel turned into bug
  points** (001, 019 ×3, 020). The project judged them reachable under the suite's own arrival
  model ([[Contradictions]] #7, #8). Against the 48/38 labels, S2 reports them and they count as
  false positives. Against 53/33, they count as hits. The two remaining traps are the case-022 pair.
- **Inference, not a measured fact:** all five relabelled triples lie inside BMC4AV's 25 cases, and
  none is `(R,W,W)`. A zero-false-positive report on the 48/38 labels implies that BMC4AV did *not*
  report them. If so, on the same 25 cases, `(R,W,W)` excluded, under 53/33, BMC4AV would detect
  37 of 42. That is its 38 minus the corrected 022 bug 2, against a ground truth that adds the five.
  This needs BMC4AV's per-case output to confirm. The artifact (`../BMC4AV`) is not on this machine.
- **Runtime does not compose.** BMC4AV reports 6.35 s on a Xeon E5-2620. S1's static stages take
  169.7 s for all 31 cases on the Ryzen above, and S2 adds about 960 s of LLM time. The workloads
  differ too: bounded model checking of each case, against a whole-program static pipeline plus
  304 LLM calls.

## 3. Against NIChecker, on NIChecker's terms

[[NIChecker (paper)]] evaluates **all 31 cases** with **54 violations** as ground truth. That is
six more than the 48 annotated bug points of the time, and the six are still unexplained
([[Racebench]] §"Reconciling the papers' counts"). It reports **54 detected, 2 false positives,
precision 0.964** (`run`, Xeon Silver 4215).

| Labels | System | Detected / GT | False positives (traps) | Precision |
| --- | --- | --- | --- | --- |
| NIChecker's 54 | NIChecker (S0) | 54/54 | 2 | 0.964 |
| 48/38 | S1 | 48/48 | 16 | 0.750 |
| | S2 | 48/48 | 7 | 0.873 |
| 53/33 | S1 | 53/53 | 11 | 0.828 |
| | S2 | **53/53** | **2** | **0.964** |

- **No like-for-like row exists.** NIChecker's 54 cannot be mapped to annotations, so neither
  label set reproduces its ground truth. The rows are placed side by side, not aligned.
- The equal precision under 53/33 (0.964 = 54/56 = 53/55) is a coincidence of counts. It is not
  evidence that the two tools agree on which candidates are real.
- NIChecker counts false positives as its own warnings that it judges wrong. S1/S2 count planted
  traps reported. These are different denominators ([[Precision Metrics]]).

## 4. IntRace, and the baselines the papers copy

- **[[IntRace (paper)]]** detects **data races**, not atomicity violations, on 30 cases with a
  ground truth of 50, and reports a detection rate of 0.907 and 5 false positives. The defect class
  differs, so no S1/S2 row is placed against it ([[Contradictions]] #5).
- **Baselines quoted inside the papers**, none re-run here and all unobtainable
  ([[Reported Results Across Papers]]):
  - intAtom: recall 1.0 per NIChecker (`copied`); 44 warnings and 6 FP per BMC4AV (`copied`);
  - iCBMC+: 58 warnings, 20 FP, 130.36 s per BMC4AV (`unknown`);
  - CPA4AV: handles 14 of the 31 cases, and fails on 3 of them (`unknown`).

  They go into the thesis as context, labelled with their provenance. They are not competitors S2
  is measured against.

## What this supports, and what it does not

- **Supported:** on every view, S1 and S2 detect every annotated bug point, the `(R,W,W)` ones
  included. Neither BMC4AV nor IntRace can claim that, because each redefines the ground truth.
  The triage costs no recall. It cuts reported traps from 11 to 2 on 53/33, a 0.828 → 0.964
  precision gain, at about 304 Sonnet calls per full run.
- **Not supported:**
  - "S2 beats NIChecker". Its 54 does not align with either label set.
  - Any runtime ranking.
  - Any claim about BMC4AV under 53/33 until its per-case output is checked.

## Open for gate M2

1. Is the per-baseline framing convincing as the thesis's T1 presentation?
2. How is NIChecker's 54 presented: side by side and explicitly unaligned, as above, or left out
   of the table?
3. Should the BMC4AV artifact be fetched to confirm the inference in §2 (that it did not report
   the five relabelled triples)? Re-running it needs its toolchain (a CBMC fork).
