---
type: tool
tags: [wiki, tool]
sources: ["[[BMC4AV (paper)]]"]
updated: 2026-08-20
status: solid
---

# BMC4AV (tool)

Bounded model checker for [[Atomicity Violation]]s guided by a partial-order
[[Memory Access Graph]]. Paper: [[BMC4AV (paper)]] (preprint).

- **Family**: [[Bounded Model Checking]], but with order relations maintained as a graph
  inside the solver rather than emitted as constraints.
- **Built on**: [[CBMC]] as front-end, MiniSat as back-end
  ([[Supporting Infrastructure]]).
- **Pipeline**: symbolic encoding of memory events → identify *potential* violations and
  extract key RF partial orders → extend a MAG under RF-guidance until stable and acyclic →
  *confirm* real violations.
- **User burden**: none reported for variable/pattern selection — full automation is the
  claimed advantage over [[NIChecker (tool)]].
- **Pattern set**: `(R,W,R)`, `(W,W,R)`, `(W,R,W)`; `(R,W,W)` treated as benign.
- **Availability**: **obtained** — the Figshare artifact is local at `../BMC4AV`. Full
  source, not a binary drop: a fork of [[CBMC]] under `BMC4AV-Ourtool/src/` with a bundled
  `minisat-2.2.1`, prebuilt `bmc4av` and `bmc4av-ng` executables in `src/cbmc/`, both
  benchmarks, and the scripts that regenerate every table in the paper.

**Reported results**: 38/38 violations with 0 FP on its 25-case [[Racebench]] subset in
6.35 s; 94/94 with 0 FP on the 18-program [[Real-World Program Benchmark]] in 21.12 s and
567.21 MB — framed as 92.0% less time and 62.0% less exploration space than NIChecker, plus
57 false negatives uncovered in it.

**The ablation is the part to trust**: BMC4AV-NRF (no RF-guidance) misses 63 violations;
BMC4AV-ARF (all RF-edges) costs 368.17 s; BMC4AV-NG (no graph) costs 45.97 s and 739.74 MB.
Single team, single machine, no copied numbers.

**Status caveat**: SSRN preprint, not peer reviewed, and its headline comparison rests on its
own manual re-count of another team's benchmark ([[Contradictions]]).

## Running it

```
./bmc4av <source.c> --function <entry> [--rf-guidance] [--redu]
```

`--rf-guidance` selects BMC4AV proper; without it the tool is the BMC4AV-NRF ablation. `--redu`
explores all RF assignments (BMC4AV-ARF). `bmc4av-ng` is the no-graph variant and accepts
neither flag. Build dependencies are `g++ gcc flex bison make cmake` on Ubuntu 20.04; the
executables ship prebuilt. Batch scripts `run_racebench.sh`, `run_realworld.sh`,
`run_rf_guidance.sh`, `run_nrf.sh`, `run_arf.sh`, `run_ng.sh` and `run_compare_ng.sh` sit in
`BMC4AV-Ourtool/` — note the README refers to two of them as `run_neg.sh` and
`run_compare_neg.sh`, which do not exist under those names.

Being fully automatic from a source file and an entry function makes it usable as a
**third-party fix validator** for atomicity violations, which is stronger evidence than
self-validation by the analysis that found the defect ([[Pipeline Design]]). Its blind spot is
`(R,W,W)`, so violations of that shape need [[CBMC]] with a hand-written assertion instead.

## What the artifact shows that the paper does not

- Its results files reproduce **38** and **94** exactly, broken down by pattern — the
  breakdown is not in the paper. On Racebench: `RWR = 25`, `WWR = 7`, `WRW = 6`. On the
  real-world suite: `RWR = 18`, `WWR = 75`, `WRW = 1`, so **80% of its real-world findings are
  a single pattern**.
- The Racebench figures match the benchmark's own annotations pattern-for-pattern once
  `(R,W,W)` is removed ([[Racebench]]), which anchors a number the wiki had treated as
  unexplained.
- It ships NIChecker's `violation.info` ground-truth files **unchanged**, and those count
  violations per *variable* while its own tables count per *instance* — the likely source of
  the 94-vs-37 dispute ([[Contradictions]] #1).
- Three different titles are attached to the same work: the SSRN title, the README's
  *"Bounded Model Checking for Atomicity Violations … via a Guided Memory Access Graph"*, and
  `REQUIREMENTS.md`'s *"Atomicity Violations Detection for Interrupt-driven Programs via
  Partial Order-Guided **Event Graph**"*. The scripts and result folders use "event graph" and
  "memory access graph" interchangeably. Consistent with a paper under revision across venues,
  and a reason to re-check its publication status ([[Open Questions]]).
