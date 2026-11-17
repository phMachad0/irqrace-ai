# Dossier svp_simple_030_001/D2

**Case** `svp_simple_030_001` · **location** `svp_simple_030_001_gloable_var` (`volatile int`, declared svp_simple_030_001.c:22) · **2 triple(s) to adjudicate** · run `svp_simple_030_001-20261115T134146Z-0e8887`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (43, 52, 43) | unannotated: c157bd275544b85d9 |
| (43, 56, 43) | unannotated: c034f9ecf0fb23fcc |

Sibling links:

- E2: svp_simple_030_001@43-52-43 ~ svp_simple_030_001@43-56-43

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

`| 30   | svp_simple_030_001.c | svp_simple_030_001_main | svp_simple_030_001_isr_1/1/1     svp_simple_030_001_isr_2/2/2  svp_simple_030_001_isr_3/3/3 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_030_001__main` | - | 0 | isr_1, isr_2, isr_3 | 1, 2, 3 |
| isr_1 | isr | `svp_simple_030_001_isr_1` | 1 | 1 | isr_2, isr_3 | 2 |
| isr_2 | isr | `svp_simple_030_001_isr_2` | 2 | 2 | isr_3 | - |
| isr_3 | isr | `svp_simple_030_001_isr_3` | 3 | 3 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 28 in svp_simple_030_001__main); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 2: D (disable_isr(-1) at line 27 in svp_simple_030_001__main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 48 in svp_simple_030_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 3: D (disable_isr(-1) at line 27 in svp_simple_030_001__main); E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 28 in svp_simple_030_001__main); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 2: D (disable_isr(-1) at line 27 in svp_simple_030_001__main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 48 in svp_simple_030_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 3: D (disable_isr(-1) at line 27 in svp_simple_030_001__main); E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 28 in svp_simple_030_001__main); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 2: D (disable_isr(-1) at line 27 in svp_simple_030_001__main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 48 in svp_simple_030_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 3: D (disable_isr(-1) at line 27 in svp_simple_030_001__main); E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 2: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 3: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, isr_2, isr_3, main
- `writers.svp_simple_030_001_gloable_var` [proven]: every store to svp_simple_030_001_gloable_var the analysis found (5): isr_1: addData svp_simple_030/svp_simple_030_001.c:43 `svp_simple_030_001_gloable_var++;`; isr_2: svp_simple_030_001_isr_2 svp_simple_030/svp_simple_030_001.c:52 `svp_simple_030_001_gloable_var++;`; isr_3: svp_simple_030_001_isr_3 svp_simple_030/svp_simple_030_001.c:56 `svp_simple_030_001_gloable_var++;`; main: svp_simple_030_001__main svp_simple_030/svp_simple_030_001.c:30 `svp_simple_030_001_gloable_var = 0;`; main: svp_simple_030_001_init svp_simple_030/svp_simple_030_001.c:36 `svp_simple_030_001_gloable_var = rand();`. declared at svp_simple_030/svp_simple_030_001.c:22 `volatile int svp_simple_030_001_gloable_var;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_030_001_isr_1_flag` [proven]: every store to svp_simple_030_001_isr_1_flag the analysis found (2): isr_1: svp_simple_030_001_isr_1 svp_simple_030/svp_simple_030_001.c:47 `svp_simple_030_001_isr_1_flag = 0;`; main: svp_simple_030_001_init svp_simple_030/svp_simple_030_001.c:37 `svp_simple_030_001_isr_1_flag = rand();`. declared at svp_simple_030/svp_simple_030_001.c:21 `volatile int svp_simple_030_001_isr_1_flag;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `masking_primitives.disable_isr` [assumed_from_config]: disable_isr(n) disables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 43, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced

## Triples

### T1. (43, 52, 43) — `svp_simple_030_001@43-52-43`

**Record `c157bd275544b85d9`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_030_001.c:43 | `addData` | isr_1 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_030_001_gloable_var++;` |
| B | write | svp_simple_030_001.c:52 | `svp_simple_030_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_030_001_gloable_var++;` |
| A2 | write | svp_simple_030_001.c:43 | `addData` | isr_1 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_030_001_gloable_var++;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2, 3], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_2` into `isr_1`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 43 of `addData`; left unconstrained: interference, isr-entry-state, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `masking.interval` [overapproximated]: isr_2 may run within [line 43, line 43] of isr_1, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init; enable_isr(2) at line 48 in svp_simple_030_001_isr_1; isr_1 may itself start with irq 2 unmasked: an ISR begins in the state of whatever point it preempted, and isr_1 may fire wherever irq 2 is unmasked -- including before any masking call in the flows it preempts (F8).

Witness form:

```yaml
- id: R22-____
  case: svp_simple_030_001
  variable: svp_simple_030_001_gloable_var
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 43, flow: isr_1}
    - {role: B, kind: write, line: 52, flow: isr_2}
    - {role: A2, kind: write, line: 43, flow: isr_1}
  candidate_ids: [c157bd275544b85d9]
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

