---
type: benchmark
tags: [wiki, benchmark, real-world, cpp, esp32]
sources: []
updated: 2026-10-29
status: draft
---

# Rastro-Robot Firmware

The first run of the tool on **real firmware the human wrote**: a line-following robot on an
ESP32 (DOIT DevKit v1), C++ on Arduino over ESP-IDF 4.4.5 and FreeRTOS. It is not a benchmark
suite: there is no annotated ground truth, only one **planted** defect with a known location.
Its value is that it is the first subject that is C++, dual-core and an RTOS application, which
are three things [[Racebench]] never exercises. It surfaced three problems in the pipeline that
31 Racebench cases could not have shown.

Numbers on this page come from one run on 2026-10-29
(`rastro-robot-prio-20261029T221653Z-0f675a`, tool `0.2.0`), not from a paper. The repository
lives outside the vault at `~/Documentos/PlatformIO/Projects/rastro-robot`. The two C1 files
used are kept by the human outside the vault (`~/Downloads/rastro-robot-c1-{prio,flat}.yaml`).

## The subject

| | |
| --- | --- |
| Build | PlatformIO env `firmware`: 13 translation units, `main.cpp` + `app/` + `hal/` + `control/` |
| Flows | `setup`, `loop` (Arduino `loopTask`, core 1, p1); `taskImu` (core 1, p5), `taskLineSensor` (core 1, p4), `taskControl` (core 1, p3), `taskSupervisor` (core 0, p3), `taskTelemetry` (core 0, p2); ISRs `irTimerIsr` (hardware timer 0) and `imuDataReadyIsr` (GPIO 23) |
| Not a flow | `buttonIsr`, compiled out by `FEATURE_AUTOSTART = 1` |
| Masking | none: the code uses no critical section and no interrupt masking |
| Shared state by design | mailboxes (`xQueueOverwrite`/`xQueuePeek`), an event group, two `volatile` counters in `imu.cpp`, `g_imu_status` |

**Getting it into bitcode.** clang-14 compiles the real ESP-IDF headers once it is given
`--target=i686-unknown-none-elf` (32-bit, like Xtensa), clang's own resource headers in place of
GCC's `lib/gcc/.../include` (whose `stddef.h` uses `__float128`), `-D__XTENSA__
-D__XTENSA_EL__` (so newlib declares the POSIX threads `libstdc++` expects) and every include
path and define from `pio project metadata -e firmware`. All 13 TUs compiled and linked with no
source change. Entry points are the **mangled** names (`_ZN12_GLOBAL__N_114taskLineSensorEPv`):
the tasks and ISRs live in anonymous namespaces.

## The planted defect

A lost update between the IR timer ISR and the task it wakes (`src/app/tasks.cpp`, left
uncommitted in the subject's working tree):

```cpp
// irTimerIsr()                                   line 131
g_ir_ticks_pending++;

