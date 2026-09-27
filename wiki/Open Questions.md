---
type: synthesis
tags: [wiki, open-questions]
sources: ["[[SDRacer (paper)]]", "[[IntRace (paper)]]", "[[NIChecker (paper)]]", "[[BMC4AV (paper)]]"]
updated: 2026-09-10
status: draft
---

# Open Questions

Gaps, unresolved conflicts, and things to chase. Maintained by lint passes and updated on
ingest. Roughly ordered by value to the thesis ([[Thesis Goal]]).

## Decisions that block development

Every item here must be settled **before** the corresponding code is written, because each one
changes the shape of what gets built rather than its quality. Resolved items are struck through
with the date.

- [x] ~~Mirror the [[BMC4AV (tool)]] artifact; clone both benchmarks.~~ Done 2026-08-20 — all
  three are local at `../BMC4AV` (full source), `../NIChecker`, `../racebench`.
- [x] ~~Decide the priority-direction convention.~~ Settled 2026-08-20 from the benchmark READMEs
  and `priority.info`: **larger number = higher priority** ([[Contradictions]] #3).
- [x] ~~Z3 stage or no Z3 stage?~~ Decided 2026-08-27: **required, ahead of the LLM**
  ([[Pipeline Design]]).
- [x] ~~Infer the interrupt model, or write it by hand?~~ Decided 2026-08-27: **hand-written
  configuration file** ([[Specification Inference]]).
- [x] ~~Precomputed slice, or retrieval on demand?~~ Decided 2026-08-27: **progressive
  prompting**; slicing kept as a documented alternative ([[Program Slicing]]).

### Still open — static side

- [x] ~~**Fix the counting unit, and state it.**~~ Settled 2026-09-10: **per-triple-instance**,
  giving **48 bug points and 38 traps** over the 31 simple cases. The alternatives were measured
  on the same suite — per-(case, variable) gives 33/29 and per-case gives 31/31 — and both hide
  structure the finer unit keeps, such as `svp_simple_017_001` carrying four distinct bug points
  on one variable. It is also the unit [[BMC4AV (paper)]]'s tables count, so cross-paper
  comparison survives. Recorded in every run manifest;
  `project-src/docs/evaluation-protocol.md`.
- [x] ~~**Define the match rule.**~~ Settled 2026-09-10: a candidate matches an annotation when
  it is in the **same subject**, concerns the **same shared location**, and its **ordered access
  lines equal the annotation's corrected lines**. Access kinds are reported but not required —
  the ordered line triple already separates all 86 annotations with zero collisions and no
  bug/trap clash, so kinds add failure modes and no discrimination, and 20 annotated accesses
  name a line that both reads and writes. Variable *names* are not required either, since 12
  annotations name the location through an alias (`*p`, `*ptr_var`, `global_array[1]`) that the
  may-alias analysis is supposed to resolve. Per [[Pair-Triple Unification]], the recall gate is
  measured on triples only; pair candidates get a separate *pair coverage* number.
  `project-src/docs/evaluation-protocol.md`.
- [x] ~~**Validate the ground-truth parser by hand.**~~ Done 2026-09-10. The tolerant parser
  reproduces **48 bug points and 38 traps** and agrees with a hand count of the five most
  adversarial cases — 001 (juxtaposed accesses, full-width colon), 016 (missing bracket, wrong
  access kind, no trap section), 019 (line drift), 022 (headerless bug list), 031 (reversed
  fields) — at 12 bugs and 9 traps. `project-src/docs/groundtruth-handcount.md`.
  **Caveat, and the reason this is not fully closed in spirit**: the same person wrote the parser
  and the hand count, so it establishes agreement, not correctness. Pedro spot-checks 019 and
  022, the two where the count rests on a judgement rather than transcription.
- [ ] **Are `svp_simple_019_001`'s bug/trap labels stale?** Its annotations predate an edit that
  inserted `{`, `enable_isr(1);` and `}` into two guarded blocks in `main` — which is how the
  line drift was reconstructed ([[Racebench]]). That edit is *semantically significant*: the
  `enable_isr(1)` is what makes the reads at lines 51 and 59 preemptible despite the
  `disable_isr(1)` above them. If the annotations were written before it, the labels may be as
  stale as the line numbers, and the errata deliberately corrects only the latter. One bug point
  and four traps — about 1% of the ground truth — turn on this. Cannot be settled from the
  repository alone; would need the suite's history or its authors. Blocks: nothing, but it is a
  stated threat to validity.

- [ ] **Decide whether equal-priority flows can preempt each other.** `svp_real_002` and
  `wdt_pci_1` both have same-priority ISR pairs, and no formal model in any of the four papers
  covers the case ([[Asymmetric Preemption]]). The recall-safe default is *yes, either may
  preempt*, but it must be a stated assumption because it changes the candidate set. Blocks:
  stage 2.
- [ ] **Fix the interrupt arrival model.** [[Racebench]]'s README says an interrupt may fire at
  any enabled point, at unspecified moments, an **unspecified number of times**. So: may an ISR
  preempt itself? May it fire more than once inside one interval `[A₁, A₂]`? [[SDRacer (tool)]]
  excludes reentrant interrupts and [[NIChecker (tool)]] bounds ISR executions, so the corpus
  does not agree. Affects which triples exist at all. Blocks: candidate derivation.
- [x] ~~**Write the soundness assumption list as a page.**~~ Done 2026-09-10:
  [[Soundness Assumptions]]. Nine groups, 27 entries, each giving the assumption, **how it could
  hide a defect**, and where it is implemented or checked. Four entries are honest gaps —
  SVF's own soundness (inherited, not proven here), SVF's behaviour on unresolved indirect calls,
  inter-procedural reachability (not yet built), and `svp_simple_019_001`'s labels. One entry,
  **E3 ISR re-entrancy**, is deliberately *not* recall-safe and is flagged for revisit before any
  recall claim is final.
- [ ] **Settle the external-function model list.** With multi-file input now a stated capability
  ([[Pipeline Design]]), functions with no body in the module go from a rarity to a routine
  occurrence. The sound default — assume any global may be read and written — is correct and
  ruinous for precision, so a hand-modelled set is needed for the recurring cases (`mem*`,
  `str*`, kernel accessors), and which functions were modelled belongs in the assumption list.
  Blocks: stage 1 on any real project.
- [ ] **Verify SVF's behaviour on unresolved indirect calls.** The design requires that an
  unresolvable target set be treated as *every address-taken function with a matching
  signature*, never as empty ([[Soundness and False Negatives]] §1). Confirm what SVF actually
  does by default and override it if necessary — this is the single largest silent-recall risk
  at repository scope, and it is testable with a small function-pointer dispatch fixture.
- [ ] **Confirm the build flags against SVF's own recommendations.** `-g` is mandatory; `-O0`
  marks functions `optnone` and can cause the pass manager to skip them. Cheap to settle
  empirically, and it blocks everything.
- [ ] **Choose the pointer-analysis configuration.** Field sensitivity, context sensitivity and
  indirect-call resolution in SVF, all in **may**-alias mode. Determines both recall and cost,
  and the function-pointer ISR vector table makes indirect-call handling recall-critical
  ([[Soundness and False Negatives]] §1). Blocks: stage 1.

### Still open — interface

- [ ] **Does the candidate explorer need whole-repository scale?** Tier-2 runs put ~13
  candidates in front of the LLM per program, but a whole-repository run could produce
  thousands. The answer decides whether the explorer can render a table or needs server-side
  paging and indexing ([[Dashboard Design]]).
- [ ] **Confirm the Streamlit mechanics for long-running jobs** — auto-rerunning fragments for
  polling, `st.status` for staged progress, query parameters for deep links. All exist; verify
  the current API before designing around specifics.

### Still open — LLM side

- [ ] **Probe whether LLM triage works on interrupt concurrency at all, before building
  anything.** No source in this wiki has tried, and triage precision already varies by 30 points
  between two *sequential* bug types ([[ChatGPT for Static Analysis (paper)]]). Hand-build
  context records for ten [[Racebench]] candidates — five bug points, five planted traps — and
  score a current model by hand. A negative result reshapes the whole design, so this is the
  cheapest high-information experiment available and should come first.
- [ ] **Write down the benignity criterion the LLM will apply, before it applies one.**
  [[BMC4AV (paper)]] asserts `(R,W,W)` is benign without argument and this wiki treats that as a
  defect ([[Contradictions]] #2). If the triage stage makes benignity judgements case-by-case
  without a stated, testable criterion, the project has reproduced the problem it set out to
  fix. Candidate starting point is the Bai et al. rule via [[IntRace (paper)]] — which is a
  reason to read it primarily rather than second-hand.
- [ ] **Establish a current cost and capability baseline.** Every model number in the corpus is
  from 2023–24 (GPT-4, GPT-3.5, Claude 2, Bard, Llama 3) and none should be used to choose a
  model ([[LLM Integration Patterns]]). Measure tokens and cost per candidate on the probe above
  and record the model and date with the figure ([[Precision Metrics]] #8).
- [ ] **Instrument the progressive-prompt request channel from the first prototype.** What the
  model asks for, how often and how deep **is** the specification of the context record, now
  that precomputed slicing is out ([[Program Slicing]]). Not blocking, but it must be built in
  from the start rather than retrofitted, because the data cannot be recovered later.

## Sources to acquire

- [ ] **intAtom** (Li et al.) — the most-cited static baseline in the corpus; both BMC papers
  agree it finds every violation. Currently a second-hand page ([[intAtom]]).
- [ ] **Rchecker** (Feng et al., QRS-C 2020) — the Interrupt Mask List idea deserves a
  primary reading ([[Rchecker]]).
- [ ] **CPA4AV** — only known through hostile citations ([[CPA4AV]]).
- [ ] **iCBMC / "Effective verification of low-level software with nested interrupts"**
  (Kroening et al., DATE 2015; TECS 2017) — the ancestor of the BMC branch ([[iCBMC]]).
- [ ] **IntAbs** (Sung et al.) — supplies IntRace's nesting semantics and part of the
  real-world program set.
- [ ] **Lazy-CSeq** (Inverso et al.) — to judge how much of NIChecker is inherited.
- [ ] Anything **post-2026** citing [[BMC4AV (paper)]], and whether the preprint was
  published. Its status matters for how much weight the 94-violation re-count can carry — and
  the artifact carries **three different titles** for the work, including one using "event
  graph" rather than "memory access graph", which suggests revision across venues
  ([[BMC4AV (tool)]]).
- [x] ~~The LLM-plus-static-analysis literature.~~ Ingested 2026-08-23; see
  [[LLM Integration Patterns]].
- [ ] **UBITect** (Zhai et al. 2020) — the analyzer [[LLift (paper)]] sits on top of, and the
  clearest published example of a *soundness-oriented* static analysis whose precision stage
  cannot keep up. Its two-tier design is the structural precedent for this project.
- [ ] **Kharkar et al.** — the false-positive-removal baselines (GPT-C, DeepInferEnhance) that
  [[SkipAnalyzer (paper)]] compares against; pre-LLM learned triage, useful for judging how much
  the LLM actually adds.
- [ ] **Bai et al.** — the harmfulness criterion [[IntRace (paper)]] adopts (shared variable
  feeds a branch, or indexes an array/pointer). It is about to become a prompt rule in
  [[LLM Stage Design]], so it deserves a primary reading rather than a second-hand one.

## Now cheap to answer, with the artifacts in hand

- [ ] **Where do NIChecker's extra violations come from?** A direct parse of `2.1_remarks`
  gives **48** bug points across the 31 simple cases; [[NIChecker (paper)]] works with 54, and
  the [[Racebench (documentation)]] export says 50. Three numbers, one annotation file.
  NIChecker's repository ships its per-case results, so the diff is now mechanical
  ([[Contradictions]] #2).
- [ ] **Reconcile 45 / 47 / 94 on the real-world suite.** The shipped `violation.info` files
  hold 45 `true violation` entries; NIChecker publishes 47; BMC4AV reports 94 instances. The
  per-variable/per-instance mismatch explains most of it — confirm on `logger` and `wdt_pci_3`,
  where the gap is widest ([[Real-World Program Benchmark]]).
- [ ] **Is BMC4AV's Racebench recall really 79.2%?** Its 38 matches the annotations exactly once
  `(R,W,W)` is removed, but three `(R,W,W)` bug points sit inside its own 25-case subset. Run
  the local `bmc4av` on `svp_simple_017`, `_021`, `_023` and confirm it reports nothing for
  them.
- [ ] **Recover the real seven defect patterns.** The repository README grounds the suite in
  seven access-order violation patterns citing two prior works, but neither the repo docs nor
  [[Racebench (documentation)]] enumerate them — the DeepWiki reconstruction is speculative.
  Track down the two cited papers on interrupt data access conflicts in aerospace software.
- [ ] **Does any tool handle equal-priority ISRs?** `svp_real_002` gives two ISRs the same
  priority — and so does `wdt_pci_1` in the *main* real-world suite, which every atomicity paper
  evaluates on. None of the four formal models cover the case. Running the local `bmc4av` on
  `wdt_pci_1` and inspecting whether it considers `writer1_isr`/`writer2_isr` interleavings
  would answer it directly ([[Asymmetric Preemption]]).
- [ ] **Were the complex cases ever used in the papers?** All four papers evaluate on the 31
  simple cases; `svp_real_001` / `svp_real_002` carry 3 of the 53 bug points and the hardest
  scoring weights, and appear nowhere in the corpus. Running a tool on them would be a small
  original result.

## Empirical questions a TCC could actually answer

- [ ] **Re-count one package of the [[Real-World Program Benchmark]]** (e.g. `logger` or
  `blink`, ~150–190 LoC each) by hand against both pattern sets, and see whether the 37/47 or
  the 94 figure holds ([[Contradictions]] #1). Small, self-contained, genuinely original.
- [ ] **Is `(R,W,W)` benign?** Construct a counterexample program where an `(R,W,W)`
  interleaving causes observable misbehaviour, or argue convincingly that it cannot
  ([[Contradictions]] #2). BMC4AV asserts it without argument — and the benchmarks disagree
  with it: 10 of 48 Racebench bug points and six shipped real-world `true violation` entries
  are `rww`, including all three in `logger1`. `logger1` is ~170 lines and is the obvious place
  to settle this by hand.
- [ ] **Cross-class case study**: `i2c`-family and `shortprint` programs appear in both the
  data-race and atomicity-violation literatures. Do the two analyses report defects on the
  same variables? Nobody has checked.
- [ ] **What would a unified detector cost?** Nothing in the corpus detects both defect
  classes in one pass, though the pipelines share their first two stages.

## LLM stage questions

- [ ] **Run an LLift-style ablation for this domain.** Simple prompt → +interrupt pattern rules
  → +progressive prompting → +task decomposition → +self-validation, scored on the 48 bug points
  and 38 traps. LLift's table gives a directly comparable shape, and no equivalent exists for
  concurrency. Probably the single most publishable experiment available here
  ([[Prompt Architecture]]).
- [ ] **What is the right size for the context record?** Now the *primary* open question on the
  LLM side, since precomputed slicing was dropped in favour of progressive prompting
  ([[Program Slicing]]). Instrument the request channel from the first prototype and log what
  the model asks for, how often, and how deep. That distribution **is** the specification of the
  record, and it is also the evidence that would justify reviving slicing.
- [ ] **Does repair transfer?** Logic Rate 97.3% on Null Dereference says nothing about
  inserting `irq_disable`/`irq_enable` with the right *scope* (whole interval for a triple, one
  access for a race) under timing constraints ([[LLM-Assisted Repair]]).
- [ ] **Is a cheap ranking pre-pass good enough?** At ~208 candidates per program and ~$0.43 per
  LLM call, full triage is ~$90 per program. [[AdaTaint (paper)]]'s embedding-plus-static-features
  scorer ranks without dropping. Measure whether it puts the real defects near the top.

## Method questions for the tool being built

- [x] ~~What is the union pattern set?~~ Answered in [[Pair-Triple Unification]]: derive pairs
  and triples separately from one access enumeration; include `(R,W,W)`; never derive triples by
  joining confirmed pairs.
- [ ] **What exactly goes in the context record?** Variable, access pair/triple with source
  ranges, call stacks, ISR identity and priority, masking state along the path, and a `dg`
  backward slice — but how much slice is enough for an LLM to judge feasibility, and does the
  answer scale with program size? [[Program Slicing]] argues for layering rather than dumping
  the slice; that needs testing.
- [ ] **Does the split-critical-section atomicity violation occur in the wild?** The case that
  breaks the pair abstraction — both local accesses individually protected, the gap between
  them not — is constructed in [[Pair-Triple Unification]] but was not found in [[Racebench]].
  Finding a real instance would justify the extra triple machinery; failing to find one is also
  worth reporting.
- [ ] **On the solver's residue, where do solver and LLM agree?** Now a characterisation
  question rather than an either/or, since Z3 is fixed in the pipeline. Does the model ever
  contradict an `UNSAT` proof? That would be a prompt or context-record defect and is worth
  catching early ([[Pipeline Design]]).
- [ ] **Can an LLM's "benign" judgement be trusted?** IntRace names unclassified benign races as
  a false-positive cause and BMC4AV asserts `(R,W,W)` is benign without argument. If the LLM
  stage makes that call, its criterion must be stated and testable, or it becomes the same
  unexamined assumption in a new place ([[Precision Metrics]] #6).
- [ ] **Does a repaired program stay correct?** [[SDRacer (paper)]] measured repair overhead
  and found two of eleven subjects markedly degraded because disabling interrupts changed the
  main task's control flow. Any fix-application stage needs that check plus a timing argument.

## Method questions

- [ ] Does the [[Memory Access Graph]] idea transfer to [[Data Race]] detection, or is it
  specific to three-access patterns?
- [ ] Could [[Loop Abstraction]] be added to [[IntRace (tool)]], which currently asks the user
  for a loop depth?
- [ ] How much of NIChecker's runtime problem is sequentialization rather than solving? Its
  own numbers say 158.71 s total against 34.12 s of CBMC — so most of it. Does BMC4AV's
  speed-up mostly come from skipping sequentialization rather than from the graph?
- [ ] Repair after 2020: has anyone revisited it? Do modern static repair techniques handle
  interrupt disable/enable insertion with timing constraints? ([[Synthesis]] §6)

## Missing from the wiki

- [ ] Real fault reports: the uCLinux UART race in [[SDRacer (paper)]] §2.3 is the only
  concrete field defect described in any source. More would strengthen the motivation section
  of a thesis considerably.
- [ ] Anything about **RTOS-level** concurrency (FreeRTOS, AUTOSAR/OSEK) — all four sources
  work on bare interrupt handlers. This is simultaneously a gap in the wiki and a candidate
  scope decision for the tool: extending to RTOS tasks would be novel, but it changes the
  concurrency model the whole corpus assumes.
- [ ] Any **industrial adoption** evidence. Every tool is a research prototype; three of four
  are unobtainable.
