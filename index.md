---
type: index
tags: [wiki, index]
updated: 2026-09-27
---

# Index

Catalog of the wiki. Start at [[Overview]]; read [[Thesis Goal]] for what this vault is *for*,
[[Synthesis]] for the current thesis and [[Open Questions]] for what to do next. Maintained by
the LLM per `CLAUDE.md` — update on every ingest.

**Counts**: 12 sources (5 concurrency, 7 LLM) · 4 tool pages + 7 baseline/infrastructure ·
20 concepts · 4 benchmarks · 5 comparisons · 6 project pages.

## Navigation

| Page | What it is |
| --- | --- |
| [[Overview]] | map of content — the entry point |
| [[Thesis Goal]] | **what the TCC is building**: a sound detector with an LLM triage/repair loop |
| [[Pipeline Design]] | the static half: each borrowed technique, and fix validation |
| [[LLM Stage Design]] | the LLM half: architecture, context record, prompt design, evaluation plan |
| [[Dashboard Design]] | the UI: Streamlit over a headless core, 45 numbered requirements, run store layout |
| [[Soundness Assumptions]] | **the list the no-false-negatives claim is relative to** — 27 entries, each with how it could hide a defect |
| [[Roadmap]] | 10-week plan to 6 Nov: static / LLM / UI tracks, four contracts, five milestones, de-scoping ladder |
| [[Synthesis]] | what the four sources collectively say; working thesis statement |
| [[Open Questions]] | sources to acquire, empirical questions a TCC could answer |

## Diário de implementação (`wiki/diario/`) — **em português**

A única parte do vault escrita em português brasileiro: uma página por semana do [[Roadmap]],
explicando em detalhe o que foi implementado, com trechos de código e todo conceito definido.
Criada e revisada ao fim de cada semana de implementação (ver `CLAUDE.md`).

| Página | Semana | Conteúdo |
| --- | --- | --- |
| [[Semana 1 — Contratos e Toolchain]] | W1 · 31 ago–4 set | os quatro contratos C1–C4, toolchain LLVM/SVF, `irqrace-probe`, três achados |
| [[Semana 2 — Ground Truth e Protocolo de Avaliação]] | W2 · 7–11 set | parser tolerante das anotações, conferência à mão, unidade de contagem, regra de casamento, errata |
| [[Semana 3 — O Front End do Stage 1]] | W3 · 14–18 set | grafo de chamadas, alcançabilidade, may-alias, enumeração de acessos, `may_precede` |
| [[Semana 4 — Derivação de Candidatos e o Recall Gate]] | W4 · 21–25 set | pares e trincas, as quatro formas não serializáveis, **recall gate 48/48**, M2 |

## Implementation (`project-src/`)

The tool itself, outside the wiki layer. Started 2026-08-31 (W1 of [[Roadmap]]). Track B started 2026-09-26 on branch
`track-b/llm-integration`; **M1 answered GO** the same day (see `log.md`).

| Path | What it is |
| --- | --- |
| `project-src/README.md` | status against the Roadmap, layout, how to build and run |
| `project-src/contracts/` | **C1–C4 frozen as JSON Schema**, with a worked example of each and a synthetic C3 run directory |
| `project-src/src/irqrace/` | Python: contract validation, C1 parser, bitcode build, SVF probe, run store |
| `project-src/src/irqrace/llm/` | **Track B**: the triage and repair stage. Provider-neutral backends, four active ablation rows (progressive deferred), C4 resolver, scoring, the tolerant annotation reader |
| `project-src/fixtures/` | the 20 labelled context records — 10 bug points, 10 traps, six adversarial pairs |
| `project-src/analysis/` | C++ over SVF: `irqrace-probe` ([[Dashboard Design]] R4, R7) and `irqrace-stage1` (reachability, shared locations, accesses, may-precede) |
| `project-src/bench/configs/` | one generated C1 file per [[Racebench]] simple case (31) |
| `project-src/docs/masking-semantics.md` | why per-flow interval masking drops a real bug point |
| `project-src/docs/toolchain-notes.md` | SVF/LLVM pairing, the `optnone` trap, the K&R-prototype call-graph trap |
| `project-src/docs/evaluation-protocol.md` | counting unit, match rule, what is reported and what is gated |
| `project-src/docs/groundtruth-handcount.md` | the five hand-counted cases certifying the annotation parser |
| `project-src/bench/racebench-errata.yaml` | 12 curated corrections to the Racebench annotations, with evidence |

