# Dossier svp_simple_017_001/D1

**Case** `svp_simple_017_001` · **location** `svp_simple_017_001_global_var` (`volatile int`, declared svp_simple_017_001.c:22) · **5 triple(s) to adjudicate** · run `svp_simple_017_001-20261115T133941Z-58c820`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (29, 39, 29) | 2.1 bug 1 |
| (29, 39, 30) | unannotated: c502edb5b32abb573, cd1bcdf969ef2e17b, cf22a34950f93f3fa |
| (29, 39, 32) | 2.1 bug 2 |
| (30, 39, 29) | 2.1 bug 4 |
| (30, 39, 30) | unannotated: cc25084cc708088cd, cdb7746881d4c38cf, ce1d5fc2497a40fba |
| (30, 39, 32) | unannotated: c4abd07637bf6c106, ca38d49e4dedbfa17 |
| (32, 39, 29) | unannotated: c3ab8671ec05ae70c |
| (32, 39, 30) | 2.1 bug 3 |
| (32, 39, 32) | unannotated: c6a131ebb5b01e4b2 |

Sibling links:

- E3: svp_simple_017_001@29-39-30 ~ svp_simple_017_001@30-39-30
- E3: svp_simple_017_001@29-39-30 ~ svp_simple_017_001@30-39-32
- E3: svp_simple_017_001@29-39-30 ~ svp_simple_017_001@32-39-29
- E3: svp_simple_017_001@29-39-30 ~ svp_simple_017_001:bug:1
- E3: svp_simple_017_001@29-39-30 ~ svp_simple_017_001:bug:2
- E3: svp_simple_017_001@29-39-30 ~ svp_simple_017_001:bug:3
- E3: svp_simple_017_001@29-39-30 ~ svp_simple_017_001:bug:4
- E3: svp_simple_017_001@30-39-30 ~ svp_simple_017_001@30-39-32
- E3: svp_simple_017_001@30-39-30 ~ svp_simple_017_001:bug:3
- E3: svp_simple_017_001@30-39-30 ~ svp_simple_017_001:bug:4
- E3: svp_simple_017_001@30-39-32 ~ svp_simple_017_001@32-39-29
- E3: svp_simple_017_001@30-39-32 ~ svp_simple_017_001@32-39-32
- E3: svp_simple_017_001@30-39-32 ~ svp_simple_017_001:bug:2
- E3: svp_simple_017_001@30-39-32 ~ svp_simple_017_001:bug:3
- E3: svp_simple_017_001@30-39-32 ~ svp_simple_017_001:bug:4
- E3: svp_simple_017_001@32-39-29 ~ svp_simple_017_001@32-39-32
- E3: svp_simple_017_001@32-39-29 ~ svp_simple_017_001:bug:1
- E3: svp_simple_017_001@32-39-29 ~ svp_simple_017_001:bug:2
- E3: svp_simple_017_001@32-39-29 ~ svp_simple_017_001:bug:3
- E3: svp_simple_017_001@32-39-29 ~ svp_simple_017_001:bug:4
- E3: svp_simple_017_001@32-39-32 ~ svp_simple_017_001:bug:2
- E3: svp_simple_017_001@32-39-32 ~ svp_simple_017_001:bug:3
- E3: svp_simple_017_001:bug:1 ~ svp_simple_017_001:bug:2
- E3: svp_simple_017_001:bug:1 ~ svp_simple_017_001:bug:4
- E3: svp_simple_017_001:bug:2 ~ svp_simple_017_001:bug:3
- E3: svp_simple_017_001:bug:2 ~ svp_simple_017_001:bug:4
- E3: svp_simple_017_001:bug:3 ~ svp_simple_017_001:bug:4

The suite's own labels are listed because the grouping uses them. They are not evidence about the triples below: the suite plants traps as siblings of its bug points (12 of 2.1's groups mix the two), so every triple gets its own verdict.

## Interrupt model

