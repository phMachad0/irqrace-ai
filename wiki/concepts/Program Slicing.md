---
type: concept
tags: [wiki, concept]
sources: ["[[NIChecker (paper)]]", "[[IntRace (paper)]]", "[[LLift (paper)]]"]
updated: 2026-08-27
status: draft
---

# Program Slicing

Reduce a program to the statements that can affect a chosen *slicing criterion* — a variable at
a program point — discarding everything provably irrelevant. Two possible uses here, and only
one of them is in the design.

- **As a verification optimization**: in the corpus, and useful.
- **As the context-retrieval mechanism for the LLM stage**: **not adopted** — superseded by
  progressive prompting. Kept below as a documented alternative.

## How the corpus uses it

[[NIChecker (paper)]] slices on a criterion built from the target global variable before handing
the sequentialized program to [[CBMC]]. Combined with preemption-point reduction this yields up
to a **42.2% verification speed-up** (its RQ3). The purpose is purely performance: a smaller
program means a smaller formula. That use is uncontested, and it is the one that could matter in
this project's **fix-validation** step, where a bounded model checker runs on a repaired program
([[Pipeline Design]]).

[[IntRace (paper)]] does not slice, but cites `dg` (reference 26) among its infrastructure
alongside Clang/LLVM and Z3.

## What `dg` is

`github.com/mchalupa/dg`, MIT-licensed and actively maintained (~3.2k commits). A program
analysis library for **LLVM bitcode** providing pointer analysis, data-dependence and
control-dependence analysis, dependence-graph construction, value-relation analysis, and static
slicing — the last exposed as the `llvm-slicer` tool. It is the slicing engine behind the
Symbiotic verification toolchain.

Note that the **dependence graph, not the slicer, is the part this project needs**: data and
control dependence feed the concurrency analysis and the harmfulness criterion. Keeping `dg` as
a dependency is still justified on those grounds even though slicing is not in the context path
([[Reimplementation Assessment]]).

## Why it is not the context-retrieval mechanism

The question a context record must answer is *how much of the program to show the model*.
Slicing answers it by computing relevance in advance. [[LLift (paper)]] answers it by **not
deciding**: the model is told to ask when it lacks a definition, in a fixed parseable format,
and the harness resolves the request against the source tree. Average 2.78 turns, maximum 8, and
in the ablation this component is part of the configuration that reaches recall 1.00
([[Prompt Architecture]]).

Three reasons to prefer asking over slicing:

1. **A backward slice on a global is not small.** Globals are written from many flows and the
   slice closes over all of them plus everything computing their values, which on a real driver
   approaches the whole module. Slicing was introduced here to shrink a *formula*, where a 42%
   reduction is a win; a 42% reduction of a 10,000-line module is still not a prompt.
2. **An incomplete slice is a false-negative generator.** A model shown a slice that omits the
   relevant path will confidently declare a candidate infeasible and give a plausible reason.
   That miss is laundered through context capture rather than through a filter and is very hard
   to detect afterwards ([[Soundness and False Negatives]] §7c). Progressive prompting fails the
   other way: the model asks, and if the harness cannot answer, that is visible and loggable.
3. **It is engineering spent ahead of evidence.** Slicing, IR-to-source mapping through
   `DILocation`, and truncation heuristics all have to be built and tuned *before* knowing what
   the model actually needs. The request distribution from progressive prompting **is** the
   specification of the context record — measure it first, then decide whether anything needs
   precomputing ([[Open Questions]]).

## Kept as an alternative

Two situations would bring it back:

- **Progressive prompting proves too slow or too expensive.** Each request is a round trip; if
  candidates routinely need many, a precomputed slice may be cheaper than the turns it saves.
  This is measurable once the triage stage exists.
- **A model that cannot use progressive prompting.** [[LLift (paper)]] found GPT-3.5 and Bard
  simply would not request definitions, and had to be run without that component. If the project
  ever needs a small local model for cost reasons, precomputed context becomes necessary rather
  than optional.

If it is revived, three requirements hold. Slice on **the specific access instruction in the
specific flow** — and for a triple, the interval `[A₁, A₂]` — not on the global's whole history.
Map the sliced instructions back to **source lines** via `DILocation` and emit the original C,
since IR is close to useless to a reviewer, human or otherwise. And ensure the dependence
analysis **over-approximates**: every may-dependence retained, or the slice must be labelled in
the prompt as partial evidence.

Related: [[Prompt Architecture]], [[LLM Stage Design]], [[Path Feasibility Analysis]],
[[Loop Abstraction]].