## Sources (`wiki/sources/`)

| Page | Year | Summary |
| --- | --- | --- |
| [[SDRacer (paper)]] | 2020 | IEEE TSE. Static + symbolic + dynamic detection of data races on a virtual platform, **plus automated repair**. 190 races on 11 subjects. |
| [[IntRace (paper)]] | 2024 | J. Supercomputing. Three-stage static data race detection ending in Z3 path feasibility. 73.2% fewer false positives than Rchecker. |
| [[NIChecker (paper)]] | 2024/25 | ACM TOSEM. Lazy sequentialization + CBMC for atomicity violations, with loop abstraction, slicing and preemption-point reduction. 96.4% precision on Racebench. |
| [[BMC4AV (paper)]] | 2026 | SSRN preprint. BMC guided by a partial-order memory access graph. Claims 94/94 violations and 57 false negatives in NIChecker. |
| [[Racebench (documentation)]] | 2026 export | DeepWiki documentation of the `racebench` repository: composition, ground-truth annotation grammar, conventions, competition rules. Partly inferred — provenance caveats on the page. |

### LLM-assisted static analysis (`wiki/sources/`)

| Page | Year | Summary |
| --- | --- | --- |
| [[LLift (paper)]] | 2024 | OOPSLA. LLM decides UBITect's 53,000 undecided cases. Ablation: recall **0.15 → 1.00** on prompt architecture alone. The template. |
| [[IRIS (paper)]] | 2024–25 | Neuro-symbolic: LLM infers taint specs, CodeQL runs. 27 → 55 of 120 detected; FDR still 84.8%. Open source. |
| [[SkipAnalyzer (paper)]] | 2023 | Detect + FP-filter + repair on Infer warnings. Repair Logic Rate 97.3%. Companion to the AIware study. |
| [[ChatGPT for Static Analysis (paper)]] | 2024 | AIware. Prompt-template mechanics; FP-removal precision 93.9% vs 63.3% across two bug types. |
| [[AdaTaint (paper)]] | 2025 | Spec inference + learned filter. Synthetic benchmarks, unreliable numbers; recall 75.4%. |
| [[Reducing False Alarms (paper)]] | 2025 | Fine-tuned CodeBERT filters CppCheck alerts. Honest about the recall cost. Source of Inspection Ratio. |
| [[SAST-Genius (paper)]] | 2025 | Preprint. Semgrep + fine-tuned Llama 3; orchestration layer, exploit validation, prompt-injection risk. |

Raw clippings live in `Clippings/`, PDFs in `raw/`. Both are immutable.

## Concepts (`wiki/concepts/`)