README of the suite (original, then the project's translation):

> 测试用例不考虑中断的周期性，中断可以在允许中断的情况下打断主程序或者低级中断，打断的时刻不定，位置不定，次数不定。
>
> *Test cases do not consider the periodicity of interrupts: an interrupt may preempt the main program or a lower-priority interrupt whenever it is enabled, at an indeterminate moment, position and number of times.*

> 中断号用于测试用例中提供的中断开关函数。enable_isr(n)和disable_isr(n)可视为unlock和lock原语。其中n表示中断号，当n为-1时，表示屏蔽/打开所有中断。
>
> *Interrupt numbers are those used by the interrupt switch functions the cases provide. enable_isr(n) and disable_isr(n) can be treated as unlock and lock primitives; n is the interrupt number, and n = -1 means masking / unmasking all interrupts.*

> 优先级数字越大，优先级越高
>
> *A larger priority number means a higher priority.*

Case row of the README table (case, main entry, handler/irq/priority):

`| 17   | svp_simple_017_001.c | svp_simple_017_001_main | svp_simple_017_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_017_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_017_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, main
- `writers.svp_simple_017_001_global_var` [proven]: every store to svp_simple_017_001_global_var the analysis found (3): isr_1: svp_simple_017_001_isr_1 svp_simple_017/svp_simple_017_001.c:39 `svp_simple_017_001_global_var = TRIGGER;`; main: svp_simple_017_001_main svp_simple_017/svp_simple_017_001.c:29 `for (svp_simple_017_001_global_var = 0; svp_simple_017_001_global_var < MAX_LENGTH;`; main: svp_simple_017_001_main svp_simple_017/svp_simple_017_001.c:30 `svp_simple_017_001_global_var++)`. declared at svp_simple_017/svp_simple_017_001.c:22 `volatile int svp_simple_017_001_global_var;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `macros` [proven]: definitions of macros the shipped code uses: MAX_LENGTH = 100 (svp_simple_017/svp_simple_017_001.c:19); TRIGGER = 50 (svp_simple_017/svp_simple_017_001.c:20)

## Triples

### T1. (29, 39, 30) — `svp_simple_017_001@29-39-30`

**Record `c502edb5b32abb573`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_017_001.c:29 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `for (svp_simple_017_001_global_var = 0; svp_simple_017_001_global_var < MAX_LENGTH;` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | write | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 29 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 29, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 30 (read), line 32 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 29, line 30] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

**Record `cd1bcdf969ef2e17b`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_017_001.c:29 | `svp_simple_017_001_main` | main | irq 1 enabled | no | `for (svp_simple_017_001_global_var = 0; svp_simple_017_001_global_var < MAX_LENGTH;` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 29 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 30, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 29 (read), line 30 (write), line 32 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 29, line 30] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

**Record `cf22a34950f93f3fa`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_017_001.c:29 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `for (svp_simple_017_001_global_var = 0; svp_simple_017_001_global_var < MAX_LENGTH;` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 29 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 29, read): reaches a branch condition; A2 (line 30, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 30 (write), line 32 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 29, line 30] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_017_001
  variable: svp_simple_017_001_global_var
  triple:            # A1, B, A2
  # the tool reports these lines with kinds RWR, RWW, WWR; keep the kinds the witness uses
    - {role: A1, kind: read, line: 29, flow: main}
    - {role: B, kind: write, line: 39, flow: isr_1}
    - {role: A2, kind: write, line: 30, flow: main}
  candidate_ids: [c502edb5b32abb573, cd1bcdf969ef2e17b, cf22a34950f93f3fa]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWR/RWW/WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T2. (30, 39, 30) — `svp_simple_017_001@30-39-30`

**Record `cc25084cc708088cd`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 29 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 30, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 29 (read), line 32 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 30, line 30] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

**Record `cdb7746881d4c38cf`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | write | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 30 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 30, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 29 (read), line 32 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 30, line 30] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

**Record `ce1d5fc2497a40fba`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 30 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 30, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced; A2 (line 30, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 29 (read), line 30 (write), line 32 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 30, line 30] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_017_001
  variable: svp_simple_017_001_global_var
  triple:            # A1, B, A2
  # the tool reports these lines with kinds RWR, RWW, WWR; keep the kinds the witness uses
    - {role: A1, kind: write, line: 30, flow: main}
    - {role: B, kind: write, line: 39, flow: isr_1}
    - {role: A2, kind: read, line: 30, flow: main}
  candidate_ids: [cc25084cc708088cd, cdb7746881d4c38cf, ce1d5fc2497a40fba]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWR/RWW/WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T3. (30, 39, 32) — `svp_simple_017_001@30-39-32`