// taskLineSensor(), once per sample
const uint32_t pending = g_ir_ticks_pending;      // line 240  A1
if (pending > 1) { g_ir_overruns += pending - 1; }
g_ir_ticks_pending = 0;                           // line 244  A2
```

An ISR activation between lines 240 and 244 has its increment overwritten, and the overrun
telemetry undercounts. Expected candidate: `(R 240, W 131, W 244)`, pattern `RWW`. The natural
repair needs no lock: `ulTaskNotifyTake(pdTRUE, …)` already returns the number of pending
notifications, atomically.

## The funnel

| Stage | Out | Wall | The planted defect |
| --- | --- | --- | --- |
| Stage 1, default `indirect_calls` | ~15.9M (upper bound) | killed at 10 min | — |
| Stage 1, `points-to-only` | **2770** (24 shared objects) | 46 s | present, `cf18edaa4d5fcb591` |
| Stage 2 | **10** (2494 dropped by priority, 266 no-path) | 25 s | kept |
| Stage 3 (Z3) | **10** sat, 0 unsat, 0 inconclusive | 2.7 s | `sat` |
| Triage (`claude-cli:sonnet`, `+self-validation`) | 10 (9 `likely_real`, 1 `likely_benign`) | 325 s | `likely_real`, feasible 0.93 / harmful 0.80 |

**The planted defect is found and survives every filter.** Its context record is accurate:
`volatile uint32_t`, sharing proven by may-alias between `irTimerIsr` and `taskLineSensor`,
`A₁`/`A₂` inside the task's loop (header line 236), `feeds_branch: true`, no masking present.

The 10 candidates reaching the LLM:

| Variable | Candidates | Reading (the human's call, not yet made) |
| --- | --- | --- |
| `g_ir_ticks_pending` | `RWW [240,131,244]` (planted); `WRW [244,131,244]`, which contains the same window; `RWR [240,131,240]` and `WWR [244,131,240]`, which are the counter's intended protocol across iterations | 1 defect, seen through 2 triples |
| `g_interrupt_count` (`imu.cpp`, pre-existing) | 4 × `RWR` between `dataReady()` (116) and `read()` (141); 2 × `WWR` from `begin()` zeroing the counter (95) after `attachInterrupt` (93) | probably benign by design: the task always consumes the latest count |

## Three problems it exposed

1. **Arity-matched indirect calls explode on C++.** Stage 1's fallback for an unresolved
   indirect call ([[Soundness Assumptions]] B2) matches targets by arity alone. Every virtual
   call has one argument, so the 8 unresolved `StopPolicy` virtual calls reached every task body
   (`void(void*)`) and constructors, and `setup` and `taskSupervisor` "ran" the whole control
   loop. `g_follower` alone, one `LineFollower` collapsed to its base object, had 408 accesses
   in 3 flows. The run finished only with `points-to-only`, **the unsound setting B2 forbids**.
   It was checked by hand that those 8 sites do not touch the planted defect. That is a
   hand-checked argument, not a guarantee from the tool.
   [#4](https://github.com/phMachad0/irqrace-ai/issues/4).
2. **Context-insensitive `this` fakes sharing.** The two local `RateMeter rate;` objects, one
   on each of two task stacks, are one object to a points-to analysis that cannot tell which
   caller's `this` it is looking at. That accounts for 2704 of the 2770 stage-1 candidates
   (98%), all false. Stage 2 removed them only because the two tasks happen to have different
   priorities on the same core. Precision only ([[Soundness Assumptions]] C2b).
   [#5](https://github.com/phMachad0/irqrace-ai/issues/5).
3. **The priority filter assumes one core.** 25 of the priority drops pair flows on *different*
   cores, which run in parallel on the ESP32. Examples are `g_imu_status` (`taskImu` core 1
   against `taskSupervisor` core 0, 12 triples) and `g_ir_overruns` (`taskLineSensor` against
   `taskTelemetry`, 2). Each was recorded as a proof and is not one. None hid the planted
   defect, which is ISR against task on one core ([[Soundness Assumptions]] E6). The sound
   configuration today is `rastro-robot-c1-flat.yaml`, with every flow at one priority. It was
   written but not run. [#6](https://github.com/phMachad0/irqrace-ai/issues/6).

## What the triage did

The run shows a ranking that works and a bucketing that does not.

- **Ranking works.** The planted defect is at the top: harmful 0.80, tied only with one of its
  own variants. The `g_interrupt_count` candidates score 0.55–0.70. Its reasoning names the
  mechanism exactly, "the task's clear at line 244 then discards that increment", and adds the
  right impact estimate: a diagnostic counter, because the ISR's task notification still wakes
  the next cycle.
- **Bucketing does not.** 9 of 10 land in `likely_real`. The harmfulness criterion fires on
  `feeds a branch` / `persistent shared state` almost mechanically, so a counter read whose
  every value is a legal snapshot is marked harmful because "I can't point to a specific reason
  for benignity". Only the polling re-read in `while (!dataReady())` got `likely_benign`. This
  is the [[Open Questions]] item on stating the benignity criterion, measured on code that has
  benign-by-design races. Racebench has almost none.
- **It guessed the hardware.** "The 32-bit volatile read is probably atomic" (on
  `c1843cbdccc5433c6`) is a platform fact the model had to assume, because nothing in the record
  says the target is an Xtensa LX6. It is the motivating case for declaring the hardware in C1
  and passing it to the model ([#7](https://github.com/phMachad0/irqrace-ai/issues/7)).
  Following [[LLM Triage]], that declaration may sharpen the ranking but must not license a
  discard.

Nothing was dropped by the LLM, and nothing could be: triage only buckets
([[Soundness Assumptions]] H3).

## Reproducing

The C1 files embed the full flag list. With the subject at the path above:

```bash
.venv/bin/irqrace stage3 ~/Downloads/rastro-robot-c1-prio.yaml -v
```

```bash
.venv/bin/irqrace llm triage runs/<run_id> --backend claude-cli:sonnet
```

Run from `project-src/`, with `scripts/env.sh` sourced. The project `.venv` is the interpreter
that has `pydantic`. The system `python3` behind `irqrace` does not have it.

## Relation to the rest of the wiki

- [[Candidate Evaluation Subjects]]: this is a fourth kind of subject, the human's own code,
  usable for planted-defect tests but not for recall measurement.
- [[Specification Inference]]: writing this C1 by hand took mangled names, PlatformIO metadata
  and a judgement about cores. The cores judgement is the one the schema could not record.
- [[Real-World Program Benchmark]]: the corpus's "real world" is single-file C extractions. This
  subject is the first multi-TU C++ program, and the first SMP one.
