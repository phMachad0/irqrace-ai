---
type: source
tags: [wiki, source]
sources: ["[[BMC4AV (paper)]]"]
updated: 2026-08-17
status: solid
---

# From Potential to Confirmed: Effective Detection of Atomicity Violations in Interrupt-Driven Programs via Guided Memory Access Graph

**SSRN preprint (not peer reviewed) · 2026-04-25 · Zixuan Yuan, Bin Yu, Xincheng Wang, Xu Lu, Cheng Wen, Wensheng Wang, Hao Wang, Chu Chen, Cong Tian (Xidian University et al.) · clipping: [[BMC4AV]] · PDF: `raw/BMC4AV.pdf` · [source](https://ssrn.com/abstract=6731320)**

> [!warning] Preprint
> Not peer reviewed. The strongest claims in this wiki come from this paper, and several of
> them are re-counts of another team's benchmark. Treat accordingly.

The newest source, and the one that most directly attacks another tool in the wiki:
[[NIChecker (tool)]]. Introduces [[BMC4AV (tool)]].

## Problem

Existing atomicity-violation detectors for interrupt-driven programs are placed in two
families and faulted individually (§1): [[intAtom]]'s data-flow analysis lacks precise
reachability and cannot cope with non-deterministic interleavings across priorities;
[[CPA4AV]] struggles with complex data types; [[NIChecker (tool)]] requires the user to
specify violation types (so it is not fully automatic), can miss violations through
semantic mismatch in its assertion insertion, and inherits CBMC's unoptimized encoding.

## Approach

A [[Bounded Model Checking]] pipeline in which the front-end tells the back-end *what to
look for*:

1. **Symbolic encoding** — SSA form, symbolic memory events, and ordering encoding capture
   possible interleavings among tasks of different priority.
2. **Potential-violation identification** — match the encoded events against the three
   patterns `(R,W,R)`, `(W,W,R)`, `(W,R,W)` and extract, for each candidate, the **key
   partial orders** (specifically key *read-from* / RF orders) that would have to hold.
3. **Guided [[Memory Access Graph]]** — inside the solver, maintain a MAG whose edges are
   inferred (RF, WS, FR) rather than encoded as constraints up front. It is extended
   incrementally under RF-guidance until it is stable and acyclic, at which point a
   candidate is *confirmed* as real.

The design claim is that guidance buys precision and the graph buys efficiency: unnecessary
order constraints are never generated because edges are inferred on the graph instead.
Implemented on [[CBMC]] with MiniSat.

## Evaluation

Intel Xeon E5-2620, 32 GB, Ubuntu 20.04 — explicitly weaker hardware than NIChecker's, and
identical to intAtom's. Loops abstracted with the same strategy NIChecker used.

- **[[Racebench]] 2.1**, 25 of 31 cases, 1541 LoC, **38 violations**. Six cases were
  *excluded because their only pattern is `(R,W,W)`, which the authors classify as benign* —
  a definitional choice that alone changes the ground truth. BMC4AV: **38/38, zero false
  positives**, 6.35 s total. Baselines: iCBMC+ 58 warnings / 20 FP (67.9% precision),
  intAtom 44 warnings / 6 FP (86.4%), NIChecker 40 warnings / 2 FP, CPA4AV largely
  unsupported or timing out.
- **[[Real-World Program Benchmark]]**, the same 18 programs NIChecker used, 10633 LoC.
  Here the paper re-counts the ground truth: **94 actual violations, not the 37 NIChecker
  reports after removing `(R,W,W)`**. BMC4AV: **94/94, 0 FP, 21.12 s, 567.21 MB**.
  NIChecker: 37/37 with 0 FP but **57 false negatives — a 39.4% hit rate**. iCBMC+ finds all
  94 but with 72 false positives (56.3% precision) in 744.55 s. Headline framing:
  **92.0% less detection time and 62.0% less exploration space than NIChecker**.
- **Ablation** (Table 3): against BMC4AV-NRF (no RF-guidance), BMC4AV needs far fewer key
  RF-edges (94 vs 258) while NRF misses 63 violations; BMC4AV-ARF (all RF-edges) finds
  everything but costs 368.17 s vs 21.12 s; BMC4AV-NG (no MAG) costs 45.97 s and 739.74 MB
  vs 21.12 s and 567.21 MB.

## Claims to trust and claims to check

- Trust: the **ablation**. It is self-contained, run on one machine by one team, and it
  isolates the two contributions cleanly — RF-guidance buys precision, the MAG buys speed.
- Check: the **94 vs 37** re-count. The paper argues NIChecker's 37 violations were all
  *manually injected by NIChecker's own authors*, and that in-depth analysis reveals 94. That
  reasoning is plausible — a tool that only checks user-nominated variables cannot find what
  it was not pointed at — but it is one team's manual re-count of another team's benchmark,
  published without peer review, and it is the foundation of the headline claim. Flagged in
  [[Contradictions]].
- Check: cross-tool runtimes mix re-runs and numbers copied from published papers on
  different hardware. The paper defends the comparison by noting its own hardware is weaker.

## Limitations and threats to validity

Preprint status. The `(R,W,W)`-is-benign decision is asserted rather than argued at length,
yet it silently reshapes both benchmarks. Evaluation is confined to C programs and to the
same two suites everyone in this literature uses.

## Relation to other sources

- Successor and direct challenger to [[NIChecker (paper)]]; reuses its benchmark, its
  loop-abstraction strategy, and its backend, then disputes its recall.
- Shares the BMC family with NIChecker but replaces sequentialization with in-solver graph
  construction — see [[Tool Capability Matrix]].
- No relation to the dynamic lineage of [[SDRacer (paper)]]; hardware states and virtual
  platforms play no role here.
