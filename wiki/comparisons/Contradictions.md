---
type: comparison
tags: [wiki, comparison]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[Racebench (documentation)]]"]
updated: 2026-10-29
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
and their `violation.info` ground-truth files are identical in 17 of 18 programs, so there is
one ground-truth document that both teams shipped. *Corrected 2026-10-29:* this page said
"byte-identical". `i8xx_tco_1` differs: BMC4AV's copy appends an unexplained `no` to
`tco_expect_close wwr`. The programs and their priorities differ much more (#9). It contains **45 `true violation` entries, one per shared
variable**. BMC4AV's results file counts **per access-triple instance**. The two agree closely
on the small programs and diverge monotonically with program size — `wdt_pci_3` is 4 entries
against 29 reported instances — which is what a per-variable versus per-instance mismatch
looks like and is not what a 57-defect recall failure looks like.

The full per-program table is in [[Real-World Program Benchmark]]. This does not make BMC4AV
*wrong*: counting instances is defensible, and its tool genuinely reports more findings. It
does mean the headline "NIChecker misses 57 of 94" divides a per-instance numerator by a
per-variable denominator, and should not be quoted without that caveat.

**The 47 is now accounted for, 2026-09-26: the artifact is corrupt, and NIChecker's published
figure is right.** Recounted from the repository.

`violation.info` is not a standalone list. Each program also ships `mode.txt`, the **nomination
list** — the (variable, pattern) pairs the tool was told to check — and `violation.info` records
one verdict per nomination. The arithmetic confirms the relationship exactly: across the 18
programs `mode.txt` holds **59** lines, and `violation.info` holds **45 `true violation` + 14
`false violation` = 59**. So the ground truth is a verdict table, and the 14 `false violation`
entries are planted false positives, making this suite a triage benchmark in the same way
[[Racebench]] is.

**`logger2/violation.info` is a stray file from a different program.** It names
`test_global_var1/2/3`, which occur **zero** times in `logger2/main.c` — those names belong to
the twelve anonymised programs (`brake*`, `i2c_pca_isa*`, `i8xx_tco*`, `wdt_pci*`), never to
`logger*` or `blink*`, which use real identifiers. It is also the only file in the suite
carrying no `true`/`false` prefix, and logger2 is the only program whose `mode.txt` count and
`violation.info` count disagree in that way.

So **logger2's two nominations have no recorded verdict**. They are `int numberOfRecords rww`
and `int tickCounter wwr`, both variables present in its code (13 and 11 occurrences), and
`logger3` — the sibling variant, 188 lines against 183, differing in 39 — nominates *the same
two pairs* and records **both as `true violation`**.

That gives **45 recorded + 2 lost = 47**, which is exactly NIChecker's published count. The
last step is an inference rather than a proof: logger2's verdicts are gone and cannot be read
back, only reconstructed from its sibling. But it explains the discrepancy the entry above left
open, and it does so without anyone having miscounted — the paper reported what its ground
truth said before a file was overwritten.

**What remains open**: BMC4AV's 94 is still a per-instance count against a per-variable
denominator, so the "misses 57 of 94" headline keeps its caveat. And the ground truth **mixes
units inside itself**: `blink1`–`blink3` write triples with line numbers
(`timerCount(95W,121W,96R)`, 12 entries in all) while the other fifteen programs write only
variable and pattern (50 entries). Fixing a unit — this wiki suggests per-triple-instance —
therefore requires re-deriving line numbers for fifteen programs, not three.

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

## 7. A planted trap is reachable under the suite's own arrival model

> **Resolved 2026-10-28 by relabelling the suite** — the traps below are bug points in
> the suite's source since then — `../racebench/2.1_remarks` at the time, the vendored
> `project-src/bench/racebench` from 2026-10-29 ([[Racebench#Relabel 2026-10-28]]). Kept as the record of why.

Found 2026-10-22 while implementing stage 2 (`project-src/docs/masking-semantics.md`,
"Correction"; [[Soundness Assumptions]] F8, I4). Not a disagreement between papers, but between
two parts of one primary artifact.

- **[[Racebench]]'s annotations** label `svp_simple_001_001_global_var <W#43><R#63><W#44>` a
  planted false positive. The intended reasoning: `main` masks irq 2 at line 28, and `isr_1`
  unmasks it only at line 46, after both writes, so `isr_2` cannot read in between.
- **Racebench's README** says an interrupt may preempt the main program or a lower-level
  interrupt whenever it is enabled, "at an indeterminate moment, position, and number of
  times". Under that model `isr_1` may start with irq 2 unmasked in two independent ways: by
  firing between `init()` (which calls `enable_isr(-1)`) and `main`'s `disable_isr(2)`; or by
  firing a second time after its own `enable_isr(2)` — a global unlock — has persisted. Either
  way `isr_2` may preempt between lines 43 and 44.

This project's stage 2 follows the README and **keeps** the candidate, so a sound tool's
trap-rejection ceiling on the suite is below 38/38.

**A second instance**, found by stage 3 on 2026-10-22: `svp_simple_020_001_global_var
<R#37><W#44><R#40>` is labelled a false positive because the guards at lines 36 and 39
(`sum > para`, `sum < para`) look exclusive. But `isr_1` — whose write at line 44 is the B —
sets the flag and unmasks irq 2, and `isr_2` then sets `para = 11` before line 39 is evaluated.
With `para = 0` and `sum = 2` the two reads both execute. Hand-checked as a concrete
interleaving, not inferred from a SAT verdict. The label is not corrected
([[Soundness Assumptions]] I4), for the reason the errata gives for `svp_simple_019_001`.

**Why the published tools agree with the label — partly verified.** [[BMC4AV (paper)]] reports
0 false positives on the suite ([[Reported Results Across Papers]]). The local source
(`../BMC4AV/BMC4AV-Ourtool/src/goto-instrument/interrupt.cpp`, ll. 89–120) is CBMC's `--isr`
instrumentation, which inserts a nondeterministic ISR call only before instructions whose
read/write set conflicts with the ISR's. Between `init()` and `disable_isr(2)` there is no
such instruction, so in that model `isr_1` cannot fire there — the first route does not exist.
That is a partial-order reduction which treats mask operations as invisible, and they are not:
moving a preemption past `disable_isr(2)` changes what the ISR sees. Whether the second route
(two activations of `isr_1`) is excluded by bounding activations or by how masking is encoded
was not established; `disable_isr` and `enable_isr` appear in BMC4AV's `ignore_fun` sets
(`goto-symex/memory_model.h` l. 70, `interrupt_atomic_violation_check.cpp` l. 106) as
non-events, and where they *are* modelled was not found in a first pass. Open in
[[Open Questions]].


## 8. Three more Racebench trap labels the suite's own semantics contradict

> **Resolved 2026-10-28 by relabelling the suite** — the traps below are bug points in
> the suite's source since then — `../racebench/2.1_remarks` at the time, the vendored
> `project-src/bench/racebench` from 2026-10-29 ([[Racebench#Relabel 2026-10-28]]). Kept as the record of why.

Found 2026-10-28 reviewing the full 31-case run ([[Racebench Full Run 2026-10-28]]), all in
`svp_simple_019_001`, whose annotations are line-shifted (errata) and exist in two copies of the
source, `2.1` and the annotated `2.1_remarks`:

- **Trap #2 `<R#45>,<W#71>,<R#51>`** (errata lines) is a valid trap in `2.1`, where the read sits
  inside `disable_isr(1) … enable_isr(1)` and an ISR firing earlier clears `condition3`, killing the
  read's guard. In `2.1_remarks` the `enable_isr(1)` moved inside the `if`, before the read, so the
  ISR can fire after the guard has passed. The label was not updated with the code.
- **Traps #3 `<R#51>,<W#71>,<R#59>` and #4 `<R#48>,<W#69>,<R#56>`** are reachable in **both**
  copies: the two main-task reads need `condition3` to change between them, which only `isr_1`
  can do, in the unmasked gap between one critical section's `enable_isr(1)` and the next
  `disable_isr(1)` — and it writes `var1` while doing so. The labels follow "each access in its
  own critical section is protected", which [[Atomicity Violation]] and the project's domain rules
  reject: protecting both endpoints is not protecting the interval.

Together with #7 that is five of the 38 traps reachable under the README. The model calls all five
feasible; the scored false-positive count includes them.

## 9. The two copies of the real-world programs are different programs

Found 2026-10-29 while vendoring the suite ([[Real-World Program Benchmark]]). The 18 programs
ship twice: in the NIChecker repository (`NIChecker_Experiments/benchmark2_atomicity_violations`)
and in the BMC4AV artifact (`Real-world-Programs/`). The earlier pages here treated them as one
suite because the ground-truth files agree (#1). They are not one suite:

- **`main.c` differs in all 18.** NIChecker's `main` masks around its initialisation
  (`disable_isr(-1)` … `enable_isr(-1)`). BMC4AV's replaces that with a CBMC thread harness
  (`__CPROVER_ASYNC_1: Timer_A_isr();`) and carries its own tool's results in comments.
- **`priority.info` disagrees in five programs**, under the same stated convention (larger =
  higher). In `wdt_pci_1` NIChecker has writers at 2 and closers at 4, and BMC4AV has writers at
  4 and closers at 2: the opposite preemption relation. The others are `logger2`, `logger3`,
  `i8xx_tco_1` (`closer2` 4 against 2) and `wdt_pci_2`.
- **Six NIChecker programs do not compile as shipped** under clang 14. BMC4AV's
  copy compiles in 17 of 18 because it was edited (lines deleted, a typo fixed).

**Consequence.** Any per-program comparison between [[NIChecker (paper)]] and [[BMC4AV (paper)]]
on this suite, including the 37/47-against-94 dispute (#1), may compare runs on different
programs with different interrupt models. Neither paper says which copy its numbers come from.
Since the priority relation decides which interleavings exist, this matters most for
`wdt_pci_1` and `wdt_pci_2`. Those are also where BMC4AV's count diverges most from the shipped
ground truth.

**And NIChecker's priorities contradict NIChecker's ground truth** (first full run, 2026-10-29).
With NIChecker's `priority.info`, five ground-truth violations in `logger3`, `wdt_pci_1` and
`wdt_pci_2` are dropped by stage 2 with a correct proof. Each needs a lower-priority flow to
preempt a higher one, under the convention [[NIChecker (paper)]] itself states (`p0 < p1 ≤ … ≤
pn`). In `wdt_pci_1`, `writer1` (p2) would have to preempt `closer1` (p4) between lines 989 and
990. Mirroring NIChecker's priorities for all 18 programs drops the gate to 18/45, so the file
convention is not inverted wholesale. BMC4AV's priorities make all five disputed programs
consistent with the ground truth (9/9). With them adopted as errata for those three programs
(the human's decision, 2026-10-30), the official run is 45/45. The simplest reading is
that BMC4AV silently corrected five wrong `priority.info` files. If so, the 37/47-against-94
comparison (#1) also runs the two tools on differently corrected inputs. The diary has the details
([[Semana 9 — O Benchmark de Programas Reais]] §3.8).

**This project's position.** It analyses NIChecker's copy, vendored at
`project-src/bench/realworld`. It adopts BMC4AV's priorities as errata for the three programs where
NIChecker's contradict NIChecker's own ground truth. For the other two disputed programs it runs
BMC4AV's as a second configuration, because nothing there decides between them
(`bench/realworld-errata.yaml`). One more inconsistency of the same kind: the ground truth needs
equal-priority ISRs to preempt each other (`i8xx_tco_1`, `closer1`/`closer2` at 4). The NIChecker
paper's semantics forbid that.
