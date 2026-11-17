# Dossier svp_simple_027_001/D3

**Case** `svp_simple_027_001` · **location** `svp_simple_027_001_gloable_var` (`volatile int`, declared svp_simple_027_001.c:21) · **1 triple(s) to adjudicate** · run `svp_simple_027_001-20261115T134107Z-3c3d1d`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (45, 48, 45) | unannotated: c000abd6b90bd3301 |

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

`| 27   | svp_simple_027_001.c | svp_simple_027_001_main | svp_simple_027_001_isr_1/1/1    svp_simple_027_001_isr_2/2/2    svp_simple_027_001_isr_3/3/3 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_027_001_main` | - | 0 | isr_1, isr_2, isr_3 | 1, 2, 3 |
| isr_1 | isr | `svp_simple_027_001_isr_1` | 1 | 1 | isr_2, isr_3 | 2 |
| isr_2 | isr | `svp_simple_027_001_isr_2` | 2 | 2 | isr_3 | - |
| isr_3 | isr | `svp_simple_027_001_isr_3` | 3 | 3 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 26 in svp_simple_027_001_main); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 2: D (disable_isr(-1) at line 25 in svp_simple_027_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 42 in svp_simple_027_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 3: D (disable_isr(-1) at line 25 in svp_simple_027_001_main); E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 26 in svp_simple_027_001_main); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 2: D (disable_isr(-1) at line 25 in svp_simple_027_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 42 in svp_simple_027_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 3: D (disable_isr(-1) at line 25 in svp_simple_027_001_main); E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 26 in svp_simple_027_001_main); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 2: D (disable_isr(-1) at line 25 in svp_simple_027_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(2) at line 42 in svp_simple_027_001_isr_1); E (the initial state (masking.initial_state = all-enabled))
- `isr_3` enters with irq 3: D (disable_isr(-1) at line 25 in svp_simple_027_001_main); E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 2: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 3: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, isr_2, isr_3, main
- `writers.svp_simple_027_001_gloable_var` [proven]: every store to svp_simple_027_001_gloable_var the analysis found (5): isr_1: svp_simple_027_001_isr_1 svp_simple_027/svp_simple_027_001.c:41 `svp_simple_027_001_gloable_var++;`; isr_2: svp_simple_027_001_isr_2 svp_simple_027/svp_simple_027_001.c:45 `svp_simple_027_001_gloable_var += 2;`; isr_3: svp_simple_027_001_isr_3 svp_simple_027/svp_simple_027_001.c:48 `svp_simple_027_001_gloable_var += 3;`; main: svp_simple_027_001_main svp_simple_027/svp_simple_027_001.c:28 `svp_simple_027_001_gloable_var = 0;`; main: svp_simple_027_001_init svp_simple_027/svp_simple_027_001.c:35 `svp_simple_027_001_gloable_var = rand();`. declared at svp_simple_027/svp_simple_027_001.c:21 `volatile int svp_simple_027_001_gloable_var;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.disable_isr` [assumed_from_config]: disable_isr(n) disables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 45, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `masking.interval` [overapproximated]: isr_3 may run within [line 45, line 45] of isr_2, at nesting depth 1; irq 3 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init; isr_2 may itself start with irq 3 unmasked: an ISR begins in the state of whatever point it preempted, and isr_2 may fire wherever irq 3 is unmasked -- including before any masking call in the flows it preempts (F8).

## Triples

### T1. (45, 48, 45) — `svp_simple_027_001@45-48-45`

**Record `c000abd6b90bd3301`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_027_001.c:45 | `svp_simple_027_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_027_001_gloable_var += 2;` |
| B | write | svp_simple_027_001.c:48 | `svp_simple_027_001_isr_3` | isr_3 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_027_001_gloable_var += 3;` |
| A2 | write | svp_simple_027_001.c:45 | `svp_simple_027_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled, irq 3 enabled | no | `svp_simple_027_001_gloable_var += 2;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2, 3], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_3` into `isr_2`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 45 of `svp_simple_027_001_isr_2`; left unconstrained: interference, isr-entry-state, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_027_001
  variable: svp_simple_027_001_gloable_var
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 45, flow: isr_2}
    - {role: B, kind: write, line: 48, flow: isr_3}
    - {role: A2, kind: write, line: 45, flow: isr_2}
  candidate_ids: [c000abd6b90bd3301]
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

Top level of `svp_simple_027_001.c` before its first function:

```c
19  void svp_simple_027_001_init();
20  
21  volatile int svp_simple_027_001_gloable_var;
```

`svp_simple_027_001_isr_2` — svp_simple_027_001.c:44-46

```c
44  void svp_simple_027_001_isr_2() {
45    svp_simple_027_001_gloable_var += 2;  
46  }
```

`svp_simple_027_001_isr_3` — svp_simple_027_001.c:47-49

```c
47  void svp_simple_027_001_isr_3() {
48    svp_simple_027_001_gloable_var += 3;  
49  }
```

`svp_simple_027_001_main` — svp_simple_027_001.c:22-32

```c
22  int svp_simple_027_001_main() {
23    svp_simple_027_001_init();
24  
25    disable_isr(-1);
26    enable_isr(1);
27    if (svp_simple_027_001_gloable_var > 12) {  
28      svp_simple_027_001_gloable_var = 0;       
29    }
30  
31    return 0;
32  }
```

`svp_simple_027_001_init` — svp_simple_027_001.c:34-38

```c
34  void svp_simple_027_001_init() {
35    svp_simple_027_001_gloable_var = rand();
36  
37    init();
38  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```

`svp_simple_027_001_isr_1` — svp_simple_027_001.c:40-43

```c
40  void svp_simple_027_001_isr_1() {
41    svp_simple_027_001_gloable_var++;  
42    enable_isr(2);
43  }
```
