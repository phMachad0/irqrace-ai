# Dossier svp_simple_021_001/D1

**Case** `svp_simple_021_001` · **location** `svp_simple_021_001_tc_block_rcvd_bytes_ch1` (`volatile unsigned16`, declared svp_simple_021_001.c:20) · **3 triple(s) to adjudicate** · run `svp_simple_021_001-20261115T134014Z-701ade`

Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, "DRAFT -- Racebench 2.2"). Decide every triple from the source and the README rules below. Everything marked *tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.

## Grouping (rule E)

Rule: same-case-same-location; E1 same three lines | E2 same A1 and A2 | E3 same B and a shared endpoint; transitive closure over the triples counted.

| triple (A1, B, A2) | what it is |
| --- | --- |
| (34, 79, 44) | unannotated: c8a2f0d687072a0ef |
| (34, 79, 65) | unannotated: c238f1a05deb2bb97 |
| (44, 79, 45) | 2.1 bug 1 |
| (44, 79, 65) | 2.1 bug 3 |
| (45, 79, 65) | 2.1 bug 2 |
| (65, 79, 65) | unannotated: c558fcf2f793ffc6d |

Sibling links:

- E3: svp_simple_021_001@34-79-44 ~ svp_simple_021_001@34-79-65
- E3: svp_simple_021_001@34-79-44 ~ svp_simple_021_001:bug:1
- E3: svp_simple_021_001@34-79-44 ~ svp_simple_021_001:bug:3
- E3: svp_simple_021_001@34-79-65 ~ svp_simple_021_001@65-79-65
- E3: svp_simple_021_001@34-79-65 ~ svp_simple_021_001:bug:2
- E3: svp_simple_021_001@34-79-65 ~ svp_simple_021_001:bug:3
- E3: svp_simple_021_001@65-79-65 ~ svp_simple_021_001:bug:2
- E3: svp_simple_021_001@65-79-65 ~ svp_simple_021_001:bug:3
- E3: svp_simple_021_001:bug:1 ~ svp_simple_021_001:bug:2
- E3: svp_simple_021_001:bug:1 ~ svp_simple_021_001:bug:3
- E3: svp_simple_021_001:bug:2 ~ svp_simple_021_001:bug:3

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

`| 21   | svp_simple_021_001.c | svp_simple_021_001_main | svp_simple_021_001_isr_1/1/1                                 |`

Flows (configuration and stage 2, tool output):

| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |
| --- | --- | --- | --- | --- | --- | --- |
| main | task | `svp_simple_021_001_main` | - | 0 | isr_1 | 1 |
| isr_1 | isr | `svp_simple_021_001_isr_1` | 1 | 1 | - | - |

Masking state each flow may start with (stage 2, tool output):

- `isr_1` enters with irq 1: E (enable_isr(-1) at line 25 in init); E (the initial state (masking.initial_state = all-enabled))
- `main` enters with irq 1: E (the initial state (masking.initial_state = all-enabled))

Static facts shared by every record below (tool output):

- `variable.shared` [proven]: SVF may-alias: object 6 is reached from flows isr_1, main
- `writers.svp_simple_021_001_tc_block_rcvd_bytes_ch1` [proven]: every store to svp_simple_021_001_tc_block_rcvd_bytes_ch1 the analysis found (3): isr_1: svp_simple_021_001_isr_1 svp_simple_021/svp_simple_021_001.c:79 `svp_simple_021_001_tc_block_rcvd_bytes_ch1 =`; main: svp_simple_021_001_init svp_simple_021/svp_simple_021_001.c:34 `svp_simple_021_001_tc_block_rcvd_bytes_ch1 = rand();`; main: svp_simple_021_001_RecvTcBlock svp_simple_021/svp_simple_021_001.c:45 `svp_simple_021_001_tc_block_rcvd_bytes_ch1 = 0;`. declared at svp_simple_021/svp_simple_021_001.c:20 `volatile unsigned16 svp_simple_021_001_tc_block_rcvd_bytes_ch1;`. The list is complete: no unresolved indirect call and every called external is modelled.
- `externals.rand` [assumed_from_config]: C1 models rand as effect 'none': libc, no shared state in these subjects
- `masking_primitives.enable_isr` [assumed_from_config]: enable_isr(n) enables interrupt number n (n is argument 0 of the call); n = -1 means every interrupt. Its effect is modelled by the analysis, not opaque.
- `macros` [proven]: definitions of macros the shipped code uses: svp_simple_021_001_CNT = (volatile unsigned int *)0x10000000 (svp_simple_021/svp_simple_021_001.c:18)

