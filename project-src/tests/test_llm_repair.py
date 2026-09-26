"""The repair stage: the witness requirement, and how the two rates score."""

import pytest

from irqrace.llm.fixtures import load_all
from irqrace.llm.prompts import FULL
from irqrace.llm.repair import (
    Patch,
    Strategy,
    Witness,
    is_wellformed_diff,
    logic_rate,
    syntax_rate,
    witness_problems,
)
from irqrace.llm.repair_references import missing_for, references_for

FIXTURES = load_all()
BUGS = [f for f in FIXTURES if f.is_real]
REFS = references_for(FIXTURES)

DIFF = """@@ -31,3 +31,5 @@
+  disable_isr(1);
   x = 1;
+  enable_isr(1);
"""


def _patch(strategy=Strategy.mask_interval, irqs=(1,), lo=32, hi=35,
           flow="isr_2", order=("A1", "B", "A2")):
    return Patch(
        reasoning="r",
        witness=Witness(
            firing_flow=flow,
            preemption_point="between lines 32 and 35",
            access_order=list(order),
            divergence="the array element keeps the value 0 in every serial run",
        ),
        strategy=strategy,
        masked_irqs=list(irqs),
        covers_from_line=lo,
        covers_to_line=hi,
        latency_note="four statements, bounded",
        diff=DIFF,
    )


# -- the reference set -----------------------------------------------------


def test_every_bug_point_has_a_reference_fix():
    """Logic Rate is uncomputable for a bug point without one."""
    assert missing_for(FIXTURES) == []
    assert len(REFS) == len(BUGS) == 10


def test_each_reference_carries_its_reasoning():
    for ref in REFS.values():
        assert ref.rationale.strip()


def test_the_001_reference_masks_both_interrupts():
    """The interval is punctured by isr_1, so masking irq 2 alone is a no-op."""
    ref = next(r for k, r in REFS.items() if k == _id("svp_simple_001_001"))
    assert ref.masked_irqs == {1, 2}
    assert "no-op" in ref.also_mask_note


def test_the_017_reference_covers_the_loop_not_the_line():
    """A1 and A2 are one statement in two iterations, so the interval is the
    loop body -- masking the annotated line alone protects nothing."""
    ref = next(r for k, r in REFS.items() if k == _id("svp_simple_017_001"))
    assert (ref.covers_from_line, ref.covers_to_line) == (29, 33)


def test_the_029_reference_fixes_the_caller_not_the_accessors():
    """GetTmData and SetTmData are shared by both flows; the interval is in
    SetSelfCtrlFlag."""
    ref = next(r for k, r in REFS.items() if k == _id("svp_simple_029_001"))
    assert (ref.covers_from_line, ref.covers_to_line) == (73, 77)


def _id(subject):
    return next(f.candidate_id for f in FIXTURES if f.subject == subject and f.is_real)


# -- Logic Rate ------------------------------------------------------------


def test_an_exact_match_scores():
    cid = _id("svp_simple_009_001")
    rate, missed = logic_rate({cid: _patch(irqs=(1,), lo=32, hi=33)}, REFS)
    assert rate == 1.0 and missed == []


def test_covering_more_than_the_reference_still_matches():
    """Widening beyond the interval is conservative; latency_note justifies it,
    not the Logic Rate."""
    cid = _id("svp_simple_009_001")
    rate, _ = logic_rate({cid: _patch(irqs=(1,), lo=30, hi=40)}, REFS)
    assert rate == 1.0


def test_covering_less_does_not_match():
    cid = _id("svp_simple_017_001")
    rate, missed = logic_rate({cid: _patch(irqs=(1,), lo=29, hi=29)}, REFS)
    assert rate == 0.0
    assert "reference is" in missed[0]


def test_masking_too_few_interrupts_does_not_match():
    """The 001 trap for a repair model: irq 2 alone leaves the puncture open."""
    cid = _id("svp_simple_001_001")
    rate, _ = logic_rate({cid: _patch(irqs=(2,), lo=32, hi=35)}, REFS)
    assert rate == 0.0


def test_extend_and_mask_interval_are_accepted_for_one_another():
    """Widening an existing section or opening a new one over the same region
    is a style difference, and the reference names only one of them."""
    cid = _id("svp_simple_003_001")
    rate, _ = logic_rate(
        {cid: _patch(strategy=Strategy.mask_interval, irqs=(1,), lo=50, hi=55)},
        REFS,
    )
    assert rate == 1.0


def test_mask_access_is_not_accepted_for_an_interval_fix():
    """Protecting the endpoints leaves the gap the remote access lands in."""
    cid = _id("svp_simple_009_001")
    rate, _ = logic_rate(
        {cid: _patch(strategy=Strategy.mask_access, irqs=(1,), lo=32, hi=33)}, REFS
    )
    assert rate == 0.0


def test_a_patch_without_a_reference_is_reported_not_skipped():
    rate, missed = logic_rate({"cdeadbeefdeadbeef": _patch()}, REFS)
    assert "no reference fix" in missed[0]


# -- Syntax Rate -----------------------------------------------------------


def test_syntax_rate_is_none_when_the_checker_cannot_run():
    """No compiler must yield 'not measured', never 100%."""
    rate, failed = syntax_rate({"c1": _patch()}, lambda p: None)
    assert rate is None and failed == []


def test_syntax_rate_reports_which_patches_failed():
    rate, failed = syntax_rate(
        {"c1": _patch(), "c2": _patch()}, lambda p: p.covers_to_line != 35
    )
    assert rate == 0.0
    assert set(failed) == {"c1", "c2"}


@pytest.mark.parametrize(
    "diff,ok",
    [
        (DIFF, True),
        ("just some prose", False),
        ("@@ -1,2 +1,3 @@\n context only\n", False),
    ],
)
def test_a_diff_is_recognisable_as_one(diff, ok):
    assert is_wellformed_diff(diff) is ok


# -- the witness -----------------------------------------------------------


def test_a_good_witness_has_no_problems():
    record = next(f.record for f in FIXTURES if f.subject == "svp_simple_001_001" and f.is_real)
    remote = record["preemption"]["preempting_flow"]
    assert witness_problems(_patch(flow=remote), record) == []


def test_a_witness_naming_an_unknown_flow_is_caught():
    record = BUGS[0].record
    assert any(
        "not in the record" in p
        for p in witness_problems(_patch(flow="isr_99"), record)
    )


def test_a_witness_contradicting_the_analysis_is_caught():
    record = next(f.record for f in FIXTURES if f.subject == "svp_simple_001_001" and f.is_real)
    problems = witness_problems(_patch(flow="main"), record)
    assert any("the analysis says" in p for p in problems)


def test_a_witness_that_does_not_interleave_is_caught():
    """B outside the local pair is not an atomicity violation at all."""
    record = next(f.record for f in FIXTURES if f.subject == "svp_simple_001_001" and f.is_real)
    remote = record["preemption"]["preempting_flow"]
    problems = witness_problems(
        _patch(flow=remote, order=("A1", "A2", "B")), record
    )
    assert any("between the local pair" in p for p in problems)


# -- the prompt ------------------------------------------------------------


def test_the_repair_prompt_forbids_thread_primitives():
    from irqrace.llm import prompts

    text = (prompts._ASSETS / "repair.md").read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert "do not reach for a mutex" in flat
    assert "an ISR cannot wait" in flat


def test_the_repair_prompt_states_the_interval_rule():
    from irqrace.llm import prompts

    flat = " ".join(
        (prompts._ASSETS / "repair.md").read_text(encoding="utf-8").split()
    )
    assert "does not fix it" in flat
    assert "Latency is a correctness property" in flat
