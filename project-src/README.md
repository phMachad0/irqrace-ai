# irqrace

A static analyzer that finds **data races and atomicity violations in
interrupt-driven embedded C with no false negatives**, emits a rich per-candidate
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

## Status — end of W1 (31 Aug 2026)

| W1 item | State |
| --- | --- |
| C1–C4 frozen as schema files with examples | done — `contracts/` |
| Toolchain: `clang -g -emit-llvm`, `llvm-link`, SVF building and running | done — clang-14 / LLVM 14 / SVF 2.7 |
| Config file parser (C1) | done — `src/irqrace/config.py` |
| **All 31 Racebench simple cases compile to bitcode** | done — 31/31 |
| **The config loads for one case** | done — for all 31, generated from the suite README |
| **SVF lists its globals** | done — `irqrace probe` |

Not W1 and not started: stage 1, stage 2, the Z3 stage, the LLM stage, the
dashboard.

## Layout

```
contracts/        C1-C4: the frozen schemas, plus one worked example of each
  examples/       svp_simple_001_001 -- one real bug point, one planted trap,
                  and run-fixture/, a hand-written C3 run directory
src/irqrace/      the Python half: contracts, config, build, probe, run store
analysis/         the C++ half: SVF-based analysis binaries
bench/configs/    one generated C1 file per Racebench simple case (31)
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
python3 -m pytest tests -q
```

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
code: masking is three-valued, the interval property is separate from the point
property, the solver verdict has four values including `inconclusive`,
`provenance` is mandatory, and there is no `slice` field.

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
