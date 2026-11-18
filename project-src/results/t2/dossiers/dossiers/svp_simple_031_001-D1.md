# Dossier svp_simple_031_001/D1

**Case** `svp_simple_031_001` · **location** `svp_simple_031_001_tc_block_rcvd_bytes_ch1` (`volatile unsigned16`, declared svp_simple_031_001.c:25) · **7 triple(s) to adjudicate** · run `svp_simple_031_001-20261115T134202Z-089d5a`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (46, 90, 65) | unannotated: c4fb991e08f8f4d8f |
| (46, 90, 83) | 2.1 bug 1 |
| (46, 90, 85) | unannotated: c7c2151d22b1c78e0 |
| (73, 90, 46) | unannotated: c840fad6c904b5273 |
| (73, 90, 65) | unannotated: c821a3a052824c724 |
| (73, 90, 83) | unannotated: c972c69d779adeb88 |
| (73, 90, 85) | unannotated: c169e80e5a66908b6 |
| (83, 90, 65) | unannotated: ceea334fffb35ec48 |
| (83, 90, 85) | 2.1 bug 2 |
| (85, 90, 65) | 2.1 bug 3 |

Sibling links:

- E3: svp_simple_031_001@46-90-65 ~ svp_simple_031_001@46-90-85
- E3: svp_simple_031_001@46-90-65 ~ svp_simple_031_001@73-90-46
- E3: svp_simple_031_001@46-90-65 ~ svp_simple_031_001@73-90-65
- E3: svp_simple_031_001@46-90-65 ~ svp_simple_031_001@83-90-65
- E3: svp_simple_031_001@46-90-65 ~ svp_simple_031_001:bug:1
- E3: svp_simple_031_001@46-90-65 ~ svp_simple_031_001:bug:3
- E3: svp_simple_031_001@46-90-85 ~ svp_simple_031_001@73-90-46
- E3: svp_simple_031_001@46-90-85 ~ svp_simple_031_001@73-90-85
- E3: svp_simple_031_001@46-90-85 ~ svp_simple_031_001:bug:1
- E3: svp_simple_031_001@46-90-85 ~ svp_simple_031_001:bug:2
- E3: svp_simple_031_001@46-90-85 ~ svp_simple_031_001:bug:3
- E3: svp_simple_031_001@73-90-46 ~ svp_simple_031_001@73-90-65
- E3: svp_simple_031_001@73-90-46 ~ svp_simple_031_001@73-90-83
- E3: svp_simple_031_001@73-90-46 ~ svp_simple_031_001@73-90-85
- E3: svp_simple_031_001@73-90-46 ~ svp_simple_031_001:bug:1
- E3: svp_simple_031_001@73-90-65 ~ svp_simple_031_001@73-90-83
- E3: svp_simple_031_001@73-90-65 ~ svp_simple_031_001@73-90-85
- E3: svp_simple_031_001@73-90-65 ~ svp_simple_031_001@83-90-65
- E3: svp_simple_031_001@73-90-65 ~ svp_simple_031_001:bug:3
- E3: svp_simple_031_001@73-90-83 ~ svp_simple_031_001@73-90-85
- E3: svp_simple_031_001@73-90-83 ~ svp_simple_031_001@83-90-65
- E3: svp_simple_031_001@73-90-83 ~ svp_simple_031_001:bug:1
- E3: svp_simple_031_001@73-90-83 ~ svp_simple_031_001:bug:2
- E3: svp_simple_031_001@73-90-85 ~ svp_simple_031_001:bug:2
- E3: svp_simple_031_001@73-90-85 ~ svp_simple_031_001:bug:3
- E3: svp_simple_031_001@83-90-65 ~ svp_simple_031_001:bug:1
- E3: svp_simple_031_001@83-90-65 ~ svp_simple_031_001:bug:2
- E3: svp_simple_031_001@83-90-65 ~ svp_simple_031_001:bug:3
- E3: svp_simple_031_001:bug:1 ~ svp_simple_031_001:bug:2
- E3: svp_simple_031_001:bug:2 ~ svp_simple_031_001:bug:3

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

`| 31   | svp_simple_031_001.c | svp_simple_031_001_main | svp_simple_031_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_031_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_031_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 12 is reached from flows isr_1, main
- `writers.svp_simple_031_001_tc_block_rcvd_bytes_ch1` [proven]: every store to svp_simple_031_001_tc_block_rcvd_bytes_ch1 the analysis found (2): isr_1: svp_simple_031_001_isr_1 svp_simple_031/svp_simple_031_001.c:90 `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =`; main: svp_simple_031_001_init svp_simple_031/svp_simple_031_001.c:73 `svp_simple_031_001_tc_block_rcvd_bytes_ch1 = rand();`. declared at svp_simple_031/svp_simple_031_001.c:25 `volatile unsigned16 svp_simple_031_001_tc_block_rcvd_bytes_ch1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `macros` [proven]: definitions of macros the shipped code uses: svp_simple_031_001_CNT = (volatile unsigned int *)0x10000000 (svp_simple_031/svp_simple_031_001.c:24)

