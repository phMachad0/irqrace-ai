# Dossier svp_simple_009_001/D1

**Case** `svp_simple_009_001` · **location** `svp_simple_009_001_local_var1` (`int`, declared svp_simple_009_001.c:26) · **2 triple(s) to adjudicate** · run `svp_simple_009_001-20261115T133905Z-ff7f00`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (26, 44, 32) | unannotated: ca08972fa0dd520c7 |
| (26, 44, 33) | unannotated: c582d02f9ddeae9fd |

Sibling links:

- E3: svp_simple_009_001@26-44-32 ~ svp_simple_009_001@26-44-33

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

`| 9    | svp_simple_009_001.c | svp_simple_009_001_main | svp_simple_009_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_009_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_009_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 14 is reached from flows isr_1, main
- `writers.svp_simple_009_001_local_var1` [proven]: every store to svp_simple_009_001_local_var1 the analysis found (3): main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:26 `int svp_simple_009_001_local_var1 = 0x01;`; main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:32 `*svp_simple_009_001_p = 0x02;`; main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:33 `*svp_simple_009_001_q = 0x03;`. declared at svp_simple_009/svp_simple_009_001.c:26 `int svp_simple_009_001_local_var1 = 0x01;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_009_001_p` [proven]: every store to svp_simple_009_001_p the analysis found (1): main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:29 `svp_simple_009_001_p = &svp_simple_009_001_local_var1;`. declared at svp_simple_009/svp_simple_009_001.c:19 `volatile int *svp_simple_009_001_p;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_009_001_m` [proven]: every store to svp_simple_009_001_m the analysis found (2): isr_1: svp_simple_009_001_isr_1 svp_simple_009/svp_simple_009_001.c:46 `svp_simple_009_001_m = &svp_simple_009_001_local_var3;`; main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:35 `svp_simple_009_001_m = &svp_simple_009_001_local_var2;`. declared at svp_simple_009/svp_simple_009_001.c:22 `volatile int *svp_simple_009_001_m;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_009_001_local_var2` [proven]: every store to svp_simple_009_001_local_var2 the analysis found (3): main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:27 `int svp_simple_009_001_local_var2 = 0x09;`; main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:37 `*svp_simple_009_001_m = 0x06;`; main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:38 `*svp_simple_009_001_m = 0x06;`. declared at svp_simple_009/svp_simple_009_001.c:27 `int svp_simple_009_001_local_var2 = 0x09;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_009_001_local_var3` [proven]: every store to svp_simple_009_001_local_var3 the analysis found (3): isr_1: svp_simple_009_001_isr_1 svp_simple_009/svp_simple_009_001.c:45 `int svp_simple_009_001_local_var3 = 0x08;`; main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:37 `*svp_simple_009_001_m = 0x06;`; main: svp_simple_009_001_main svp_simple_009/svp_simple_009_001.c:38 `*svp_simple_009_001_m = 0x06;`. declared at svp_simple_009/svp_simple_009_001.c:45 `int svp_simple_009_001_local_var3 = 0x08;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): B (line 44, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read

## Triples

### T1. (26, 44, 32) — `svp_simple_009_001@26-44-32`

**Record `ca08972fa0dd520c7`** — shape WRW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_009_001.c:26 | `svp_simple_009_001_main` | main | irq 1 enabled | no | `int svp_simple_009_001_local_var1 = 0x01;` |
| B | read | svp_simple_009_001.c:44 | `svp_simple_009_001_isr_1` | isr_1 | irq 1 enabled | no | `reader1 = *svp_simple_009_001_p;` |
| A2 | write | svp_simple_009_001.c:32 | `svp_simple_009_001_main` | main | irq 1 enabled | no | `*svp_simple_009_001_p = 0x02;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 30 of `svp_simple_009_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `masking.interval` [overapproximated]: isr_1 may run within [line 26, line 32] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_009_001
  variable: svp_simple_009_001_local_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 26, flow: main}
    - {role: B, kind: read, line: 44, flow: isr_1}
    - {role: A2, kind: write, line: 32, flow: main}
  candidate_ids: [ca08972fa0dd520c7]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WRW
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T2. (26, 44, 33) — `svp_simple_009_001@26-44-33`

**Record `c582d02f9ddeae9fd`** — shape WRW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_009_001.c:26 | `svp_simple_009_001_main` | main | irq 1 enabled | no | `int svp_simple_009_001_local_var1 = 0x01;` |
| B | read | svp_simple_009_001.c:44 | `svp_simple_009_001_isr_1` | isr_1 | irq 1 enabled | no | `reader1 = *svp_simple_009_001_p;` |
| A2 | write | svp_simple_009_001.c:33 | `svp_simple_009_001_main` | main | irq 1 enabled | no | `*svp_simple_009_001_q = 0x03;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 30 of `svp_simple_009_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 32 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 26, line 33] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_009_001
  variable: svp_simple_009_001_local_var1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 26, flow: main}
    - {role: B, kind: read, line: 44, flow: isr_1}
    - {role: A2, kind: write, line: 33, flow: main}
  candidate_ids: [c582d02f9ddeae9fd]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WRW
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

## Source

Top level of `svp_simple_009_001.c` before its first function:

```c
19  volatile int *svp_simple_009_001_p;
20  volatile int *svp_simple_009_001_q;
21  
22  volatile int *svp_simple_009_001_m;
```

`svp_simple_009_001_main` — svp_simple_009_001.c:24-39

```c
24  void svp_simple_009_001_main() {
25    init();
26    int svp_simple_009_001_local_var1 = 0x01;
27    int svp_simple_009_001_local_var2 = 0x09;
28  
29    svp_simple_009_001_p = &svp_simple_009_001_local_var1;
30    svp_simple_009_001_q = &svp_simple_009_001_local_var1;
31  
32    *svp_simple_009_001_p = 0x02;
33    *svp_simple_009_001_q = 0x03;
34  
35    svp_simple_009_001_m = &svp_simple_009_001_local_var2;
36  
37    *svp_simple_009_001_m = 0x06;
38    *svp_simple_009_001_m = 0x06;
39  }
```

`svp_simple_009_001_isr_1` — svp_simple_009_001.c:41-48

```c
41  void svp_simple_009_001_isr_1() {
42    int reader1, reader2;
43    idlerun();
44    reader1 = *svp_simple_009_001_p;
45    int svp_simple_009_001_local_var3 = 0x08;
46    svp_simple_009_001_m = &svp_simple_009_001_local_var3;
47    reader2 = *svp_simple_009_001_m;
48  }
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