**Record `c4abd07637bf6c106`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:32 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_local_array[svp_simple_017_001_global_var] = i++;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 29 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 32, read): reaches an array index
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 29 (read), line 30 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 30, line 32] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

**Record `ca38d49e4dedbfa17`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_017_001.c:30 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_global_var++)` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:32 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_local_array[svp_simple_017_001_global_var] = i++;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 30 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 30, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced; A2 (line 32, read): reaches an array index
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 29 (read), line 30 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 30, line 32] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_017_001
  variable: svp_simple_017_001_global_var
  triple:            # A1, B, A2
  # the tool reports these lines with kinds RWR, WWR; keep the kinds the witness uses
    - {role: A1, kind: write, line: 30, flow: main}
    - {role: B, kind: write, line: 39, flow: isr_1}
    - {role: A2, kind: read, line: 32, flow: main}
  candidate_ids: [c4abd07637bf6c106, ca38d49e4dedbfa17]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWR/WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T4. (32, 39, 29) — `svp_simple_017_001@32-39-29`

**Record `c3ab8671ec05ae70c`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_017_001.c:32 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_local_array[svp_simple_017_001_global_var] = i++;` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:29 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `for (svp_simple_017_001_global_var = 0; svp_simple_017_001_global_var < MAX_LENGTH;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 32 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 32, read): reaches an array index; A2 (line 29, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 30 (read), line 30 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 32, line 29] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_017_001
  variable: svp_simple_017_001_global_var
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 32, flow: main}
    - {role: B, kind: write, line: 39, flow: isr_1}
    - {role: A2, kind: read, line: 29, flow: main}
  candidate_ids: [c3ab8671ec05ae70c]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T5. (32, 39, 32) — `svp_simple_017_001@32-39-32`

**Record `c6a131ebb5b01e4b2`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_017_001.c:32 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_local_array[svp_simple_017_001_global_var] = i++;` |
| B | write | svp_simple_017_001.c:39 | `svp_simple_017_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_017_001_global_var = TRIGGER;` |
| A2 | read | svp_simple_017_001.c:32 | `svp_simple_017_001_main` | main | irq 1 enabled | yes (header 29) | `svp_simple_017_001_local_array[svp_simple_017_001_global_var] = i++;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 32 of `svp_simple_017_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 32, read): reaches an array index; A2 (line 32, read): reaches an array index
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 29 (read), line 30 (read), line 30 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 32, line 32] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_017_001
  variable: svp_simple_017_001_global_var
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 32, flow: main}
    - {role: B, kind: write, line: 39, flow: isr_1}
    - {role: A2, kind: read, line: 32, flow: main}
  candidate_ids: [c6a131ebb5b01e4b2]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

## Source

Top level of `svp_simple_017_001.c` before its first function:

```c
19  #define MAX_LENGTH 100
20  #define TRIGGER 50
21  
22  volatile int svp_simple_017_001_global_var;
23  volatile int svp_simple_017_001_local_array[MAX_LENGTH];
```

`svp_simple_017_001_main` — svp_simple_017_001.c:25-34

```c
25  void svp_simple_017_001_main() {
26    init();
27    int i = 0;
28  
29    for (svp_simple_017_001_global_var = 0; svp_simple_017_001_global_var < MAX_LENGTH;
30         svp_simple_017_001_global_var++)
31    {
32      svp_simple_017_001_local_array[svp_simple_017_001_global_var] = i++;
33    }
34  }
```

`svp_simple_017_001_isr_1` — svp_simple_017_001.c:36-42

```c
36  void svp_simple_017_001_isr_1() {
37    idlerun();
38  
39    svp_simple_017_001_global_var = TRIGGER;
40  
41    svp_simple_017_001_local_array[TRIGGER] = 0;
42  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```

`idlerun` — common.c:18-23

```c
18  void idlerun() {
19    int i = 0;
20    for (i = 0; i <= 100; i++) {
21      //		print2("Running....");
22    }
23  }
```