## Triples

### T1. (46, 90, 65) — `svp_simple_031_001@46-90-65`

**Record `c4fb991e08f8f4d8f`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_031_001.c:46 | `svp_simple_031_001_main` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1;` |
| B | write | svp_simple_031_001.c:90 | `svp_simple_031_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_031_001.c:65 | `svp_simple_031_001_func_2` | main | irq 1 enabled | no | `if (svp_simple_031_001_tc_block_rcvd_bytes_ch1 > 0) {` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 45 of `svp_simple_031_001_main`; left unconstrained: interference, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 46, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced; A2 (line 65, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 73 (write), line 83 (read), line 85 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 46, line 65] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_031_001
  variable: svp_simple_031_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 46, flow: main}
    - {role: B, kind: write, line: 90, flow: isr_1}
    - {role: A2, kind: read, line: 65, flow: main}
  candidate_ids: [c4fb991e08f8f4d8f]
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

### T2. (46, 90, 85) — `svp_simple_031_001@46-90-85`

**Record `c7c2151d22b1c78e0`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_031_001.c:46 | `svp_simple_031_001_main` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1;` |
| B | write | svp_simple_031_001.c:90 | `svp_simple_031_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_031_001.c:85 | `svp_simple_031_001_func_3` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1);` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 45 of `svp_simple_031_001_main`; left unconstrained: interference, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 46, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced; A2 (line 85, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 65 (read), line 73 (write), line 83 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 46, line 85] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_031_001
  variable: svp_simple_031_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 46, flow: main}
    - {role: B, kind: write, line: 90, flow: isr_1}
    - {role: A2, kind: read, line: 85, flow: main}
  candidate_ids: [c7c2151d22b1c78e0]
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

### T3. (73, 90, 46) — `svp_simple_031_001@73-90-46`

**Record `c840fad6c904b5273`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_031_001.c:73 | `svp_simple_031_001_init` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 = rand();` |
| B | write | svp_simple_031_001.c:90 | `svp_simple_031_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_031_001.c:46 | `svp_simple_031_001_main` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 74 of `svp_simple_031_001_init`; left unconstrained: interference, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 46, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 65 (read), line 83 (read), line 85 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 73, line 46] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_031_001
  variable: svp_simple_031_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 73, flow: main}
    - {role: B, kind: write, line: 90, flow: isr_1}
    - {role: A2, kind: read, line: 46, flow: main}
  candidate_ids: [c840fad6c904b5273]
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

### T4. (73, 90, 65) — `svp_simple_031_001@73-90-65`

**Record `c821a3a052824c724`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_031_001.c:73 | `svp_simple_031_001_init` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 = rand();` |
| B | write | svp_simple_031_001.c:90 | `svp_simple_031_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_031_001.c:65 | `svp_simple_031_001_func_2` | main | irq 1 enabled | no | `if (svp_simple_031_001_tc_block_rcvd_bytes_ch1 > 0) {` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 74 of `svp_simple_031_001_init`; left unconstrained: interference, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 65, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 46 (read), line 83 (read), line 85 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 73, line 65] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_031_001
  variable: svp_simple_031_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 73, flow: main}
    - {role: B, kind: write, line: 90, flow: isr_1}
    - {role: A2, kind: read, line: 65, flow: main}
  candidate_ids: [c821a3a052824c724]
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

### T5. (73, 90, 83) — `svp_simple_031_001@73-90-83`

**Record `c972c69d779adeb88`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_031_001.c:73 | `svp_simple_031_001_init` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 = rand();` |
| B | write | svp_simple_031_001.c:90 | `svp_simple_031_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_031_001.c:83 | `svp_simple_031_001_func_3` | main | irq 1 enabled | no | `if (svp_simple_031_001_tc_block_rcvd_bytes_ch1 >= 16) {` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 74 of `svp_simple_031_001_init`; left unconstrained: interference, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 83, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 46 (read), line 65 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 73, line 83] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_031_001
  variable: svp_simple_031_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 73, flow: main}
    - {role: B, kind: write, line: 90, flow: isr_1}
    - {role: A2, kind: read, line: 83, flow: main}
  candidate_ids: [c972c69d779adeb88]
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

### T6. (73, 90, 85) — `svp_simple_031_001@73-90-85`

**Record `c169e80e5a66908b6`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_031_001.c:73 | `svp_simple_031_001_init` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 = rand();` |
| B | write | svp_simple_031_001.c:90 | `svp_simple_031_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_031_001.c:85 | `svp_simple_031_001_func_3` | main | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1);` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 74 of `svp_simple_031_001_init`; left unconstrained: interference, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 85, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 46 (read), line 65 (read), line 83 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 73, line 85] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_031_001
  variable: svp_simple_031_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 73, flow: main}
    - {role: B, kind: write, line: 90, flow: isr_1}
    - {role: A2, kind: read, line: 85, flow: main}
  candidate_ids: [c169e80e5a66908b6]
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