| Page | Summary |
| --- | --- |
| [[Asymmetric Preemption]] | why interrupt concurrency is not thread concurrency; breaks happens-before |
| [[Interrupt Nesting]] | ISR preempted by higher-priority ISR; the capability that most separates the tools |
| [[Interrupt Masking and Synchronization]] | disabling beats locking; ad-hoc mechanisms and the user config-file problem |
| [[Data Race]] | two-access defect; SDRacer's hardware-state condition; harmful vs benign |
| [[Atomicity Violation]] | three-access defect; where the `(R,W,W)` dispute lives |
| [[Access Interleaving Patterns]] | the cheap syntactic first filter — and the de facto bug specification |
| [[Symbolic Execution]] | SDRacer's test generator; register semantics constrain the solver |
| [[Path Feasibility Analysis]] | the expensive last filter; 86.2% of candidates, 69.7% of runtime |
| [[Bounded Model Checking]] | counterexamples vs state explosion; "bounded" qualifies every recall claim |
| [[Lazy Sequentialization]] | NIChecker's translation; invocation conditions carry priority and masking |
| [[Loop Abstraction]] | reach deep bugs at small unwind bounds; why CPA4AV fails where NIChecker doesn't |
| [[Memory Access Graph]] | BMC4AV's in-solver RF/WS/FR graph; guidance buys precision, graph buys speed |
| [[Precision Metrics]] | precision vs hit rate, Inspection Ratio, and the eight reasons numbers don't compose |
| [[Soundness and False Negatives]] | the ten places recall is lost, and the rule every filter must obey |
| [[Pair-Triple Unification]] | can races and atomicity violations be one analysis? proof, evidence, and the limit |
| [[Program Slicing]] | `dg`'s dependence graphs are used; the slicer is **not** — context is retrieved on demand |
| [[Prompt Architecture]] | the four components, and why structure beats model choice |
| [[LLM Triage]] | rank versus drop, and the measured recall cost of getting it wrong |
| [[Specification Inference]] | LLM supplies what the analyzer needs — examined and **rejected** here; the config file wins |
| [[LLM-Assisted Repair]] | what transfers from Null Dereference to interrupt fixes, and what does not |

## Tools (`wiki/tools/`)

| Page | Summary |
| --- | --- |
| [[SDRacer (tool)]] | Clang + KLEE/STP + Simics; the only tool here that repairs |
| [[IntRace (tool)]] | Clang/LLVM + IntAbs + Z3; staged static data race detection |
| [[NIChecker (tool)]] | Lazy-CSeq v2.1 + CBMC v5.6; nested interrupts, needs variable + pattern per run |
| [[BMC4AV (tool)]] | CBMC + MiniSat + guided MAG; fully automatic, **source obtained**, usable as a fix validator |
| [[intAtom]] | static atomicity baseline; unobtainable, finds everything, imprecise |
| [[CPA4AV]] | abstract reachability trees; fails on deep-loop cases (stub) |
| [[Rchecker]] | CBMC-based race detector with an Interrupt Mask List |
| [[iCBMC]] | CBMC for nested interrupts; extended by BMC4AV into iCBMC+ (stub) |
| [[CBMC]] | the shared substrate of the entire verification branch |
| [[Lazy-CSeq]] | thread sequentializer NIChecker descends from |
| [[Supporting Infrastructure]] | KLEE, Z3, MiniSat, Simics, Clang/LLVM, IntAbs — who uses what |

## Benchmarks (`wiki/benchmarks/`)

| Page | Summary |
| --- | --- |
| [[Racebench]] | 33 aerospace-derived C programs; **48 measured bug points and 38 traps** in the 31 simple cases; four incompatible annotation grammars |
| [[Real-World Program Benchmark]] | 18 extracted driver/firmware programs; the shipped ground truth says 45, BMC4AV says 94 — a counting-unit mismatch |
| [[NASAC 2019 Prototype Competition]] | where Racebench came from: five teams, asymmetric scoring, and why this field prizes precision |
| [[Candidate Evaluation Subjects]] | Linux drivers vs RTOS vs firmware for tier-3 evaluation, and whether huge codebases fit |

## Comparisons (`wiki/comparisons/`)

| Page | Summary |
| --- | --- |
| [[Tool Capability Matrix]] | all four tools side by side, feature by feature |
| [[Reported Results Across Papers]] | every headline number with its ground truth, hardware, and whether it was re-run |
| [[Contradictions]] | six open conflicts, chief among them 37/47 vs 94 violations |
| [[Reimplementation Assessment]] | study order, what to reimplement, the stack, and verified artifact availability |
| [[LLM Integration Patterns]] | seven LLM sources by attach point; what each buys and costs |
