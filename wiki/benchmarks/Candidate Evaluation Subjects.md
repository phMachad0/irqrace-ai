---
type: benchmark
tags: [wiki, benchmark]
sources: ["[[NIChecker (paper)]]", "[[BMC4AV (paper)]]", "[[IntRace (paper)]]", "[[SDRacer (paper)]]"]
updated: 2026-08-27
status: draft
---

# Candidate Evaluation Subjects

Where to find real, large, interrupt-driven open-source code with **known, already-fixed**
concurrency defects, so the tool can be run at the pre-fix commit and scored against a real
outcome ([[Thesis Goal]]). This is the third evaluation tier, after [[Racebench]] and the
[[Real-World Program Benchmark]].

## What the corpus already did — and why it matters for the answer

The "real-world" suite is not a separate world from Linux. Inspecting the shipped programs:
`wdt_pci_*` is Alan Cox's `drivers/watchdog/wdt_pci.c`, and `i8xx_tco_*`, `i2c_pca_isa_*` are
likewise Linux kernel drivers; `logger`, `blink` and `brake` are small embedded applications.
Each is extracted into **one `main.c` of 157–1639 lines** with a `priority.info` file naming
the flows and their priorities, and a `violation.info` file recording the ground truth.

Two consequences:

1. **Linux drivers are already the field's idea of "real world".** Continuing there maximizes
   comparability, and the extraction convention above is a ready-made harness format to reuse.
2. **The unit of work is a module, not a codebase.** Nobody in this literature analyses a
   whole kernel. The scaling question below is therefore not the one it first appears to be.

## Are massive codebases suitable?

Mostly yes, but the bottleneck is not where it looks. Whole-program alias analysis over the
Linux kernel or a full RTOS distribution is not a TCC-sized problem — but it is also not
required. The real costs are:

- **Harness construction.** Turning a driver into an analysable unit means identifying the
  entry points, the ISRs, their priorities and their masking primitives. This is manual, it is
  what `priority.info` encodes, and it is the dominant per-subject cost.
- **Ground truth.** A large codebase does not come with labelled defects. Everything depends on
  mining commits that *fixed* a known defect, which is why the pre-fix-commit strategy is the
  right instinct.

So: **scope the *evaluation* per module, even though the tool accepts a repository.** The two are
separate decisions and it is easy to conflate them. Multi-file and whole-repository input is a
stated capability ([[Pipeline Design]], *Input scope and build requirements*), and the tier-3
subjects here are real projects with tasks and ISRs spread across many files — so the tool must
handle them. But the *measured* results should still come from module-sized units, because that
is where ground truth is affordable and where the numbers stay comparable to the existing suite.
Analysing 20 drivers at 1–2k lines each is a stronger reported result than one heroic
whole-kernel run.

Note also that the configuration file bounds the work: analysis cost follows the code reachable
from the declared entry points, not repository size, so pointing the tool at a whole tree is not
the same as analysing a whole tree.

## Option A — Linux (and derivative) drivers · recommended primary

**Why.** Continuous with the existing benchmark, so results compare. Enormous labelled defect
supply. Mechanical mining: the kernel's `Fixes:` tag names the commit that introduced a bug,
so the pre-fix tree is one `git checkout` away, and commit messages state the defect class in
prose. KCSAN (the in-tree Kernel Concurrency Sanitizer) and syzbot reports add
machine-generated, already-triaged race reports.

**Mining sketch.** Search `drivers/` history for commit messages matching race/atomicity
keywords, intersect with commits touching interrupt handlers or `spin_lock_irqsave` /
`local_irq_disable` regions, then follow `Fixes:` to the parent state. Confirm each candidate
by hand; 10–20 confirmed cases is a solid evaluation set and, since no such benchmark exists,
is itself a contribution.

**The caveat that decides which cases are usable.** Many kernel concurrency bugs are **SMP
races between CPUs**, not interrupt-preemption races on one core. A tool built on
[[Asymmetric Preemption]] models the second and not the first. The mining filter must select
for process-context-versus-ISR conflicts — the `spin_lock_irqsave` family is the signal —
and discard pure cross-CPU cases, or recall will look terrible for reasons that have nothing
to do with the tool.

## Option B — RTOS codebases · genuine novelty, larger scope risk

Zephyr, NuttX, RIOT-OS, Contiki-NG, FreeRTOS, ChibiOS. All active, all with public issue
trackers and reviewable commit histories; Zephyr and NuttX have the largest driver trees and
the most traffic.

**The appeal is real**: every source in this wiki works on bare interrupt handlers, so nothing
in the corpus covers RTOS-level concurrency ([[Open Questions]]). Being first is worth
something.

**The cost is a change of model, not just of subject.** An RTOS introduces *symmetric*
preemption between tasks alongside asymmetric interrupt preemption, so the concurrency model
becomes a superset: task↔task, task↔ISR, ISR↔ISR. It also introduces rich synchronization —
mutexes, semaphores, message queues, `taskENTER_CRITICAL`, `portDISABLE_INTERRUPTS` — every one
of which must be modelled or it becomes an unsound masking filter
([[Soundness and False Negatives]] §2). And the "interrupts cannot block" premise that the
whole corpus rests on stops holding for tasks.

**Recommended compromise if this route is taken**: keep the analysis interrupt-centric and
scope to **ISR↔task interactions only**, treating tasks as flows with priorities and RTOS
critical-section APIs as masking primitives. That is a modest extension of the existing model
rather than a new one, it is defensible in a thesis, and it still lands in unexplored
territory.

## Option C — embedded application firmware

ArduPilot, PX4, Betaflight, Marlin, Klipper, and similar. Bare-metal or thin-RTOS, heavy real
ISR use, active issue trackers, and defects that are often reported with reproduction detail.
Closest in spirit to `logger`/`blink`/`brake`, and lower modelling risk than Option B. Weaker
on labelled ground truth than Option A.

## Recommended plan

| Tier | Subject | Purpose |
| --- | --- | --- |
| 1 | [[Racebench]] 31 simple cases | recall against annotated ground truth; trap avoidance |
| 2 | [[Real-World Program Benchmark]] 18 programs | direct comparison with NIChecker and BMC4AV outputs, both now local |
| 3 | mined Linux driver cases at pre-fix commits | novelty, realism, and a benchmark the field lacks |
| 4 | one RTOS driver subsystem, ISR↔task only | stretch; the unexplored territory, scoped to stay sound |

Tiers 1 and 2 are unblocked today. Tier 3 is where the original result is. Tier 4 is worth
attempting only once the model in [[Pipeline Design]] is stable, because it changes the
concurrency assumptions rather than merely the input size.

## Still to do

Selecting and confirming the tier-3 cases is itself a research task and is tracked in
[[Open Questions]]. Nothing on this page has been verified against specific commits yet — the
candidate projects are proposals based on their concurrency model and defect-reporting
practice, not on an audit of their bug histories.
