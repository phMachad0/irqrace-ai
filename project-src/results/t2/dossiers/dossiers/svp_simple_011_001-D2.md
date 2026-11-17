# Dossier svp_simple_011_001/D2

**Case** `svp_simple_011_001` · **location** `svp_simple_011_001_u` (`volatile int *`, declared svp_simple_011_001.c:23) · **1 triple(s) to adjudicate** · run `svp_simple_011_001-20261115T133920Z-77a05f`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (33, 43, 35) | unannotated: cc2fd45f5712c60da |

Sibling links:

- none (a group of one)

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

`| 11   | svp_simple_011_001.c | svp_simple_011_001_main | svp_simple_011_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_011_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_011_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 10 is reached from flows isr_1, main
- `writers.svp_simple_011_001_u` [proven]: every store to svp_simple_011_001_u the analysis found (2): main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:33 `svp_simple_011_001_u = &svp_simple_011_001_global_var2;`; main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:35 `svp_simple_011_001_u = &svp_simple_011_001_global_var3;`. declared at svp_simple_011/svp_simple_011_001.c:23 `volatile int *svp_simple_011_001_u;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_011_001_global_var1` [proven]: every store to svp_simple_011_001_global_var1 the analysis found (2): main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:30 `*p = 0x01;`; main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:31 `*q = 0x02;`. declared at svp_simple_011/svp_simple_011_001.c:19 `int svp_simple_011_001_global_var1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_011_001_global_var2` [proven]: every store to svp_simple_011_001_global_var2 the analysis found (2): main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:34 `*svp_simple_011_001_u = 0x01;`; main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:36 `*svp_simple_011_001_u = 0x02;`. declared at svp_simple_011/svp_simple_011_001.c:20 `int svp_simple_011_001_global_var2;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_011_001_global_var3` [proven]: every store to svp_simple_011_001_global_var3 the analysis found (2): main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:34 `*svp_simple_011_001_u = 0x01;`; main: svp_simple_011_001_main svp_simple_011/svp_simple_011_001.c:36 `*svp_simple_011_001_u = 0x02;`. declared at svp_simple_011/svp_simple_011_001.c:21 `int svp_simple_011_001_global_var3;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): B (line 43, read): reaches an address that is dereferenced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 34 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 33, line 35] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

## Triples

### T1. (33, 43, 35) — `svp_simple_011_001@33-43-35`

**Record `cc2fd45f5712c60da`** — shape WRW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_011_001.c:33 | `svp_simple_011_001_main` | main | irq 1 enabled | no | `svp_simple_011_001_u = &svp_simple_011_001_global_var2;` |
| B | read | svp_simple_011_001.c:43 | `svp_simple_011_001_isr_1` | isr_1 | irq 1 enabled | no | `reader2 = *svp_simple_011_001_u;` |
| A2 | write | svp_simple_011_001.c:35 | `svp_simple_011_001_main` | main | irq 1 enabled | no | `svp_simple_011_001_u = &svp_simple_011_001_global_var3;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 34 of `svp_simple_011_001_main`; left unconstrained: interference, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_011_001
  variable: svp_simple_011_001_u
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 33, flow: main}
    - {role: B, kind: read, line: 43, flow: isr_1}
    - {role: A2, kind: write, line: 35, flow: main}
  candidate_ids: [cc2fd45f5712c60da]
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

Top level of `svp_simple_011_001.c` before its first function:

```c
19  int svp_simple_011_001_global_var1;
20  int svp_simple_011_001_global_var2;
21  int svp_simple_011_001_global_var3;
22  
23  volatile int *svp_simple_011_001_u;
```

`svp_simple_011_001_main` — svp_simple_011_001.c:25-37

```c
25  void svp_simple_011_001_main() {
26    init();
27    int *p = &svp_simple_011_001_global_var1;
28    int *q = &svp_simple_011_001_global_var1;
29  
30    *p = 0x01;
31    *q = 0x02;
32  
33    svp_simple_011_001_u = &svp_simple_011_001_global_var2;
34    *svp_simple_011_001_u = 0x01;
35    svp_simple_011_001_u = &svp_simple_011_001_global_var3;
36    *svp_simple_011_001_u = 0x02;
37  }
```

`svp_simple_011_001_isr_1` — svp_simple_011_001.c:39-44

```c
39  void svp_simple_011_001_isr_1() {
40    int reader1, reader2;
41    int *m = &svp_simple_011_001_global_var1;
42    reader1 = *m;
43    reader2 = *svp_simple_011_001_u;
44  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```
