"""The four numbers, and the invariant underneath them."""

import dataclasses

import pytest

from irqrace.llm.fixtures import Fixture
from irqrace.llm.scoring import (
    blocking_element_groups,
    consistency,
    inspection_ratio,
    score,
    vote,
)
from irqrace.llm.verdict import (
    Bucket,
    Feasibility,
    FeasibilityAnswer,
    Harmfulness,
    HarmfulnessAnswer,
    Triage,
)


def _fixture(cid, label):
    return Fixture(
        path=None, record={"id": cid}, label=label, subject="s", annotation="a"
    )


def _triage(cid, feas, harm=None, conf=0.9):
    return Triage(
        candidate_id=cid,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(reasoning="r", verdict=feas, confidence=conf),
        harmfulness=(
            None
            if harm is None
            else HarmfulnessAnswer(reasoning="r", verdict=harm, confidence=conf)
        ),
    )


REAL, TRAP = "bug_point", "trap"


def test_perfect_row():
    fx = [_fixture("a", REAL), _fixture("b", TRAP)]
    tr = [
        _triage("a", Feasibility.feasible, Harmfulness.harmful),
        _triage("b", Feasibility.infeasible),
    ]
    s = score(fx, tr)
    assert s.recall == 1.0
    assert s.trap_rejection == 1.0
    assert s.inspection_ratio == 0.5
    assert s.gate_passed


def test_a_bug_point_called_infeasible_fails_the_gate():
    fx = [_fixture("a", REAL), _fixture("b", TRAP)]
    tr = [
        _triage("a", Feasibility.infeasible),
        _triage("b", Feasibility.infeasible),
    ]
    s = score(fx, tr)
    assert s.recall == 0.0
    assert not s.gate_passed
    assert s.missed == ("a",)
    assert "FAIL" in s.report()


def test_a_bug_point_called_uncertain_still_passes_the_gate():
    """Uncertain costs Inspection Ratio, not recall. That is the trade."""
    fx = [_fixture("a", REAL), _fixture("b", TRAP)]
    tr = [
        _triage("a", Feasibility.uncertain),
        _triage("b", Feasibility.infeasible),
    ]
    s = score(fx, tr)
    assert s.gate_passed
    assert s.recall == 1.0


def test_dropping_a_candidate_raises_rather_than_scoring_well():
    """The invariant. A dropped candidate would raise recall by vanishing."""
    fx = [_fixture("a", REAL), _fixture("b", REAL)]
    tr = [_triage("a", Feasibility.feasible, Harmfulness.harmful)]
    with pytest.raises(ValueError, match="never drop"):
        score(fx, tr)


def test_inventing_a_candidate_also_raises():
    fx = [_fixture("a", REAL)]
    tr = [
        _triage("a", Feasibility.feasible, Harmfulness.harmful),
        _triage("ghost", Feasibility.feasible, Harmfulness.harmful),
    ]
    with pytest.raises(ValueError, match="invented"):
        score(fx, tr)


def test_an_empty_scored_set_does_not_pass_the_gate():
    """Recall over nothing is 1.0. A row where every candidate was excluded --
    unreachable backend, systematic refusal -- must not report green having
    measured nothing. Reached in practice before this guard existed."""
    s = score([], [])
    assert s.recall == 1.0
    assert not s.gate_passed


def test_a_set_of_traps_alone_does_not_pass_the_gate():
    fx = [_fixture("t", TRAP)]
    assert not score(fx, [_triage("t", Feasibility.infeasible)]).gate_passed


def test_a_trap_bucketed_benign_counts_as_rejected():
    fx = [_fixture("t", TRAP)]
    tr = [_triage("t", Feasibility.feasible, Harmfulness.benign)]
    assert score(fx, tr).trap_rejection == 1.0


def test_a_trap_left_uncertain_counts_as_kept():
    fx = [_fixture("t", TRAP)]
    tr = [_triage("t", Feasibility.uncertain)]
    s = score(fx, tr)
    assert s.trap_rejection == 0.0
    assert s.traps_kept_high == ("t",)


