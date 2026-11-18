"""The Racebench 2.2 label file, its loader, and the equivalence rule (DRAFT, gate M4a)."""

from __future__ import annotations

import copy

import pytest
import yaml

from conftest import ERRATA, REPO, SUITE
from irqrace.evaluation import match_subject
from irqrace.groundtruth import load_suite
from irqrace.labels_ext import (
    LABELS_22, LabelError, Triple, cohen_kappa, defect_classes, ground_truth, is_extension,
    label_counts, load_labels, parse_labels, second_check_agreement, sibling_reason,
)

pytestmark = pytest.mark.skipif(not SUITE.is_dir(), reason="Racebench suite not available")

CASE = "svp_simple_001_001"


def _entry(**over):
    e = {
        "id": "R22-0001",
        "case": CASE,
        "variable": "svp_simple_001_001_global_array",
        "triple": [
            {"role": "A1", "kind": "write", "line": 32, "flow": "main"},
            {"role": "B", "kind": "read", "line": 55, "flow": "isr_2"},
            {"role": "A2", "kind": "write", "line": 32, "flow": "main"},
        ],
        "candidate_ids": ["cea3c0add9327f2db"],
        "verdict": "bug",
        "witness": {
            "arrival_point": "isr_2 arrives between two iterations of the loop on line 32",
            "masking_at_arrival": "irq 2 unmasked by enable_isr(2) at line 46 in an earlier isr_1",
            "guard_values": "global_flag == 1 (isr_1 ran), i == 9999",
            "effect": "isr_2 reads the element between two writes",
        },
        "blocking_reason": None,
        "adjudicator": "Lucas",
        "date": "2026-11-20",
        "second_check": {"done": False},
        "notes": None,
    }
    e.update(over)
    return e


def _doc(*entries):
    return {"schema_version": "labels-ext/1.0.0", "label_set": "2.2", "base": "2.1",
            "entries": list(entries)}


def _write(tmp_path, *entries):
    path = tmp_path / "labels.yaml"
    path.write_text(yaml.safe_dump(_doc(*entries), allow_unicode=True), encoding="utf-8")
    return path


def _suite():
    return load_suite(SUITE, ERRATA)


# -- the shipped file ------------------------------------------------------


def test_shipped_label_file_is_valid_and_empty():
    labels = load_labels(LABELS_22, suite=_suite())
    assert labels.label_set == "2.2" and labels.base == "2.1"
    assert labels.entries == []


def test_label_set_21_is_the_suite_and_22_equals_it_while_empty():
    for name in ("2.1", "2.2"):
        gt = ground_truth(name, suite_root=SUITE)
        assert (len(gt.bugs), len(gt.traps)) == (53, 33)
    with pytest.raises(LabelError):
        ground_truth("2.3", suite_root=SUITE)


# -- a synthetic entry -----------------------------------------------------


def test_a_bug_entry_extends_22_and_leaves_21_untouched(tmp_path):
    path = _write(tmp_path, _entry())
    gt = ground_truth("2.2", suite_root=SUITE, labels_path=path)
    assert (len(gt.bugs), len(gt.traps)) == (54, 33)
    new = [a for a in gt.bugs if is_extension(a)]
    assert len(new) == 1
    ann = new[0]
    assert (ann.case, ann.lines, ann.pattern, ann.index) == (CASE, (32, 55, 32), "WRW", 3)
    assert ann.raw == "racebench-2.2.yaml#R22-0001"

    # 2.1 is not the object 2.2 was built on, and reloads as 53/33.
    gt21 = ground_truth("2.1", suite_root=SUITE)
    assert (len(gt21.bugs), len(gt21.traps)) == (53, 33)
    assert not any(is_extension(a) for a in gt21.bugs)

    # The scorer's match rule finds it like any annotation.
    record = {
        "id": "cx", "variable": {"name": "svp_simple_001_001_global_array", "aliases": []},
        "accesses": [
            {"role": r, "kind": k, "source": {"file": "svp_simple_001/svp_simple_001_001.c", "line": n}}
            for r, k, n in (("A1", "write", 32), ("B", "read", 55), ("A2", "write", 32))
        ],
    }
    rep = match_subject(gt.by_case(CASE).all, [record], subject=CASE)
    hit = [m for m in rep.bug_matches if m.detected]
    assert [m.annotation.raw for m in hit] == ["racebench-2.2.yaml#R22-0001"]


