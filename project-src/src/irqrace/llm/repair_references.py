"""Hand-written reference fixes for the ten annotated bug points.

The ground truth of the repair stage. [[SkipAnalyzer (paper)]] measures Logic
Rate against fixes written by an author, and states plainly that "logically
correct" therefore means an author agreed -- so these carry the reasoning that
produced them, and name the plausible wrong answer where there is one.

Keyed by subject, because the fixture set contributes exactly one bug point per
case. Each is an *effect*, not a diff: strategy, the interrupts masked, and the
region covered. :func:`irqrace.llm.repair.logic_rate` compares on those, so a
patch that protects the same interval with the same interrupts agrees however
it is written.

Coverage is compared as "at least": a patch covering more than the reference
region still matches, since widening a critical section beyond the interval is
conservative. It is ``latency_note`` that has to justify the widening, not the
Logic Rate.
"""

from __future__ import annotations

from irqrace.llm.repair import ReferenceFix, Strategy

#: Subject -> the fix a person would write. ``candidate_id`` is filled in by
#: :func:`references_for`, which joins against the loaded fixtures.
_BY_SUBJECT: dict[str, dict] = {
    "svp_simple_001_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1, 2}),
        covers_from_line=32,
        covers_to_line=35,
        rationale=(
            "The interval [32, 35] must be atomic with respect to isr_2. irq 2 "
            "is already masked at line 28, so masking it again changes nothing "
            "-- and the defect exists anyway, because isr_1 runs on irq 1 and "
            "calls enable_isr(2) at line 46 from inside the interval. The fix "
            "has to mask irq 1 as well, or equivalently disable_isr(-1)."
        ),
        also_mask_note=(
            "The plausible wrong answer is masking irq 2 alone: it looks right, "
            "it is a no-op, and the defect survives it. This is the case the "
            "'mask every interrupt that can break the interval' rule exists for."
        ),
    ),
    "svp_simple_002_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({2}),
        covers_from_line=33,
        covers_to_line=37,
        rationale=(
            "Both local accesses are in isr_1 and the remote write is in isr_2, "
            "which preempts it on priority. Masking irq 2 across [33, 37] closes "
            "the interval. Nothing re-enables it inside."
        ),
    ),
    "svp_simple_003_001": dict(
        strategy=Strategy.extend_section,
        masked_irqs=frozenset({1}),
        covers_from_line=50,
        covers_to_line=55,
        rationale=(
            "A critical section already exists: disable_isr(1) at line 33, "
            "enable_isr(1) at line 47. The reads are at 50 and 55, just after it "
            "closes. Moving the enable to after line 57 widens the existing "
            "section rather than opening a second overlapping one."
        ),
    ),
    "svp_simple_005_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1}),
        covers_from_line=32,
        covers_to_line=40,
        rationale=(
            "The interval runs from the guarded write at line 32 to the "
            "unconditional write at line 40, so the critical section has to span "
            "the remainder of both loops."
        ),
        also_mask_note=(
            "This is the fixture where the correct fix is expensive: the covered "
            "region includes the tail of a MAX_LENGTH x MAX_LENGTH nested loop, "
            "so interrupt latency becomes unbounded in practice. SDRacer measured "
            "exactly this, overhead below 0.09 on 9 of 11 subjects and markedly "
            "worse on two. A patch that does this and says nothing in "
            "latency_note has traded a race for a deadline miss."
        ),
    ),
    "svp_simple_007_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1}),
        covers_from_line=38,
        covers_to_line=42,
        rationale=(
            "A1 writes global_array[2] under the guard i == 2 and A2 reads "
            "global_array[2]; masking irq 1 across [38, 42] keeps isr_1's write "
            "to the same element out of the gap. Bounded and cheap."
        ),
    ),
    "svp_simple_009_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1}),
        covers_from_line=32,
        covers_to_line=33,
        rationale=(
            "Two adjacent statements writing the same object through two "
            "pointers. Masking irq 1 across [32, 33] is the whole fix, and it is "
            "as cheap as a fix in this suite gets."
        ),
        also_mask_note=(
            "The fix does not depend on noticing the aliasing -- but a model that "
            "missed it will have proposed protecting only line 32, since without "
            "the alias line 33 is not an access to the same object."
        ),
    ),
    "svp_simple_015_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1}),
        covers_from_line=30,
        covers_to_line=31,
        rationale=(
            "The two reads are operands of one if condition spanning lines 30 and "
            "31. The condition must be evaluated atomically, so the section wraps "
            "the whole test."
        ),
    ),
    "svp_simple_016_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1}),
        covers_from_line=26,
        covers_to_line=27,
        rationale=(
            "The annotated reads are two operands of one three-line sum. Covering "
            "[26, 27] is the minimum; covering the whole statement from line 25 is "
            "better and also matches, since coverage is compared as 'at least'."
        ),
    ),
    "svp_simple_017_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1}),
        covers_from_line=29,
        covers_to_line=33,
        rationale=(
            "A1 and A2 are the same statement -- the for condition at line 29 -- "
            "in two different iterations. The interval between them is therefore "
            "a whole loop iteration, not a point, so the section must wrap the "
            "loop body: lines 29 to 33."
        ),
        also_mask_note=(
            "The plausible wrong answer is masking line 29 alone. It is the "
            "annotated line for both A1 and A2, and protecting it is meaningless: "
            "the interleaving happens between iterations, not within the "
            "condition. Any patch covering only line 29 is wrong here."
        ),
    ),
    "svp_simple_029_001": dict(
        strategy=Strategy.mask_interval,
        masked_irqs=frozenset({1}),
        covers_from_line=73,
        covers_to_line=77,
        rationale=(
            "The read and the write are at lines 80 and 83, but those are inside "
            "GetTmData and SetTmData, which both flows call. The interval that "
            "has to be atomic is in the caller: SetSelfCtrlFlag lines 73 to 77, "
            "the read-modify-write on ctrl_sts."
        ),
        also_mask_note=(
            "The plausible wrong answer is masking inside GetTmData or SetTmData. "
            "Those are shared by the task and the ISR, so a section there would "
            "also mask the ISR's own path and still leave the caller's "
            "read-modify-write interruptible. The fix belongs where the interval "
            "is, not where the accesses are."
        ),
    ),
}


def references_for(fixtures) -> dict[str, ReferenceFix]:
    """Join the reference fixes onto the loaded bug-point fixtures."""
    out: dict[str, ReferenceFix] = {}
    for fixture in fixtures:
        if not fixture.is_real:
            continue
        spec = _BY_SUBJECT.get(fixture.subject)
        if spec is None:
            continue
        out[fixture.candidate_id] = ReferenceFix(
            candidate_id=fixture.candidate_id, **spec
        )
    return out


def missing_for(fixtures) -> list[str]:
    """Bug points with no reference fix. Logic Rate cannot be computed for them."""
    return sorted(
        f.subject
        for f in fixtures
        if f.is_real and f.subject not in _BY_SUBJECT
    )