def test_inspection_ratio_is_driven_by_the_worst_ranked_bug_point():
    """One real defect sunk to the bottom costs the full 100%."""
    fx = [_fixture("a", REAL), _fixture("b", TRAP), _fixture("c", REAL)]
    tr = [
        _triage("a", Feasibility.feasible, Harmfulness.harmful),
        _triage("b", Feasibility.feasible, Harmfulness.harmful),
        _triage("c", Feasibility.infeasible),
    ]
    assert inspection_ratio(fx, tr) == 1.0


def test_inspection_ratio_is_zero_without_bug_points():
    fx = [_fixture("t", TRAP)]
    assert inspection_ratio(fx, [_triage("t", Feasibility.infeasible)]) == 0.0


def test_consistency_measures_agreement_across_runs():
    runs = [
        [_triage("a", Feasibility.feasible, Harmfulness.harmful)],
        [_triage("a", Feasibility.feasible, Harmfulness.harmful)],
        [_triage("a", Feasibility.uncertain)],
    ]
    out = consistency(runs)
    assert out["a"] == pytest.approx(2 / 3)
    assert out["__mean__"] == pytest.approx(2 / 3)


def test_consistency_needs_more_than_one_run():
    with pytest.raises(ValueError):
        consistency([[_triage("a", Feasibility.uncertain)]])


# -- majority voting and IRIS-style grouping -------------------------------


def test_voting_takes_the_modal_bucket():
    runs = [
        [_triage("a", Feasibility.feasible, Harmfulness.harmful)],
        [_triage("a", Feasibility.feasible, Harmfulness.harmful)],
        [_triage("a", Feasibility.infeasible)],
    ]
    assert vote(runs)[0].bucket is Bucket.likely_real


def test_a_tie_resolves_toward_the_higher_bucket():
    """Recall bias at the voting layer. Resolving a tie downward would
    reintroduce the loss the decision policy forbids one layer up."""
    runs = [
        [_triage("a", Feasibility.feasible, Harmfulness.harmful)],
        [_triage("a", Feasibility.infeasible)],
    ]
    assert vote(runs)[0].bucket is Bucket.likely_real


def test_a_tie_between_uncertain_and_benign_resolves_to_uncertain():
    runs = [
        [_triage("a", Feasibility.uncertain)],
        [_triage("a", Feasibility.feasible, Harmfulness.benign)],
    ]
    assert vote(runs)[0].bucket is Bucket.uncertain


def test_voting_keeps_a_real_explanation_rather_than_synthesising_one():
    runs = [
        [_triage("a", Feasibility.feasible, Harmfulness.harmful, conf=0.4)],
        [_triage("a", Feasibility.feasible, Harmfulness.harmful, conf=0.9)],
    ]
    winner = vote(runs)[0]
    assert winner.feasibility.confidence == 0.9


def test_voting_never_drops_or_invents_a_candidate():
    runs = [
        [_triage("a", Feasibility.uncertain), _triage("b", Feasibility.uncertain)],
        [_triage("a", Feasibility.infeasible), _triage("b", Feasibility.uncertain)],
    ]
    assert {t.candidate_id for t in vote(runs)} == {"a", "b"}


def test_blocking_elements_group_candidates_without_removing_any():
    """IRIS prunes; this design may not, so the same signal is used to shorten
    review instead -- one check clears the group."""
    shared = "isr_1 never writes this variable"
    triages = [
        Triage(
            candidate_id=cid,
            fingerprint="f" * 64,
            feasibility=FeasibilityAnswer(
                reasoning="r",
                blocking_element=element,
                verdict=Feasibility.infeasible,
                confidence=0.9,
            ),
        )
        for cid, element in [("a", shared), ("b", shared), ("c", "something else")]
    ]
    groups = blocking_element_groups(triages)
    assert groups == {shared: ["a", "b"]}
    assert len(triages) == 3, "grouping must not remove anything"


def test_candidates_without_a_blocking_element_are_not_grouped():
    assert blocking_element_groups(
        [_triage("a", Feasibility.feasible, Harmfulness.harmful)]
    ) == {}


