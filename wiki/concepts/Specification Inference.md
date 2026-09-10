---
type: concept
tags: [wiki, concept, llm]
sources: ["[[IRIS (paper)]]", "[[AdaTaint (paper)]]", "[[IntRace (paper)]]"]
updated: 2026-08-27
status: draft
---

# Specification Inference

Using an LLM to supply the **facts the static analyzer needs before it can run**, rather than to
judge what it produced. A real pattern in the literature, and — after examination — **a
documented alternative for this project rather than part of the design**. The case against it is
below; it is more instructive than the case for.

## The idea, as the literature has it

[[IRIS (paper)]] observes that taint analysis is only as good as its source and sink
specifications, that real projects call third-party APIs whose roles nobody has annotated, and
that CodeQL's hand-written specification set is why it detects 27 of 120 known vulnerabilities.
Having an LLM label candidate APIs — from name, signature, enclosing package and JavaDoc — and
feeding those specifications into an otherwise unchanged CodeQL query raises detection to 55.
The ablation confirms the effect is not incidental: substituting CodeQL's own specifications for
either the sources or the sinks collapses recall.

[[AdaTaint (paper)]] does the same for custom source/sink wrappers, adding commit history and
inline comments as signals, with majority voting across prompts to damp hallucination.

Note the mechanics, because they are widely misread: **neither tool sends the repository to the
model.** A static query enumerates candidates and their metadata; the LLM only *labels* the
candidates. The enumeration is the hard part and it is not an LLM task.

## Why it does not earn a place here

The obvious analogue is the interrupt model — [[IntRace (paper)]] needs a **user-written
configuration file** naming a project's ad-hoc interrupt enable/disable operations, and
[[Pipeline Design]] lists entry-point identification as a first-class soundness assumption. Both
are specification problems. But four things break the analogy, and together they decide it.

**1. Open world versus closed set.** IRIS's gain comes from an open-world problem: Java projects
call hundreds of third-party APIs whose taint roles are unbounded and different in every project,
so hand-enumeration is hopeless. Interrupt masking is a **closed set per platform** — ARM
Cortex-M has PRIMASK/BASEPRI/FAULTMASK, Linux has `local_irq_disable`, `disable_irq` and the
`spin_lock_irqsave` family, a given RTOS has a handful. That list is written **once per
platform**, not once per project. The condition that makes inference valuable does not hold.

**2. The unit of work is a module, not a repository.** Nothing in this literature analyses a
whole kernel; [[NIChecker (paper)]] and [[BMC4AV (paper)]] extract each subject into a single
`main.c` of 157–1639 lines ([[Real-World Program Benchmark]]). That extraction is manual, and
identifying the entry points is part of doing it. **The configuration file is a by-product of
work that cannot be avoided anyway.**

**3. Both benchmarks already ship the configuration.** [[Racebench]] names entry points by
convention (`*_main`, `*_isr_N`), supplies `disable_isr`/`enable_isr`, and states priorities in
its README. Every one of the 18 real-world programs ships a `priority.info` file listing its
flows and priorities — **3 to 9 flows per program, median 5**. Two of the three evaluation tiers
in [[Candidate Evaluation Subjects]] require no inference at all, and the third (Linux drivers)
registers handlers through `request_irq(irq, handler, …)`, where the handler is the second
argument — a `grep`, not a judgement.

**4. The recall-critical half is the mechanically easy half.** See the split below.

## The two soundness directions are not the same problem

The earlier version of this page treated "missing an ISR" and "missing a masking primitive" as
one hazard. They are opposite, and separating them is what undercuts the argument for inference.

| Error | Effect | Difficulty |
| --- | --- | --- |
| **Missing an ISR / entry point** | the flow contributes no accesses; candidates vanish — a **recall** loss, and invisible in the output | **easy**: a grep for the registration API or the vector table |
| **Missing a masking primitive** | the candidate survives unfiltered — a **precision** loss only, given the standing rule that unrecognized register writes count as *not* masking | harder: project-specific wrappers, raw register writes |
| **Wrongly listing a masking primitive** | the analyzer believes an interrupt is disabled and drops real races — a **recall** loss ([[Soundness and False Negatives]] §2) | an LLM inventing one is likelier than a human writing one down wrong |

So the error that costs recall is the one a static query already solves, and the error an LLM
might plausibly help with is recall-*safe* to get wrong. That inverts the case for automating
this.

## What survives: auditing, not authoring

One narrow, optional, late use. Give the model the module and the config file already written by
hand — *"here are the 6 functions marked as ISRs and the 4 masking primitives; what did I
miss?"* — and treat the answer as a checklist. This is a **recall check on human work**: it can
only propose *additional* flows or primitives, so it cannot subtract candidates and cannot hurt
soundness. Worth doing if tier 3 grows to dozens of mined drivers; not worth building before
then.

If it is ever built, two constraints hold. Inferred specifications must be **recall-safe by
construction** — treat a doubtful function as *possibly* an ISR, an unrecognized register write
as *not* masking, and require positive evidence to narrow rather than to widen. And every
inferred specification must be recorded and attributed to the model rather than to the code,
because it becomes part of the stated abstraction the soundness claim rests on.

Validation would be cheap: [[Racebench]] and the [[Real-World Program Benchmark]] both ship the
ground truth, so any inference can be scored against `priority.info` and the case headers before
it is trusted anywhere new.

## Status

**Not part of [[LLM Stage Design]]'s architecture.** The two LLM roles that carry real evidence
for this project are triage and repair. Recorded here so the option and its rejection are both
on the record — and because the open-world/closed-set distinction is the thing to check before
importing any other result from [[LLM Integration Patterns]].

Related: [[Interrupt Masking and Synchronization]], [[Pipeline Design]], [[LLM Triage]].
