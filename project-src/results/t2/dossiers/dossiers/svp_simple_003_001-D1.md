# Dossier svp_simple_003_001/D1

**Case** `svp_simple_003_001` · **location** `svp_simple_003_001_global_var1` (`volatile int`, declared svp_simple_003_001.c:22) · **2 triple(s) to adjudicate** · run `svp_simple_003_001-20261115T133823Z-c1b212`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (50, 65, 50) | unannotated: ce23610f351c06784 |
| (50, 65, 55) | 2.1 bug 1 |
| (50, 67, 55) | 2.1 trap 2 |
| (55, 65, 55) | unannotated: c445b6ae2e44ef46a |

Sibling links:

- E3: svp_simple_003_001@50-65-50 ~ svp_simple_003_001:bug:1
- E3: svp_simple_003_001@55-65-55 ~ svp_simple_003_001:bug:1
- E2: svp_simple_003_001:bug:1 ~ svp_simple_003_001:trap:2

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

`| 3    | svp_simple_003_001.c | svp_simple_003_001_main | svp_simple_003_001_isr_1/1/1     svp_simple_003_001_isr_2/2/2 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_003_001_main` | - | 0 | isr_1, isr_2 | 1, 2 |
| isr_1 | isr | `svp_simple_003_001_isr_1` | 1 | 1 | isr_2 | 2 |
| isr_2 | isr | `svp_simple_003_001_isr_2` | 2 | 2 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 47 in svp_simple_003_001_main); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 2: D (disable_isr(2) at line 34 in svp_simple_003_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 61 in svp_simple_003_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 1: D (disable_isr(1) at line 33 in svp_simple_003_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 47 in svp_simple_003_001_main); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 2: D (disable_isr(2) at line 34 in svp_simple_003_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 61 in svp_simple_003_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 2: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 13 is reached from flows isr_1, main
- `writers.svp_simple_003_001_global_var1` [proven]: every store to svp_simple_003_001_global_var1 the analysis found (2): isr_1: svp_simple_003_001_isr_1 svp_simple_003/svp_simple_003_001.c:65 `svp_simple_003_001_global_var1 = 999;`; isr_1: svp_simple_003_001_isr_1 svp_simple_003/svp_simple_003_001.c:67 `svp_simple_003_001_global_var1 = 888;`. declared at svp_simple_003/svp_simple_003_001.c:22 `volatile int svp_simple_003_001_global_var1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_003_001_global_var2` [proven]: every store to svp_simple_003_001_global_var2 the analysis found (1): isr_1: svp_simple_003_001_isr_1 svp_simple_003/svp_simple_003_001.c:62 `svp_simple_003_001_global_var2 = 999;`. declared at svp_simple_003/svp_simple_003_001.c:23 `volatile int svp_simple_003_001_global_var2;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_003_001_global_flag` [proven]: every store to svp_simple_003_001_global_flag the analysis found (1): isr_2: svp_simple_003_001_isr_2 svp_simple_003/svp_simple_003_001.c:73 `svp_simple_003_001_global_flag = 1;`. declared at svp_simple_003/svp_simple_003_001.c:25 `volatile int svp_simple_003_001_global_flag = 1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.disable_isr` [assumed_from_config]: disable_isr(n) disables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `macros` [proven]: definitions of macros the shipped code uses: MAX_LENGTH = 10000 (svp_simple_003/svp_simple_003_001.c:19); TRIGGER = 9999 (svp_simple_003/svp_simple_003_001.c:20)

## Triples

### T1. (50, 65, 50) — `svp_simple_003_001@50-65-50`

**Record `ce23610f351c06784`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_003_001.c:50 | `svp_simple_003_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 48) | `reader1 = svp_simple_003_001_global_var1;` |
| B | write | svp_simple_003_001.c:65 | `svp_simple_003_001_isr_1` | isr_1 | irq 1 enabled, irq 2 enabled | no | `svp_simple_003_001_global_var1 = 999;` |
| A2 | read | svp_simple_003_001.c:50 | `svp_simple_003_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 48) | `reader1 = svp_simple_003_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by ['isr_1']
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 50 of `svp_simple_003_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 50, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 50, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_1 may run within [line 50, line 50] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(1) at line 47 in svp_simple_003_001_main.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_003_001
  variable: svp_simple_003_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 50, flow: main}
    - {role: B, kind: write, line: 65, flow: isr_1}
    - {role: A2, kind: read, line: 50, flow: main}
  candidate_ids: [ce23610f351c06784]
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

### T2. (55, 65, 55) — `svp_simple_003_001@55-65-55`

**Record `c445b6ae2e44ef46a`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_003_001.c:55 | `svp_simple_003_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 53) | `reader2 = svp_simple_003_001_global_var1;` |
| B | write | svp_simple_003_001.c:65 | `svp_simple_003_001_isr_1` | isr_1 | irq 1 enabled, irq 2 enabled | no | `svp_simple_003_001_global_var1 = 999;` |
| A2 | read | svp_simple_003_001.c:55 | `svp_simple_003_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 53) | `reader2 = svp_simple_003_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by ['isr_1']
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 55 of `svp_simple_003_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 55, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 55, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_1 may run within [line 55, line 55] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(1) at line 47 in svp_simple_003_001_main.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_003_001
  variable: svp_simple_003_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 55, flow: main}
    - {role: B, kind: write, line: 65, flow: isr_1}
    - {role: A2, kind: read, line: 55, flow: main}
  candidate_ids: [c445b6ae2e44ef46a]
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

Top level of `svp_simple_003_001.c` before its first function:

```c
19  #define MAX_LENGTH 10000
20  #define TRIGGER 9999
21  
22  volatile int svp_simple_003_001_global_var1;
23  volatile int svp_simple_003_001_global_var2;
24  
25  volatile int svp_simple_003_001_global_flag = 1;
26  volatile int svp_simple_003_001_global_flag1 = 0;
```

`svp_simple_003_001_main` — svp_simple_003_001.c:27-58

```c
27  void svp_simple_003_001_main() {
28    init();
29    int reader1, reader2;
30    int reader3, reader4;
31    idlerun();
32  
33    disable_isr(1);
34    disable_isr(2);
35  
36    for (int i = 0; i < MAX_LENGTH; i++) {
37      if (i == TRIGGER) {
38        reader3 = svp_simple_003_001_global_var2;
39      }
40    }
41    for (int j = MAX_LENGTH; j > 0; j--) {
42      if (j == TRIGGER) {
43        reader4 = svp_simple_003_001_global_var2;
44      }
45    }
46    
47    enable_isr(1);
48    for (int i = 0; i < MAX_LENGTH; i++) {
49      if (i == TRIGGER) {
50        reader1 = svp_simple_003_001_global_var1;
51      }
52    }
53    for (int j = MAX_LENGTH; j > 0; j--) {
54      if (j == TRIGGER) {
55        reader2 = svp_simple_003_001_global_var1;
56      }
57    }
58  }
```

`svp_simple_003_001_isr_1` — svp_simple_003_001.c:60-69

```c
60  void svp_simple_003_001_isr_1() {
61    enable_isr(2);
62    svp_simple_003_001_global_var2 = 999;
63  
64    if (svp_simple_003_001_global_flag == 1) {
65      svp_simple_003_001_global_var1 = 999;
66    } else if (svp_simple_003_001_global_flag1 == 2) {
67      svp_simple_003_001_global_var1 = 888;
68    }
69  }
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
