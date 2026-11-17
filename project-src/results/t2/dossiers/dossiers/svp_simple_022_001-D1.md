# Dossier svp_simple_022_001/D1

**Case** `svp_simple_022_001` · **location** `svp_simple_022_001_global_var1` (`volatile int`, declared svp_simple_022_001.c:19) · **8 triple(s) to adjudicate** · run `svp_simple_022_001-20261115T134024Z-cb3385`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (32, 66, 39) | 2.1 trap 1 |
| (32, 66, 55) | 2.1 bug 1 |
| (32, 66, 63) | unannotated: cfd42dd7218774488 |
| (43, 66, 39) | unannotated: c6ef0659ec8021503 |
| (43, 66, 55) | unannotated: c757c52d642459c89 |
| (43, 66, 63) | unannotated: c730b88b509e5aa7e |
| (55, 66, 39) | unannotated: c2613aaf9ec1148ec |
| (55, 66, 56) | 2.1 trap 2 |
| (55, 66, 58) | 2.1 bug 2 |
| (55, 66, 63) | 2.1 trap 3 |
| (56, 66, 39) | unannotated: c816f84ad1fed7de0 |
| (56, 66, 63) | unannotated: c678d1bc26edf20ce |
| (58, 66, 39) | unannotated: c668997612f42c4ee |
| (58, 66, 63) | 2.1 bug 3 |
| (63, 66, 39) | 2.1 bug 4 |

Sibling links:

- E3: svp_simple_022_001@32-66-63 ~ svp_simple_022_001@43-66-63
- E3: svp_simple_022_001@32-66-63 ~ svp_simple_022_001@56-66-63
- E3: svp_simple_022_001@32-66-63 ~ svp_simple_022_001:bug:1
- E3: svp_simple_022_001@32-66-63 ~ svp_simple_022_001:bug:3
- E3: svp_simple_022_001@32-66-63 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001@32-66-63 ~ svp_simple_022_001:trap:1
- E3: svp_simple_022_001@32-66-63 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001@43-66-39 ~ svp_simple_022_001@43-66-55
- E3: svp_simple_022_001@43-66-39 ~ svp_simple_022_001@43-66-63
- E3: svp_simple_022_001@43-66-39 ~ svp_simple_022_001@55-66-39
- E3: svp_simple_022_001@43-66-39 ~ svp_simple_022_001@56-66-39
- E3: svp_simple_022_001@43-66-39 ~ svp_simple_022_001@58-66-39
- E3: svp_simple_022_001@43-66-39 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001@43-66-39 ~ svp_simple_022_001:trap:1
- E3: svp_simple_022_001@43-66-55 ~ svp_simple_022_001@43-66-63
- E3: svp_simple_022_001@43-66-55 ~ svp_simple_022_001@55-66-39
- E3: svp_simple_022_001@43-66-55 ~ svp_simple_022_001:bug:1
- E3: svp_simple_022_001@43-66-55 ~ svp_simple_022_001:bug:2
- E3: svp_simple_022_001@43-66-55 ~ svp_simple_022_001:trap:2
- E3: svp_simple_022_001@43-66-55 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001@43-66-63 ~ svp_simple_022_001@56-66-63
- E3: svp_simple_022_001@43-66-63 ~ svp_simple_022_001:bug:3
- E3: svp_simple_022_001@43-66-63 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001@43-66-63 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001@56-66-39
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001@58-66-39
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001:bug:1
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001:bug:2
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001:trap:1
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001:trap:2
- E3: svp_simple_022_001@55-66-39 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001@56-66-39 ~ svp_simple_022_001@56-66-63
- E3: svp_simple_022_001@56-66-39 ~ svp_simple_022_001@58-66-39
- E3: svp_simple_022_001@56-66-39 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001@56-66-39 ~ svp_simple_022_001:trap:1
- E3: svp_simple_022_001@56-66-39 ~ svp_simple_022_001:trap:2
- E3: svp_simple_022_001@56-66-63 ~ svp_simple_022_001:bug:3
- E3: svp_simple_022_001@56-66-63 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001@56-66-63 ~ svp_simple_022_001:trap:2
- E3: svp_simple_022_001@56-66-63 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001@58-66-39 ~ svp_simple_022_001:bug:2
- E3: svp_simple_022_001@58-66-39 ~ svp_simple_022_001:bug:3
- E3: svp_simple_022_001@58-66-39 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001@58-66-39 ~ svp_simple_022_001:trap:1
- E3: svp_simple_022_001:bug:1 ~ svp_simple_022_001:bug:2
- E3: svp_simple_022_001:bug:1 ~ svp_simple_022_001:trap:1
- E3: svp_simple_022_001:bug:1 ~ svp_simple_022_001:trap:2
- E3: svp_simple_022_001:bug:1 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001:bug:2 ~ svp_simple_022_001:bug:3
- E3: svp_simple_022_001:bug:2 ~ svp_simple_022_001:trap:2
- E3: svp_simple_022_001:bug:2 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001:bug:3 ~ svp_simple_022_001:bug:4
- E3: svp_simple_022_001:bug:3 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001:bug:4 ~ svp_simple_022_001:trap:1
- E3: svp_simple_022_001:bug:4 ~ svp_simple_022_001:trap:3
- E3: svp_simple_022_001:trap:2 ~ svp_simple_022_001:trap:3

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

