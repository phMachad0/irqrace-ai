# Dossier svp_simple_007_001/D1

**Case** `svp_simple_007_001` · **location** `svp_simple_007_001_global_array` (`volatile int[]`, declared svp_simple_007_001.c:24) · **9 triple(s) to adjudicate** · run `svp_simple_007_001-20261115T133849Z-a0418b`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (32, 47, 34) | unannotated: c18edcb43dcbb1aa1 |
| (32, 47, 42) | unannotated: cf91a346404508789 |
| (32, 50, 34) | 2.1 trap 1 |
| (32, 50, 42) | unannotated: cf6736884ab765c12 |
| (34, 47, 38) | unannotated: c2aa132697940e16d |
| (34, 47, 42) | unannotated: c25cc5f3be92d2430 |
| (34, 50, 38) | unannotated: cdee09b51b3064ed6 |
| (34, 50, 40) | unannotated: ccd333f4960c0d7d2 |
| (34, 50, 42) | unannotated: ce53c2d336ec42f89 |
| (38, 47, 42) | 2.1 bug 1 |
| (38, 50, 42) | unannotated: cc9746b918d0f7f3f |
| (40, 47, 42) | 2.1 trap 2 |

Sibling links:

- E3: svp_simple_007_001@32-47-34 ~ svp_simple_007_001@32-47-42
- E3: svp_simple_007_001@32-47-34 ~ svp_simple_007_001@34-47-38
- E3: svp_simple_007_001@32-47-34 ~ svp_simple_007_001@34-47-42
- E2: svp_simple_007_001@32-47-34 ~ svp_simple_007_001:trap:1
- E2: svp_simple_007_001@32-47-42 ~ svp_simple_007_001@32-50-42
- E3: svp_simple_007_001@32-47-42 ~ svp_simple_007_001@34-47-42
- E3: svp_simple_007_001@32-47-42 ~ svp_simple_007_001:bug:1
- E3: svp_simple_007_001@32-47-42 ~ svp_simple_007_001:trap:2
- E3: svp_simple_007_001@32-50-42 ~ svp_simple_007_001@34-50-42
- E3: svp_simple_007_001@32-50-42 ~ svp_simple_007_001@38-50-42
- E3: svp_simple_007_001@32-50-42 ~ svp_simple_007_001:trap:1
- E3: svp_simple_007_001@34-47-38 ~ svp_simple_007_001@34-47-42
- E2: svp_simple_007_001@34-47-38 ~ svp_simple_007_001@34-50-38
- E3: svp_simple_007_001@34-47-38 ~ svp_simple_007_001:bug:1
- E2: svp_simple_007_001@34-47-42 ~ svp_simple_007_001@34-50-42
- E3: svp_simple_007_001@34-47-42 ~ svp_simple_007_001:bug:1
- E3: svp_simple_007_001@34-47-42 ~ svp_simple_007_001:trap:2
- E3: svp_simple_007_001@34-50-38 ~ svp_simple_007_001@34-50-40
- E3: svp_simple_007_001@34-50-38 ~ svp_simple_007_001@34-50-42
- E3: svp_simple_007_001@34-50-38 ~ svp_simple_007_001@38-50-42
- E3: svp_simple_007_001@34-50-38 ~ svp_simple_007_001:trap:1
- E3: svp_simple_007_001@34-50-40 ~ svp_simple_007_001@34-50-42
- E3: svp_simple_007_001@34-50-40 ~ svp_simple_007_001:trap:1
- E3: svp_simple_007_001@34-50-42 ~ svp_simple_007_001@38-50-42
- E3: svp_simple_007_001@34-50-42 ~ svp_simple_007_001:trap:1
- E2: svp_simple_007_001@38-50-42 ~ svp_simple_007_001:bug:1
- E3: svp_simple_007_001:bug:1 ~ svp_simple_007_001:trap:2

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

