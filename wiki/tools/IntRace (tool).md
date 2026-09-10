---
type: tool
tags: [wiki, tool]
sources: ["[[IntRace (paper)]]"]
updated: 2026-08-17
status: solid
---

# IntRace (tool)

Static [[Data Race]] detector for interrupt-driven programs, staged for precision. Paper:
[[IntRace (paper)]].

- **Family**: pure static analysis + constraint solving. No execution, no model checker.
- **Built on**: Clang/LLVM front-end, IntAbs (Sung et al.) for interrupt-nesting interleaving
  semantics, Z3 for path constraints — see [[Supporting Infrastructure]].
- **Pipeline**: [[Access Interleaving Patterns]] → potential concurrency relationship
  analysis → [[Path Feasibility Analysis]].
- **Interrupt handling**: standard mask APIs recognized automatically; implicit/ad-hoc ones
  require a **user-supplied configuration file**; [[Interrupt Nesting]] via inside-out
  sequential conversion.
- **User burden**: the config file, plus a cycle-development depth for loops (no
  [[Loop Abstraction]]).
- **Availability**: no public release stated in the paper.

**Reported results**: on [[Racebench]], 5 false positives over 30 cases, 90.7% detection
rate, 73.2% fewer false positives than [[Rchecker]] (whose figures were copied from its own
paper). On 9 real industrial programs, 118 races with 9 false positives, under 90 s each.

**Known weaknesses, self-reported**: missed implicit interrupt operations that work through
hardware state, and benign races counted as findings.

Not used as a baseline by [[NIChecker (paper)]] or [[BMC4AV (paper)]] — they detect
atomicity violations, IntRace detects data races.
