---
type: benchmark
tags: [wiki, benchmark, context]
sources: ["[[Racebench (documentation)]]"]
updated: 2026-08-18
status: draft
---

# NASAC 2019 Prototype Competition

The event [[Racebench]] was built for: a prototype competition on **concurrent race
detection**, held 20–22 November 2019 in Hangzhou, China, with five competing teams
([[Racebench (documentation)]]). Knowing this explains most of the benchmark's design
decisions, and therefore most of the evaluation practice in this literature.

## Format

| Phase | Date | What happened |
| --- | --- | --- |
| v2.0 release | 11 Nov 2019 | 31 simple cases published for tool debugging |
| v2.1 release | 20 Nov 2019 | complete set; the 2 complex cases stayed confidential until the finals |
| Online submission | by 21 Nov, 17:00 | JSON detection results for the 31 simple cases, emailed for pre-scoring |
| On-site finals | 22 Nov 2019 | tools run live on the 2 complex real-world cases, **180 s timeout each**; 10-minute talk plus 5-minute Q&A |

Scoring was 80% benchmark testing, 20% presentation.

## The scoring rules shaped the field

| Case class | Bug points | Reward | FP traps | Penalty |
| --- | --- | --- | --- | --- |
| 31 simple | 50 | +2 each | 33 | **−3 each** |
| `svp_real_001` | 2 | +12 each | 3 | −8 each |
| `svp_real_002` | 1 | +20 | 2 | −10 each |

**False positives cost 1.5× what a detection earns** on the simple cases, and up to 5× more
than a simple detection on the complex ones. A tool that reports nothing scores zero; a tool
that over-reports scores negative. This is the origin of the whole field's obsession with
precision over recall, and it is worth naming explicitly in a thesis: the community's
evaluation instincts were set by a competition that priced recall cheaply. See
[[Precision Metrics]] and [[Synthesis]].

## Teams

| Team | Tool | Members |
| --- | --- | --- |
| 1 | Static Detection Tool for Atomicity Violations | Xu Yanting, Wang Yu, Wang Linzhang |
| 2 | Interrupt Bug Hunting | Dai Liyun |
| 3 | **Verian** — verification-enhanced interrupt data access conflict analysis | Feng Haining, Yin Liangze, Dong Wei |
| 4 | LLVM-based Variable Access Pattern Search | Tu Haoxin, Zhou Zhide, Jiang He, Ren Zhilei |
| 5 | CAICON | Fan Guangsheng, Liu Jiangchao, Wang Tengbin, Chen Taoqing, Luo Dan |

Team 3's members — Feng, Yin, Dong — are the authors of [[Rchecker]] (QRS-C 2020), so the
CBMC-based race detector that [[IntRace (paper)]] uses as its baseline began life as a
competition entry named Verian. Team 1's brief, static detection of atomicity violations, is
the same problem [[intAtom]] later addressed.

The benchmark's maintainer, R. Chen (BUAA), is also a co-author of [[intAtom]] (ISSTA 2022)
and of [[NIChecker (paper)]] (TOSEM 2025) — worth noting when reading tools' results on his
benchmark, and when reading [[BMC4AV (paper)]]'s critique of those results
([[Contradictions]]).
