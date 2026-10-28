"""The match rule and the recall gate.

Decided 2026-09-10 (docs/evaluation-protocol.md). These tests pin the two
measurements the rule rests on, so that if the suite or the errata changes and
the justification stops holding, it fails here rather than quietly degrading a
recall number.
"""
import copy
import json

import pytest
from conftest import ERRATA, EXAMPLES, SUITE

from irqrace.evaluation import (
    COUNTING_UNIT, MATCH_RULE, RACEBENCH_SIMPLE_BUG_POINTS, RACEBENCH_SIMPLE_TRAPS,
    inspection_ratio, match_subject, match_suite, normalise_variable,
)
from irqrace.groundtruth import load_suite

pytestmark = pytest.mark.skipif(
    not (SUITE / "README.md").exists(), reason="racebench suite not present"
)

BUG = json.loads((EXAMPLES / "c2-bugpoint.json").read_text())
#: A trap that is still a trap. `c2-trap.json`, the contract's original trap
#: example (001 global_var <W#43><R#64><W#44>), was relabelled a bug point on
#: 2026-10-28 (errata note relabel_2026_10_28) and is tested as such below.
TRAP = json.loads((EXAMPLES / "c2-trap-array-index.json").read_text())
RELABELLED = json.loads((EXAMPLES / "c2-trap.json").read_text())


@pytest.fixture(scope="module")
def gt():
    return load_suite(SUITE, ERRATA)


# -- the measurements the rule rests on -------------------------------------


def test_ordered_line_triple_is_a_unique_key(gt):
    """Why access kinds are not part of the match: the lines already separate
    every annotation, so kinds would add failure modes and no discrimination."""
    keys = [(a.case, a.lines) for a in gt.bugs + gt.traps]
    assert len(set(keys)) == len(keys) == 86


def test_no_trap_shares_a_line_triple_with_a_bug_point(gt):
    """Why a line-only match cannot silently score a trap as a bug point."""
    bugs = {(a.case, a.lines) for a in gt.bugs}
    assert not [a for a in gt.traps if (a.case, a.lines) in bugs]


def test_denominators_are_what_the_protocol_declares(gt):
    assert len(gt.bugs) == RACEBENCH_SIMPLE_BUG_POINTS == 53  # 48 before 2026-10-28
    assert len(gt.traps) == RACEBENCH_SIMPLE_TRAPS == 33  # 38 before 2026-10-28
    assert COUNTING_UNIT == "per-triple-instance"


def test_the_coarser_counting_units_are_what_the_protocol_says(gt):
    """Recorded so the table in the protocol cannot drift from the suite."""
    # 33 per (case, variable) before the 2026-10-28 relabel added 001's
    # global_var and 019's global_condition3 as bug-point variables.
    assert len({(a.case, a.variable) for a in gt.bugs}) == 35
    assert len({a.case for a in gt.bugs}) == 31


# -- variable normalisation -------------------------------------------------


@pytest.mark.parametrize("spelling,base", [
    ("svp_simple_001_001_global_array", "svp_simple_001_001_global_array"),
    ("*svp_simple_009_001_p", "svp_simple_009_001_p"),
    ("*p", "p"),
    ("svp_simple_024_001_global_array[1]", "svp_simple_024_001_global_array"),
    ("svp_simple_010_001_global_union.header", "svp_simple_010_001_global_union"),
    ("svp_simple_029_001_tm_blocks[36]", "svp_simple_029_001_tm_blocks"),
])
def test_normalise_variable(spelling, base):
    assert normalise_variable(spelling) == base


# -- matching ---------------------------------------------------------------


def test_the_fixtures_match_their_annotations(gt):
    r = match_subject(gt.by_case("svp_simple_001_001").all, [BUG, TRAP],
                      subject="svp_simple_001_001")
    assert r.bugs_detected == 1
    assert r.traps_reported == 1  # only two fixtures exist; trap 2 is not built
    matched = [m for m in r.bug_matches + r.trap_matches if m.detected]
    assert all(m.kinds_agree and m.name_agrees for m in matched)