### T2. (43, 56, 43) — `svp_simple_030_001@43-56-43`

**Record `c034f9ecf0fb23fcc`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_030_001.c:43 | `addData` | isr_1 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_030_001_gloable_var++;` |
| B | write | svp_simple_030_001.c:56 | `svp_simple_030_001_isr_3` | isr_3 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_030_001_gloable_var++;` |
| A2 | write | svp_simple_030_001.c:43 | `addData` | isr_1 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_030_001_gloable_var++;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2, 3], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_3` into `isr_1`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 43 of `addData`; left unconstrained: interference, isr-entry-state, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `masking.interval` [overapproximated]: isr_3 may run within [line 43, line 43] of isr_1, at nesting depth 1; irq 3 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init; isr_1 may itself start with irq 3 unmasked: an ISR begins in the state of whatever point it preempted, and isr_1 may fire wherever irq 3 is unmasked -- including before any masking call in the flows it preempts (F8).

Witness form:

```yaml
- id: R22-____
  case: svp_simple_030_001
  variable: svp_simple_030_001_gloable_var
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 43, flow: isr_1}
    - {role: B, kind: write, line: 56, flow: isr_3}
    - {role: A2, kind: write, line: 43, flow: isr_1}
  candidate_ids: [c034f9ecf0fb23fcc]
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

## Source

Top level of `svp_simple_030_001.c` before its first function:

```c
19  void svp_simple_030_001_init();
20  void addData();
21  volatile int svp_simple_030_001_isr_1_flag;
22  volatile int svp_simple_030_001_gloable_var;
```

`addData` — svp_simple_030_001.c:42-44

```c
42  void addData() {
43    svp_simple_030_001_gloable_var++;  
44  }
```

`svp_simple_030_001_isr_2` — svp_simple_030_001.c:50-54

```c
50  void svp_simple_030_001_isr_2() {
51    if (svp_simple_030_001_isr_1_flag) {
52      svp_simple_030_001_gloable_var++;  
53    }
54  }
```

`svp_simple_030_001_isr_1` — svp_simple_030_001.c:45-49

```c
45  void svp_simple_030_001_isr_1() {
46    addData(); 
47    svp_simple_030_001_isr_1_flag = 0;
48    enable_isr(2);
49  }
```

`svp_simple_030_001__main` — svp_simple_030_001.c:24-33

```c
24  int svp_simple_030_001__main() {
25    svp_simple_030_001_init();
26  
27    disable_isr(-1);
28    enable_isr(1);
29    if (svp_simple_030_001_gloable_var > 12) {  
30      svp_simple_030_001_gloable_var = 0;       
31    }
32    return 0;
33  }
```

`svp_simple_030_001_init` — svp_simple_030_001.c:35-40

```c
35  void svp_simple_030_001_init() {
36    svp_simple_030_001_gloable_var = rand();
37    svp_simple_030_001_isr_1_flag = rand();
38  
39    init();
40  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```

`svp_simple_030_001_isr_3` — svp_simple_030_001.c:55-57

```c
55  void svp_simple_030_001_isr_3() {
56    svp_simple_030_001_gloable_var++;  
57  }
```
