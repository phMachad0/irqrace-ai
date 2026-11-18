# Dossier svp_simple_018_001/D2

**Case** `svp_simple_018_001` · **location** `svp_simple_018_001_para2` (`volatile float`, declared svp_simple_018_001.c:28) · **1 triple(s) to adjudicate** · run `svp_simple_018_001-20261115T133955Z-0a7b44`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (41, 54, 48) | 2.1 bug 2 |
| (41, 54, 49) | unannotated: cabd660532d1035da |
| (48, 54, 49) | 2.1 bug 3 |

Sibling links:

- E3: svp_simple_018_001@41-54-49 ~ svp_simple_018_001:bug:2
- E3: svp_simple_018_001@41-54-49 ~ svp_simple_018_001:bug:3
- E3: svp_simple_018_001:bug:2 ~ svp_simple_018_001:bug:3

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

`| 18   | svp_simple_018_001.c | svp_simple_018_001_main | svp_simple_018_001_isr_1/1/1  svp_simple_018_001_isr_2/2/2   |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_018_001_main` | - | 0 | isr_1, isr_2 | 1, 2 |
| isr_1 | isr | `svp_simple_018_001_isr_1` | 1 | 1 | isr_2 | - |
| isr_2 | isr | `svp_simple_018_001_isr_2` | 2 | 2 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 2: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 2: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 2: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 8 is reached from flows isr_2, main
- `writers.svp_simple_018_001_para2` [proven]: every store to svp_simple_018_001_para2 the analysis found (1): isr_2: svp_simple_018_001_isr_func1 svp_simple_018/svp_simple_018_001.c:54 `svp_simple_018_001_para2 = 1.0;`. declared at svp_simple_018/svp_simple_018_001.c:28 `volatile float svp_simple_018_001_para2;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_018_001_para1` [proven]: every store to svp_simple_018_001_para1 the analysis found (1): isr_1: svp_simple_018_001_isr_1 svp_simple_018/svp_simple_018_001.c:59 `svp_simple_018_001_para1 = 2.0;`. declared at svp_simple_018/svp_simple_018_001.c:27 `volatile float svp_simple_018_001_para1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 41, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced; A2 (line 49, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 48 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_2 may run within [line 41, line 49] of main, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

## Triples

### T1. (41, 54, 49) — `svp_simple_018_001@41-54-49`

**Record `cabd660532d1035da`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_018_001.c:41 | `svp_simple_018_001_func1` | main | irq 1 enabled, irq 2 enabled | no | `svp_simple_018_001_para2;` |
| B | write | svp_simple_018_001.c:54 | `svp_simple_018_001_isr_func1` | isr_2 | irq 1 enabled, irq 2 enabled | no | `svp_simple_018_001_para2 = 1.0;` |
| A2 | read | svp_simple_018_001.c:49 | `svp_simple_018_001_func2` | main | irq 1 enabled, irq 2 enabled | no | `svp_simple_018_001_para2;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_2` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 40 of `svp_simple_018_001_func1`; left unconstrained: floating-point, interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_018_001
  variable: svp_simple_018_001_para2
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 41, flow: main}
    - {role: B, kind: write, line: 54, flow: isr_2}
    - {role: A2, kind: read, line: 49, flow: main}
  candidate_ids: [cabd660532d1035da]
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

Top level of `svp_simple_018_001.c` before its first function:

```c
19  void svp_simple_018_001_main();
20  
21  float svp_simple_018_001_func1();
22  
23  float svp_simple_018_001_func2();
24  
25  void svp_simple_018_001_isr_func1();
26  
27  volatile float svp_simple_018_001_para1;
28  volatile float svp_simple_018_001_para2;
```

`svp_simple_018_001_func1` — svp_simple_018_001.c:38-43

```c
38  float svp_simple_018_001_func1() {
39    float perimete = 0.0;
40    perimete = 2 * svp_simple_018_001_para1 *
41               svp_simple_018_001_para2;
42    return perimete;
43  }
```

`svp_simple_018_001_isr_func1` — svp_simple_018_001.c:53-55

```c
53  void svp_simple_018_001_isr_func1() {
54    svp_simple_018_001_para2 = 1.0;
55  }
```

`svp_simple_018_001_func2` — svp_simple_018_001.c:45-51

```c
45  float svp_simple_018_001_func2() {
46    float area = 0.0;
47    area = svp_simple_018_001_para1 *
48           svp_simple_018_001_para2 *
49           svp_simple_018_001_para2;
50    return area;
51  }
```

`svp_simple_018_001_main` — svp_simple_018_001.c:30-36

```c
30  void svp_simple_018_001_main() {
31    init();
32    float svp_simple_018_001_perimete = 0;
33    float svp_simple_018_001_area = 0;
34    svp_simple_018_001_perimete = svp_simple_018_001_func1();
35    svp_simple_018_001_area = svp_simple_018_001_func2();
36  }
```

`svp_simple_018_001_isr_2` — svp_simple_018_001.c:62-65

```c
62  void svp_simple_018_001_isr_2() {
63    idlerun();
64    svp_simple_018_001_isr_func1();
65  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```
