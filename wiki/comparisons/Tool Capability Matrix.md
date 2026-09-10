---
type: comparison
tags: [wiki, comparison]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-20
status: solid
---

# Tool Capability Matrix

The four tools with primary sources in this wiki, side by side. Everything here is
attributable to the tool's own paper; nothing is normalized across papers.

| | [[SDRacer (tool)]] | [[IntRace (tool)]] | [[NIChecker (tool)]] | [[BMC4AV (tool)]] |
| --- | --- | --- | --- | --- |
| Year / venue | 2020, IEEE TSE | 2024, J. Supercomputing | 2024/25, ACM TOSEM | 2026, SSRN preprint |
| Defect class | [[Data Race]] | [[Data Race]] | [[Atomicity Violation]] | [[Atomicity Violation]] |
| Method | static + [[Symbolic Execution]] + dynamic replay | static + SMT [[Path Feasibility Analysis]] | [[Lazy Sequentialization]] + [[Bounded Model Checking]] | BMC + [[Memory Access Graph]] |
| Backend | KLEE/STP + Simics | Clang/LLVM + Z3 | [[Lazy-CSeq]] + [[CBMC]] | [[CBMC]] + MiniSat |
| Executes the program? | **yes** (virtual platform) | no | no | no |
| [[Interrupt Nesting]] | excludes reentrant interrupts | inside-out sequential conversion | native (invocation conditions) | via priority-aware partial orders |
| [[Interrupt Masking and Synchronization]] | observed on real hardware state | APIs + **user config file** | encoded in invocation conditions | encoded in ordering constraints |
| Loop handling | bounded by simulation run | user-specified depth | [[Loop Abstraction]] | same LA strategy as NIChecker |
| Automation | automatic | needs config file for ad-hoc masking | **needs variable + pattern per run** | claimed fully automatic |
| Repairs defects? | **yes** | no | no | no |
| Formal correctness argument | no | no | **bounded correctness proved** | no |
| Open source / obtainable | no | no | source **withheld** (patents pending); benchmarks + results Apache-2.0 | **yes — full source, obtained** |

## Reading of the matrix

- The corpus splits cleanly in two: an **execution-grounded lineage** (SDRacer) and a
  **verification lineage** (NIChecker → BMC4AV), with IntRace in between — static like the
  verifiers, but solving only local path constraints like a race detector.
- **Nothing repairs except SDRacer**, the oldest tool. Repair disappeared from the line of
  work as it moved toward verification. That is a visible gap and a plausible thesis angle.
- The three later tools each attack the previous one's *usability* as much as its precision:
  IntRace vs Rchecker's scalability, NIChecker vs static analysis's triage burden, BMC4AV vs
  NIChecker's manual variable/pattern input.
- **No tool in this wiki handles both defect classes.** Nothing here detects data races and
  atomicity violations in one pass — the gap [[Thesis Goal]] aims at.
- **Only BMC4AV is obtainable as a tool**, and as of 2026-08-20 it is in hand as full source
  — a [[CBMC]] fork, not a binary drop. Both *benchmarks* are also local. Tabulated in
  [[Reimplementation Assessment]].

See [[Reported Results Across Papers]] for numbers and [[Contradictions]] for where they
conflict.
