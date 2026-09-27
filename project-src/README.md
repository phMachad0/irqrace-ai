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

## Status — end of W3–W4 (18 Sep 2026) · **Milestone M2**

| W3–W4 item | State |
| --- | --- |
| Entry points from config; per-flow interprocedural reachability | done |
| Shared-location identification via SVF **may**-alias | done — base-object normalised, stack objects in scope |
| Access enumeration: flow, R/W, function, call path, `DILocation`, loop context | done |
| Candidate derivation — pairs *and* triples from one access set | done — `may_precede` from the CFG; `A₁ = A₂` allowed in a loop |
| Emit C2 records and C3 run directories | done |
| **`candidates.jsonl` for all 31 cases** | done |
| **Recall gate — all 48 bug points present** | **48/48 PASS** |

```
31/31 subjects analysed
candidates: 566 total, 18.3 per subject (316 triples, 250 pairs)
RECALL GATE: 48/48 annotated bug points present -- PASS
traps reported: 35/38 (expected to be high; stage 1 does not filter)
inspection ratio: 0.30 mean
```

18.3 candidates per subject against IntRace's ~208 per program is not a precision
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

Not started: stage 2 (masking and the concurrency filter), the Z3 stage, the dashboard.
The LLM stage is Track B, below.

## Status — Track B, W1 harness (26 Sep 2026)

Track B started on branch `track-b/llm-integration`, four weeks behind the
Roadmap. The harness is built and tested; the measured work is blocked on
fixtures, which are blocked on the Racebench suite (see below).

| W1–W2 item | State |
| --- | --- |
| C4 owned and exercised against a resolver | done — `llm/resolver.py` |
| **Provider-neutral backend seam** | done — `llm/backends/`, any model via `provider:model` |
| Prompt harness: client, structured output, result cache | done — `llm/client.py`, `llm/cache.py` |
| Token, latency and cost model | done — `llm/cost.py` |
| The five ablation rows as compositions | done — `llm/prompts/` |
| Recall gate, trap rejection, Inspection Ratio, consistency | done — `llm/scoring.py` |
| **20 hand-built fixtures (10 bug points, 10 traps)** | **2/20 — blocked, see below** |
| **Feasibility probe (the W1 go/no-go)** | **not run — needs the fixtures** |

### The backend seam

The harness talks to a `Backend`, never to an SDK, so the same prompt
configuration can be measured against any model. That is not only portability:
LLift's central claim is that **prompt architecture dominates model choice**,
and holding the prompt fixed while swapping the model is the only way to check
it here rather than cite it.

| Spec | Reaches |
| --- | --- |
| `anthropic:claude-opus-5` | Claude, via the official SDK — the only adapter with prompt caching |
| `openai:gpt-4o` | any OpenAI-compatible endpoint: OpenAI, Groq, Together, OpenRouter, LiteLLM, vLLM, LM Studio — set `IRQRACE_OPENAI_BASE_URL` |
| `ollama:qwen2.5-coder:32b` | a local model |

The generic adapters speak plain HTTP from the standard library. Depending on
one vendor's SDK to talk to a local vLLM server would be backwards, and it
means a reviewer can reproduce the ablation against a local model with nothing
installed beyond this repository.

Three differences across providers are **recorded rather than smoothed over**,
because each one lands in a number: which structured-output tier served an
answer (`native_schema` / `tool_call` / `prompted_json`, stored on every
verdict as `produced_by`), whether the backend has prompt caching (so cost is
not comparable without saying so), and whether it knew its own prices — an
unpriced model yields `None`, never `0.00`.

**Blocked on the Racebench suite.** The fixtures must be built from real
`2.1_remarks` annotations; inventing source locations would poison the ground
truth every number is measured against. The suite is not on this machine and
`DEFAULT_SUITE` in `cli.py` points at Track A's checkout.

## Layout

```
contracts/        C1-C4: the frozen schemas, plus one worked example of each
  examples/       svp_simple_001_001 -- one real bug point, one planted trap,
                  and run-fixture/, a hand-written C3 run directory
fixtures/         Track B's labelled evaluation set; labels.json is the manifest
src/irqrace/      the Python half: contracts, config, build, probe, run store
  llm/            Track B: verdicts, prompts, C4 resolver, harness, scoring
analysis/         the C++ half: SVF-based analysis binaries
                  irqrace-probe   what the build produced, C1 vs bitcode (R4, R7)
                  irqrace-stage1  reachability, shared locations, accesses, may-precede
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
python3 -m pytest tests -q
```

### Track B

The LLM stage needs no toolchain, and its tests need no API key and no network
— every backend is exercised through an injected transport.

```bash
pip install -e '.[llm]'             # pydantic only; covers the OpenAI-compatible
                                    # and Ollama adapters
pip install -e '.[llm-anthropic]'   # adds the Anthropic SDK
```

```bash
irqrace llm prompts                      # the five ablation rows and their hashes
irqrace llm prompts '+self-validation'   # the full system prefix, as sent
irqrace llm backends                     # the providers and the spec form
irqrace llm backends ollama:llama3       # one spec's capabilities and caveats
irqrace llm fixtures                     # the labelled set; exits 1 while short of 10+10
python3 scripts/build-fixtures.py        # regenerate the fixtures from the specs
python3 scripts/run-ablation.py          # score the active rows; exits 1 if the gate fails
python3 scripts/run-ablation.py --cache-only --rows simple +domain   # re-score, no requests
python3 scripts/ablation-table.py a.json b.json   # the M3 table, one column group per model
```

The suite is found at `../racebench` or via `IRQRACE_RACEBENCH`.

```bash
python3 -m pytest tests/test_llm_*.py -q
```

On a machine without the Racebench suite, `pytest tests` fails during
*collection* — `tests/test_racebench.py` parametrises at module scope from
`DEFAULT_SUITE`, which is an absolute path into Track A's checkout. Until that
is guarded, use `pytest tests --ignore=tests/test_racebench.py`.

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