## Triples

### T1. (34, 79, 44) — `svp_simple_021_001@34-79-44`

**Record `c8a2f0d687072a0ef`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_021_001.c:34 | `svp_simple_021_001_init` | main | irq 1 enabled | no | `svp_simple_021_001_tc_block_rcvd_bytes_ch1 = rand();` |
| B | write | svp_simple_021_001.c:79 | `svp_simple_021_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_021_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_021_001.c:44 | `svp_simple_021_001_RecvTcBlock` | main | irq 1 enabled | no | `if (svp_simple_021_001_tc_block_rcvd_bytes_ch1 >= 16) {` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 35 of `svp_simple_021_001_init`; left unconstrained: interference, loop, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 44, read): reaches a branch condition
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 65 (read). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 34, line 44] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_021_001
  variable: svp_simple_021_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 34, flow: main}
    - {role: B, kind: write, line: 79, flow: isr_1}
    - {role: A2, kind: read, line: 44, flow: main}
  candidate_ids: [c8a2f0d687072a0ef]
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

### T2. (34, 79, 65) — `svp_simple_021_001@34-79-65`

**Record `c238f1a05deb2bb97`** — shape WWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | write | svp_simple_021_001.c:34 | `svp_simple_021_001_init` | main | irq 1 enabled | no | `svp_simple_021_001_tc_block_rcvd_bytes_ch1 = rand();` |
| B | write | svp_simple_021_001.c:79 | `svp_simple_021_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_021_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_021_001.c:65 | `svp_simple_021_001_main` | main | irq 1 enabled | yes (header 61) | `svp_simple_021_001_tc_block_rcvd_bytes_ch1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 35 of `svp_simple_021_001_init`; left unconstrained: interference, loop, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A2 (line 65, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 44 (read), line 45 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 34, line 65] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: the initial state (masking.initial_state = all-enabled); enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_021_001
  variable: svp_simple_021_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: write, line: 34, flow: main}
    - {role: B, kind: write, line: 79, flow: isr_1}
    - {role: A2, kind: read, line: 65, flow: main}
  candidate_ids: [c238f1a05deb2bb97]
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

### T3. (65, 79, 65) — `svp_simple_021_001@65-79-65`

**Record `c558fcf2f793ffc6d`** — shape RWR

| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | read | svp_simple_021_001.c:65 | `svp_simple_021_001_main` | main | irq 1 enabled | yes (header 61) | `svp_simple_021_001_tc_block_rcvd_bytes_ch1;` |
| B | write | svp_simple_021_001.c:79 | `svp_simple_021_001_isr_1` | isr_1 | irq 1 enabled | no | `svp_simple_021_001_tc_block_rcvd_bytes_ch1 =` |
| A2 | read | svp_simple_021_001.c:65 | `svp_simple_021_001_main` | main | irq 1 enabled | yes (header 61) | `svp_simple_021_001_tc_block_rcvd_bytes_ch1;` |

Static facts about this record (tool output, not a judgement on the defect):

- masking over the interval A1..A2: enabled somewhere [1], disabled throughout [], unknown [], re-enabled within the interval by []
- preemption: `isr_1` into `main`, priority relation strictly-higher, nesting depth 1, timing unconstrained
- solver (z3 4.8.12): result `sat`, preemption placed at line 64 of `svp_simple_021_001_main`; left unconstrained: interference, loop, timing, unresolved-pointer. `sat` means *not refuted* by an over-approximate encoding; it is not a witness.
- `value_use` [proven]: where the value the interleaving changes goes, within its function (def-use, through locals): A1 (line 65, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced; A2 (line 65, read): leaves the function (passed to a call, returned or stored to non-local memory); its use there is not traced
- `interval.local_accesses` [overapproximated]: the local flow may also access this location between A1 and A2, on some path: line 34 (write), line 44 (read), line 45 (write). A remote access landing between such an access and A2 forms another, narrower triple; this one is not dropped.
- `masking.interval` [overapproximated]: isr_1 may run within [line 65, line 65] of main, at nesting depth 1; irq 1 is not masked on every path there; it may be enabled by: enable_isr(-1) at line 25 in init.

Witness form:

```yaml
- id: R22-____
  case: svp_simple_021_001
  variable: svp_simple_021_001_tc_block_rcvd_bytes_ch1
  triple:            # A1, B, A2
    - {role: A1, kind: read, line: 65, flow: main}
    - {role: B, kind: write, line: 79, flow: isr_1}
    - {role: A2, kind: read, line: 65, flow: main}
  candidate_ids: [c558fcf2f793ffc6d]
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

Top level of `svp_simple_021_001.c` before its first function:

```c
18  #define svp_simple_021_001_CNT (volatile unsigned int *)0x10000000
19  
20  volatile unsigned16 svp_simple_021_001_tc_block_rcvd_bytes_ch1;
21  volatile unsigned16 svp_simple_021_001_tc_block_rcvd_bytes_ch2;
22  volatile unsigned16 svp_simple_021_001_tc_block_rcvd_bytes;
23  volatile unsigned8 svp_simple_021_001_tc_chan1_buff[256];
24  volatile unsigned8 svp_simple_021_001_tc_chan2_buff[256];
25  volatile unsigned8 *svp_simple_021_001_tc_buff_p;
26  
27  struct svp_simple_021_001_tc_block_data {
28    unsigned8 type;
29    unsigned8 id;
30    unsigned8 valid_len;
31  };
```

`svp_simple_021_001_init` — svp_simple_021_001.c:33-38

```c
33  void svp_simple_021_001_init() {
34    svp_simple_021_001_tc_block_rcvd_bytes_ch1 = rand();
35    svp_simple_021_001_tc_block_rcvd_bytes_ch2 = rand();
36  
37    init();
38  }
```

`svp_simple_021_001_isr_1` — svp_simple_021_001.c:78-81

```c
78  void svp_simple_021_001_isr_1() {
79    svp_simple_021_001_tc_block_rcvd_bytes_ch1 =
80        (*(svp_simple_021_001_CNT) >> 3) & 0x1FFF;
81  }
```

`svp_simple_021_001_RecvTcBlock` — svp_simple_021_001.c:40-52

```c
40  void svp_simple_021_001_RecvTcBlock() {
41    unsigned svp_simple_021_001_flag_chan1;
42    svp_simple_021_001_flag_chan1 = 0;
43  
44    if (svp_simple_021_001_tc_block_rcvd_bytes_ch1 >= 16) { 
45      svp_simple_021_001_tc_block_rcvd_bytes_ch1 = 0;       
46      int i;
47      for (i = 0; i < 256; i++) {
48        svp_simple_021_001_tc_chan1_buff[i] = 0;
49      }
50      svp_simple_021_001_flag_chan1 = 0xFF;
51    }
52  }
```

`svp_simple_021_001_main` — svp_simple_021_001.c:54-76

```c
54  void svp_simple_021_001_main() {
55    struct svp_simple_021_001_tc_block_data tc_block;
56  
57    svp_simple_021_001_init();
58  
59    svp_simple_021_001_RecvTcBlock();
60    int ichan;
61    for (ichan = 0; ichan < 2; ichan++) {
62      if (ichan == 0) {
63        svp_simple_021_001_tc_buff_p = svp_simple_021_001_tc_chan1_buff;
64        svp_simple_021_001_tc_block_rcvd_bytes =
65            svp_simple_021_001_tc_block_rcvd_bytes_ch1; 
66      } else {
67        svp_simple_021_001_tc_buff_p = svp_simple_021_001_tc_chan2_buff;
68        svp_simple_021_001_tc_block_rcvd_bytes =
69            svp_simple_021_001_tc_block_rcvd_bytes_ch2;
70      }
71  
72      tc_block.type = *(svp_simple_021_001_tc_buff_p + 2);
73      tc_block.id = *(svp_simple_021_001_tc_buff_p + 4);
74      tc_block.valid_len = *(svp_simple_021_001_tc_buff_p + 5);
75    }
76  }
```

`init` — common.c:25-25

```c
25  void init() { enable_isr(-1); }
```