`| 7    | svp_simple_007_001.c | svp_simple_007_001_main | svp_simple_007_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_007_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_007_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 8 is reached from flows isr_1, main
- `writers.svp_simple_007_001_global_array` [proven]: every store to svp_simple_007_001_global_array the analysis found (5): isr_1: svp_simple_007_001_isr_1 svp_simple_007/svp_simple_007_001.c:47 `svp_simple_007_001_global_array[2] = 0x09;`; isr_1: svp_simple_007_001_isr_1 svp_simple_007/svp_simple_007_001.c:50 `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x09;`; main: svp_simple_007_001_main svp_simple_007/svp_simple_007_001.c:32 `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x01;`; main: svp_simple_007_001_main svp_simple_007/svp_simple_007_001.c:38 `svp_simple_007_001_global_array[i] = 0x02;`; main: svp_simple_007_001_main svp_simple_007/svp_simple_007_001.c:40 `svp_simple_007_001_global_array[i] = 0x09;`. declared at svp_simple_007/svp_simple_007_001.c:24 `volatile int svp_simple_007_001_global_array[5];`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_007_001_global_var` [proven]: every store to svp_simple_007_001_global_var the analysis found (1): isr_1: svp_simple_007_001_isr_1 svp_simple_007/svp_simple_007_001.c:49 `svp_simple_007_001_global_var += 1;`. declared at svp_simple_007/svp_simple_007_001.c:22 `volatile int svp_simple_007_001_global_var;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.

## Triples

### T1. (32, 47, 34) — `svp_simple_007_001@32-47-34`

**Record `c18edcb43dcbb1aa1`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_007_001.c:32 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x01;` |
| B | write | svp_simple_007_001.c:47 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[2] = 0x09;` |
| A2 | read | svp_simple_007_001.c:34 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader2 = svp_simple_007_001_global_array[svp_simple_007_001_global_var];` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 34, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_1 may run within [line 32, line 34] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 32, flow: main}
    - {role: B, kind: write, line: 47, flow: isr_1}
    - {role: A2, kind: read, line: 34, flow: main}
  candidate_ids: [c18edcb43dcbb1aa1]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T2. (32, 47, 42) — `svp_simple_007_001@32-47-42`

**Record `cf91a346404508789`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_007_001.c:32 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x01;` |
| B | write | svp_simple_007_001.c:47 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[2] = 0x09;` |
| A2 | read | svp_simple_007_001.c:42 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader1 = svp_simple_007_001_global_array[2];` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 42, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 34 (read), line 38 (write), line 40 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 32, line 42] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 32, flow: main}
    - {role: B, kind: write, line: 47, flow: isr_1}
    - {role: A2, kind: read, line: 42, flow: main}
  candidate_ids: [cf91a346404508789]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T3. (32, 50, 42) — `svp_simple_007_001@32-50-42`

**Record `cf6736884ab765c12`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_007_001.c:32 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x01;` |
| B | write | svp_simple_007_001.c:50 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x09;` |
| A2 | read | svp_simple_007_001.c:42 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader1 = svp_simple_007_001_global_array[2];` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 42, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 34 (read), line 38 (write), line 40 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 32, line 42] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 32, flow: main}
    - {role: B, kind: write, line: 50, flow: isr_1}
    - {role: A2, kind: read, line: 42, flow: main}
  candidate_ids: [cf6736884ab765c12]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T4. (34, 47, 38) — `svp_simple_007_001@34-47-38`

**Record `c2aa132697940e16d`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_007_001.c:34 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader2 = svp_simple_007_001_global_array[svp_simple_007_001_global_var];` |
| B | write | svp_simple_007_001.c:47 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[2] = 0x09;` |
| A2 | write | svp_simple_007_001.c:38 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `svp_simple_007_001_global_array[i] = 0x02;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 34, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_1 may run within [line 34, line 38] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 34, flow: main}
    - {role: B, kind: write, line: 47, flow: isr_1}
    - {role: A2, kind: write, line: 38, flow: main}
  candidate_ids: [c2aa132697940e16d]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWW
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T5. (34, 47, 42) — `svp_simple_007_001@34-47-42`

**Record `c25cc5f3be92d2430`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_007_001.c:34 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader2 = svp_simple_007_001_global_array[svp_simple_007_001_global_var];` |
| B | write | svp_simple_007_001.c:47 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[2] = 0x09;` |
| A2 | read | svp_simple_007_001.c:42 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader1 = svp_simple_007_001_global_array[2];` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 34, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 42, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 38 (write), line 40 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 34, line 42] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 34, flow: main}
    - {role: B, kind: write, line: 47, flow: isr_1}
    - {role: A2, kind: read, line: 42, flow: main}
  candidate_ids: [c25cc5f3be92d2430]
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

