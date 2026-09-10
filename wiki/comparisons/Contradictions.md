---
type: comparison
tags: [wiki, comparison]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-08-20
status: solid
---

# Contradictions

Open conflicts between sources. Per the wiki schema these are preserved, not resolved by
preferring the newer paper — but where a **primary artifact** settles one, that is recorded.
As of 2026-08-20 the benchmarks and BMC4AV's source are local, so #3 is resolved, #1 is
largely explained, and #2 and #5 have measured evidence attached.

## 1. How many atomicity violations are in the 18 real-world programs? — 37/47 vs 94

- **[[NIChecker (paper)]]**: detects **47** violations, 0 false positives, 100% hit rate,
  158.71 s.
- **[[BMC4AV (paper)]]**: the suite actually contains **94**; NIChecker finds 37 after
  `(R,W,W)` removal, missing **57** (hit rate 39.4%).

**BMC4AV's reasoning**: the 37 were manually injected by NIChecker's own authors; since
NIChecker only checks user-nominated variables and patterns, naturally occurring violations
were never searched for. Its assertion-insertion strategy is also claimed to misplace
auxiliary code in large programs.

**Status: largely explained as a units mismatch, 2026-08-20.** Both artifacts are now local
and their `violation.info` ground-truth files are byte-identical, so there is one ground-truth
document that both teams shipped. It contains **45 `true violation` entries, one per shared
variable**. BMC4AV's results file counts **per access-triple instance**. The two agree closely
on the small programs and diverge monotonically with program size — `wdt_pci_3` is 4 entries
against 29 reported instances — which is what a per-variable versus per-instance mismatch
looks like and is not what a 57-defect recall failure looks like.

The full per-program table is in [[Real-World Program Benchmark]]. This does not make BMC4AV
*wrong*: counting instances is defensible, and its tool genuinely reports more findings. It
does mean the headline "NIChecker misses 57 of 94" divides a per-instance numerator by a
per-variable denominator, and should not be quoted without that caveat.

**What remains open**: NIChecker's published 47 matches neither the 45 shipped entries nor
BMC4AV's 37, and no paper defines its counting unit explicitly. Settling it completely means
fixing a unit — this wiki suggests per-triple-instance — and re-counting one package by hand
against it. `logger` (3 programs, ~170–210 lines) is the cheapest place to do that, and it is
still an original, defensible contribution.

**A separate, real gap**: six shipped `true violation` entries carry the pattern `rww`, which
BMC4AV excludes by construction and therefore cannot report — including all three violations
in `logger1`. That is a recall gap independent of any counting convention, and it belongs to
conflict #2 rather than to this one.

*Provenance note*: R. Chen, who maintains [[Racebench]], co-authors both [[intAtom]] (ISSTA
2022) and [[NIChecker (paper)]] (TOSEM 2025), while [[BMC4AV (paper)]]'s authors (Yu, Tian and
colleagues at Xidian) are the authors of [[CPA4AV]] — so this is not a neutral outsider
auditing a benchmark, it is one tool lineage re-counting another's. That cuts both ways and is
a reason to verify rather than to pick a side.

## 2. Is `(R,W,W)` a real atomicity violation?

- **[[NIChecker (paper)]]**: Racebench covers **four** harmful access interleaving patterns;
  ground truth 54 violations over 31 cases.
- **[[BMC4AV (paper)]]**: `(R,W,W)` is **benign**; six Racebench cases are excluded, leaving
  25 cases and 38 violations.

**Status: a definitional disagreement, asserted rather than argued** on the BMC4AV side. It
silently rebases every precision figure computed on either benchmark, and it partly drives
conflict 1. See [[Access Interleaving Patterns]].

**New evidence, measured from the repository on 2026-08-20** ([[Racebench]]): the 31 simple
cases carry **48 annotated bug points**, of which **10 are `(R,W,W)`** — 21% of the ground
truth. And BMC4AV's 38 is now fully traceable: over its 25-case subset the annotations hold 25
`(R,W,R)`, 7 `(W,W,R)`, 6 `(W,R,W)` and 3 `(R,W,W)`, and its results file reports exactly
25 / 7 / 6. So its ground truth *is* the benchmark's own, minus one pattern.