def test_the_relabelled_001_annotation_is_a_bug_point_on_its_corrected_line(gt):
    """Until 2026-10-28 this was trap 1, annotated with its read on line 63 (a
    declaration) and fixed to 64 by the errata. The relabel moved it to bug 2
    and wrote line 64 into the suite itself, so it matches without the errata."""
    from irqrace.groundtruth import parse_suite

    shipped = parse_suite(SUITE).by_case("svp_simple_001_001")
    r = match_subject(shipped.all, [RELABELLED], subject="svp_simple_001_001")
    assert r.bugs_detected == 1 and r.traps_reported == 0
    assert [m.annotation.index for m in r.bug_matches if m.detected] == [2]


def test_a_match_does_not_require_the_access_kinds_to_agree(gt):
    wrong_kinds = copy.deepcopy(BUG)
    for a in wrong_kinds["accesses"]:
        a["kind"] = "read" if a["kind"] == "write" else "write"
    r = match_subject(gt.by_case("svp_simple_001_001").bugs, [wrong_kinds],
                      subject="svp_simple_001_001")
    assert r.bugs_detected == 1
    assert r.bug_matches[0].kinds_agree is False


def test_among_siblings_on_the_same_lines_the_kind_agreeing_one_is_the_match(gt):
    """`x++` reads and writes on one line, so two candidates can share the
    annotated lines with different kinds. The annotated triple is the one whose
    kinds agree, wherever it sits in the reported order."""
    sibling = copy.deepcopy(BUG)
    sibling["id"] = "csibling000000000"
    for a in sibling["accesses"]:
        a["kind"] = "read" if a["kind"] == "write" else "write"
    r = match_subject(gt.by_case("svp_simple_001_001").bugs, [sibling, BUG],
                      subject="svp_simple_001_001")
    m = r.bug_matches[0]
    assert m.candidate_id == BUG["id"] and m.kinds_agree is True and m.rank == 1


def test_a_match_does_not_require_the_variable_name_to_agree(gt):
    """12 annotations name the location through an alias. A detector that
    resolved it to the underlying global must still match."""
    aliased = copy.deepcopy(BUG)
    aliased["variable"]["name"] = "resolved_object_17"
    aliased["variable"]["aliases"] = []
    r = match_subject(gt.by_case("svp_simple_001_001").bugs, [aliased],
                      subject="svp_simple_001_001")
    assert r.bugs_detected == 1
    assert r.bug_matches[0].name_agrees is False


def test_a_wrong_line_does_not_match(gt):
    moved = copy.deepcopy(BUG)
    moved["accesses"][0]["source"]["line"] += 1
    r = match_subject(gt.by_case("svp_simple_001_001").bugs, [moved],
                      subject="svp_simple_001_001")
    assert r.bugs_detected == 0


# -- the gate ---------------------------------------------------------------


def test_recall_gate_fails_when_nothing_is_reported(gt):
    r = match_suite(gt, {})
    assert r.bug_points == RACEBENCH_SIMPLE_BUG_POINTS == 53
    assert r.bugs_detected == 0
    assert r.recall_gate_passes is False
    assert len(r.missed()) == 53


def test_inspection_ratio_is_undefined_when_a_bug_point_is_missed(gt):
    """An Inspection Ratio over an incomplete detection describes how fast a
    reviewer finds the defects that were found, which is not the quantity
    anyone wants."""
    r = match_subject(gt.by_case("svp_simple_001_001").all, [TRAP, BUG],
                      subject="svp_simple_001_001")
    assert r.bugs_detected == 1  # bug 2 is missed
    assert inspection_ratio(r) is None


def test_inspection_ratio_counts_position_in_the_reported_order(gt):
    bug_1 = [b for b in gt.by_case("svp_simple_001_001").bugs if b.index == 1]
    r = match_subject(bug_1, [TRAP, BUG], subject="svp_simple_001_001")
    assert r.bugs_detected == 1
    assert inspection_ratio(r) == 1.0  # the bug point is last of two
    r2 = match_subject(bug_1, [BUG, TRAP], subject="svp_simple_001_001")
    assert inspection_ratio(r2) == 0.5


def test_the_manifest_records_both_decisions(tmp_path):
    from irqrace.config import Config
    from irqrace.runstore import RunStore

    cfg = Config.load(EXAMPLES / "c1-svp_simple_001_001.yaml")
    store = RunStore.create(cfg, run_root=tmp_path)
    sem = store.read_manifest()["semantics"]
    assert sem["counting_unit"] == COUNTING_UNIT
    assert sem["match_rule"] == MATCH_RULE
