# Dossier svp_simple_001_001/D1

**Case** `svp_simple_001_001` · **location** `svp_simple_001_001_global_array` (`volatile int[]`, declared svp_simple_001_001.c:20) · **4 triple(s) to adjudicate** · run `svp_simple_001_001-20261115T133809Z-2a7fdc`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (32, 55, 32) | unannotated: cea3c0add9327f2db |
| (32, 55, 35) | 2.1 bug 1 |
| (32, 58, 32) | unannotated: cc44dd708898f87a2 |
| (32, 60, 32) | unannotated: cd8302b6742cc6d65 |
| (32, 60, 35) | 2.1 trap 1 |
| (35, 55, 35) | unannotated: c0955b8ecddeebb9b |

Sibling links:

- E2: svp_simple_001_001@32-55-32 ~ svp_simple_001_001@32-58-32
- E2: svp_simple_001_001@32-55-32 ~ svp_simple_001_001@32-60-32
- E3: svp_simple_001_001@32-55-32 ~ svp_simple_001_001:bug:1
- E2: svp_simple_001_001@32-58-32 ~ svp_simple_001_001@32-60-32
- E3: svp_simple_001_001@32-60-32 ~ svp_simple_001_001:trap:1
- E3: svp_simple_001_001@35-55-35 ~ svp_simple_001_001:bug:1
- E2: svp_simple_001_001:bug:1 ~ svp_simple_001_001:trap:1

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

`| 1    | svp_simple_001_001.c | svp_simple_001_001_main | svp_simple_001_001_isr_1/1/1   svp_simple_001_001_isr_2/2/2  |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_001_001_main` | - | 0 | isr_1, isr_2 | 1, 2 |
| isr_1 | isr | `svp_simple_001_001_isr_1` | 1 | 1 | isr_2 | 2 |
| isr_2 | isr | `svp_simple_001_001_isr_2` | 2 | 2 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 2: D (disable_isr(2) at line 28 in svp_simple_001_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 46 in svp_simple_001_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 2: D (disable_isr(2) at line 28 in svp_simple_001_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 46 in svp_simple_001_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 2: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 14 is reached from flows isr_2, main
- `writers.svp_simple_001_001_global_array` [proven]: every store to svp_simple_001_001_global_array the analysis found (2): main: svp_simple_001_001_main svp_simple_001/svp_simple_001_001.c:32 `for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;`; main: svp_simple_001_001_main svp_simple_001/svp_simple_001_001.c:35 `if (i == TRIGGER) svp_simple_001_001_global_array[i] = 1;`. declared at svp_simple_001/svp_simple_001_001.c:20 `volatile int svp_simple_001_001_global_array[10000];`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_001_001_global_flag` [proven]: every store to svp_simple_001_001_global_flag the analysis found (1): isr_1: svp_simple_001_001_isr_1 svp_simple_001/svp_simple_001_001.c:41 `svp_simple_001_001_global_flag = 1;`. declared at svp_simple_001/svp_simple_001_001.c:21 `volatile int svp_simple_001_001_global_flag = 0;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_001_001_global_var` [proven]: every store to svp_simple_001_001_global_var the analysis found (2): isr_1: svp_simple_001_001_isr_1 svp_simple_001/svp_simple_001_001.c:43 `svp_simple_001_001_global_var = 0;`; isr_1: svp_simple_001_001_isr_1 svp_simple_001/svp_simple_001_001.c:44 `svp_simple_001_001_global_var = 1;`. declared at svp_simple_001/svp_simple_001_001.c:19 `volatile int svp_simple_001_001_global_var;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.disable_isr` [assumed_from_config]: disable_isr(n) disables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `macros` [proven]: definitions of macros the shipped code uses: TRIGGER = 9999 (svp_simple_001/svp_simple_001_001.c:23)

## Triples

### T1. (32, 55, 32) — `svp_simple_001_001@32-55-32`

**Record `cea3c0add9327f2db`** — shape WRW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_001_001.c:32 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 32) | `for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;` |
| B | read | svp_simple_001_001.c:55 | `svp_simple_001_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled | no | `reader1 = svp_simple_001_001_global_array[TRIGGER];` |
| A2 | write | svp_simple_001_001.c:32 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 32) | `for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by ['isr_1']
- preemption: `isr_2` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 32 of `svp_simple_001_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): B (line 55, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_2 may run within [line 32, line 32] of main, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: enable_isr(2) at line 46 in svp_simple_001_001_isr_1; main masks it itself (disable_isr(2) at line 28 in svp_simple_001_001_main), but isr_1 may run inside the interval and unmask it -- computed from main's own control flow alone, this candidate would have been dropped.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_001_001
  variable: svp_simple_001_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 32, flow: main}
    - {role: B, kind: read, line: 55, flow: isr_2}
    - {role: A2, kind: write, line: 32, flow: main}
  candidate_ids: [cea3c0add9327f2db]
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

### T2. (32, 58, 32) — `svp_simple_001_001@32-58-32`

