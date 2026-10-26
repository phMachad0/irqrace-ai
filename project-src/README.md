# irqrace

A static analyzer that finds **atomicity violations in interrupt-driven embedded C
with no false negatives**, emits a rich per-candidate
context record, and hands the residue to an LLM stage that triages, repairs and
re-verifies. Detect → contextualize → triage → repair → re-verify.

The design lives in the wiki one directory up:
[Thesis Goal](../wiki/Thesis%20Goal.md) ·
[Pipeline Design](../wiki/Pipeline%20Design.md) ·
[LLM Stage Design](../wiki/LLM%20Stage%20Design.md) ·
[Dashboard Design](../wiki/Dashboard%20Design.md) ·
[Roadmap](../wiki/Roadmap.md).

**The one rule everything else follows from: a solver may drop a candidate; the
LLM may not.** Recall is the headline metric and it must be 100%; precision is
traded away deliberately.

## Status — 24 Oct 2026 · one candidate class

Since 2026-10-24 the tool generates, filters and reports **atomicity-violation triples only**
([Triples Only](../wiki/Triples%20Only.md)). Contracts C1 and C2 are at `2.0.0`, and the tool at
`0.2.0`. Every triple result — candidate ids, stage-2 decisions and masking states, solver
verdicts, matches against the ground truth — is identical to the run before the change, subject
by subject. The numbers in the sections below are re-measured with the current code.

```
31/31 subjects analysed
stage 1: 316 candidates, 10.2 per subject  [1727 ms total]
stage 2: 202 kept, 114 dropped with proof (masking 7, no-path 62, priority 45)  [1325 ms total]
attrition: 36.1% overall; 0-62% per subject
  of which concurrency (priority + masking): 16.5%; no-path is stage 1's cross-function may-precede refined, not a concurrency result
  for scale: IntRace reports 54.2% (33-63% per project) for its stage 2, on another candidate class, in real-world subjects
solver: 202 in -> 166 sat, 0 inconclusive, 36 unsat (dropped with proof)  [17636 ms total]
reaching the LLM: 166, 5.4 per subject; solver attrition 17.8%
  for scale: IntRace reports 86.2% (41-93%) for its feasibility stage, on another candidate class, in real-world subjects
funnel: 316 -> 202 -> 166  [stage 1 1727 ms, stage 2 1325 ms, solver 17636 ms]
slowest subjects in the solver: svp_simple_019_001 7582 ms, svp_simple_024_001 2358 ms, svp_simple_003_001 1127 ms
RECALL GATE (stage3): 48/48 annotated bug points present -- PASS
traps reported: 35/38 after stage 1, 30/38 after stage 2, 16/38 reaching the LLM (14 refuted by the solver)
inspection ratio: 0.84 mean over 31 subject(s) whose bug points were all found
runstore check: 31/31 runs conform to C3 (rule 6: nothing vanished without a proof)
```

## Status — end of W6–W7 (22 Oct 2026) · stage 3 (Z3)

| W6–W7 item | State |
| --- | --- |
| Symbolic ISR summaries; splice at the preemption point; discharge path constraints | done — `analysis/src/irqrace-stage3.cpp`, symbolic execution over the LLVM IR with Z3 |
| **Reachability only**, the solver's role kept to "prove impossible" | done — the query is "A1, then B inside [A1, A2], then A2, on one memory cell" |
| Timeout and unsupported constructs → **`inconclusive`**, kept and passed on | done — never `sat`, never a drop; pinned by tests |
| **The full funnel measured, with per-stage timings** | 316 → 202 → **166** reaching the LLM — see above |
| **Recall gate still 100%** | **48/48 PASS**, taken on the context records |

```
solver: 202 in -> 166 sat, 0 inconclusive, 36 unsat (dropped with proof)  [17636 ms total]
reaching the LLM: 166, 5.4 per subject; solver attrition 17.8%
RECALL GATE (stage3): 48/48 annotated bug points present -- PASS
traps reported: 35/38 after stage 1, 30/38 after stage 2, 16/38 reaching the LLM (14 refuted by the solver)
```

