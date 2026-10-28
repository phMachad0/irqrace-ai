---
type: comparison
tags: [wiki, comparison, project]
sources: ["[[LLM Triage]]", "[[LLM Stage Design]]", "[[Prompt Architecture]]", "[[Racebench]]", "[[Triples Only]]", "[[Precision Metrics]]"]
updated: 2026-10-27
status: draft
---

# Triage Study 2026-10-26 — why the LLM triage underperforms on real records

A study of the triage stage on the static pipeline's own output (not on the 20 hand-built
fixtures), started because `svp_simple_001_001`'s bug point `(32, 55, 35)` came back `uncertain`
with a reasoning that hedged on facts the record named but did not show. Diary context:
[[Semana 8 — Integração das Trilhas A e B]].

## Setup

- **Subjects:** 15 of the 31 simple [[Racebench]] cases (001, 004, 006, 007, 009, 013, 014, 016,
  019, 020, 021, 022, 026, 028, 030) — every case with a trap that survives the solver, plus three
  for pattern coverage. 184 stage-1 triples, **101 reach the LLM**: 23 bug points, 16 traps,
  62 unannotated.
- **Pipeline:** `irqrace pipeline … --backend claude-cli:sonnet` (the desktop app's own steps,
  headless), prompt row `+self-validation`, one sample. Track B branch after the merge of Track
  A's stages 2 and 3.
- **Analysis:** four agents, one per case group. Each judged every labelled candidate against the
  C source, classified each wrong or hedged answer, re-ran up to ~20 single-record triages across
  the ablation rows, and ran **counterfactuals**: copies of a record with one class of fact added
  by hand, nothing else changed. Reports: `project-src/runs/triage-study/analysis/group-{A,B,C,D}.md`
  (run store, not versioned).
- Scoring follows the 2026-09-27 decision ("option C", `log.md`): on Racebench only feasibility is
  scored, because its readers are dead locals by design.

## Results

| | reach the LLM | feasible | uncertain | infeasible |
| --- | --- | --- | --- | --- |
| bug points | 23 | 18 | 5 | 0 |
| traps | 16 | 10 | 5 | 1 |

- **Recall held**: no bug point was called infeasible.
- **Discrimination was almost absent**: 1 of 16 traps rejected. 5 traps landed in `likely_real`,
  and 14 of 23 bug points landed below it (8 `uncertain`, 6 `likely_benign`).
- **Inspection Ratio** (mean per case): 0.80 in the records' own order (a hash, i.e. arbitrary) →
  0.66 after triage (0.67 under option C). Confidences cluster on 0.85 and 0.90, so the order
  inside a bucket is coarse.
- **5 of the 16 traps are disputed**: reachable in the analysed file (001 trap 1 and 020 trap 1,
  already in `docs/masking-semantics.md`; 019 traps 2–4, the last two feasible in both copies of
  the source). The model was right on them. Of the 11 genuine traps, 1 was rejected.

## Causes, by weight of evidence

