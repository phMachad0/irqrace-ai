---
type: source
tags: [wiki, source]
sources: ["[[IntRace (paper)]]"]
updated: 2026-08-17
status: solid
---
	
# Efficient data race detection for interrupt-driven programs via path feasibility analysis

**The Journal of Supercomputing · 2024-06-13 · Jingwen Zhao, Yanxia Wu, Jibin Dong · clipping: [[IntRace]] · PDF: `raw/IntRace.pdf` · [source](https://link.springer.com/article/10.1007/s11227-024-06189-4)**

Purely static + constraint solving. Introduces the tool [[IntRace (tool)]]. The only source
in this wiki that targets [[Data Race]]s with static analysis alone and scales the claim to
thousands of lines of industrial code.

## Problem

Static detectors for interrupt races are cheap and complete but drown the user in false
positives. The paper's diagnosis: prior work ignores **implicit dependencies** between tasks
and ISRs, lacks program semantics, and handles [[Interrupt Nesting]] poorly. Rchecker
([[Rchecker]]) handles synchronization with an interrupt mask list but does not scale;
Chopra's disjoint blocks assume a standard synchronization discipline that embedded code
routinely violates with ad-hoc, self-organizing mechanisms.

## Approach

Three stages, each strictly more precise and more expensive than the last:

1. **Interleaving pattern matching** — Clang AST plus an LLVM pass build the CFG;
   inter-procedural alias analysis populates a shared-resource pool (globals and
   pointer-typed parameters). Guard conditions and interrupt state are deliberately ignored
   so nothing is missed, and candidate pairs are matched against the
   [[Access Interleaving Patterns]] (at least one write, different priorities).
2. **Potential concurrency relationship analysis** — each task/ISR becomes a block
   `(T, I, S, p)`: name, interrupt status, timing/period, priority. Pairs whose blocks
   cannot overlap — masked interrupts, incompatible timing, priority ordering — are
   discarded. Interrupt nesting is handled by an inside-out sequential conversion. Implicit,
   non-standard enable/disable APIs are supplied by the user in a **configuration file**.
3. **Access-pair feasibility checking** — build a symbolic summary of each ISR, splice the
   high-priority block into the low-priority block at the preemption point, and discharge
   the resulting path constraints with Z3. See [[Path Feasibility Analysis]].

## Evaluation

Two datasets. Intel Xeon E5-2630, 32 GB, Ubuntu.

- **[[Racebench]]**: 30 of 31 cases (one excluded because Rchecker errored on it).
  IntRace reports **5 false positives, a 90.7% detection rate, and a 73.2% reduction in
  false positives versus [[Rchecker]]** — whose numbers were taken from its published paper,
  not re-run, because the implementation is unavailable. 36 of the found races are judged
  *harmful* by the Bai et al. criterion (shared variable feeds a branch condition, or an
  array/pointer access).
- **9 real industrial programs** ([[Real-World Program Benchmark]] — device drivers
  `mv643xx_eth.c`, `short`, `shortprint`, three programs from the China Academy of Space
  Technology, three from Sung's suite): **118 races detected, 9 false positives**, no false
  negatives found by manual inspection. 11 harmful races in the three space-agency programs
  were confirmed against an independent validation report.
- **Stage-by-stage attrition** (RQ2): ~208 candidate races per project after stage 1;
  concurrency analysis removes **54.2%** overall (33–63% per project, ~95 left);
  feasibility checking removes a further **86.2%** (41–93%).
- **Cost** (RQ3): matching 8.87% of time, concurrency analysis 21.43%, feasibility
  checking **69.70%**. Under 90 s per real program.

## Claims to trust and claims to check

- Trust: the stage-attrition percentages and the timing split — internally measured and the
  most transferable result in the paper, since they say *where* precision comes from.
- Check: the 73.2% headline compares against numbers copied from Rchecker's paper on
  different hardware, with the tool itself unobtainable. The authors say so explicitly.
- Check: "no false negatives" is again manual inspection over a suite the authors
  themselves selected ([[Precision Metrics]]).

## Limitations and threats to validity

The two acknowledged false-positive causes are honest and worth carrying into the thesis:
(1) implicit interrupt operations that go through hardware state are only partly covered —
the rest require a **user-written configuration file**, which is a real usability cost and a
soundness hole; (2) benign races, deliberately left unsynchronized for real-time reasons,
are not distinguished. Loop depth must be specified by the user, with no equivalent of the
[[Loop Abstraction]] that [[NIChecker (paper)]] introduces.

## Relation to other sources

- Same staged-filtering philosophy as [[SDRacer (paper)]], with Z3 constraint solving
  standing in for dynamic replay on a virtual platform — cheaper, but no ground truth from
  an actual execution.
- Targets **data races**, while [[NIChecker (paper)]] and [[BMC4AV (paper)]] target
  **atomicity violations** on the same Racebench suite. Comparing across that line is a trap;
  see [[Contradictions]].
- Cites SDRacer as related work and notes its false-negative exposure from simulation.