That traceability sharpens the disagreement rather than settling it. BMC4AV drops six cases
"because their only pattern is `(R,W,W)`", but `(R,W,W)` bug points also sit in
`svp_simple_017`, `_021` and `_023`, **inside** its evaluated subset. Against the benchmark's
annotations its Racebench recall is **38/48 = 79.2%**, not 100% — and on the real-world suite
six more shipped `true violation` entries are `rww`. The `(R,W,W)`-is-benign decision is
therefore not a bookkeeping choice about which cases to show; it is a load-bearing recall
assumption, still asserted without argument.

For [[Thesis Goal]] the practical consequence is that the pattern must be **included**:
excluding a pattern is a definitional false negative ([[Soundness and False Negatives]] §5),
and under the pair abstraction `(R,W,W)` decomposes into two ordinary races anyway, so
including it costs nothing structurally ([[Pair-Triple Unification]]).

## 3. Priority numbering is inverted between papers — **resolved**

[[SDRacer (paper)]] and [[IntRace (paper)]]: larger number = **lower** priority.
[[BMC4AV (paper)]]: larger number = **higher** priority, `Pri(Main) = 0`.

**Settled from the primary artifact, 2026-08-20.** The `racebench/2.1_remarks` README states
it directly — *"优先级数字越大，优先级越高"*, the larger the priority number, the higher the
priority — and each case header repeats it. The `priority.info` files in the
[[Real-World Program Benchmark]] follow the same direction, with `main:0` as the lowest.

So the benchmark and [[BMC4AV (paper)]] agree, and the two data-race papers' prose is inverted
relative to the suite they evaluate on. Their implementations presumably follow the benchmark;
this wiki still has not verified that, and cannot, since neither tool is obtainable. **Use
larger = higher** ([[Pipeline Design]]); getting it backwards drops exactly the real
preemptions ([[Soundness and False Negatives]] §6).

## 4. "No false negatives" claims rest on incompatible evidence

- [[SDRacer (paper)]] and [[IntRace (paper)]]: **manual inspection** found none.
- [[NIChecker (paper)]] and [[BMC4AV (paper)]]: no counterexample **up to a bound**.

BMC4AV's re-count is a direct demonstration that manual-inspection-based claims can be wrong
by a factor of two. Any thesis statement about recall in this literature should say which
kind of evidence it rests on ([[Precision Metrics]]).

## 5. Is the benchmark measuring races or atomicity violations?

The suite is named *racebench*, the competition was billed as **race detection**, and
[[IntRace (paper)]] evaluates it as a [[Data Race]] benchmark — but its ground-truth
annotations are **three-access triples** ([[Racebench (documentation)]]), which is the shape
of an [[Atomicity Violation]].

Nobody in the corpus addresses this.

**Partly answered, 2026-08-20** ([[Pair-Triple Unification]]). All 48 annotated bug points
project onto access pairs containing at least one write, so on this benchmark the two
literatures are indeed looking at overlapping evidence, and IntRace counting these triples as
"data races" is not a category error. But the defect classes are not identical: an atomicity
violation whose two local accesses sit in *separate* critical sections contains no data race
at all, and a pair-level detector with a sound masking filter reports nothing for it. The
overlap is real; the identification is false. Numbers from the two branches can be compared on
this suite only after fixing a common counting unit — see #1.

## 6. Cross-tool runtime comparisons mix re-runs with copied numbers

Every comparison in the corpus contains at least one baseline whose binary could not be
obtained: Rchecker and intAtom (unavailable to both NIChecker and IntRace), intAtom, Rchecker
and NIChecker (unavailable to BMC4AV). Each paper discloses this; secondary summaries of them
usually do not. Treat all cross-tool time and memory figures as indicative only.
