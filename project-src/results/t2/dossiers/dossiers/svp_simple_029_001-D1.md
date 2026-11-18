# Dossier svp_simple_029_001/D1

**Case** `svp_simple_029_001` · **location** `svp_simple_029_001_tm_blocks` (`volatile unsigned8[]`, declared svp_simple_029_001.c:19) · **1 triple(s) to adjudicate** · run `svp_simple_029_001-20261115T134139Z-169fa3`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (45, 83, 80) | unannotated: cda9b1d644c8ca8d9 |
| (80, 83, 80) | 2.1 trap 1 |
| (80, 83, 83) | 2.1 bug 1 |

Sibling links:

- E3: svp_simple_029_001@45-83-80 ~ svp_simple_029_001:bug:1
- E3: svp_simple_029_001@45-83-80 ~ svp_simple_029_001:trap:1
- E3: svp_simple_029_001:bug:1 ~ svp_simple_029_001:trap:1

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

`| 29   | svp_simple_029_001.c | svp_simple_029_001_main | svp_simple_029_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_029_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_029_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 7 is reached from flows isr_1, main
- `writers.svp_simple_029_001_tm_blocks` [proven]: every store to svp_simple_029_001_tm_blocks the analysis found (3): isr_1: svp_simple_029_001_SetTmData svp_simple_029/svp_simple_029_001.c:83 `svp_simple_029_001_tm_blocks[tm_name] = tm_data;`; main: svp_simple_029_001_init svp_simple_029/svp_simple_029_001.c:45 `svp_simple_029_001_tm_blocks[i] = rand();`; main: svp_simple_029_001_SetTmData svp_simple_029/svp_simple_029_001.c:83 `svp_simple_029_001_tm_blocks[tm_name] = tm_data;`. declared at svp_simple_029/svp_simple_029_001.c:19 `volatile unsigned8 svp_simple_029_001_tm_blocks[4096];`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.tm_data` [proven]: every store to tm_data the analysis found (0): none. declared at svp_simple_029/svp_simple_029_001.c:82 `void svp_simple_029_001_SetTmData(unsigned32 tm_name, unsigned8 tm_data) {`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.tm_name` [proven]: every store to tm_name the analysis found (0): none. declared at svp_simple_029/svp_simple_029_001.c:82 `void svp_simple_029_001_SetTmData(unsigned32 tm_name, unsigned8 tm_data) {`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_029_001_ptr_SetTmData` [proven]: every store to svp_simple_029_001_ptr_SetTmData the analysis found (1): main: svp_simple_029_001_TmOrgFuncMap svp_simple_029/svp_simple_029_001.c:53 `svp_simple_029_001_ptr_SetTmData = svp_simple_029_001_SetTmData;`. declared at svp_simple_029/svp_simple_029_001.c:23 `void (*svp_simple_029_001_ptr_SetTmData)(unsigned32, unsigned8);`. The list is complete: no unresolved indirect call and every called external is modelled.
- `writers.svp_simple_029_001_average_adjust_flag` [proven]: every store to svp_simple_029_001_average_adjust_flag the analysis found (1): main: svp_simple_029_001_init svp_simple_029/svp_simple_029_001.c:47 `svp_simple_029_001_average_adjust_flag = 0xFF;`. declared at svp_simple_029/svp_simple_029_001.c:20 `volatile unsigned8 svp_simple_029_001_average_adjust_flag;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 80, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 83 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 45, line 80] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

## Triples

### T1. (45, 83, 80) — `svp_simple_029_001@45-83-80`

**Record `cda9b1d644c8ca8d9`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_029_001.c:45 | `svp_simple_029_001_init` | main | irq 1 enabled | yes (header 44) | `svp_simple_029_001_tm_blocks[i] = rand();` |
| B | write | svp_simple_029_001.c:83 | `svp_simple_029_001_SetTmData` | isr_1 | irq 1 enabled | no | `svp_simple_029_001_tm_blocks[tm_name] = tm_data;` |
| A2 | read | svp_simple_029_001.c:80 | `svp_simple_029_001_GetTmData` | main | irq 1 enabled | no | `return svp_simple_029_001_tm_blocks[tm_name];` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 54 of `svp_simple_029_001_TmOrgFuncMap`; left unconstrained: interference, loop, timing. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_029_001
  variable: svp_simple_029_001_tm_blocks
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 45, flow: main}
    - {role: B, kind: write, line: 83, flow: isr_1}
    - {role: A2, kind: read, line: 80, flow: main}
  candidate_ids: [cda9b1d644c8ca8d9]
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

Top level of `svp_simple_029_001.c` before its first function:

```c
19  volatile unsigned8 svp_simple_029_001_tm_blocks[4096];
20  volatile unsigned8 svp_simple_029_001_average_adjust_flag;
21  volatile unsigned8 svp_simple_029_001_average_adjust_count;
22  volatile unsigned8 (*svp_simple_029_001_ptr_GetTmData)(unsigned32);
23  void (*svp_simple_029_001_ptr_SetTmData)(unsigned32, unsigned8);
24  void (*svp_simple_029_001_ptr_SetSelfCtrlFlag)(unsigned32, unsigned8, unsigned8);
25  
26  void svp_simple_029_001_TmOrgFuncMap();
27  void svp_simple_029_001_SetSelfCtrlFlag(unsigned32 tm_para, unsigned8 ctrl_flag,
28                                      unsigned8 flag_pos);
29  unsigned8 svp_simple_029_001_GetTmData(unsigned32 tm_name);
30  void svp_simple_029_001_SetTmData(unsigned32 tm_name, unsigned8 tm_data);
31  
32  void svp_simple_029_001_init();
```

`svp_simple_029_001_init` — svp_simple_029_001.c:43-50

```c
43  void svp_simple_029_001_init() {
44    for (int i = 0; i < 4096; i++) {
45      svp_simple_029_001_tm_blocks[i] = rand();
46    }
47    svp_simple_029_001_average_adjust_flag = 0xFF;
48  
49    init();
50  }
```

`svp_simple_029_001_SetTmData` — svp_simple_029_001.c:82-84

```c
82  void svp_simple_029_001_SetTmData(unsigned32 tm_name, unsigned8 tm_data) {
83    svp_simple_029_001_tm_blocks[tm_name] = tm_data; 
84  }
```

`svp_simple_029_001_GetTmData` — svp_simple_029_001.c:79-81

```c
79  unsigned8 svp_simple_029_001_GetTmData(unsigned32 tm_name) {
80    return svp_simple_029_001_tm_blocks[tm_name]; 
81  }
```

`svp_simple_029_001_main` — svp_simple_029_001.c:34-42

```c
34  void svp_simple_029_001_main() {
35    unsigned8 svp_simple_029_001_local_status = 1;
36    svp_simple_029_001_init();
37    svp_simple_029_001_TmOrgFuncMap();
38    
39    if (svp_simple_029_001_local_status == 1) {
40      svp_simple_029_001_ptr_SetSelfCtrlFlag(36, 0xFF, 0);
41    }
42  }
```

`svp_simple_029_001_isr_1` — svp_simple_029_001.c:86-95

```c
86  void svp_simple_029_001_isr_1() {
87    if (svp_simple_029_001_average_adjust_flag == 0xFF) {
88      svp_simple_029_001_average_adjust_count++;
89      svp_simple_029_001_ptr_SetTmData(
90          36, svp_simple_029_001_average_adjust_count); 
91    } else {
92      svp_simple_029_001_average_adjust_count = 0;
93      svp_simple_029_001_ptr_SetTmData(36, svp_simple_029_001_average_adjust_count);
94    }
95  }
```

`svp_simple_029_001_SetSelfCtrlFlag` — svp_simple_029_001.c:57-78

```c
57  void svp_simple_029_001_SetSelfCtrlFlag(unsigned32 tm_para, unsigned8 ctrl_flag,
58                                      unsigned8 flag_pos) {
59    unsigned8 tmp1;
60    unsigned8 tmp2;
61    unsigned8 ctrl_sts;
62  
63    if (ctrl_flag > 0x80) {
64      tmp1 = 1;
65    } else {
66      tmp1 = 0;
67    }
68  
69    tmp1 <<= flag_pos;
70    tmp2 = 1;
71    tmp2 <<= ~tmp2;
72  
73    ctrl_sts = svp_simple_029_001_ptr_GetTmData(tm_para);       
74    ctrl_sts -= svp_simple_029_001_ptr_GetTmData(tm_para + 1);  
75    ctrl_sts |= tmp1;
76  
77    svp_simple_029_001_ptr_SetTmData(tm_para, ctrl_sts);  
78  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```