def test_verdicts_map_to_denominators(tmp_path):
    trap = _entry(id="R22-0002", verdict="trap", witness={},
                  blocking_reason="irq 2 is masked on every path into line 32",
                  triple=[{"role": "A1", "kind": "write", "line": 32},
                          {"role": "B", "kind": "read", "line": 58},
                          {"role": "A2", "kind": "write", "line": 32}])
    nad = _entry(id="R22-0003", verdict="not-a-defect", witness={},
                 blocking_reason="the ISR writes the value already there",
                 triple=[{"role": "A1", "kind": "write", "line": 32},
                         {"role": "B", "kind": "read", "line": 60},
                         {"role": "A2", "kind": "write", "line": 32}])
    und = _entry(id="R22-0004", verdict="undecided", witness={},
                 blocking_reason="depends on the hardware's arrival latency",
                 triple=[{"role": "A1", "kind": "write", "line": 35},
                         {"role": "B", "kind": "read", "line": 55},
                         {"role": "A2", "kind": "write", "line": 35}])
    path = _write(tmp_path, trap, nad, und)
    gt = ground_truth("2.2", suite_root=SUITE, labels_path=path)
    assert (len(gt.bugs), len(gt.traps)) == (53, 34)
    gt = ground_truth("2.2", suite_root=SUITE, labels_path=path, not_a_defect_as_trap=True)
    assert (len(gt.bugs), len(gt.traps)) == (53, 35)
    assert load_labels(path).by_verdict() == {"trap": 1, "not-a-defect": 1, "undecided": 1}


@pytest.mark.parametrize("over, message", [
    ({"witness": {"arrival_point": "x"}}, "needs a concrete interleaving witness"),
    ({"verdict": "trap", "witness": {}}, "needs a blocking_reason"),
    ({"verdict": "likely"}, "is not one of"),
    ({"adjudicator": ""}, "missing adjudicator"),
    ({"date": "20 Nov"}, "is not an ISO date"),
    ({"triple": [{"role": "A1", "kind": "write", "line": 32}]}, "exactly three"),
    ({"triple": [{"role": "B", "kind": "write", "line": 32},
                 {"role": "A1", "kind": "read", "line": 55},
                 {"role": "A2", "kind": "write", "line": 32}]}, "order is A1, B, A2"),
    ({"triple": [{"role": "A1", "kind": "modify", "line": 32},
                 {"role": "B", "kind": "read", "line": 55},
                 {"role": "A2", "kind": "write", "line": 32}]}, "not read/write"),
    ({"second_check": {"done": True, "adjudicator": "Lucas", "verdict": "bug"}}, "different person"),
    ({"second_check": {"done": True, "adjudicator": "Pedro"}}, "is not a verdict"),
])
def test_malformed_entries_are_rejected(over, message):
    with pytest.raises(LabelError, match=message):
        parse_labels(_doc(_entry(**over)))


def test_duplicates_and_collisions_with_21_are_rejected(tmp_path):
    with pytest.raises(LabelError, match="used 2 times"):
        parse_labels(_doc(_entry(), _entry()))
    with pytest.raises(LabelError, match="labelled 2 times"):
        parse_labels(_doc(_entry(), _entry(id="R22-0009")))
    # (32, 55, 35) is 2.1 bug 1 of this case.
    clash = _entry(triple=[{"role": "A1", "kind": "write", "line": 32},
                           {"role": "B", "kind": "read", "line": 55},
                           {"role": "A2", "kind": "write", "line": 35}])
    with pytest.raises(LabelError, match="already 2.1 bug 1"):
        ground_truth("2.2", suite_root=SUITE, labels_path=_write(tmp_path, clash))
    with pytest.raises(LabelError, match="outside"):
        load_labels(_write(tmp_path, _entry(triple=[
            {"role": "A1", "kind": "write", "line": 32},
            {"role": "B", "kind": "read", "line": 999},
            {"role": "A2", "kind": "write", "line": 32}])), suite=_suite())
    with pytest.raises(LabelError, match="unknown case"):
        load_labels(_write(tmp_path, _entry(case="svp_simple_099_001")), suite=_suite())


def test_header_is_checked():
    doc = _doc()
    for key, bad in (("schema_version", "labels-ext/0.9"), ("label_set", "2.1"), ("base", "2.0")):
        broken = copy.deepcopy(doc)
        broken[key] = bad
        with pytest.raises(LabelError, match=key):
            parse_labels(broken)


