---
type: benchmark
tags: [wiki, benchmark]
sources: ["[[Racebench (documentation)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-08-31
status: solid
---

# Racebench

The academic benchmark everyone in this literature evaluates on: interrupt-driven C programs
modelled on real aerospace embedded software, at `github.com/chenruibuaa/racebench`. Built
for the [[NASAC 2019 Prototype Competition]], not as a research artifact — which explains its
traps, its scoring and its confidential cases.

Since ingesting [[Racebench (documentation)]] the benchmark's own ground truth is known, so
the papers' counts can finally be checked against it rather than only against each other.
**The repository is now local** (`../racebench`), so the annotations below were parsed
directly rather than taken from the DeepWiki export — which changes two of the numbers.

## Composition (version 2.1)

| | Cases | Bug points | FP traps |
| --- | --- | --- | --- |
| Simple (`svp_simple_001_001` … `svp_simple_031_001`) | 31 | **48** *(measured)* | **38** *(measured)* |
| Complex (`svp_real_001`, `svp_real_002`) | 2 | 3 | 5 |

Counted on 2026-08-20 by parsing every `//bug点` and `//误报点` entry in
`racebench/2.1_remarks`, with a tolerant parser (see below) and two repaired typos. The
[[Racebench (documentation)]] export gives **50** and **33** for the simple cases; neither
matches. Since the export is AI-generated and partly inferential while these figures come from
the annotations themselves, prefer 48/38 — but note that this is now a *third* set of numbers
in circulation, and the discrepancy has not been reconciled with the repository's own README.

Versions: **2.0** (11 Nov 2019, the 31 simple cases, for tool debugging), **2.1** (20 Nov
2019, adds the two complex cases, used for final evaluation), **2.1_remarks** (same content
with explicit inline ground-truth markers). Programs are short — roughly 37–97 LoC in the
subset [[BMC4AV (paper)]] tabulates — with a main task and 1–3 ISRs at up to three priority
levels. Some cases require unwinding a loop **10,000 times** before the defect appears, which
is what breaks bounded tools lacking [[Loop Abstraction]].

The two complex cases are aerospace-derived and were kept secret until the on-site finals:
`svp_real_001` (ISRs `CAN_ISR`, `TIMER_ISR`; 2 bugs, 3 traps), `svp_real_002` (ISRs
`interrupt_low_0`, `interrupt_low_1`, `interrupt_high` — **two ISRs sharing priority 1**;
1 bug, 2 traps). Equal-priority ISRs are a case none of the four tools' formal models in this
wiki discuss explicitly.

## Conventions

- Entry point `*_main`; handlers `*isr_[N]`, where **higher N = higher priority**. The
  repository README states this outright — *"优先级数字越大，优先级越高"*, larger priority
  number means higher priority — which settles [[Contradictions]] #3 from the primary source.
- Shared state is `volatile int` / `volatile int*` at global scope; `common.h` supplies
  `init()`, `idlerun()`, `rand()`.
- `disable_isr(n)` / `enable_isr(n)` behave as lock/unlock for interrupt `n`; **`n = -1`
  affects all interrupts**. Some cases use them *correctly*, and reporting a race inside
  those protected regions is one of the planted false positives
  ([[Interrupt Masking and Synchronization]]).
- Interrupts are **non-periodic**: an ISR may preempt the main task or any lower-priority ISR
  at any point where interrupts are enabled.
- The priority direction here matches [[BMC4AV (paper)]] and is **inverted relative to** the
  formalism in [[SDRacer (paper)]] and [[IntRace (paper)]] ([[Asymmetric Preemption]]).

## Ground truth is annotated as access triples

The `2.1_remarks` variant marks each defect inline, as a variable name followed by **three**
accesses with line numbers, the middle one from an ISR:

```
//bug点:
//1.svp_simple_019_001_global_var1<R#45>,<W#65>,<R#54>
```

Measured shape distribution over the 48 bug points and 38 traps of the 31 simple cases:

| Shape | Bug points | FP traps |
| --- | --- | --- |
| `(R,W,R)` | 25 | 19 |
| `(R,W,W)` | 10 | 6 |
| `(W,W,R)` | 7 | 5 |
| `(W,R,W)` | 6 | 8 |

Every bug point is a triple in the four-pattern set, and **all 48 project onto access pairs
containing at least one write** — the empirical half of the argument in
[[Pair-Triple Unification]].

### The annotations are not machine-readable without a tolerant parser

This is a practical warning for anyone measuring recall automatically against this suite. The
31 simple cases use **at least four incompatible access grammars**:

| Grammar | Example | Where |
| --- | --- | --- |
| type-then-line, no spaces | `var<R#45>,<W#65>,<R#54>` | most of 001–020 |
| accesses juxtaposed, no commas | `var<W#43><R#63><W#44>` | `svp_simple_001` |
| comma inside the brackets | `var <R,#44>, <W,#79>, <W,#45>` | 021, 025, 029 |
| **line-then-type, reversed fields** | `var <#46,R> <#90,W>,<#83,R>` | `svp_simple_031` |

Section headers vary too — `//bug点:`, `// bug点：` (full-width colon), `//误报点:`,
`// 误报点：`, `// 可能误报` ("possible false positive"), and `svp_simple_022_001` has a bug
list with **no header at all**, just `// 1:` numbering. There are also outright errors:

- `svp_simple_004_001` has a doubled bracket, `<<R#52>`;
- `svp_simple_016_001` bug point 2 is missing a closing bracket, `<W#33,`;
- `svp_simple_016_001` bug point 1 is written `<W#24>,<R#33>,<R#25>`, but line 33 is
  `global_var1 = 0x09;` — a **write**. The annotation's access type is wrong, and taken
  literally it is the only "defect" in the suite that would be invisible to a race detector;
- `svp_simple_027_001` writes its middle access without the `#`, as `<W, 41>`.

A strict parser silently returns 28 bug points instead of 48 — a 42% undercount, with no
error. That is very plausibly a contributing cause of the count disagreements below, and it is
worth stating in any evaluation section.

**This matters more than it looks.** The benchmark's own ground truth is *atomicity-violation
shaped* — three accesses — even though the suite is called "racebench" and the competition
was billed as race detection. It means:

- [[IntRace (paper)]] counting **50 "data races"** is counting exactly these 50 simple bug
  points, and so is reporting triples under a two-access name ([[Data Race]]).
- The `(R,W,W)`-vs-`(W,W,R)` argument between [[NIChecker (paper)]] and [[BMC4AV (paper)]] is
  an argument about which annotated triples count — not about how to read the code.

### Two entry points are named wrongly in the README

Found 2026-08-31 while generating configurations from the case table (see `log.md`). The table
gives the main entry point of cases 28 and 30 as `svp_simple_028_001_main` and
`svp_simple_030_001_main`; both files actually define `svp_simple_028_001__main` and
`svp_simple_030_001__main`, with a **double underscore**. Both are also declared `int` rather
than `void`, and both cases carry a separate `svp_simple_0NN_001_init()` that the other cases do
not have.

This matters more than a typo in a table normally would. A tool that takes its entry points from
the README analyses the main task of those two cases as unreachable: it contributes no accesses,
and every defect involving it disappears with no error anywhere. It is a concrete instance of
the first soundness assumption in [[Pipeline Design]] — a flow whose entry point is not
recognised is invisible, and the loss does not show up in the output.

The same generation pass also measured the constructs the suite actually contains: **exactly one
of the 31 simple cases, `svp_simple_029_001`, dispatches through function pointers**, assigning
three of them in an init routine and calling them from both the task and an ISR. It is therefore
the only subject that can exercise indirect-call handling, and the other 30 cannot test it at
all. (Reaching that number required stripping bitcasts from call sites: `common.h` declares
`init`, `idlerun` and `rand` K&R-style, so after linking every call to them goes through a
`ConstantExpr` bitcast and looks indirect.)

## Reconciling the papers' counts

| Source | Defect class | Cases used | Ground truth assumed | Against the benchmark |
| --- | --- | --- | --- | --- |
| benchmark itself | annotated triples | 31 simple | **48** bug points, 38 traps *(measured)* | — |
| [[Racebench (documentation)]] | — | 31 simple | 50 bug points, 33 traps | +2 / −5 against the annotations |
| [[IntRace (paper)]] | [[Data Race]] | 30 (one dropped: [[Rchecker]] errored on it) | 50 | +2 |
| [[NIChecker (paper)]] | [[Atomicity Violation]] | 31 | 54, "four harmful patterns" | **+6** — still unexplained |
| [[BMC4AV (paper)]] | [[Atomicity Violation]] | 25 (six dropped as `(R,W,W)`-only) | 38 | **exactly reproduces the annotations** — see below |

### BMC4AV's 38 is fully traceable, and reveals an inconsistency

The artifact's own results file reports, over its 25-case subset, `RWR = 25`, `WWR = 7`,
`WRW = 6`. The `2.1_remarks` annotations for those same 25 cases contain **41 bug points**:
25 `(R,W,R)`, 7 `(W,W,R)`, 6 `(W,R,W)` — and 3 `(R,W,W)`. Pattern by pattern the non-`(R,W,W)`
counts match exactly, so BMC4AV's ground truth is the benchmark's own, minus `(R,W,W)`.

But that exposes a gap in its own framing. BMC4AV excludes six cases "because their only
pattern is `(R,W,W)`" — yet `(R,W,W)` bug points also occur in `svp_simple_017`, `_021` and
`_023`, which are **inside** its evaluated subset. Measured against the benchmark's
annotations, BMC4AV's Racebench recall is therefore **38 of 48 (79.2%)**, not 100%: three
annotated bug points are missed inside the subset it reports on, and the rest fall in the
cases it removed. Its precision claim is unaffected; its recall claim is relative to a ground
truth it redefined. See [[Contradictions]] #2.

## False positives are planted, and scored punitively

All 38 traps sit in the simple cases, by the measured count. In the competition a false positive cost **−3**
against **+2** for a detection ([[NASAC 2019 Prototype Competition]]). Two consequences for
reading any Racebench result:

1. A precision figure on this suite measures **trap avoidance on deliberately adversarial
   code**, not precision in the wild. High precision here is a real result, but a narrow one.
2. Every tool in this literature is optimizing against a scoring function that priced recall
   at zero — which is the backdrop to [[BMC4AV (paper)]]'s finding that a "100% precision"
   tool had a 39.4% hit rate ([[Precision Metrics]]).

## Results reported on it

- [[IntRace (tool)]]: 5 FP over 30 cases, 90.7% detection rate, 73.2% fewer FPs than
  [[Rchecker]].
- [[NIChecker (tool)]]: 96.4% precision, all violations found, 2 FP (both pointer/struct).
- [[BMC4AV (tool)]]: 38/38, 0 FP, 6.35 s — versus [[iCBMC]]+ 67.9% precision, [[intAtom]]
  86.4%, [[CPA4AV]] mostly unsupported or timing out.

## The "seven defect patterns"

The repository's README grounds the suite in **seven defect patterns based on variable access
order violations**, derived from research on interrupt data access conflicts in aerospace
software. The enumeration itself is *not* in the repository documentation:
[[Racebench (documentation)]] says so explicitly and then offers a reconstruction of its own,
which this wiki does not treat as authoritative. Recovering the real seven from the primary
source is listed in [[Open Questions]]; the papers in this wiki use their own three- or
four-element pattern sets instead ([[Access Interleaving Patterns]]).