`| 22   | svp_simple_022_001.c | svp_simple_022_001_main | svp_simple_022_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_022_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_022_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, main
- `writers.svp_simple_022_001_global_var1` [proven]: every store to svp_simple_022_001_global_var1 the analysis found (5): isr_1: svp_simple_022_001_isr_1 svp_simple_022/svp_simple_022_001.c:66 `svp_simple_022_001_global_var1 = 0;`; main: svp_simple_022_001_main svp_simple_022/svp_simple_022_001.c:32 `svp_simple_022_001_global_var1 = 0;`; main: svp_simple_022_001_init svp_simple_022/svp_simple_022_001.c:43 `svp_simple_022_001_global_var1 = rand();`; main: svp_simple_022_001_func_3 svp_simple_022/svp_simple_022_001.c:56 `svp_simple_022_001_global_var1 = 12;`; main: svp_simple_022_001_func_3 svp_simple_022/svp_simple_022_001.c:58 `svp_simple_022_001_global_var1 = 0;`. declared at svp_simple_022/svp_simple_022_001.c:19 `volatile int svp_simple_022_001_global_var1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.

## Triples

### T1. (32, 66, 63) — `svp_simple_022_001@32-66-63`

**Record `cfd42dd7218774488`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_022_001.c:32 | `svp_simple_022_001_main` | main | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:63 | `svp_simple_022_001_func_4` | main | irq 1 enabled | no | `svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 33 of `svp_simple_022_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 63, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 39 (read), line 43 (write), line 55 (read), line 56 (write), line 58 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 32, line 63] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 32, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 63, flow: main}
  candidate_ids: [cfd42dd7218774488]
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

### T2. (43, 66, 39) — `svp_simple_022_001@43-66-39`

**Record `c6ef0659ec8021503`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_022_001.c:43 | `svp_simple_022_001_init` | main | irq 1 enabled | no | `svp_simple_022_001_global_var1 = rand();` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:39 | `svp_simple_022_001_main` | main | irq 1 enabled | no | `svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 44 of `svp_simple_022_001_init`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 39, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write), line 55 (read), line 56 (write), line 58 (write), line 63 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 43, line 39] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 43, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 39, flow: main}
  candidate_ids: [c6ef0659ec8021503]
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

### T3. (43, 66, 55) — `svp_simple_022_001@43-66-55`

**Record `c757c52d642459c89`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_022_001.c:43 | `svp_simple_022_001_init` | main | irq 1 enabled | no | `svp_simple_022_001_global_var1 = rand();` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:55 | `svp_simple_022_001_func_3` | main | irq 1 enabled | no | `if (svp_simple_022_001_global_var1 >= 12) {` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 44 of `svp_simple_022_001_init`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 55, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write), line 39 (read), line 63 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 43, line 55] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 43, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 55, flow: main}
  candidate_ids: [c757c52d642459c89]
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

### T4. (43, 66, 63) — `svp_simple_022_001@43-66-63`

**Record `c730b88b509e5aa7e`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_022_001.c:43 | `svp_simple_022_001_init` | main | irq 1 enabled | no | `svp_simple_022_001_global_var1 = rand();` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:63 | `svp_simple_022_001_func_4` | main | irq 1 enabled | no | `svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 44 of `svp_simple_022_001_init`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 63, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write), line 39 (read), line 55 (read), line 56 (write), line 58 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 43, line 63] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 43, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 63, flow: main}
  candidate_ids: [c730b88b509e5aa7e]
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

### T5. (55, 66, 39) — `svp_simple_022_001@55-66-39`