### T6. (34, 50, 38) — `svp_simple_007_001@34-50-38`

**Record `cdee09b51b3064ed6`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_007_001.c:34 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader2 = svp_simple_007_001_global_array[svp_simple_007_001_global_var];` |
| B | write | svp_simple_007_001.c:50 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x09;` |
| A2 | write | svp_simple_007_001.c:38 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `svp_simple_007_001_global_array[i] = 0x02;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 34, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_1 may run within [line 34, line 38] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 34, flow: main}
    - {role: B, kind: write, line: 50, flow: isr_1}
    - {role: A2, kind: write, line: 38, flow: main}
  candidate_ids: [cdee09b51b3064ed6]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWW
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T7. (34, 50, 40) — `svp_simple_007_001@34-50-40`

**Record `ccd333f4960c0d7d2`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_007_001.c:34 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader2 = svp_simple_007_001_global_array[svp_simple_007_001_global_var];` |
| B | write | svp_simple_007_001.c:50 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x09;` |
| A2 | write | svp_simple_007_001.c:40 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `svp_simple_007_001_global_array[i] = 0x09;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 34, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_1 may run within [line 34, line 40] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 34, flow: main}
    - {role: B, kind: write, line: 50, flow: isr_1}
    - {role: A2, kind: write, line: 40, flow: main}
  candidate_ids: [ccd333f4960c0d7d2]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape RWW
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T8. (34, 50, 42) — `svp_simple_007_001@34-50-42`

**Record `ce53c2d336ec42f89`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_007_001.c:34 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader2 = svp_simple_007_001_global_array[svp_simple_007_001_global_var];` |
| B | write | svp_simple_007_001.c:50 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x09;` |
| A2 | read | svp_simple_007_001.c:42 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader1 = svp_simple_007_001_global_array[2];` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 34, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 42, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 38 (write), line 40 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 34, line 42] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 34, flow: main}
    - {role: B, kind: write, line: 50, flow: isr_1}
    - {role: A2, kind: read, line: 42, flow: main}
  candidate_ids: [ce53c2d336ec42f89]
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

### T9. (38, 50, 42) — `svp_simple_007_001@38-50-42`

**Record `cc9746b918d0f7f3f`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_007_001.c:38 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `svp_simple_007_001_global_array[i] = 0x02;` |
| B | write | svp_simple_007_001.c:50 | `svp_simple_007_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x09;` |
| A2 | read | svp_simple_007_001.c:42 | `svp_simple_007_001_main` | main | irq 1 enabled | no | `reader1 = svp_simple_007_001_global_array[2];` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 38 of `svp_simple_007_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 42, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_1 may run within [line 38, line 42] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_007_001
  variable: svp_simple_007_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 38, flow: main}
    - {role: B, kind: write, line: 50, flow: isr_1}
    - {role: A2, kind: read, line: 42, flow: main}
  candidate_ids: [cc9746b918d0f7f3f]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

## Source

Top level of `svp_simple_007_001.c` before its first function:

```c
19  #define MAX_LENGTH 10000
20  #define TRIGGER 9999
21  
22  volatile int svp_simple_007_001_global_var;
23  
24  volatile int svp_simple_007_001_global_array[5];
```

`svp_simple_007_001_main` — svp_simple_007_001.c:26-43

```c
26  void svp_simple_007_001_main() {
27    init();
28    int reader1, reader2;
29  
30    
31  
32    svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x01;
33  
34    reader2 = svp_simple_007_001_global_array[svp_simple_007_001_global_var];
35  
36    int i = rand();
37    if (i == 2)
38      svp_simple_007_001_global_array[i] = 0x02;
39    else
40      svp_simple_007_001_global_array[i] = 0x09;
41  
42    reader1 = svp_simple_007_001_global_array[2];
43  }
```

`svp_simple_007_001_isr_1` — svp_simple_007_001.c:45-51

```c
45  void svp_simple_007_001_isr_1() {
46    idlerun();
47    svp_simple_007_001_global_array[2] = 0x09;
48  
49    svp_simple_007_001_global_var += 1;
50    svp_simple_007_001_global_array[svp_simple_007_001_global_var] = 0x09;
51  }
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
