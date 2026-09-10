---
type: project
tags: [wiki, project, roadmap]
sources: ["[[IntRace (paper)]]", "[[LLift (paper)]]", "[[SkipAnalyzer (paper)]]"]
updated: 2026-08-27
status: draft
---

# Roadmap — 10 weeks, two people, three tracks

Implementation plan for [[Thesis Goal]]. **Track A (static analysis)** and **Track B (LLM
integration)** run in parallel on two people; **Track C (dashboard)** is built from shared slack
and is ordered so that its most useful pieces land first.

Calendar: **Mon 31 Aug – Fri 6 Nov 2026**, ten working weeks.

> [!warning] Stated assumptions
> Two people, part-time student effort. This schedule is **ambitious**: it reimplements
> [[IntRace (tool)]]'s three stages, a full LLM pipeline and a UI in ten weeks. It is achievable
> only because the de-scoping ladder at the end is used early rather than late. If either person
> has less than roughly 15 hours a week, start from ladder rung 2, not from the full plan.

## The idea that makes parallel work possible

Track B must not wait for Track A. It doesn't have to, provided **four contracts are frozen in
the first three days** and Track B works against **hand-built fixtures** until Track A's output
is real.

| | Contract | Owner | Consumers |
| --- | --- | --- | --- |
| **C1** | configuration file — interrupt model + analysis settings | A | A, C |
| **C2** | **context record** — one JSON object per candidate ([[LLM Stage Design]]) | A | B, C |
| **C3** | run store layout — directories, NDJSON, manifest ([[Dashboard Design]]) | A | B, C |
| **C4** | context request protocol — progressive-prompt requests and replies | B | A |

**C2 is the critical one.** It is the seam between the two people, and everything below depends
on it being stable by Wednesday of week 1. C4 is owned by B because the *consumer* should
specify what it needs to ask for; A implements the resolver behind it.

**The fixture trick.** In week 1 Track B hand-builds ~20 context records from [[Racebench]] —
10 annotated bug points and 10 planted traps — conforming to C2. Those fixtures are the input
to the entire LLM pipeline until week 8. They also *are* the feasibility probe that
[[Open Questions]] says must run before anything is built, so the work is not throwaway.

Track B builds a **mock resolver** for C4 that serves function definitions and masking state
from static files alongside the fixtures. In week 8 the mock is swapped for Track A's real
resolver and nothing else changes.

---

## Track A — static analysis (Pedro)

### W1 · 31 Aug – 4 Sep · Contracts and build
- **Days 1–3, joint with B**: freeze C1, C2, C3, C4. Write them as schema files with examples,
  in the repo, not in prose.
- Toolchain up: `clang -g -emit-llvm`, `llvm-link`, SVF building and running.
- Config file parser (C1).
- **Done when**: every one of the 31 [[Racebench]] simple cases compiles to bitcode; the config
  loads for one case; SVF lists its globals.

### W2 · 7–11 Sep · Ground truth and assumptions
Deliberately before any analysis, because everything downstream is measured against it.
- Tolerant annotation parser for `2.1_remarks` — four grammars, the two typos
  ([[Racebench]]). **Hand-count five cases to certify it.**
- Fix and document the **counting unit** (recommended: per-triple-instance) and the **match
  rule** between a reported candidate and an annotated bug point — both currently open blockers
  ([[Open Questions]]).
- Write the **soundness assumption list** as a page: pointer model, indirect calls, external
  functions, loops, arrival model, priority semantics, equal-priority preemption.
- **Done when**: parser reproduces 48 bug points and 38 traps and agrees with the hand count;
  match rule and counting unit are written down; assumption list exists.

### W3–W4 · 14–25 Sep · Stage 1
- Entry points from config; per-flow interprocedural reachability.
- Shared-location identification via SVF **may**-alias.
- Access enumeration: flow, R/W, enclosing function, call path, `DILocation`, loop context.
- Candidate derivation — **pairs and triples from one access set**
  ([[Pair-Triple Unification]]). Triples need intra-flow CFG ordering and must allow
  `A₁ = A₂` inside a loop.
- Emit C2 records and C3 run directories.
- **Done when**: `candidates.jsonl` exists for all 31 cases and the **recall gate passes — all
  48 bug points present**. Report the candidate count without embarrassment; compare to
  IntRace's ~208 per program.
- **Milestone M2.**

