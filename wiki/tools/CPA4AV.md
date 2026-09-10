---
type: tool
tags: [wiki, tool, baseline]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-18
status: stub
---

# CPA4AV

Model-checking-based [[Atomicity Violation]] detector using flow-sensitive analysis with
abstract reachability trees. Full reference, via [[BMC4AV (paper)]]'s bibliography: B. Yu,
C. Tian, H. Xing, Z. Yang, "Detecting atomicity violations in interrupt-driven programs via
interruption points selecting and delayed ISR-triggering", ESEC/FSE 2023.

**Bin Yu and Cong Tian are also authors of [[BMC4AV (paper)]]** — so BMC4AV's harshest
baseline criticism ("struggles with complex data types") is aimed at its own team's earlier
tool. That makes the criticism more credible, not less, but it should be stated when the
comparison is quoted.

- **Criticized by** [[BMC4AV (paper)]] for struggling with complex data types.
- **Coverage problem**: supports only 14 of 31 [[Racebench]] cases, so
  [[NIChecker (paper)]] could compare on that subset only.
- **Scalability problem**: times out or runs out of memory on the three cases requiring an
  unwind bound of 10,000 — the concrete evidence for why [[Loop Abstraction]] matters.
- In BMC4AV's real-world results it fails outright (T.O. / O.O.M.) on several programs and
  reaches only 36 true positives with 3 false positives where it completes.

Status: **stub** — no primary source ingested.