**The encoding over-approximates every execution, so UNSAT is a proof and SAT is only "not
refuted".** Memory is one byte array per SVF object; loops are one pass with everything they
may write havocked at the header; at every instruction boundary where stage 2 says another
flow may run, everything that flow may write is havocked; the preempting flow runs from its
entry on the memory at the preemption point. A cheap **address projection** — every path to
each access explored on its own, then "can the three addresses coincide?" — refutes index and
dead-code traps before the full search runs.

**17.8% against IntRace's 86.2%** is the honest gap of a thread-modular encoding: a trap whose
infeasibility rests on *the order* in which ISRs run (028's flag that only `isr_1` clears, and
only before it unmasks `isr_2`) looks feasible once every value another flow writes is
havocked. Those reach the LLM marked `sat` with their `unconstrained` list.

**Three bugs in the solver, caught before any number was reported** — by the recall gate and by
auditing every UNSAT against the source: a volatile load counted as a write (every ISR then
"wrote everything"); a preemption just before A2 that made A2 unselectable (an UNSAT on a
reachable trap); a back edge crossed once in total instead of once per phase. Each has a
mutation-tested regression test in `tests/test_stage3.py`.

**One finding.** `svp_simple_020_001`'s trap `<R#37><W#44><R#40>` is reachable under the
suite's README, like 001's — the label assumes `sum > para` and `sum < para` exclusive, but
`isr_2` may change `para` inside the interval; hand-checked with a concrete interleaving.

## Status — end of W5 (22 Oct 2026) · stage 2

| W5 item | State |
| --- | --- |
| Block model `(T, I, S, p)`; priority check with **larger = higher** | done — `config.can_preempt` + nesting (`masking.may_preempt`) |
| Timing left unconstrained | done — every record says `timing: unconstrained` |
| Masking dataflow: masked only if masked on **every** path | done — `src/irqrace/masking.py`, three-valued with origins |
| **Interval property**: masked throughout `[A₁, A₂]` | done — interval = every point on every path A₁→A₂, callees included |
| Equal-priority and arrival-model decisions explicit, in the manifest | done — plus `triple_interval: single-activation` (G2c) |
| **Attrition measured against IntRace's 54.2%** | 36.1% overall, 16.5% from concurrency — see below |
| **Recall gate still 100%** | **48/48 PASS** after stage 2 |

```
stage 1: 316 candidates, 10.2 per subject
stage 2: 202 kept, 114 dropped with proof (masking 7, no-path 62, priority 45)
attrition: 36.1% overall; 0-62% per subject
  of which concurrency (priority + masking): 16.5%
RECALL GATE (stage2): 48/48 annotated bug points present -- PASS
traps reported: 35/38 after stage 1, 30/38 after stage 2 (5 rejected by stage 2)
runstore check: 31/31 runs conform to C3 (rule 6)
```

**Every drop is a proof.** Each one writes a line to `stage2/dropped.jsonl` with its reason, the
argument in prose with the source lines, and the Soundness Assumptions it relies on;
`irqrace runstore check` fails a run where a stage-1 candidate vanished without one.

**Against IntRace's 54.2%:** not comparable, and the gap is expected. IntRace's figure is on
another candidate class in real-world subjects, which mask far more than Racebench does; 19 of
the 31 cases here have no masking call at all, so a candidate there can only fall to priority or
to no-path. `no-path` (62) is not a concurrency result: it is stage
1's over-approximate cross-function may-precede, refined on the flow's supergraph.

**The masking analysis is whole-program, because the mask is shared hardware.** An ISR that
preempts an interval and unmasks an interrupt breaks the local flow's proof; an ISR starts in
the union of every state it may preempt; a nested activation is judged from the state it
fired in. Each rule has a synthetic test in `tests/test_masking.py`.

