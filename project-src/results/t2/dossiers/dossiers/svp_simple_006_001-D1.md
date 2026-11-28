# Dossier svp_simple_006_001/D1

**Case** `svp_simple_006_001` · **location** `svp_simple_006_001_global_var1` (`volatile int`, declared svp_simple_006_001.c:22) · **3 triple(s) to adjudicate** · run `svp_simple_006_001-20261115T133841Z-87cb29`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (33, 52, 33) | unannotated: c461eb09e51d7728b |
| (33, 52, 35) | 2.1 bug 1 |
| (35, 52, 33) | unannotated: c6995719cc418f376 |
| (35, 52, 35) | unannotated: cc9cc336bd366845b |
| (35, 52, 37) | 2.1 trap 1 |

Sibling links:

- E3: svp_simple_006_001@33-52-33 ~ svp_simple_006_001@35-52-33
- E3: svp_simple_006_001@33-52-33 ~ svp_simple_006_001:bug:1
- E3: svp_simple_006_001@35-52-33 ~ svp_simple_006_001@35-52-35
- E3: svp_simple_006_001@35-52-33 ~ svp_simple_006_001:bug:1
- E3: svp_simple_006_001@35-52-33 ~ svp_simple_006_001:trap:1
- E3: svp_simple_006_001@35-52-35 ~ svp_simple_006_001:bug:1
- E3: svp_simple_006_001@35-52-35 ~ svp_simple_006_001:trap:1
- E3: svp_simple_006_001:bug:1 ~ svp_simple_006_001:trap:1

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

`| 6    | svp_simple_006_001.c | svp_simple_006_001_main | svp_simple_006_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_006_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_006_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 9 is reached from flows isr_1, main
- `writers.svp_simple_006_001_global_var1` [proven]: every store to svp_simple_006_001_global_var1 the analysis found (1): isr_1: svp_simple_006_001_isr_1 svp_simple_006/svp_simple_006_001.c:52 `svp_simple_006_001_global_var1 = 0;`. declared at svp_simple_006/svp_simple_006_001.c:22 `volatile int svp_simple_006_001_global_var1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_006_001_global_var2` [proven]: every store to svp_simple_006_001_global_var2 the analysis found (1): main: svp_simple_006_001_main svp_simple_006/svp_simple_006_001.c:44 `svp_simple_006_001_global_var2 = 0x02;`. declared at svp_simple_006/svp_simple_006_001.c:23 `volatile int svp_simple_006_001_global_var2;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.

## Triples

### T1. (33, 52, 33) — `svp_simple_006_001@33-52-33`

**Record `c461eb09e51d7728b`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_006_001.c:33 | `svp_simple_006_001_main` | main | irq 1 enabled | yes (header 30, 29) | `reader1 = svp_simple_006_001_global_var1;` |
| B | write | svp_simple_006_001.c:52 | `svp_simple_006_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_006_001_global_var1 = 0;` |
| A2 | read | svp_simple_006_001.c:33 | `svp_simple_006_001_main` | main | irq 1 enabled | yes (header 30, 29) | `reader1 = svp_simple_006_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 33 of `svp_simple_006_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 33, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 33, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 35 (read), line 37 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 33, line 33] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_006_001
  variable: svp_simple_006_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 33, flow: main}
    - {role: B, kind: write, line: 52, flow: isr_1}
    - {role: A2, kind: read, line: 33, flow: main}
  candidate_ids: [c461eb09e51d7728b]
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

### T2. (35, 52, 33) — `svp_simple_006_001@35-52-33`

**Record `c6995719cc418f376`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_006_001.c:35 | `svp_simple_006_001_main` | main | irq 1 enabled | yes (header 30, 29) | `reader2 = svp_simple_006_001_global_var1;` |
| B | write | svp_simple_006_001.c:52 | `svp_simple_006_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_006_001_global_var1 = 0;` |
| A2 | read | svp_simple_006_001.c:33 | `svp_simple_006_001_main` | main | irq 1 enabled | yes (header 30, 29) | `reader1 = svp_simple_006_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 35 of `svp_simple_006_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 35, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 33, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 37 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 35, line 33] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_006_001
  variable: svp_simple_006_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 35, flow: main}
    - {role: B, kind: write, line: 52, flow: isr_1}
    - {role: A2, kind: read, line: 33, flow: main}
  candidate_ids: [c6995719cc418f376]
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

### T3. (35, 52, 35) — `svp_simple_006_001@35-52-35`

**Record `cc9cc336bd366845b`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_006_001.c:35 | `svp_simple_006_001_main` | main | irq 1 enabled | yes (header 30, 29) | `reader2 = svp_simple_006_001_global_var1;` |
| B | write | svp_simple_006_001.c:52 | `svp_simple_006_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_006_001_global_var1 = 0;` |
| A2 | read | svp_simple_006_001.c:35 | `svp_simple_006_001_main` | main | irq 1 enabled | yes (header 30, 29) | `reader2 = svp_simple_006_001_global_var1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 35 of `svp_simple_006_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 35, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read; A2 (line 35, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 33 (read), line 37 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 35, line 35] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_006_001
  variable: svp_simple_006_001_global_var1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 35, flow: main}
    - {role: B, kind: write, line: 52, flow: isr_1}
    - {role: A2, kind: read, line: 35, flow: main}
  candidate_ids: [cc9cc336bd366845b]
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

Top level of `svp_simple_006_001.c` before its first function:

```c
19  #define MAX_LENGTH 10000
20  #define TRIGGER 9999
21  
22  volatile int svp_simple_006_001_global_var1;
23  volatile int svp_simple_006_001_global_var2;
24  volatile unsigned char flag = 0x55;
```

`svp_simple_006_001_main` — svp_simple_006_001.c:25-46

```c
25  void svp_simple_006_001_main() {
26    init();
27    int reader1, reader2;
28    
29    for (int i = 0; i < 5; i++)
30      for (int j = 0; j < 5; j++) {
31        if (i == j) {
32          if (i == 0)
33            reader1 = svp_simple_006_001_global_var1;
34          else if (i == 4)
35            reader2 = svp_simple_006_001_global_var1;
36          else if (i == 6)
37            reader2 = svp_simple_006_001_global_var1;
38        }
39      }
40  
41    for (int i = 0; i < 5; i++)
42      for (int j = 0; j < 5; j++) {
43        if (((i + j) == 6) && (i < j))
44          svp_simple_006_001_global_var2 = 0x02;
45      }
46  }
```

`svp_simple_006_001_isr_1` — svp_simple_006_001.c:48-54

```c
48  void svp_simple_006_001_isr_1() {
49    int reader2;
50    idlerun();
51  
52    svp_simple_006_001_global_var1 = 0;
53    reader2 = svp_simple_006_001_global_var2;
54  }
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