**Record `cc44dd708898f87a2`** — shape WRW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_001_001.c:32 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 32) | `for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;` |
| B | read | svp_simple_001_001.c:58 | `svp_simple_001_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled | no | `svp_simple_001_001_global_array[0];    }` |
| A2 | write | svp_simple_001_001.c:32 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 32) | `for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by ['isr_1']
- preemption: `isr_2` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 32 of `svp_simple_001_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): B (line 58, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_2 may run within [line 32, line 32] of main, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: enable_isr(2) at line 46 in svp_simple_001_001_isr_1; main masks it itself (disable_isr(2) at line 28 in svp_simple_001_001_main), but isr_1 may run inside the interval and unmask it -- computed from main's own control flow alone, this candidate would have been dropped.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_001_001
  variable: svp_simple_001_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 32, flow: main}
    - {role: B, kind: read, line: 58, flow: isr_2}
    - {role: A2, kind: write, line: 32, flow: main}
  candidate_ids: [cc44dd708898f87a2]
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

### T3. (32, 60, 32) — `svp_simple_001_001@32-60-32`

**Record `cd8302b6742cc6d65`** — shape WRW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_001_001.c:32 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 32) | `for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;` |
| B | read | svp_simple_001_001.c:60 | `svp_simple_001_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled | no | `reader3 = svp_simple_001_001_global_array` |
| A2 | write | svp_simple_001_001.c:32 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 32) | `for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by ['isr_1']
- preemption: `isr_2` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 32 of `svp_simple_001_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): B (line 60, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_2 may run within [line 32, line 32] of main, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: enable_isr(2) at line 46 in svp_simple_001_001_isr_1; main masks it itself (disable_isr(2) at line 28 in svp_simple_001_001_main), but isr_1 may run inside the interval and unmask it -- computed from main's own control flow alone, this candidate would have been dropped.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_001_001
  variable: svp_simple_001_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 32, flow: main}
    - {role: B, kind: read, line: 60, flow: isr_2}
    - {role: A2, kind: write, line: 32, flow: main}
  candidate_ids: [cd8302b6742cc6d65]
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

### T4. (35, 55, 35) — `svp_simple_001_001@35-55-35`

**Record `c0955b8ecddeebb9b`** — shape WRW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_001_001.c:35 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 34) | `if (i == TRIGGER) svp_simple_001_001_global_array[i] = 1;` |
| B | read | svp_simple_001_001.c:55 | `svp_simple_001_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled | no | `reader1 = svp_simple_001_001_global_array[TRIGGER];` |
| A2 | write | svp_simple_001_001.c:35 | `svp_simple_001_001_main` | main | irq 1 enabled, irq 2 enabled | yes (header 34) | `if (i == TRIGGER) svp_simple_001_001_global_array[i] = 1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by ['isr_1']
- preemption: `isr_2` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 35 of `svp_simple_001_001_main`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): B (line 55, read): the loaded value is discarded -- stored in a local whose address is not taken and that is never read
- `masking.interval` [overapproximated]: isr_2 may run within [line 35, line 35] of main, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: enable_isr(2) at line 46 in svp_simple_001_001_isr_1; main masks it itself (disable_isr(2) at line 28 in svp_simple_001_001_main), but isr_1 may run inside the interval and unmask it -- computed from main's own control flow alone, this candidate would have been dropped.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_001_001
  variable: svp_simple_001_001_global_array
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 35, flow: main}
    - {role: B, kind: read, line: 55, flow: isr_2}
    - {role: A2, kind: write, line: 35, flow: main}
  candidate_ids: [c0955b8ecddeebb9b]
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

Top level of `svp_simple_001_001.c` before its first function:

```c
19  volatile int svp_simple_001_001_global_var;
20  volatile int svp_simple_001_001_global_array[10000];
21  volatile int svp_simple_001_001_global_flag = 0;
22  
23  #define TRIGGER 9999
```

`svp_simple_001_001_main` — svp_simple_001_001.c:25-37

```c
25  void svp_simple_001_001_main() {
26    init();
27  
28    disable_isr(2);
29  
30    idlerun();
31  
32    for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;
33  
34    for (int i = 0; i < 10000; i++) {
35      if (i == TRIGGER) svp_simple_001_001_global_array[i] = 1;
36    }
37  }
```

`svp_simple_001_001_isr_2` — svp_simple_001_001.c:51-65

```c
51  void svp_simple_001_001_isr_2() {
52    int reader1, reader3;
53    if (svp_simple_001_001_global_flag ==
54        1)
55      reader1 = svp_simple_001_001_global_array[TRIGGER];
56    else {
57      reader1 =
58          svp_simple_001_001_global_array[0];    }
59  
60    reader3 = svp_simple_001_001_global_array
61        [1000];
62  
63    int reader2;
64    reader2 = svp_simple_001_001_global_var;
65  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```

`svp_simple_001_001_isr_1` — svp_simple_001_001.c:39-49

```c
39  void svp_simple_001_001_isr_1() {
40    idlerun();
41    svp_simple_001_001_global_flag = 1;
42  
43    svp_simple_001_001_global_var = 0;
44    svp_simple_001_001_global_var = 1;
45      
46    enable_isr(2);
47  
48    idlerun();
49  }
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