**One finding, recorded rather than fixed** (`docs/masking-semantics.md`, "Correction").
`svp_simple_001_001`'s first trap, `<W#43><R#63><W#44>`, is reachable under the suite's own
README: `isr_1` may start with irq 2 unmasked, before main's `disable_isr(2)` or after an
earlier activation of itself. Stage 2 keeps it. The W1 fixtures had asserted it was provably
infeasible; they now carry what stage 2 really emits.

## Status — end of W3–W4 (18 Sep 2026) · **Milestone M2**

| W3–W4 item | State |
| --- | --- |
| Entry points from config; per-flow interprocedural reachability | done |
| Shared-location identification via SVF **may**-alias | done — base-object normalised, stack objects in scope |
| Access enumeration: flow, R/W, function, call path, `DILocation`, loop context | done |
| Candidate derivation — triples from one access set | done — `may_precede` from the CFG; `A₁ = A₂` allowed in a loop |
| Emit C2 records and C3 run directories | done |
| **`candidates.jsonl` for all 31 cases** | done |
| **Recall gate — all 48 bug points present** | **48/48 PASS** |

```
31/31 subjects analysed
candidates: 316 total, 10.2 per subject
RECALL GATE: 48/48 annotated bug points present -- PASS
traps reported: 35/38 (expected to be high; stage 1 does not filter)
inspection ratio: 0.58 mean over 31 subject(s) whose bug points were all found
```

10.2 candidates per subject against IntRace's ~208 per program is not a precision
win: these are 37–97 line cases and IntRace's figure is for real-world subjects.
The number to keep is the gate.

The three traps stage 1 does not report are each explained, not symptoms.
`svp_simple_002_001` trap 3 and `svp_simple_017_001` trap 1 are `(W,W,W)` once
corrected — serializable, and outside the four unserializable shapes by design.
`svp_simple_015_001` trap 1 names the two arms of `p == 1 ? v : v` as `A₁` and
`A₂`; they are mutually exclusive and the CFG establishes it, so no candidate is
generated rather than one being filtered.

## Status — end of W2 (10 Sep 2026)

| W2 item | State |
| --- | --- |
| Tolerant annotation parser for `2.1_remarks` | done — reproduces **48 / 38**, records every deviation it tolerates |
| Hand-count five cases to certify it | done — 12 bugs / 9 traps, agrees; `docs/groundtruth-handcount.md` |
| **Counting unit fixed and documented** | **per-triple-instance**, 48 / 38 |
| **Match rule fixed and documented** | same subject, same location, same ordered lines; `docs/evaluation-protocol.md` |
| Soundness assumption list exists | done — `../wiki/Soundness Assumptions.md`, 27 entries |

Also produced, because the certification turned it up: a curated errata of 12 corrections to the
Racebench annotations (`bench/racebench-errata.yaml`), each with its evidence. Matching against
the shipped text scores zero on `svp_simple_019_001`'s bug point, whose ISR write is annotated
six lines above where it is.

## Status — end of W1 (31 Aug 2026)

| W1 item | State |
| --- | --- |
| C1–C4 frozen as schema files with examples | done — `contracts/` |
| Toolchain: `clang -g -emit-llvm`, `llvm-link`, SVF building and running | done — clang-14 / LLVM 14 / SVF 2.7 |
| Config file parser (C1) | done — `src/irqrace/config.py` |
| **All 31 Racebench simple cases compile to bitcode** | done — 31/31 |
| **The config loads for one case** | done — for all 31, generated from the suite README |
| **SVF lists its globals** | done — `irqrace probe` |

Not started at the end of W1: stage 2, the Z3 stage, the LLM stage, the dashboard. As of
W5, stage 2 exists; as of W6–W7, the Z3 stage too. The LLM stage and the dashboard live on
Track B's branch, `track-b/llm-integration`.

## Layout

