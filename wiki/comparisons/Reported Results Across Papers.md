---
type: comparison
tags: [wiki, comparison]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-17
status: solid
---

# Reported Results Across Papers

Every headline number in the wiki, with what it is measured against. **These columns are not
comparable to each other** — see [[Precision Metrics]] for why, and check the ground-truth
assumption in [[Racebench]] / [[Real-World Program Benchmark]] before quoting any of them.

## On Racebench

| Tool | Reported by | Cases | Result | Time |
| --- | --- | --- | --- | --- |
| [[IntRace (tool)]] | own paper | 30 | 5 FP, 90.7% detection rate, −73.2% FP vs [[Rchecker]] | — |
| [[Rchecker]] | via IntRace | 30 | baseline (numbers copied from its own paper) | — |
| [[NIChecker (tool)]] | own paper | 31 | 96.4% precision, all 54 violations, 2 FP | — |
| [[intAtom]] | via NIChecker | 31 | all violations, higher FP rate than NIChecker | copied |
| [[CPA4AV]] | via NIChecker | 14 only | fails on 3 deep-loop cases (T.O./O.O.M.) | — |
| [[BMC4AV (tool)]] | own paper | 25 | 38/38, 0 FP | 6.35 s |
| [[iCBMC]]+ | via BMC4AV | 25 | 58 WN, 20 FP, 67.9% precision | 130.36 s |
| [[intAtom]] | via BMC4AV | 25 | 44 WN, 6 FP, 86.4% precision | copied |
| [[NIChecker (tool)]] | via BMC4AV | 25 | 40 WN, 2 FP | — |

## On the 18-program real-world suite

| Tool | Reported by | Found | FP | FN | Time | Memory |
| --- | --- | --- | --- | --- | --- | --- |
| [[NIChecker (tool)]] | own paper | 47 | 0 | not reported | 158.71 s (34.12 s CBMC) | 4270.82 MB |
| [[NIChecker (tool)]] | via [[BMC4AV (paper)]] | 37 of 94 | 0 | **57** | 262.39 s | 1493.08 MB |
| [[BMC4AV (tool)]] | own paper | 94 of 94 | 0 | 0 | 21.12 s | 567.21 MB |
| [[iCBMC]]+ | via BMC4AV | 94 of 94 | 72 | 0 | 744.55 s | 2528.98 MB |
| [[CPA4AV]] | via BMC4AV | 36 | 3 | 10 + failures | T.O./O.O.M. on several | — |

## Other suites (not comparable to the above)

| Tool | Suite | Result |
| --- | --- | --- |
| [[SDRacer (tool)]] | 11 embedded subjects | 190 races; SE removes 40.3% of warnings, dynamic validation a further 36.7%; repair overhead <0.09 on 9/11 |
| [[IntRace (tool)]] | 9 industrial programs | 118 races, 9 FP, <90 s each; stage attrition 54.2% then 86.2% |

## Ablations (single team, single machine — the most trustworthy numbers here)

| Variant | Effect |
| --- | --- |
| BMC4AV-NRF (no RF-guidance) | 63 false negatives; 258 key RF-edges vs 94 |
| BMC4AV-ARF (all RF-edges) | no FN, but 368.17 s vs 21.12 s |
| BMC4AV-NG (no [[Memory Access Graph]]) | same precision, 45.97 s and 739.74 MB vs 21.12 s and 567.21 MB |
| NIChecker + slicing + PPR | up to 42.2% verification speed-up |
| IntRace stage 2 → stage 3 | 54.2% then 86.2% of candidates eliminated; 69.7% of runtime in stage 3 |

## Hardware, for the runtime columns

- [[IntRace (paper)]]: Xeon E5-2630, 32 GB, Ubuntu 16.
- [[BMC4AV (paper)]]: Xeon E5-2620, 32 GB, Ubuntu 20.04 — same as intAtom's, weaker than
  NIChecker's, which the paper offers as a fairness argument.
- [[NIChecker (paper)]]: Xeon Silver 4215 (8 cores), **128 GB**, Ubuntu 20 — markedly stronger than the machines used by IntRace and BMC4AV, which is why BMC4AV frames its own weaker hardware as a fairness argument.
- Numbers marked "copied" were taken from another paper and re-run by nobody.
