"""The decision policy, as tests.

Every case here is a restatement of "a solver may drop a candidate; the LLM may
not". If one of these starts failing, the project's central claim has quietly
changed.
"""

import pytest

from irqrace.llm.verdict import (
    INSPECTION_ORDER,
    Bucket,
    Feasibility,
    FeasibilityAnswer,
    Harmfulness,
    HarmfulnessAnswer,
    Triage,
    bucket_of,
)


def _triage(feas, harm=None, conf=0.9, harm_conf=0.9, cid="c0000000000000001"):
    return Triage(
        candidate_id=cid,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(
            reasoning="r", verdict=feas, confidence=conf
        ),
        harmfulness=(
            None
            if harm is None
            else HarmfulnessAnswer(reasoning="r", verdict=harm, confidence=harm_conf)
        ),
    )


@pytest.mark.parametrize(
    "feas,harm,expected",
    [
        (Feasibility.feasible, Harmfulness.harmful, Bucket.likely_real),
        (Feasibility.feasible, Harmfulness.benign, Bucket.likely_benign),
        (Feasibility.infeasible, None, Bucket.likely_infeasible),
    ],
)
def test_the_three_confident_paths(feas, harm, expected):
    assert bucket_of(feas, harm) is expected


@pytest.mark.parametrize(
    "feas,harm",
    [
        (Feasibility.uncertain, Harmfulness.harmful),
        (Feasibility.uncertain, Harmfulness.benign),
        (Feasibility.uncertain, None),
        (Feasibility.feasible, Harmfulness.uncertain),
        (Feasibility.feasible, None),
    ],
)
def test_uncertainty_on_either_axis_yields_uncertain(feas, harm):
    """The recall bias. Never a low bucket from an unsure answer."""
    assert bucket_of(feas, harm) is Bucket.uncertain


def test_a_missing_harmfulness_answer_is_not_evidence_of_harmlessness():
    """Absence of the second conversation must not read as 'benign'."""
    assert bucket_of(Feasibility.feasible, None) is not Bucket.likely_benign


def test_likely_infeasible_is_reachable_only_from_an_explicit_claim():
    reachable = {
        bucket_of(f, h)
        for f in Feasibility
        for h in list(Harmfulness) + [None]
        if f is not Feasibility.infeasible
    }
    assert Bucket.likely_infeasible not in reachable


def test_inspection_order_puts_uncertain_above_both_low_buckets():
    """Costing a reviewer one candidate beats hiding a defect."""
    order = list(INSPECTION_ORDER)
    assert order.index(Bucket.uncertain) < order.index(Bucket.likely_benign)
    assert order.index(Bucket.uncertain) < order.index(Bucket.likely_infeasible)


def test_ranking_is_bucket_first_then_confidence():
    high = _triage(Feasibility.feasible, Harmfulness.harmful, conf=0.9, cid="c" + "1" * 16)
    low = _triage(Feasibility.feasible, Harmfulness.harmful, conf=0.4, cid="c" + "2" * 16)
    unsure = _triage(Feasibility.uncertain, conf=0.99, cid="c" + "3" * 16)

    ranked = sorted([unsure, low, high], key=lambda t: t.rank_key)
    assert [t.bucket for t in ranked] == [
        Bucket.likely_real,
        Bucket.likely_real,
        Bucket.uncertain,
    ]
    assert ranked[0].feasibility.confidence == 0.9


def test_rank_confidence_takes_the_weaker_of_the_two_answers():
    t = _triage(Feasibility.feasible, Harmfulness.harmful, conf=0.9, harm_conf=0.3)
    assert t.rank_key[1] == -0.3


def test_explanation_carries_both_conversations():
    t = Triage(
        candidate_id="c" + "0" * 16,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(
            reasoning="isr_2 preempts the interval at line 46",
            verdict=Feasibility.feasible,
            confidence=0.8,
        ),
        harmfulness=HarmfulnessAnswer(
            reasoning="the variable indexes an array",
            verdict=Harmfulness.harmful,
            confidence=0.8,
        ),
    )
    assert "line 46" in t.explanation
    assert "indexes an array" in t.explanation


# -- protocol violations ---------------------------------------------------


def _harm(verdict, criterion=None):
    return HarmfulnessAnswer(reasoning="r", verdict=verdict, confidence=0.8,
                             criterion_matched=criterion)


def test_a_benign_verdict_without_a_criterion_is_a_violation():
    """Found on the first live run: two real bug points came back benign with
    criterion_matched null, which the prompt forbids in those words."""
    t = Triage(
        candidate_id="c" + "0" * 16,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(reasoning="r", verdict=Feasibility.feasible,
                                      confidence=0.9),
        harmfulness=_harm(Harmfulness.benign),
    )
    assert any("no criterion named" in v for v in t.protocol_violations())


def test_a_benign_verdict_with_a_criterion_is_clean():
    t = Triage(
        candidate_id="c" + "0" * 16,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(reasoning="r", verdict=Feasibility.feasible,
                                      confidence=0.9),
        harmfulness=_harm(Harmfulness.benign, "the value is never read again"),
    )
    assert t.protocol_violations() == []


def test_a_harmful_verdict_needs_no_criterion():
    """Nullable is right here: no benignity clause applies to a harmful call."""
    t = Triage(
        candidate_id="c" + "0" * 16,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(reasoning="r", verdict=Feasibility.feasible,
                                      confidence=0.9),
        harmfulness=_harm(Harmfulness.harmful),
    )
    assert t.protocol_violations() == []


def test_an_infeasible_verdict_without_a_blocking_element_is_a_violation():
    """Nothing can be propagated to other candidates, and the claim cannot be
    checked against the masking analysis."""
    t = _triage(Feasibility.infeasible)
    assert any("no blocking element" in v for v in t.protocol_violations())


def test_a_blocking_element_on_a_feasible_verdict_is_a_violation():
    t = Triage(
        candidate_id="c" + "0" * 16,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(
            reasoning="r", blocking_element="irq 2 is masked",
            verdict=Feasibility.feasible, confidence=0.9,
        ),
        harmfulness=_harm(Harmfulness.harmful),
    )
    assert any("not infeasible" in v for v in t.protocol_violations())


def test_a_violation_never_discards_the_verdict():
    """The stage may not drop a candidate, and a violation is evidence about
    the prompt rather than grounds to throw the answer away."""
    t = Triage(
        candidate_id="c" + "0" * 16,
        fingerprint="f" * 64,
        feasibility=FeasibilityAnswer(reasoning="r", verdict=Feasibility.feasible,
                                      confidence=0.9),
        harmfulness=_harm(Harmfulness.benign),
    )
    assert t.protocol_violations()
    assert t.bucket is Bucket.likely_benign
