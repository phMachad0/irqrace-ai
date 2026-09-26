"""The eighteen fixtures: which annotation, and the analysis behind it.

Each entry names a Racebench annotation and carries the stage-2 analysis a
person did by reading the case -- masking at each access and across the
interval, whether the remote flow can preempt, and why. The mechanical half
comes from the source (:mod:`irqrace.llm.fixture_builder`).

**Selection is by coverage, not convenience.** With the annotation reader in
place the whole suite is visible, so the set is chosen to span:

* the four access patterns the suite actually uses;
* every row of the D#1 interrupt-pattern table that the simple cases contain;
* the constructs that separate the tools -- interrupt nesting, pointer
  aliasing, function-pointer dispatch, interprocedural call paths, arrays;
* and, deliberately, **adversarial pairs**: fixtures that differ in label while
  differing in exactly one fact. ``svp_simple_003_001``'s bug point and its
  second trap share A1, A2, variable, flows and masking, and part only on
  whether the remote write sits in a reachable branch. ``svp_simple_017_001``
  bug 1 and ``svp_simple_006_001`` trap 2 are both "the same statement twice in
  a loop", and one loop runs many times while the other runs exactly once. A
  prompt that separates those has learned the rule; one that pattern-matches
  the shape cannot.

**Excluded: ``svp_simple_019_001``.** Its five annotations describe the older
copy of the case, in which `enable_isr(1)` sits *after* the guarded read rather
than before it -- so the masking state of the annotated accesses is inverted
between the two files, and the labels cannot be trusted until someone decides
which program they describe (``wiki/benchmarks/Racebench.md``).

Traps in this suite come in more shapes than the design anticipated, which is
itself a finding: only one of the nine here is the "critical section covers the
interval" shape the D#1 table leads with. The rest are unreachable guards,
disjoint array elements, a reassigned pointer, a ternary that evaluates one arm,
and a loop body that executes exactly once.
"""

from __future__ import annotations

from irqrace.llm.fixture_builder import AccessSpec, FixtureSpec

#: ``init()`` in ``common.c`` calls ``enable_isr(-1)``, so every flow starts
#: with all interrupts enabled unless the case masks one.
ALL_ENABLED = (1, 2, 3)

#: Source paths, as C2 records them: relative to the suite root.
SRC = {
    case: f"{case}/{case}_001.c"
    for case in ("svp_simple_001", "svp_simple_003", "svp_simple_029")
}


def _enabled(*irqs: int) -> AccessSpec:
    return AccessSpec(enabled=irqs)


#: Recorded on every fixture whose accesses sit inside an ISR. The suite README
#: says a higher-priority interrupt may preempt a lower-priority one but does
#: not say whether an ISR's own line is masked while it runs. Unmodelled, and
#: surfaced rather than assumed away.
_AUTOMASK_NOTE = {
    "fact": "masking.per_access",
    "status": "unknown",
    "note": (
        "whether an ISR's own interrupt line is masked for the duration of the "
        "handler is not specified by the suite and is not modelled here; only "
        "explicit disable_isr/enable_isr calls are treated as established"
    ),
}