**Record `c2613aaf9ec1148ec`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_022_001.c:55 | `svp_simple_022_001_func_3` | main | irq 1 enabled | no | `if (svp_simple_022_001_global_var1 >= 12) {` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:39 | `svp_simple_022_001_main` | main | irq 1 enabled | no | `svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 55 of `svp_simple_022_001_func_3`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 55, read): reaches a branch condition; A2 (line 39, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write), line 43 (write), line 56 (write), line 58 (write), line 63 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 55, line 39] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 55, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 39, flow: main}
  candidate_ids: [c2613aaf9ec1148ec]
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

### T6. (56, 66, 39) — `svp_simple_022_001@56-66-39`

**Record `c816f84ad1fed7de0`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_022_001.c:56 | `svp_simple_022_001_func_3` | main | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 12;` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:39 | `svp_simple_022_001_main` | main | irq 1 enabled | no | `svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 57 of `svp_simple_022_001_func_3`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 39, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write), line 43 (write), line 63 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 56, line 39] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 56, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 39, flow: main}
  candidate_ids: [c816f84ad1fed7de0]
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

### T7. (56, 66, 63) — `svp_simple_022_001@56-66-63`

**Record `c678d1bc26edf20ce`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_022_001.c:56 | `svp_simple_022_001_func_3` | main | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 12;` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:63 | `svp_simple_022_001_func_4` | main | irq 1 enabled | no | `svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 57 of `svp_simple_022_001_func_3`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 63, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write), line 39 (read), line 43 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 56, line 63] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 56, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 63, flow: main}
  candidate_ids: [c678d1bc26edf20ce]
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

### T8. (58, 66, 39) — `svp_simple_022_001@58-66-39`

**Record `c668997612f42c4ee`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_022_001.c:58 | `svp_simple_022_001_func_3` | main | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| B | write | svp_simple_022_001.c:66 | `svp_simple_022_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_022_001_global_var1 = 0;` |
| A2 | read | svp_simple_022_001.c:39 | `svp_simple_022_001_main` | main | irq 1 enabled | no | `svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 0 of `svp_simple_022_001_func_3`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 39, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write), line 43 (write), line 63 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 58, line 39] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_022_001
  variable: svp_simple_022_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 58, flow: main}
    - {role: B, kind: write, line: 66, flow: isr_1}
    - {role: A2, kind: read, line: 39, flow: main}
  candidate_ids: [c668997612f42c4ee]
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

Top level of `svp_simple_022_001.c` before its first function:

```c
19  volatile int svp_simple_022_001_global_var1;
20  volatile int svp_simple_022_001_global_var2;
21  volatile int svp_simple_022_001_global_var3;
22  volatile int svp_simple_022_001_global_array[256];
23  void svp_simple_022_001_func_1();
24  void svp_simple_022_001_func_2();
25  void svp_simple_022_001_func_3();
26  void svp_simple_022_001_func_4();
27  void svp_simple_022_001_init();
```

`svp_simple_022_001_main` — svp_simple_022_001.c:29-40

```c
29  void svp_simple_022_001_main() {
30    svp_simple_022_001_init();
31  
32    svp_simple_022_001_global_var1 = 0;  
33    svp_simple_022_001_func_1();
34    int i;
35    for (i = 0; i < 256; i++) {
36      svp_simple_022_001_global_array[i] = 0;
37    }
38    svp_simple_022_001_func_2();
39    svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1; 
40  }
```

`svp_simple_022_001_isr_1` — svp_simple_022_001.c:65-67

```c
65  void svp_simple_022_001_isr_1() {
66    svp_simple_022_001_global_var1 = 0; 
67  }
```

`svp_simple_022_001_func_4` — svp_simple_022_001.c:62-64

```c
62  void svp_simple_022_001_func_4() {
63    svp_simple_022_001_global_var3 = svp_simple_022_001_global_var1;  
64  }
```

`svp_simple_022_001_func_2` — svp_simple_022_001.c:52-52

```c
52  void svp_simple_022_001_func_2() { svp_simple_022_001_func_4(); }
```

`svp_simple_022_001_init` — svp_simple_022_001.c:42-48

```c
42  void svp_simple_022_001_init() {
43    svp_simple_022_001_global_var1 = rand();
44    svp_simple_022_001_global_var2 = rand();
45    svp_simple_022_001_global_var3 = rand();
46  
47    init();
48  }
```

`svp_simple_022_001_func_3` — svp_simple_022_001.c:54-60

```c
54  void svp_simple_022_001_func_3() {
55    if (svp_simple_022_001_global_var1 >= 12) { 
56      svp_simple_022_001_global_var1 = 12;       
57    } else {
58      svp_simple_022_001_global_var1 = 0;  
59    }
60  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```

`svp_simple_022_001_func_1` — svp_simple_022_001.c:50-50

```c
50  void svp_simple_022_001_func_1() { svp_simple_022_001_func_3(); }
```