**1. The record omits the code that decides the case (dominant).** Stage 1 builds `flows` and
`enclosing_source` only from the functions containing A1, B and A2. When a flow the record itself
names (`masking.interval.reenabled_within_interval_by`) is absent from `flows`, **12 of 16** answers
are `uncertain`; when it is present, **78 of 85** are `feasible`. Counterfactuals made it causal:
adding only the missing flow and its body turned the 001 bug point `feasible` (2/2) and the 014 bug
point `feasible`; adding that plus every store to the guard variable turned **5 of 6** hedged or
wrong genuine traps into `infeasible`, each naming the right blocking element (typically "isr_1
clears the flag before it unmasks isr_2"). The hedge is identical in every ablation row from
`simple` on, so it is not the prompt's policy.

**2. Record fields carry no stated meaning.** `masking.per_access[].state.enabled` means "may be
enabled on some path, interference included"; read without that, it contradicted a visible
`disable_isr` in 4 of 11 labelled answers (group C) and was discounted. `disable_isr`/`enable_isr`
are listed in `opaque_external_calls` although C1 models them. `static_features.feeds_branch` and
`used_as_index` are `null` in 101 of 101 records (never computed) and were cited as "not
established" in 13 of 28 answers in one group.

**3. Prompt defects (secondary).**
- Feasibility is asked as a timing question; nothing says A1, B and A2 must touch **the same memory
  location**. Two genuine traps (007, 009) and four unannotated 007 candidates were called feasible
  although B writes another array element or another object. A counterfactual paragraph turned the
  007 trap `infeasible` — but lowered a real candidate's confidence from 0.90 to 0.55, so the
  change carries recall risk.
- The self-validation checklist is in the system prefix both questions share, so its rules 2 and
  4 also turn `benign` into `uncertain` on the harmfulness question (benign in 6/6 answers without
  it, 2/4 with it, one group).
- The harmfulness criterion talks about "the shared variable", not the value the interleaving
  changes; it fired on a branch evaluated before A1 and missed a use in a flow absent from the record.
- A domain rule says an ISR re-enables "a lower-priority interrupt"; the common case is a higher one.
- Hypothesis refuted: the model weighs a `sat` witness correctly, discounting it exactly where it
  rests on loop or interference havoc.

**4. Ground truth leaked into the records.** `_enclosing_source` used `line_end + 1`; the line after
the last function of a Racebench file is the annotation header `//bug点:`. It was in **50 of 101**
records and the model cited it about seven times ("the planted bug, as the 'bug点' comment
suggests"), moving harm verdicts. On real code that line is noise; here it contaminates every
number above for 10 of the 15 cases. The counterfactuals are controlled (only one fact added), so
the causal findings stand.

**5. Static-stage limits.** Two traps in 022 are *subsumed* triples (a local write lies between A1
and A2 on every path), which the feasibility question cannot reject. Points-to ignores statement
order (009). Interference values are fully havocked, so a solver witness can run through dead code.

**6. Backend.** `claude-cli:sonnet` refused about half of the calls on the combined-schema rows
(`simple`, `+domain`) with a `reasoning_extraction` safeguard, and none on the decomposed rows. The
production row is decomposed. Ablation rows 1–2 are not comparable on this backend without a
refusal column.

## What to change (all general — no rule names a benchmark)

1. Fix the `line_end + 1` extent and re-run (measurement validity).
2. Complete the record: every flow named anywhere in it, with its body; the store sites of shared
   variables read in the functions involved, with a completeness flag (a guard is "never true" only
   over a complete writer set); C1's models of externals and masking primitives as
   `assumed_from_config`; numbered source lines, macro definitions, global initialisers.
3. State the meaning of the masking and solver fields in the prompt.
4. Define feasibility over one memory location and widen `blocking_element` — with an explicit
   argument required, `uncertain` otherwise.
5. Keep the self-validation checklist to feasibility; make the harm criterion pattern-specific
   (the value B reads in WRW, A2's re-read in RWR, the lost write in RWW, A2's read in WWR); fix the
   domain-rule wording.
6. Static stage: a "subsumed" fact for ranking only (never a drop); compute or remove the two null
   features; order-sensitive points-to; bounded interference when the writer set is complete. The
   alternative to shipping everything up front is enabling `+progressive` (C4 requests).

Items 1–3 were implemented the same day; see [[#Follow-up]].

## Follow-up

Items 1–3 were implemented on `track-b/llm-integration` (2026-10-26/27), and the same 15 cases were
re-run with the same backend and row (`runs/triage-study-v2`, one sample, 101 records, no backend
failure). What changed in the record:

- `enclosing_source` now runs from a function's first line to the brace that closes it
  (`source_context.function_extent`); no record carries the annotations any more.
- `flows` lists every configured flow; `enclosing_source` adds the functions on the access call
  paths, the code of every flow that touches the variable or calls a masking primitive, and short
  direct callees, under a size cap.
- `provenance` gains `writers.<variable>` for the candidate's variable and every shared variable the
  shipped code reads (each store site, the declaration, `proven` when the set is complete),
  `masking_primitives.<fn>` / `externals.<fn>` from C1 (`assumed_from_config`), and `macros`;
  `opaque_external_calls` lists only calls with no model.
- The rendered source is numbered with file lines, and `base.md` states what the masking, solver,
  writer, external and `static_features` fields mean.

| | before | after |
| --- | --- | --- |
| bug points called feasible | 18 / 23 (5 uncertain) | **23 / 23** |
| bug points called infeasible | 0 | 0 |
| genuine traps rejected (infeasible) | 1 / 11 | **8 / 11** |
| disputed (reachable) traps called infeasible | 0 / 5 | 0 / 5 |
| mean Inspection Ratio, feasibility only (option C) | 0.67 | **0.55** |
| mean Inspection Ratio, reported buckets | 0.66 | 0.59 |

- Each of the eight rejections names the right blocking element: five "the ISR clears the flag
  before it unmasks the reader" (004, 013, 014, 028, 030), two guards that are never true (022 trap
  2, 006), and one pointer retargeted before the access (009).
- The three genuine traps still accepted are the two classes left untouched: the same-location
  definition (007, item 4) and subsumed triples (022 traps 1 and 3, item 6).
- Of the nine unannotated candidates now called infeasible, six already were (statements that run
  once); the three new ones (two on 022's dead line 56, one loop-order case in 006) match the
  group-A analyst's hand reading.
- The bucket view gains less because harmfulness is untouched: 11 of 23 bug points sit in
  `likely_benign` (dead readers, correct about the code) — item 5.

Still open: items 4–6, and a second sample to measure variance; the numbers above are one sample
each.

## Second follow-up — items 4–6 and a benchmark-semantics row (2026-10-27)

**Items 4–6, in the production row (`+self-validation`):**

- *Same location* (item 4): `base.md` defines the triple over one memory location (same element,
  same pointee); the domain table gains a "B touches a different location on every path" row that
  requires the index or pointer argument; `blocking_element` lists the new kinds.
- *Harmfulness* (item 5): the two questions now get different system prompts. Feasibility keeps the
  domain table and the self-validation checklist; harmfulness gets a pattern-specific criterion
  (`harmfulness.md`: the value B reads in WRW, A2's re-read in RWR, the lost write in RWW, A2's read
  in WWR; a branch evaluated before the changed value does not count) and a two-rule checklist of
  its own. The domain rule on re-enabling now says "typically a higher-priority one".
- *Static* (item 6, partly): stage 1's C++ traces where each read's loaded value goes inside its
  function (def-use through locals: branch, index, dereferenced address, escapes, discarded). From
  it, `static_features.feeds_branch` / `used_as_index` are computed on the reads that matter for the
  pattern (null only when the value escapes), and a `value_use` provenance entry states it. An
  `interval.local_accesses` entry lists same-flow accesses that may fall between A1 and A2 (evidence
  for subsumed triples; nothing is dropped). Not done: order-sensitive points-to and bounded
  interference values, both changes to SVF use and to stage 3's encoding.

**A benchmark-semantics row, `+racebench` (experimental, never the reported ablation).** The
production row plus one add-on asset, `racebench_semantics.md`, drafted by an agent from the
Racebench DeepWiki export and checked against the suite's own README and `common.c` (rationale and
per-rule provenance: `project-src/docs/racebench-prompt-rationale.md`). No examples, no case or
identifier names. Its main rules: the interleaving itself is the defect, effect not required (so
harm = harmful for the four shapes); same location means same storage; **A1 and A2 must be
adjacent** — if the same flow touches the location again on every path between them, the suite
counts the finer triples and this one is a trap; the README's arrival model (any time while
unmasked, any number of times, nesting; equal priority does not preempt; `init` unmasks all).
Uncertain points it flags itself: adjacency rests mainly on one case; equal-priority
non-preemption is a literal README reading and contradicts the project's C1 default.

Same 15 cases, one sample each, no backend failure:

| | items 1–3 | + items 4–6 | `+racebench` |
| --- | --- | --- | --- |
| bug points feasible | 23/23 | 23/23 | 23/23 |
| bug points in `likely_real` | 10 | 8 | **23** |
| genuine traps rejected | 8/11 | 9/11 | **10/11** (1 uncertain) |
| disputed traps called infeasible | 0/5 | 0/5 | 0/5 |
| unannotated called infeasible | 9 | 15 | 37 |
| mean Inspection Ratio, buckets | 0.59 | 0.63 | **0.44** |
| mean Inspection Ratio, feasibility only | 0.55 | 0.53 | **0.42** |

- Items 4–6 move feasibility a little (one more trap rejected; 007's index-increment candidates now
  called a different location) and make harmfulness honest about dead readers: 15 of 23 bug points
  are `likely_benign`, correct about the code, which is why the bucket view loses ground.
- `+racebench` aligns the buckets with the benchmark. Of its 22 extra `infeasible` verdicts on
  unannotated candidates, 20 cite an intervening same-flow access (the adjacency rule) and 2 a
  different array element. The adjacency rule judges *redundancy*, not reachability: the
  interleaving is possible, the suite just counts a finer triple. It belongs in a benchmark
  evaluation row, not in the production prompt, where it would put reachable interleavings under
  `likely_infeasible`.
- Reading for the thesis: on Racebench the gap between rows is mostly a definitional gap — what
  the benchmark calls a defect — not a reasoning gap. Feasibility of bug points was already 23/23.

Still open: a second sample per row for variance; points-to and interference precision (item 6);
whether the adjacency convention is the suite's or an annotation habit.
