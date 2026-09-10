---
type: tool
tags: [wiki, tool]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-18
status: solid
---

# NIChecker (tool)

"Nested-Interrupt-Checker" — bounded verifier for [[Atomicity Violation]]s and user-defined
assertions in interrupt-driven C. Paper: [[NIChecker (paper)]].

- **Family**: [[Bounded Model Checking]] via [[Lazy Sequentialization]].
- **Built on**: [[Lazy-CSeq]] v2.1 (CSeq framework) with [[CBMC]] v5.6 as backend; modules in
  Python (instrument, [[Loop Abstraction]], atomicity violation) and Java (slicing, PPR).
- **Optimizations**: loop abstraction, slicing, preemption point reduction — up to 42.2%
  verification speed-up.
- **User burden**: the user must nominate the **global variable and the pattern**; one run per
  combination. This is the hinge of the later critique.
- **Formal status**: bounded correctness of the translation is proved.
- **Availability**: benchmark set is public (`github.com/zhvngyuan/NIChecker`); the tool
  itself is described by [[BMC4AV (paper)]] as **not open source**.

## Two accounts of the same tool

| | [[NIChecker (paper)]] (self-reported) | [[BMC4AV (paper)]] (re-evaluated) |
| --- | --- | --- |
| Racebench | 96.4% precision, all 54 violations found (the benchmark annotates 50) | 40 warnings / 2 FP on its 25-case subset |
| Real-world suite | **47 violations, 0 FP, 158.71 s** | **37 found of 94 actual → 39.4% hit rate, 57 FN**, 262.39 s |

Both can be literally true at once — they assume different ground truths and different
benchmark variants (NIChecker's "Benchmark 2$" is itself a variant). The disagreement is
recorded in [[Contradictions]] and is the most thesis-relevant conflict in this wiki.

**Root cause BMC4AV alleges**: NIChecker only examines variables and patterns the user
supplies, and its assertion-insertion strategy cannot guarantee that auxiliary code lands in
the right place in large programs. NIChecker's own limitations section separately concedes
coarse modelling of pointers and structures.