```
contracts/        C1-C4: the frozen schemas, plus one worked example of each
  examples/       svp_simple_001_001 -- one real bug point, two planted traps,
                  one stage-2 drop record, and run-fixture/, a C3 run directory
src/irqrace/      the Python half: contracts, config, build, probe, run store,
                  stage-1 derivation, the masking analysis (masking.py), stage 2,
                  and the stage-3 driver (stage3.py)
analysis/         the C++ half: SVF-based analysis binaries
                  irqrace-probe   what the build produced, C1 vs bitcode (R4, R7)
                  irqrace-stage1  reachability, shared locations, accesses, may-precede,
                                  and the event CFG stage 2's masking analysis reads
                  irqrace-stage3  path feasibility: symbolic execution over the IR, Z3
bench/configs/    one generated C1 file per Racebench simple case (31)
bench/racebench-errata.yaml   12 curated corrections to the annotations, with evidence
scripts/          toolchain setup
docs/             notes that are about the implementation rather than the field
tests/            unit tests, plus an end-to-end pass over all 31 subjects
```

## Getting started

```bash
sudo apt install clang-14 llvm-14 llvm-14-dev libz3-dev ninja-build gcc-11 g++-11
```

```bash
./scripts/setup-svf.sh && ./scripts/build-analysis.sh && source scripts/env.sh
```

`setup-svf.sh` builds SVF 2.7 against the **system** LLVM 14 rather than
downloading SVF's own prebuilt LLVM: the download is several gigabytes unpacked,
and using the same LLVM for compiling subjects and for analysing them keeps the
bitcode version and the analysis in step. It costs about 64 MB and ten minutes.

```bash
irqrace doctor
```

```bash
irqrace contracts validate
```

```bash
irqrace bench gen-configs && irqrace bench build-all --probe
```

```bash
irqrace probe bench/configs/svp_simple_001_001.yaml
```

```bash
irqrace stage3-all
```

```bash
irqrace stage3 bench/configs/svp_simple_001_001.yaml -v
```

```bash
irqrace stage2-all
```

```bash
irqrace stage2 bench/configs/svp_simple_001_001.yaml -v
```

```bash
python3 -m pytest tests -q
```

If `python3` on your `PATH` is not the interpreter `irqrace` was installed with (a PlatformIO
virtualenv, say), run the tests as `/usr/bin/python3 -m pytest tests -q`.

## The contracts

Four contracts were frozen in W1 so that the static track, the LLM track and the
dashboard can proceed in parallel. `contracts/README.md` has the details; the
short version:

- **C1** — the configuration file, i.e. the hand-written interrupt model. It
  *bounds* the analysis: cost follows code reachable from the declared entry
  points, not repository size.
- **C2** — the context record, one JSON object per candidate. The seam between
  the two people, and the contract everything else depends on.
- **C3** — the run store. A run is a directory, not a session.
- **C4** — the context request protocol, so the model can ask for what it lacks
  instead of being handed a precomputed slice.

Five recall decisions are made structural in those schemas rather than left to
code: masking is three-valued, the interval property is a field of its own, the
solver verdict has four values including `inconclusive`, `provenance` is
mandatory, and there is no `slice` field.

## Two findings from W1

**The Racebench README names two entry points wrongly.** Its case table gives
`svp_simple_028_001_main` and `svp_simple_030_001_main`; both files actually
define `..._001__main`, with two underscores. A tool that trusts the table
analyses the main task of those cases as unreachable and loses every defect
involving it, silently. `irqrace probe`'s R7 check caught this on the first build
of the suite, which is exactly what that check exists for. Recorded as
`ENTRY_OVERRIDES` in `src/irqrace/racebench.py`, with a test that fails if the
suite is ever corrected.

**Per-flow masking analysis drops an annotated bug point.** In
`svp_simple_001_001` the main task masks interrupt 2 across the whole interval of
its bug point — but `isr_1` preempts that interval and re-enables it. Interval
masking must therefore account for flows that may execute *inside* the interval,
not just the local CFG. Written up in `docs/masking-semantics.md`, and both the
bug point and the neighbouring trap that turns on the same line are shipped as
fixtures.
