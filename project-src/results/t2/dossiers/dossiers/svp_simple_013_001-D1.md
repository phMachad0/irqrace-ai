# Dossier svp_simple_013_001/D1

**Case** `svp_simple_013_001` · **location** `svp_simple_013_001_global_var1` (`volatile int`, declared svp_simple_013_001.c:22) · **1 triple(s) to adjudicate** · run `svp_simple_013_001-20261115T133926Z-ff6c71`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (39, 65, 39) | unannotated: cc954c26bffac79bc |
| (39, 65, 41) | 2.1 bug 1 |

Sibling links:

- E3: svp_simple_013_001@39-65-39 ~ svp_simple_013_001:bug:1

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

`| 13   | svp_simple_013_001.c | svp_simple_013_001_main | svp_simple_013_001_isr_1/1/1  svp_simple_013_001_isr_2/2/2  svp_simple_013_001_isr_3/3/3 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_013_001_main` | - | 0 | isr_1, isr_2, isr_3 | 1, 2, 3 |
| isr_1 | isr | `svp_simple_013_001_isr_1` | 1 | 1 | isr_2, isr_3 | 2 |
| isr_2 | isr | `svp_simple_013_001_isr_2` | 2 | 2 | isr_3 | 3 |
| isr_3 | isr | `svp_simple_013_001_isr_3` | 3 | 3 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 2: D (disable_isr(2) at line 30 in svp_simple_013_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 50 in svp_simple_013_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 3: D (disable_isr(3) at line 31 in svp_simple_013_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(3) at line 60 in svp_simple_013_001_isr_2); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 2: D (disable_isr(2) at line 30 in svp_simple_013_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 50 in svp_simple_013_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 3: D (disable_isr(3) at line 31 in svp_simple_013_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(3) at line 60 in svp_simple_013_001_isr_2); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 2: D (disable_isr(2) at line 30 in svp_simple_013_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 50 in svp_simple_013_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 3: D (disable_isr(3) at line 31 in svp_simple_013_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(3) at line 60 in svp_simple_013_001_isr_2); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 2: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 3: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 11 is reached from flows isr_3, main
- `writers.svp_simple_013_001_global_var1` [proven]: every store to svp_simple_013_001_global_var1 the analysis found (1): isr_3: svp_simple_013_001_isr_3 svp_simple_013/svp_simple_013_001.c:65 `if (svp_simple_013_001_global_flag1 == 1) svp_simple_013_001_global_var1 = 0x01;`. declared at svp_simple_013/svp_simple_013_001.c:22 `volatile int svp_simple_013_001_global_var1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_013_001_global_var2` [proven]: every store to svp_simple_013_001_global_var2 the analysis found (1): isr_3: svp_simple_013_001_isr_3 svp_simple_013/svp_simple_013_001.c:66 `if (svp_simple_013_001_global_flag2 == 1) svp_simple_013_001_global_var2 = 0x01;`. declared at svp_simple_013/svp_simple_013_001.c:23 `volatile int svp_simple_013_001_global_var2;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_013_001_global_flag1` [proven]: every store to svp_simple_013_001_global_flag1 the analysis found (1): isr_2: svp_simple_013_001_isr_2 svp_simple_013/svp_simple_013_001.c:56 `svp_simple_013_001_global_flag1 = 1;`. declared at svp_simple_013/svp_simple_013_001.c:25 `int svp_simple_013_001_global_flag1 = 0;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_013_001_global_flag2` [proven]: every store to svp_simple_013_001_global_flag2 the analysis found (1): isr_2: svp_simple_013_001_isr_2 svp_simple_013/svp_simple_013_001.c:58 `svp_simple_013_001_global_flag2 = 0;`. declared at svp_simple_013/svp_simple_013_001.c:26 `int svp_simple_013_001_global_flag2 = 1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.disable_isr` [assumed_from_config]: disable_isr(n) disables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `macros` [proven]: definitions of macros the shipped code uses: MAX_LENGTH = 100 (svp_simple_013/svp_simple_013_001.c:19); TRIGGER = 99 (svp_simple_013/svp_simple_013_001.c:20)
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 39, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 39, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_3 may run within [line 39, line 39] of main, at nesting depth 1; irq 3 is not masked on every path there; it may be enabled by: enable_isr(3) at line 60 in svp_simple_013_001_isr_2; main masks it itself (disable_isr(3) at line 31 in svp_simple_013_001_main), but isr_1, isr_2 may run inside the interval and unmask it -- computed from main's own control flow alone, this candidate would have been dropped.

## Triples

### T1. (39, 65, 39) — `svp_simple_013_001@39-65-39`

**Record `cc954c26bffac79bc`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_013_001.c:39 | `svp_simple_013_001_main` | main | irq 1 enabled, irq 2 enabled, irq 3 enabled | yes (header 38) | `if (i == TRIGGER) reader1 = svp_simple_013_001_global_var1;` |
| B | write | svp_simple_013_001.c:65 | `svp_simple_013_001_isr_3` | isr_3 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `if (svp_simple_013_001_global_flag1 == 1) svp_simple_013_001_global_var1 = 0x01;` |
| A2 | read | svp_simple_013_001.c:39 | `svp_simple_013_001_main` | main | irq 1 enabled, irq 2 enabled, irq 3 enabled | yes (header 38) | `if (i == TRIGGER) reader1 = svp_simple_013_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2, 3], disabled throughout [], unknown [], re-enabled within the interval by ['isr_1', 'isr_2']
- preemption: `isr_3` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 39 of `svp_simple_013_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_013_001
  variable: svp_simple_013_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 39, flow: main}
    - {role: B, kind: write, line: 65, flow: isr_3}
    - {role: A2, kind: read, line: 39, flow: main}
  candidate_ids: [cc954c26bffac79bc]
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

Top level of `svp_simple_013_001.c` before its first function:

```c
19  #define MAX_LENGTH 100
20  #define TRIGGER 99
21  
22  volatile int svp_simple_013_001_global_var1;
23  volatile int svp_simple_013_001_global_var2;
24  
25  int svp_simple_013_001_global_flag1 = 0;
26  int svp_simple_013_001_global_flag2 = 1;
```

`svp_simple_013_001_main` — svp_simple_013_001.c:28-46

```c
28  void svp_simple_013_001_main() {
29    init();
30    disable_isr(2);
31    disable_isr(3);
32  
33    
34    
35    int reader1, reader2;
36    int reader3, reader4;
37  
38    for (int i = 0; i < MAX_LENGTH; i++)
39      if (i == TRIGGER) reader1 = svp_simple_013_001_global_var1;
40  
41    reader2 = svp_simple_013_001_global_var1;
42  
43    reader3 = svp_simple_013_001_global_var2;
44  
45    reader4 = svp_simple_013_001_global_var2;
46  }
```

`svp_simple_013_001_isr_3` — svp_simple_013_001.c:64-67

```c
64  void svp_simple_013_001_isr_3() {
65    if (svp_simple_013_001_global_flag1 == 1) svp_simple_013_001_global_var1 = 0x01;
66    if (svp_simple_013_001_global_flag2 == 1) svp_simple_013_001_global_var2 = 0x01;
67  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```

`svp_simple_013_001_isr_1` — svp_simple_013_001.c:48-52

```c
48  void svp_simple_013_001_isr_1() {
49    idlerun();
50    enable_isr(2);
51    idlerun();
52  }
```

`svp_simple_013_001_isr_2` — svp_simple_013_001.c:54-62

```c
54  void svp_simple_013_001_isr_2() {
55    idlerun();
56    svp_simple_013_001_global_flag1 = 1;
57  
58    svp_simple_013_001_global_flag2 = 0;
59  
60    enable_isr(3);
61    idlerun();
62  }
```