# -- the equivalence rule --------------------------------------------------


def _t(key, lines, names=("v",), case="c"):
    return Triple(key=key, case=case, names=frozenset(names),
                  sites=tuple(("c.c", n) for n in lines))


def test_sibling_clauses():
    assert sibling_reason(_t("a", (1, 9, 2)), _t("b", (1, 9, 2))) == "E1"
    assert sibling_reason(_t("a", (1, 9, 2)), _t("b", (1, 8, 2))) == "E2"
    assert sibling_reason(_t("a", (1, 9, 2)), _t("b", (2, 9, 3))) == "E3"
    assert sibling_reason(_t("a", (1, 9, 3)), _t("b", (1, 9, 2))) == "E3"
    # Same B but disjoint pairs: not siblings. Another variable or case: never.
    assert sibling_reason(_t("a", (1, 9, 2)), _t("b", (3, 9, 4))) is None
    assert sibling_reason(_t("a", (1, 9, 2)), _t("b", (1, 9, 2), names=("w",))) is None
    assert sibling_reason(_t("a", (1, 9, 2)), _t("b", (1, 9, 2), case="d")) is None
    # Another B and one shared endpoint only: not siblings.
    assert sibling_reason(_t("a", (1, 9, 2)), _t("b", (2, 8, 3))) is None


def test_closure_is_over_the_triples_counted_only():
    a, bridge, c = _t("a", (1, 9, 2)), _t("bridge", (2, 9, 3)), _t("c", (3, 9, 4))
    assert len(defect_classes([a, bridge, c])) == 1
    # Without the bridging triple (say it was judged not a defect) a and c stay apart.
    assert len(defect_classes([a, c])) == 2


def test_rule_calibrated_on_21():
    """53 bug triples are 35 defects; the planted traps share classes with bugs."""
    counts = label_counts(_suite())
    assert counts["bug_triples"] == 53 and counts["bug_defects"] == 35
    assert counts["trap_triples"] == 33 and counts["trap_defects"] == 27
    assert counts["bug_triples_added"] == counts["bug_defects_added"] == 0


def test_new_triples_and_new_defects_are_counted_apart(tmp_path):
    sibling = _entry()  # (32, 55, 32): E3 sibling of 2.1 bug 1 (32, 55, 35)
    fresh = _entry(id="R22-0002", variable="svp_simple_001_001_global_flag", triple=[
        {"role": "A1", "kind": "write", "line": 41, "flow": "isr_1"},
        {"role": "B", "kind": "read", "line": 53, "flow": "isr_2"},
        {"role": "A2", "kind": "write", "line": 41, "flow": "isr_1"}])
    gt = ground_truth("2.2", suite_root=SUITE, labels_path=_write(tmp_path, sibling, fresh))
    counts = label_counts(gt)
    assert counts["bug_triples"] == 55 and counts["bug_triples_added"] == 2
    assert counts["bug_defects"] == 36 and counts["bug_defects_added"] == 1


# -- agreement -------------------------------------------------------------


def test_cohen_kappa():
    assert cohen_kappa([]) is None
    assert cohen_kappa([("bug", "bug"), ("trap", "trap")]) == 1.0
    # Textbook 2x2: 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no -> kappa = 0.4.
    pairs = [("y", "y")] * 20 + [("y", "n")] * 5 + [("n", "y")] * 10 + [("n", "n")] * 15
    assert cohen_kappa(pairs) == pytest.approx(0.4)


def test_second_check_agreement():
    a = _entry(second_check={"done": True, "adjudicator": "Pedro", "verdict": "bug", "date": "2026-11-21"})
    b = _entry(id="R22-0002", verdict="trap", witness={}, blocking_reason="masked",
               triple=[{"role": "A1", "kind": "write", "line": 32},
                       {"role": "B", "kind": "read", "line": 58},
                       {"role": "A2", "kind": "write", "line": 32}],
               second_check={"done": True, "adjudicator": "Pedro", "verdict": "bug"})
    got = second_check_agreement(parse_labels(_doc(a, b)))
    assert got["n"] == 2 and got["agree"] == 1


def test_label_file_lives_in_bench():
    assert LABELS_22 == REPO / "bench" / "racebench-2.2.yaml"
