# Dossier svp_simple_023_001/D1

**Case** `svp_simple_023_001` · **location** `svp_simple_023_001_global_var` (`volatile int`, declared svp_simple_023_001.c:19) · **2 triple(s) to adjudicate** · run `svp_simple_023_001-20261115T134040Z-eb695c`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (25, 39, 35) | 2.1 bug 1 |
| (28, 39, 25) | unannotated: c46c1fc8258abe2f6 |
| (28, 39, 35) | unannotated: c6fada599ade39dff |
| (35, 39, 35) | 2.1 bug 2 |

Sibling links:

- E3: svp_simple_023_001@28-39-25 ~ svp_simple_023_001@28-39-35
- E3: svp_simple_023_001@28-39-25 ~ svp_simple_023_001:bug:1
- E3: svp_simple_023_001@28-39-35 ~ svp_simple_023_001:bug:1
- E3: svp_simple_023_001@28-39-35 ~ svp_simple_023_001:bug:2
- E3: svp_simple_023_001:bug:1 ~ svp_simple_023_001:bug:2

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

`| 23   | svp_simple_023_001.c | svp_simple_023_001_main | svp_simple_023_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_023_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_023_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, main
- `writers.svp_simple_023_001_global_var` [proven]: every store to svp_simple_023_001_global_var the analysis found (3): isr_1: svp_simple_023_001_isr_1 svp_simple_023/svp_simple_023_001.c:39 `svp_simple_023_001_global_var = 0;`; main: svp_simple_023_001_init svp_simple_023/svp_simple_023_001.c:28 `svp_simple_023_001_global_var = rand();`; main: svp_simple_023_001_func_1 svp_simple_023/svp_simple_023_001.c:35 `svp_simple_023_001_global_var = svp_simple_023_001_global_var + 1;`. declared at svp_simple_023/svp_simple_023_001.c:19 `volatile int svp_simple_023_001_global_var;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.

## Triples

### T1. (28, 39, 25) — `svp_simple_023_001@28-39-25`

**Record `c46c1fc8258abe2f6`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_023_001.c:28 | `svp_simple_023_001_init` | main | irq 1 enabled | no | `svp_simple_023_001_global_var = rand();` |
| B | write | svp_simple_023_001.c:39 | `svp_simple_023_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_023_001_global_var = 0;` |
| A2 | read | svp_simple_023_001.c:25 | `svp_simple_023_001_main` | main | irq 1 enabled | no | `svp_simple_023_001_func_1(svp_simple_023_001_global_var);` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 30 of `svp_simple_023_001_init`; left unconstrained: interference, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 25, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 35 (read), line 35 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 28, line 25] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_023_001
  variable: svp_simple_023_001_global_var
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 28, flow: main}
    - {role: B, kind: write, line: 39, flow: isr_1}
    - {role: A2, kind: read, line: 25, flow: main}
  candidate_ids: [c46c1fc8258abe2f6]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

### T2. (28, 39, 35) — `svp_simple_023_001@28-39-35`

**Record `c6fada599ade39dff`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_023_001.c:28 | `svp_simple_023_001_init` | main | irq 1 enabled | no | `svp_simple_023_001_global_var = rand();` |
| B | write | svp_simple_023_001.c:39 | `svp_simple_023_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_023_001_global_var = 0;` |
| A2 | read | svp_simple_023_001.c:35 | `svp_simple_023_001_func_1` | main | irq 1 enabled | no | `svp_simple_023_001_global_var = svp_simple_023_001_global_var + 1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 30 of `svp_simple_023_001_init`; left unconstrained: interference, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 35, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 25 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 28, line 35] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_023_001
  variable: svp_simple_023_001_global_var
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 28, flow: main}
    - {role: B, kind: write, line: 39, flow: isr_1}
    - {role: A2, kind: read, line: 35, flow: main}
  candidate_ids: [c6fada599ade39dff]
  verdict:           # bug | trap | not-a-defect | undecided
  witness:           # all four required for bug
    arrival_point:       # function and the two lines B's flow arrives between
    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)
    guard_values:        # values that make every guard on A1, B and A2 pass
    effect:              # observable change in A1/A2; shape WWR
  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable
  adjudicator:
  date:
  second_check: {done: false, adjudicator: null, verdict: null, date: null}
  notes:
```

## Source

Top level of `svp_simple_023_001.c` before its first function:

```c
19  volatile int svp_simple_023_001_global_var;
20  void svp_simple_023_001_func_1(int x);
21  void svp_simple_023_001_init();
```

`svp_simple_023_001_init` — svp_simple_023_001.c:27-31

```c
27  void svp_simple_023_001_init() {
28    svp_simple_023_001_global_var = rand();
29  
30    init();
31  }
```

`svp_simple_023_001_isr_1` — svp_simple_023_001.c:38-40

```c
38  void svp_simple_023_001_isr_1() {
39    svp_simple_023_001_global_var = 0; 
40  }
```

`svp_simple_023_001_main` — svp_simple_023_001.c:23-26

```c
23  void svp_simple_023_001_main() {
24    svp_simple_023_001_init();
25    svp_simple_023_001_func_1(svp_simple_023_001_global_var);  
26  }
```

`svp_simple_023_001_func_1` — svp_simple_023_001.c:33-37

```c
33  void svp_simple_023_001_func_1(int var) {
34    if (var > 0 && var < 12) {
35      svp_simple_023_001_global_var = svp_simple_023_001_global_var + 1;  
36    }
37  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```
