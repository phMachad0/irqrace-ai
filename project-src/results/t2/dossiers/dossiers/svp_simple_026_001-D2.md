# Dossier svp_simple_026_001/D2

**Case** `svp_simple_026_001` · **location** `svp_simple_026_001_gloable_var` (`volatile int`, declared svp_simple_026_001.c:21) · **1 triple(s) to adjudicate** · run `svp_simple_026_001-20261115T134059Z-b2a2c8`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (40, 43, 40) | unannotated: c423d7fc5292241b4 |

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

`| 26   | svp_simple_026_001.c | svp_simple_026_001_main | svp_simple_026_001_isr_1/1/1     svp_simple_026_001_isr_2/2/2 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_026_001_main` | - | 0 | isr_1, isr_2 | 1, 2 |
| isr_1 | isr | `svp_simple_026_001_isr_1` | 1 | 1 | isr_2 | - |
| isr_2 | isr | `svp_simple_026_001_isr_2` | 2 | 2 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 29 in svp_simple_026_001_main); E (the initial state (masking.initial_state = all-enabled))
- `isr_1` enters with irq 2: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 1: D (disable_isr(1) at line 25 in svp_simple_026_001_main); E (enable_isr(-1) at line 25 in init); E (enable_isr(1) at line 29 in svp_simple_026_001_main); E (the initial state (masking.initial_state = all-enabled))
- `isr_2` enters with irq 2: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 2: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, isr_2, main
- `writers.svp_simple_026_001_gloable_var` [proven]: every store to svp_simple_026_001_gloable_var the analysis found (4): isr_1: svp_simple_026_001_isr_1 svp_simple_026/svp_simple_026_001.c:40 `svp_simple_026_001_gloable_var++;`; isr_2: svp_simple_026_001_isr_2 svp_simple_026/svp_simple_026_001.c:43 `svp_simple_026_001_gloable_var--;`; main: svp_simple_026_001_main svp_simple_026/svp_simple_026_001.c:27 `svp_simple_026_001_gloable_var = 0;`; main: svp_simple_026_001_init svp_simple_026/svp_simple_026_001.c:34 `svp_simple_026_001_gloable_var = rand();`. declared at svp_simple_026/svp_simple_026_001.c:21 `volatile int svp_simple_026_001_gloable_var;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `masking_primitives.disable_isr` [assumed_from_config]: disable_isr(n) disables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 40, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `masking.interval` [overapproximated]: isr_2 may run within [line 40, line 40] of isr_1, at nesting depth 1; irq 2 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init; isr_1 may itself start with irq 2 unmasked: an ISR begins in the state of whatever point it preempted, and isr_1 may fire wherever irq 2 is unmasked -- including before any masking call in the flows it preempts (F8).

## Triples

### T1. (40, 43, 40) — `svp_simple_026_001@40-43-40`

**Record `c423d7fc5292241b4`** — shape RWW

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_026_001.c:40 | `svp_simple_026_001_isr_1` | isr_1 | irq 1 enabled, irq 2 enabled | no | `svp_simple_026_001_gloable_var++;` |
| B | write | svp_simple_026_001.c:43 | `svp_simple_026_001_isr_2` | isr_2 | irq 1 enabled, irq 2 enabled | no | `svp_simple_026_001_gloable_var--;` |
| A2 | write | svp_simple_026_001.c:40 | `svp_simple_026_001_isr_1` | isr_1 | irq 1 enabled, irq 2 enabled | no | `svp_simple_026_001_gloable_var++;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1, 2], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_2` into `isr_1`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 40 of `svp_simple_026_001_isr_1`; left unconstrained: interference, isr-entry-state, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_026_001
  variable: svp_simple_026_001_gloable_var
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 40, flow: isr_1}
    - {role: B, kind: write, line: 43, flow: isr_2}
    - {role: A2, kind: write, line: 40, flow: isr_1}
  candidate_ids: [c423d7fc5292241b4]
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

Top level of `svp_simple_026_001.c` before its first function:

```c
19  void svp_simple_026_001_init();
20  
21  volatile int svp_simple_026_001_gloable_var;
```

`svp_simple_026_001_isr_1` — svp_simple_026_001.c:39-41

```c
39  void svp_simple_026_001_isr_1() {
40    svp_simple_026_001_gloable_var++;  
41  }
```

`svp_simple_026_001_isr_2` — svp_simple_026_001.c:42-44

```c
42  void svp_simple_026_001_isr_2() {
43    svp_simple_026_001_gloable_var--;  
44  }
```

`svp_simple_026_001_main` — svp_simple_026_001.c:22-32

```c
22  int svp_simple_026_001_main() {
23    svp_simple_026_001_init();
24  
25    disable_isr(1);
26    if (svp_simple_026_001_gloable_var > 12) {  
27      svp_simple_026_001_gloable_var = 0;       
28    }
29    enable_isr(1);
30  
31    return 0;
32  }
```

`svp_simple_026_001_init` — svp_simple_026_001.c:33-37

```c
33  void svp_simple_026_001_init() {
34    svp_simple_026_001_gloable_var = rand();
35  
36    init();
37  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```
