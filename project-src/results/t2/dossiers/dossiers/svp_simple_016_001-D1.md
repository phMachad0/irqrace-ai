# Dossier svp_simple_016_001/D1

**Case** `svp_simple_016_001` · **location** `svp_simple_016_001_global_var1` (`volatile int`, declared svp_simple_016_001.c:19) · **3 triple(s) to adjudicate** · run `svp_simple_016_001-20261115T133937Z-830070`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (24, 33, 25) | 2.1 bug 1 |
| (24, 33, 26) | unannotated: c4cc0a67531b887cb |
| (24, 33, 27) | unannotated: ca6a58e16b5c72761 |
| (25, 33, 26) | 2.1 bug 2 |
| (25, 33, 27) | unannotated: ca6d9783b3130a1ba |
| (26, 33, 27) | 2.1 bug 3 |

Sibling links:

- E3: svp_simple_016_001@24-33-26 ~ svp_simple_016_001@24-33-27
- E3: svp_simple_016_001@24-33-26 ~ svp_simple_016_001:bug:1
- E3: svp_simple_016_001@24-33-26 ~ svp_simple_016_001:bug:2
- E3: svp_simple_016_001@24-33-26 ~ svp_simple_016_001:bug:3
- E3: svp_simple_016_001@24-33-27 ~ svp_simple_016_001@25-33-27
- E3: svp_simple_016_001@24-33-27 ~ svp_simple_016_001:bug:1
- E3: svp_simple_016_001@24-33-27 ~ svp_simple_016_001:bug:3
- E3: svp_simple_016_001@25-33-27 ~ svp_simple_016_001:bug:1
- E3: svp_simple_016_001@25-33-27 ~ svp_simple_016_001:bug:2
- E3: svp_simple_016_001@25-33-27 ~ svp_simple_016_001:bug:3
- E3: svp_simple_016_001:bug:1 ~ svp_simple_016_001:bug:2
- E3: svp_simple_016_001:bug:2 ~ svp_simple_016_001:bug:3

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

`| 16   | svp_simple_016_001.c | svp_simple_016_001_main | svp_simple_016_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_016_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_016_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, main
- `writers.svp_simple_016_001_global_var1` [proven]: every store to svp_simple_016_001_global_var1 the analysis found (2): isr_1: svp_simple_016_001_isr_1 svp_simple_016/svp_simple_016_001.c:33 `svp_simple_016_001_global_var1 = 0x09;`; main: svp_simple_016_001_main svp_simple_016/svp_simple_016_001.c:24 `svp_simple_016_001_global_var1 = 0x01;`. declared at svp_simple_016/svp_simple_016_001.c:19 `volatile int svp_simple_016_001_global_var1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.

## Triples

### T1. (24, 33, 26) — `svp_simple_016_001@24-33-26`

**Record `c4cc0a67531b887cb`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_016_001.c:24 | `svp_simple_016_001_main` | main | irq 1 enabled | no | `svp_simple_016_001_global_var1 = 0x01;` |
| B | write | svp_simple_016_001.c:33 | `svp_simple_016_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_016_001_global_var1 = 0x09;` |
| A2 | read | svp_simple_016_001.c:26 | `svp_simple_016_001_main` | main | irq 1 enabled | no | `svp_simple_016_001_global_var1 +` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 25 of `svp_simple_016_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 26, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 25 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 24, line 26] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_016_001
  variable: svp_simple_016_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 24, flow: main}
    - {role: B, kind: write, line: 33, flow: isr_1}
    - {role: A2, kind: read, line: 26, flow: main}
  candidate_ids: [c4cc0a67531b887cb]
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

### T2. (24, 33, 27) — `svp_simple_016_001@24-33-27`

**Record `ca6a58e16b5c72761`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_016_001.c:24 | `svp_simple_016_001_main` | main | irq 1 enabled | no | `svp_simple_016_001_global_var1 = 0x01;` |
| B | write | svp_simple_016_001.c:33 | `svp_simple_016_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_016_001_global_var1 = 0x09;` |
| A2 | read | svp_simple_016_001.c:27 | `svp_simple_016_001_main` | main | irq 1 enabled | no | `svp_simple_016_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 25 of `svp_simple_016_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 27, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 25 (read), line 26 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 24, line 27] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_016_001
  variable: svp_simple_016_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 24, flow: main}
    - {role: B, kind: write, line: 33, flow: isr_1}
    - {role: A2, kind: read, line: 27, flow: main}
  candidate_ids: [ca6a58e16b5c72761]
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

### T3. (25, 33, 27) — `svp_simple_016_001@25-33-27`

**Record `ca6d9783b3130a1ba`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_016_001.c:25 | `svp_simple_016_001_main` | main | irq 1 enabled | no | `reader1 = svp_simple_016_001_global_var1 +` |
| B | write | svp_simple_016_001.c:33 | `svp_simple_016_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_016_001_global_var1 = 0x09;` |
| A2 | read | svp_simple_016_001.c:27 | `svp_simple_016_001_main` | main | irq 1 enabled | no | `svp_simple_016_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 26 of `svp_simple_016_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 25, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 27, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 26 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 25, line 27] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_016_001
  variable: svp_simple_016_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 25, flow: main}
    - {role: B, kind: write, line: 33, flow: isr_1}
    - {role: A2, kind: read, line: 27, flow: main}
  candidate_ids: [ca6d9783b3130a1ba]
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

Top level of `svp_simple_016_001.c` before its first function:

```c
19  volatile int svp_simple_016_001_global_var1;
```

`svp_simple_016_001_main` — svp_simple_016_001.c:21-29

```c
21  void svp_simple_016_001_main() {
22    init();
23    int reader1;
24    svp_simple_016_001_global_var1 = 0x01;
25    reader1 = svp_simple_016_001_global_var1 +
26              svp_simple_016_001_global_var1 +
27              svp_simple_016_001_global_var1;
28  
29  }
```

`svp_simple_016_001_isr_1` — svp_simple_016_001.c:31-34

```c
31  void svp_simple_016_001_isr_1() {
32    idlerun();
33    svp_simple_016_001_global_var1 = 0x09;
34  }
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