### T7. (83, 90, 65) — `svp_simple_031_001@83-90-65`

**Record `ceea334fffb35ec48`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_031_001.c:83 | `svp_simple_031_001_func_3` | main | irq 1 enabled | no | `if (svp_simple_031_001_tc_block_rcvd_bytes_ch1 >= 16) {` |
| B | write | svp_simple_031_001.c:90 | `svp_simple_031_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_031_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_031_001.c:65 | `svp_simple_031_001_func_2` | main | irq 1 enabled | no | `if (svp_simple_031_001_tc_block_rcvd_bytes_ch1 > 0) {` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 83 of `svp_simple_031_001_func_3`; left unconstrained: interference, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 83, read): reaches a branch condition; A2 (line 65, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 46 (read), line 73 (write), line 85 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 83, line 65] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_031_001
  variable: svp_simple_031_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 83, flow: main}
    - {role: B, kind: write, line: 90, flow: isr_1}
    - {role: A2, kind: read, line: 65, flow: main}
  candidate_ids: [ceea334fffb35ec48]
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

Top level of `svp_simple_031_001.c` before its first function:

```c
19  void svp_simple_031_001_init();
20  int svp_simple_031_001_func_1(int a, int b);
21  int svp_simple_031_001_func_2(int x);
22  void svp_simple_031_001_func_3();
23  
24  #define svp_simple_031_001_CNT (volatile unsigned int *)0x10000000
25  volatile unsigned16 svp_simple_031_001_tc_block_rcvd_bytes_ch1;
26  volatile unsigned16 svp_simple_031_001_tc_block_rcvd_bytes_ch2;
27  volatile unsigned16 svp_simple_031_001_tc_block_rcvd_bytes;
28  volatile unsigned8 svp_simple_031_001_tc_chan1_buff[256];
29  volatile unsigned8 svp_simple_031_001_tc_chan2_buff[256];
30  volatile unsigned8 *svp_simple_031_001_tc_buff_p;
31  volatile unsigned32 svp_simple_031_001_gloable_var1;
32  
33  struct svp_simple_031_001_tc_block_data {
34    unsigned8 type;
35    unsigned8 id;
36    unsigned8 valid_len;
37  };
```

`svp_simple_031_001_main` — svp_simple_031_001.c:38-53

```c
38  void svp_simple_031_001_main() {
39    svp_simple_031_001_init();
40    struct svp_simple_031_001_tc_block_data tc_block;
41  
42    int ichan = 0;
43    if (ichan == 0) {
44      svp_simple_031_001_tc_buff_p = svp_simple_031_001_tc_chan1_buff;
45      svp_simple_031_001_tc_block_rcvd_bytes =
46          svp_simple_031_001_tc_block_rcvd_bytes_ch1;  
47    }
48  
49    tc_block.type = *(svp_simple_031_001_tc_buff_p + 2);
50    tc_block.id = *(svp_simple_031_001_tc_buff_p + 4);
51    tc_block.valid_len = *(svp_simple_031_001_tc_buff_p + 5);
52    svp_simple_031_001_func_3();
53  }
```

`svp_simple_031_001_isr_1` — svp_simple_031_001.c:89-92

```c
89  void svp_simple_031_001_isr_1() {
90    svp_simple_031_001_tc_block_rcvd_bytes_ch1 =
91        (*(svp_simple_031_001_CNT) >> 3) & 0x1FFF;  
92  }
```

`svp_simple_031_001_func_2` — svp_simple_031_001.c:64-70

```c
64  int svp_simple_031_001_func_2(int x) {
65    if (svp_simple_031_001_tc_block_rcvd_bytes_ch1 > 0) {  
66      return x;
67    } else {
68      return 0;
69    }
70  }
```

`svp_simple_031_001_func_3` — svp_simple_031_001.c:79-87

```c
79  void svp_simple_031_001_func_3() {
80    unsigned svp_simple_031_001_flag_chan1;
81    svp_simple_031_001_flag_chan1 = 0;
82  
83    if (svp_simple_031_001_tc_block_rcvd_bytes_ch1 >= 16) {  
84      svp_simple_031_001_func_1(svp_simple_031_001_gloable_var1,
85                            svp_simple_031_001_tc_block_rcvd_bytes_ch1);  
86    }
87  }
```

`svp_simple_031_001_func_1` — svp_simple_031_001.c:55-63

```c
55  int svp_simple_031_001_func_1(int a, int b) {
56    int c;
57    if (a < b) {
58      c = a * b;
59    } else {
60      c = svp_simple_031_001_func_2(10);
61    }
62    return c;
63  }
```

`svp_simple_031_001_init` — svp_simple_031_001.c:72-77

```c
72  void svp_simple_031_001_init() {
73    svp_simple_031_001_tc_block_rcvd_bytes_ch1 = rand();
74    svp_simple_031_001_tc_block_rcvd_bytes_ch2 = rand();
75  
76    init();
77  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```