### W5 · 28 Sep – 2 Oct · Stage 2
- Block model `(T, I, S, p)`; priority check with **larger = higher**
  ([[Contradictions]] #3); timing left unconstrained.
- Masking dataflow: masked only if masked on **every** path. Point property for pairs,
  **interval property for triples** — masked throughout `[A₁, A₂]` on all paths.
- Equal-priority and arrival-model decisions made explicit and recorded in the manifest.
- **Done when**: attrition measured against IntRace's 54.2%; recall gate still 100%.

### W6–W7 · 5–16 Oct · Stage 3 (Z3)
- Symbolic ISR summaries; splice at preemption point; discharge path constraints.
- **Reachability only, not unserializability** — keep the solver's role as "prove impossible".
- Timeout and unsupported constructs → **`inconclusive`, kept and passed on**, never `SAT`,
  never dropped ([[Path Feasibility Analysis]]).
- **Done when**: the full funnel is measured — stage 1 → stage 2 → Z3 → reaching the LLM — with
  per-stage timings. Recall gate still 100%.

### W8 · 19–23 Oct · Integration
- Real context records replace fixtures; implement the C4 resolver behind B's protocol.
- End-to-end run on Racebench with B's pipeline.
- **Milestone M4.**

### W9 · 26–30 Oct · Real-world suite and repair support
- The 18-program [[Real-World Program Benchmark]], `priority.info` imported directly.
- Re-verification support: re-run analysis for a certificate **and a regression check**; invoke
  [[CBMC]] or the local `bmc4av` for inconclusive cases ([[Pipeline Design]]).

### W10 · 2–6 Nov · Consolidation
Buffer, results tables, write-up. **Milestone M5.**

---

## Track B — LLM integration (Lucas)

Track B is never blocked on Track A. Weeks 1–7 run entirely on fixtures.

### W1 · 31 Aug – 4 Sep · Contracts, fixtures, feasibility probe
- Days 1–3 joint: contracts. **B owns C4** — decide what the model may ask for: a function
  definition, an ISR body, masking state at a line, a macro expansion, all other accesses to a
  variable.
- Hand-build **20 context records** from Racebench: 10 bug points, 10 planted traps, conforming
  to C2. Building them by hand is how schema gaps get found while they are still cheap to fix.
- **Run the feasibility probe by hand**: give a current model ten of them and score it.
- **Done when**: 20 fixtures exist; the probe has a written verdict. **This is a go/no-go
  signal** — a negative result reshapes the design rather than tuning it
  ([[Open Questions]]).
- **Milestone M1** (joint with A's W2).

### W2 · 7–11 Sep · Harness and baseline
- Prompt harness: model client, structured output, per-candidate result caching keyed by
  `(candidate hash, prompt config, model)`.
- **Simple-prompt baseline** — the first row of the ablation.
- Measure tokens, latency and cost per candidate; record model and date
  ([[Precision Metrics]] #8).
- **Done when**: baseline scored on all 20 fixtures; cost model established.

### W3 · 14–18 Sep · D#1 — domain rules
- Few-shot teaching of the interrupt pattern table in [[LLM Stage Design]]: one critical section
  covering the interval, split critical sections, priority ordering, equal priority, dynamic
  masking, same-statement-in-a-loop, the harmfulness criterion.
- State the priority convention explicitly in the prompt.
- **Done when**: ablation row 2 measured.

### W4 · 21–25 Sep · D#2 — progressive prompting
- Implement C4 against the **mock resolver**.
- **Log every request**: what was asked for, how often, how deep. That distribution is the
  specification of the context record and answers a standing open question
  ([[Program Slicing]]).
- **Done when**: ablation row 3; request distribution reported.

### W5 · 28 Sep – 2 Oct · D#3 and D#4
- Task decomposition: separate conversations for *feasible?*, *harmful?*, *what is the fix?*
- Self-validation with **recall-biased rules** — unknown masking ⇒ enabled, unavailable
  definition ⇒ may access, equal priority ⇒ may preempt, "uncertain" always safe.
- **Done when**: the **full ablation table** exists in [[LLift (paper)]]'s shape.
- **Milestone M3 — the headline result.**

### W6 · 5–9 Oct · Buckets, voting, consistency
- Four buckets, ranking, explanation as a first-class output.
- Majority voting across *n* runs; measure **consistency** (agreement between runs).
- [[IRIS (paper)]]'s pruning: when rejecting, ask *which element* is spurious and propagate.
- **Done when**: recall gate on fixtures — no bug point ranked *likely infeasible*; consistency
  reported.

### W7 · 12–16 Oct · Repair
- Patch generation with the **required interleaving witness**.
- **Syntax Rate** by parser; **Logic Rate** against hand-written fixes
  ([[SkipAnalyzer (paper)]]).
- **Done when**: patches for the 10 fixture bug points, both rates reported.

### W8 · 19–23 Oct · Integration
Swap the mock resolver for A's real one; re-run triage on real candidates. Note the population
changed — real candidates are the **post-Z3 residue**, the hardest ones — so re-report rather
than reuse fixture numbers. **Milestone M4.**

### W9 · 26–30 Oct · Real-world suite and loop closure
Triage and repair on the 18-program suite; close the loop by invoking re-verification.

### W10 · 2–6 Nov · Consolidation
Cost tables, ablation write-up, threats to validity. **Milestone M5.**

---

## Track C — dashboard

No third person, so Track C is built from slack. It is ordered by **payback**, not by the
screen order in [[Dashboard Design]] — the read-only explorer repays its cost immediately by
making Track A's debugging far faster.

| When | Piece | Depends on | Why here |
| --- | --- | --- | --- |
| W2–W3 | run store + manifest (R42) | C3 | Not really UI. A needs it anyway for reproducibility. |
| W4–W5 | **read-only candidate explorer + source viewer** (R23, R25, R26) | C2, C3 | Highest payback. Debugging stage 1 by reading JSON is the slow path. |
| W6 | config editor with validation + `priority.info` import (R5–R9) | C1 | Removes the most error-prone manual step; makes 18 subjects zero-config. |
| W7 | run launcher, funnel, log tail (R17–R22) | A's CLI | Turns the tool into something demonstrable. |
| W8–W9 | triage + repair views, conversation transcript (R29–R35) | B's output | Needed for M4/M5 demos. |
| W10 | evaluation dashboard (R36–R41) | ground truth | Nice for the final presentation; the numbers exist without it. |

Build against **synthetic runs** from week 2 — a hand-written run directory conforming to C3 —
so Track C is never blocked either.

---

## Milestones for the advisor

| # | Date | What is shown |
| --- | --- | --- |
| **M1** | Fri 11 Sep | Contracts frozen; ground truth certified (48 + 38, hand-checked); 20 fixtures; **LLM feasibility probe answered**. The go/no-go. |
| **M2** | Fri 25 Sep | Stage 1 on all 31 Racebench cases; **recall gate 48/48**; candidate counts; explorer showing candidates against source. |
| **M3** | Fri 2 Oct | **The ablation table** — simple prompt → full pipeline, in LLift's shape. The most publishable single artifact in the project. |
| **M4** | Fri 23 Oct | End-to-end on Racebench: static → Z3 → triage → repair, driven from the dashboard. |
| **M5** | Fri 6 Nov | Real-world suite; recall, trap rejection, Inspection Ratio, repair rates; full write-up. |

M1 and M3 are the two that matter most. M1 because a negative probe result changes the plan
while there is still time; M3 because it is the result no one in either literature has produced
for concurrency.

## Weekly interlock

A 30-minute sync each Monday, with three standing items: **has any contract changed?** (if yes,
who is broken); **is the recall gate still green?**; **what is the current cost per candidate?**
Contract changes after week 2 are the main schedule risk, which is why week 1 is spent on them.

## Risks and the de-scoping ladder

| Risk | Signal | Response |
| --- | --- | --- |
| SVF learning curve overruns W3–W4 | stage 1 not emitting by Fri 25 Sep | drop multi-file input (rung 1) and buy a week |
| Z3 stage overruns W6–W7 | nothing solving by Fri 16 Oct | rung 3 — ship without it |
| Feasibility probe is negative | M1 | pivot B to *ranking and explanation only*, drop autonomous bucketing; the static tool still stands alone |
| Contract churn | either side blocked twice in a week | freeze C2 by decree; version it and adapt rather than renegotiate |
| LLM cost overrun | > $30 on fixtures by W5 | cut majority-voting runs from 3 to 1 outside the final measurement |

**De-scoping ladder — use it early, in this order:**

1. **Multi-file / whole-repository input.** Benchmarks are single `main.c`; nothing measurable
   depends on it. Cheapest cut, largest saving.
2. **The 18-program real-world suite.** Racebench alone still gives the recall gate, trap
   rejection and the ablation.
3. **The Z3 stage.** Painful but survivable: without it the design is still *sound* — Z3 only
   ever discards — just noisier and more expensive per program. Report it as a known gap, not
   as a result.
4. **Repair.** Detection plus triage plus the ablation is already a complete TCC
   ([[Reimplementation Assessment]]).
5. **Dashboard beyond the explorer.** The explorer earns its keep; the rest is presentation.

Do **not** cut: the recall gate, the ground-truth parser certification, or the assumption list.
Those are what make the central claim of [[Thesis Goal]] checkable, and without them the numbers
mean nothing.