SPECS: tuple[FixtureSpec, ...] = (
    # ---------------------------------------------------------------- bug points
    FixtureSpec(
        case="svp_simple_001",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "D#1 row 7 -- dynamic masking. main disables irq 2 at line 28 and "
            "never re-enables it, so a per-flow reading of main's CFG calls the "
            "interval protected. But isr_1 runs on irq 1, which is not masked, "
            "and it calls enable_isr(2) at line 46 from inside the interval. "
            "Interval masking has to account for flows that execute within the "
            "interval, not just the local CFG; the alternative drops a real "
            "defect (project-src/docs/masking-semantics.md)."
        ),
        accesses=(
            AccessSpec(disabled=(2,), enabled=(1,)),
            AccessSpec(enabled=(2,), unknown=(1,)),
            AccessSpec(disabled=(2,), enabled=(1,)),
        ),
        interval_enabled=(1, 2),
        reenabled_within_interval_by=("isr_1",),
        critical_sections=(
            {
                "irqs": [2],
                "begin": {"file": SRC["svp_simple_001"], "line": 28},
                "end": {"file": SRC["svp_simple_001"], "line": 46},
                "covers_interval": False,
            },
        ),
        used_as_index=True,
        provenance=(
            {
                "fact": "masking.interval.reenabled_within_interval_by",
                "status": "proven",
                "note": (
                    "irq 2 is masked at line 28 on every path through main, but "
                    "isr_1 may preempt the interval and calls enable_isr(2) at "
                    "line 46, so irq 2 is NOT masked throughout. Computing this "
                    "from main's CFG alone would drop an annotated bug point"
                ),
            },
            {
                "fact": "accesses[1].source",
                "status": "proven",
                "note": (
                    "the read at line 55 is guarded by global_flag == 1, which "
                    "isr_1 sets at line 41 before re-enabling irq 2 -- so the "
                    "guard and the unmasking come from the same preemption"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_002",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "interrupt nesting: both local accesses are in isr_1 (irq 1) and the "
            "remote write is in isr_2 (irq 2). The preempting flow is an ISR, not "
            "the task, which is the capability that most separates the tools "
            "(wiki/concepts/Interrupt Nesting.md). No masking anywhere in the case."
        ),
        accesses=(_enabled(1, 2), _enabled(1, 2), _enabled(1, 2)),
        interval_enabled=(1, 2),
        provenance=(
            _AUTOMASK_NOTE,
            {
                "fact": "preemption",
                "status": "proven",
                "note": (
                    "isr_2 has priority 2 and isr_1 priority 1; by the README's "
                    "stated convention a larger number is higher, so isr_2 may "
                    "preempt isr_1. The case contains no disable_isr call."
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_003",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "masking released mid-function. main masks irq 1 at line 33 and "
            "re-enables it at line 47; both local reads sit after line 47, so the "
            "interval is unprotected even though the function opens with a "
            "critical section. Adversarially paired with the 003 trap below, "
            "whose only difference is the branch the remote write sits in."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        interval_unknown=(2,),
        reenabled_within_interval_by=("isr_1",),
        critical_sections=(
            {
                "irqs": [1],
                "begin": {"file": SRC["svp_simple_003"], "line": 33},
                "end": {"file": SRC["svp_simple_003"], "line": 47},
                "covers_interval": False,
            },
        ),
        provenance=(
            {
                "fact": "masking.interval",
                "status": "proven",
                "note": (
                    "irq 1 is disabled at line 33 and re-enabled at line 47; both "
                    "reads are at lines 50 and 55, after the critical section "
                    "closes, so irq 1 is enabled throughout the interval"
                ),
            },
            {
                "fact": "masking.interval.reenabled_within_interval_by",
                "status": "proven",
                "note": (
                    "irq 2 is disabled at line 34 and never re-enabled in main, "
                    "but isr_1 calls enable_isr(2) at line 61 and isr_1 may run "
                    "inside the interval, so irq 2 is not disabled throughout"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_005",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "no synchronisation of any kind: the case contains no disable_isr "
            "call at all. The baseline against which a model that hallucinates "
            "protection is visible."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        provenance=(
            {
                "fact": "masking",
                "status": "proven",
                "note": "the subject contains no disable_isr call on any path",
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_007",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "array element identity. A1 writes global_array[i] under the guard "
            "i == 2, the remote write targets global_array[2], and A2 reads "
            "global_array[2] -- the same element on every path, which is what "
            "makes this real where the 007 trap is not."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        used_as_index=True,
        provenance=(
            {
                "fact": "accesses",
                "status": "proven",
                "note": (
                    "A1 is guarded by i == 2 so it writes element 2; the remote "
                    "write and A2 both name element 2 literally"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_009",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "pointer aliasing. A2 writes through q, not p, and the triple is real "
            "only because lines 29 and 30 assign both pointers the address of the "
            "same object. One of the five cases in the suite whose annotation "
            "names a global that the annotated line reaches indirectly."
        ),
        variable="svp_simple_009_001_p",
        aliases=("svp_simple_009_001_q",),
        accesses=(
            _enabled(1),
            _enabled(1),
            AccessSpec(
                enabled=(1,),
                correction=(
                    "line 33 writes through svp_simple_009_001_q, which line 30 "
                    "assigns &local_var1 -- the same object line 29 assigns to "
                    "svp_simple_009_001_p. The annotation names *p; the access is "
                    "through its alias"
                ),
            ),
        ),
        interval_enabled=(1,),
        provenance=(
            {
                "fact": "variable",
                "status": "proven",
                "note": (
                    "the shared object is main's local_var1, whose address escapes "
                    "into the globals p and q; storage is recorded as global "
                    "because the annotation names the pointer, and the aliasing is "
                    "what the candidate turns on"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_015",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "two reads of one condition, split across lines 30 and 31, with the "
            "remote write between them. The variable feeds a branch, so the "
            "harmfulness criterion fires -- this is the fixture that separates "
            "the feasibility question from the harm question."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        feeds_branch=True,
        provenance=(
            {
                "fact": "static_features.feeds_branch",
                "status": "proven",
                "note": (
                    "both reads are operands of the if condition at lines 30-31, "
                    "so an interleaved write changes control flow"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_016",
        kind="bug_point",
        index=3,
        label="bug_point",
        exercises=(
            "one C statement spanning three lines, with two of its reads as A1 "
            "and A2. Tests whether the model treats a multi-line expression as "
            "several accesses rather than one. Bug point 3 is used rather than "
            "1 because bug point 1 is written <W#24>,<R#33>,<R#25> while line 33 "
            "is a write -- its middle access type is wrong in the suite "
            "(wiki/benchmarks/Racebench.md)."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
    ),
    FixtureSpec(
        case="svp_simple_017",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "D#1 row 5 -- the same statement inside a loop serving as both A1 and "
            "A2. Line 29 is the for-condition and it is read once per iteration, "
            "so two iterations give two accesses. Adversarially paired with the "
            "006 trap, which has the same shape and executes exactly once."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        feeds_branch=True,
        used_as_index=True,
        provenance=(
            {
                "fact": "loop_context.a1_a2_same_statement",
                "status": "proven",
                "note": (
                    "the for header at line 29 runs MAX_LENGTH times, so its "
                    "condition read occurs repeatedly and A1 and A2 are two "
                    "distinct executions of one statement"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_029",
        kind="bug_point",
        index=1,
        label="bug_point",
        exercises=(
            "function-pointer dispatch and interprocedural call paths. Every "
            "access reaches tm_blocks through a pointer assigned in "
            "TmOrgFuncMap, and the remote write shares a source line with A2 "
            "while belonging to a different flow. The only case in the suite "
            "that exercises indirect calls at all."
        ),
        accesses=(
            AccessSpec(
                enabled=(1,),
                flow="main",
                frames=(
                    {"function": "svp_simple_029_001_main",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 40}},
                    {"function": "svp_simple_029_001_SetSelfCtrlFlag",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 73},
                     "resolution": "indirect-resolved"},
                    {"function": "svp_simple_029_001_GetTmData"},
                ),
            ),
            AccessSpec(
                enabled=(1,),
                flow="isr_1",
                frames=(
                    {"function": "svp_simple_029_001_isr_1",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 89},
                     "resolution": "indirect-resolved"},
                    {"function": "svp_simple_029_001_SetTmData"},
                ),
            ),
            AccessSpec(
                enabled=(1,),
                flow="main",
                frames=(
                    {"function": "svp_simple_029_001_main",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 40}},
                    {"function": "svp_simple_029_001_SetSelfCtrlFlag",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 77},
                     "resolution": "indirect-resolved"},
                    {"function": "svp_simple_029_001_SetTmData"},
                ),
            ),
        ),
        interval_enabled=(1,),
        used_as_index=True,
        provenance=(
            {
                "fact": "call_paths",
                "status": "proven",
                "note": (
                    "the three pointers are assigned their only targets in "
                    "TmOrgFuncMap at lines 53-55, which main calls before any "
                    "dispatch, so each indirect call has exactly one resolution"
                ),
            },
            {
                "fact": "accesses",
                "status": "proven",
                "note": (
                    "B and A2 share source line 83 and differ only in flow: the "
                    "ISR reaches SetTmData directly, the task through "
                    "SetSelfCtrlFlag line 77. Both write tm_blocks[36]"
                ),
            },
        ),
    ),
    # -------------------------------------------------------------------- traps
    FixtureSpec(
        case="svp_simple_001",
        kind="trap",
        index=1,
        label="trap",
        exercises=(
            "D#1 row 1 -- one critical section covering the interval, and the "
            "counterpart to the 001 bug point. Both writes sit at lines 43-44 "
            "inside isr_1, irq 2 is masked from line 28, and isr_1's "
            "enable_isr(2) is at line 46, after both. Same subject, same WRW "
            "pattern, same shape of evidence, opposite answer: the only "
            "difference is whether a flow running inside the interval re-enables "
            "the interrupt. A prompt that gets both right has learned the rule."
        ),
        accesses=(
            AccessSpec(disabled=(2,), enabled=(1,)),
            AccessSpec(
                line=64,
                enabled=(2,),
                unknown=(1,),
                correction=(
                    "the annotation gives <R#63>, but line 63 is `int reader2;`, "
                    "a declaration with no access to the variable; the read is on "
                    "line 64"
                ),
            ),
            AccessSpec(disabled=(2,), enabled=(1,)),
        ),
        interval_disabled=(2,),
        critical_sections=(
            {
                "irqs": [2],
                "begin": {"file": SRC["svp_simple_001"], "line": 28},
                "end": {"file": SRC["svp_simple_001"], "line": 46},
                "covers_interval": True,
            },
        ),
        provenance=(
            {
                "fact": "masking.interval.disabled_throughout",
                "status": "proven",
                "note": (
                    "main disables irq 2 at line 28 and isr_1 re-enables it at "
                    "line 46, after both writes; no flow that may run inside "
                    "[43, 44] re-enables it, so irq 2 is masked throughout"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_002",
        kind="trap",
        index=1,
        label="trap",
        exercises=(
            "unreachable guard. A1 sits under if (i == MAX_LENGTH + 1) inside a "
            "loop bounded by i < MAX_LENGTH, so it never executes. Masking is "
            "irrelevant and a model reaching for it has misread the case."
        ),
        accesses=(_enabled(1, 2), _enabled(1, 2), _enabled(1, 2)),
        interval_enabled=(1, 2),
        provenance=(
            _AUTOMASK_NOTE,
            {
                "fact": "accesses[0].source",
                "status": "proven",
                "note": (
                    "the enclosing loop runs i from 0 to MAX_LENGTH - 1, so the "
                    "guard i == MAX_LENGTH + 1 at line 34 is unsatisfiable and "
                    "line 35 is dead"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_003",
        kind="trap",
        index=1,
        label="trap",
        exercises=(
            "D#1 row 1 -- one critical section covering the whole interval. Both "
            "reads sit between disable_isr(1) at line 33 and enable_isr(1) at "
            "line 47, and no flow that could run inside the interval re-enables "
            "irq 1, so the remote write cannot land between them."
        ),
        accesses=(
            AccessSpec(disabled=(1, 2)),
            AccessSpec(disabled=(1, 2)),
            AccessSpec(disabled=(1, 2)),
        ),
        interval_disabled=(1, 2),
        critical_sections=(
            {
                "irqs": [1, 2],
                "begin": {"file": SRC["svp_simple_003"], "line": 33},
                "end": {"file": SRC["svp_simple_003"], "line": 47},
                "covers_interval": True,
            },
        ),
        provenance=(
            {
                "fact": "masking.interval.disabled_throughout",
                "status": "proven",
                "note": (
                    "irq 1 and irq 2 are disabled at lines 33-34 and irq 1 is only "
                    "re-enabled at line 47, after both reads. The only flow that "
                    "re-enables irq 2 is isr_1, which cannot run while irq 1 is "
                    "masked, so the interval is genuinely closed -- unlike "
                    "svp_simple_001_001, where isr_1 punctures it"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_003",
        kind="trap",
        index=2,
        label="trap",
        exercises=(
            "the remote write sits in an unreachable branch. Identical to the 003 "
            "bug point in variable, flows, local accesses and masking; the only "
            "difference is that the write is at line 67, under else-if "
            "(global_flag1 == 2), and global_flag1 is initialised to 0 and never "
            "assigned anywhere in the subject. The sharpest pair in the set."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        interval_unknown=(2,),
        reenabled_within_interval_by=("isr_1",),
        provenance=(
            {
                "fact": "accesses[1].source",
                "status": "proven",
                "note": (
                    "global_flag1 is declared and initialised to 0 at line 26 and "
                    "never written on any path, so the else-if at line 66 is "
                    "unsatisfiable and the write at line 67 is dead. The masking "
                    "state is the same as the annotated bug point's"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_005",
        kind="trap",
        index=1,
        label="trap",
        exercises=(
            "A2 under a guard on a global that is never written. "
            "global_condition is initialised to 0 and no flow assigns it, so line "
            "38 is dead and the triple cannot complete."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        provenance=(
            {
                "fact": "accesses[2].source",
                "status": "proven",
                "note": (
                    "global_condition is initialised to 0 at line 23 and never "
                    "assigned in main or isr_1, so the guard at line 36 is "
                    "unsatisfiable and line 38 is dead"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_006",
        kind="trap",
        index=2,
        label="trap",
        exercises=(
            "the counterpart to D#1 row 5. A1 and A2 are the same statement in a "
            "nested loop -- the shape the domain rule calls a valid triple -- but "
            "the guard ((i + j) == 6) && (i < j) has exactly one solution over "
            "i, j in [0, 5), so the statement executes once and cannot be both "
            "endpoints. A model that applies the rule by shape fails here."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        provenance=(
            {
                "fact": "loop_context.a1_a2_same_statement",
                "status": "proven",
                "note": (
                    "over i, j in [0, 5) the guard (i + j) == 6 and i < j is "
                    "satisfied only by (2, 4), so line 44 executes exactly once "
                    "per call and cannot supply two accesses"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_007",
        kind="trap",
        index=2,
        label="trap",
        exercises=(
            "disjoint array elements under a path condition. A1 is the else arm, "
            "so it writes global_array[i] with i != 2, while A2 reads "
            "global_array[2]. Same array, provably different element."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        used_as_index=True,
        provenance=(
            {
                "fact": "accesses[0].source",
                "status": "proven",
                "note": (
                    "line 40 is the else arm of if (i == 2), so it writes an "
                    "element other than 2, while A2 at line 42 reads element 2"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_009",
        kind="trap",
        index=1,
        label="trap",
        exercises=(
            "the remote access is through a pointer the remote flow reassigned. "
            "isr_1 points m at its own local_var3 at line 46 before reading *m at "
            "line 47, so the read is of a different object than main's writes."
        ),
        variable="svp_simple_009_001_m",
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        provenance=(
            {
                "fact": "accesses[1].source",
                "status": "proven",
                "note": (
                    "isr_1 assigns m = &local_var3 at line 46, one line before the "
                    "read at 47, so the read cannot observe main's writes to "
                    "local_var2 through the same pointer"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_015",
        kind="trap",
        index=1,
        label="trap",
        exercises=(
            "a ternary evaluates one arm. Line 34 mentions global_var2 twice, but "
            "p == 1 ? var2 : var2 reads it exactly once, so the line cannot "
            "supply both A1 and A2. Two textual occurrences, one access."
        ),
        accesses=(_enabled(1), _enabled(1), _enabled(1)),
        interval_enabled=(1,),
        provenance=(
            {
                "fact": "loop_context.a1_a2_same_statement",
                "status": "proven",
                "note": (
                    "the conditional operator at line 34 evaluates exactly one of "
                    "its two arms, so global_var2 is read once; A1 and A2 cannot "
                    "both be that read"
                ),
            },
        ),
    ),
    FixtureSpec(
        case="svp_simple_029",
        kind="trap",
        index=1,
        label="trap",
        exercises=(
            "one source line, two call sites, two array elements. A1 and A2 are "
            "both the read at line 80, reached from lines 73 and 74, which pass "
            "tm_para and tm_para + 1 -- so they touch elements 36 and 37. "
            "Requires call-site sensitivity, not just a call graph."
        ),
        accesses=(
            AccessSpec(
                enabled=(1,),
                flow="main",
                frames=(
                    {"function": "svp_simple_029_001_main",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 40}},
                    {"function": "svp_simple_029_001_SetSelfCtrlFlag",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 73},
                     "resolution": "indirect-resolved"},
                    {"function": "svp_simple_029_001_GetTmData"},
                ),
            ),
            AccessSpec(
                enabled=(1,),
                flow="isr_1",
                frames=(
                    {"function": "svp_simple_029_001_isr_1",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 89},
                     "resolution": "indirect-resolved"},
                    {"function": "svp_simple_029_001_SetTmData"},
                ),
            ),
            AccessSpec(
                enabled=(1,),
                flow="main",
                frames=(
                    {"function": "svp_simple_029_001_main",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 40}},
                    {"function": "svp_simple_029_001_SetSelfCtrlFlag",
                     "call_site": {"file": SRC["svp_simple_029"], "line": 74},
                     "resolution": "indirect-resolved"},
                    {"function": "svp_simple_029_001_GetTmData"},
                ),
            ),
        ),
        interval_enabled=(1,),
        used_as_index=True,
        provenance=(
            {
                "fact": "call_paths",
                "status": "proven",
                "note": (
                    "line 73 calls GetTmData(tm_para) and line 74 calls "
                    "GetTmData(tm_para + 1); main invokes SetSelfCtrlFlag with "
                    "tm_para = 36, so the two reads at line 80 are of elements 36 "
                    "and 37 respectively"
                ),
            },
        ),
    ),
)
