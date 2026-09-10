---
type: tool
tags: [wiki, tool, baseline]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-17
status: draft
---

# Supporting Infrastructure

The third-party components the four tools stand on. Useful when arguing about which
differences between tools are real contributions and which are inherited.

| Component                                | Role                                                                             | Used by                                                                   |
| ---------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| [[CBMC]]                                 | bounded model checking of C                                                      | [[NIChecker (tool)]], [[BMC4AV (tool)]], [[Rchecker]], [[iCBMC]]          |
| MiniSat                                  | SAT solving backend                                                              | [[BMC4AV (tool)]]                                                         |
| Z3                                       | SMT solving for path constraints                                                 | [[IntRace (tool)]]                                                        |
| Clang / LLVM                             | C front-end, AST and CFG construction, LLVM passes                               | [[IntRace (tool)]] (Clang+LLVM-PASS), [[SDRacer (tool)]] (Clang Tool 3.4) |
| IntAbs (Sung et al.)                     | abstract-interpretation framework for interrupt interleaving semantics           | [[IntRace (tool)]]                                                        |
| [[Lazy-CSeq]] / CSeq                     | lazy sequentialization framework                                                 | [[NIChecker (tool)]]                                                      |
| Simics (virtual platform, simulated x86) | forcing interrupts at arbitrary points via Python APIs, observing hardware state | [[SDRacer (tool)]]                                                        |
| KLEE 1.2 + STP + KLEE-uClibc             | guided symbolic execution for input and interrupt-schedule generation            | [[SDRacer (tool)]]                                                        |

SDRacer's KLEE was **modified**: KLEE-uClibc was extended to support kernel functions such
as `request_irq()`, and constraint gathering was restricted to paths produced by the static
analysis so the search is guided toward candidate racing points ([[SDRacer (paper)]], §3.5).

Two observations for the thesis:

- The **BMC branch is monocultural**: everything descends from CBMC, so its shared
  limitations (bounded reachability, coarse compound-data-type modelling) are systemic rather
  than per-tool.
- Only [[SDRacer (tool)]] needs a **simulatable target platform**, which is simultaneously
  its source of ground truth and the reason it is hardest to apply to arbitrary industrial
  code.