# -- coverage --------------------------------------------------------------


def test_a_partial_row_does_not_pass_the_gate():
    """Reached in practice: 3 of 20 scored after rate limits and a DNS blip,
    and the row reported 'PASS, 3/3 bug points'."""
    fx = [_fixture("a", REAL)]
    s = score(fx, [_triage("a", Feasibility.feasible, Harmfulness.harmful)], n_expected=20)
    assert s.recall == 1.0
    assert not s.gate_passed
    assert s.coverage == 0.05
    assert "INCOMPLETE" in s.report()


def test_a_complete_row_still_passes():
    fx = [_fixture("a", REAL), _fixture("t", TRAP)]
    s = score(fx, [
        _triage("a", Feasibility.feasible, Harmfulness.harmful),
        _triage("t", Feasibility.infeasible),
    ], n_expected=2)
    assert s.gate_passed and s.complete


def test_trap_rejection_over_no_traps_is_not_reported_as_perfect():
    """0/0 read as 100% in a real run and looked like a result."""
    fx = [_fixture("a", REAL)]
    s = score(fx, [_triage("a", Feasibility.feasible, Harmfulness.harmful)])
    assert "n/a" in s.report()


# -- the Racebench view: harmfulness asked, not scored --------------------


def test_without_harm_a_benign_bug_point_ranks_as_found():
    """svp_simple_005's shape: feasible, reader is a dead local, model says
    benign. Scored with harm it sinks to the bottom; without, it is found."""
    fixtures = [_fixture("bug", "bug_point"), _fixture("t1", "trap"),
                _fixture("t2", "trap")]
    triages = [
        _triage("bug", Feasibility.feasible, Harmfulness.benign),
        _triage("t1", Feasibility.feasible, Harmfulness.harmful),
        _triage("t2", Feasibility.uncertain),
    ]
    with_harm = score(fixtures, triages)
    without = score(fixtures, triages, harm_scored=False)
    assert with_harm.inspection_ratio == 1.0
    assert without.inspection_ratio < with_harm.inspection_ratio
    assert without.harm_scored is False


def test_without_harm_only_infeasible_rejects_a_trap():
    """A trap called benign no longer counts as rejected: precision on Racebench
    rests on feasibility alone, which is the cost option C accepts."""
    fixtures = [_fixture("bug", "bug_point"), _fixture("trap", "trap")]
    triages = [
        _triage("bug", Feasibility.feasible, Harmfulness.harmful),
        _triage("trap", Feasibility.feasible, Harmfulness.benign),
    ]
    assert score(fixtures, triages).trap_rejection == 1.0
    assert score(fixtures, triages, harm_scored=False).trap_rejection == 0.0


def test_the_view_never_changes_the_reported_bucket():
    """A measurement view, not a second decision policy."""
    fixtures = [_fixture("bug", "bug_point")]
    t = _triage("bug", Feasibility.feasible, Harmfulness.benign)
    s = score(fixtures, [t], harm_scored=False)
    assert t.bucket is Bucket.likely_benign
    assert s.bucket_counts == {"likely_benign": 1}
    assert "not scored" in s.report()


def test_without_harm_the_recall_gate_still_catches_infeasible():
    fixtures = [_fixture("bug", "bug_point")]
    s = score(fixtures, [_triage("bug", Feasibility.infeasible)], harm_scored=False)
    assert not s.gate_passed
    assert s.missed == ("bug",)


def test_inspection_ratio_ties_are_broken_pessimistically():
    """Equal bucket and confidence: the bug point is read last. The figure must
    not depend on how candidate ids sort -- ids are hashes."""
    fixtures = [_fixture("a_bug", "bug_point"), _fixture("z_trap", "trap")]
    triages = [
        _triage("a_bug", Feasibility.feasible, Harmfulness.harmful, conf=0.9),
        _triage("z_trap", Feasibility.feasible, Harmfulness.harmful, conf=0.9),
    ]
    assert inspection_ratio(fixtures, triages) == 1.0
