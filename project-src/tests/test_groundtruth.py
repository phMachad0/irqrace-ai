"""The ground-truth parser, and the errata applied on top of it.

The number these tests defend is the denominator of every recall figure the
project will ever report. A strict parser reads 28 bug points here and raises no
error, so "it ran without crashing" is not evidence of anything.
"""
import pytest
from conftest import ERRATA, SUITE

from irqrace.groundtruth import (
    ACCESS, Access, ErrataError, apply_errata, load_errata, load_suite, parse_case,
    parse_suite,
)

pytestmark = pytest.mark.skipif(
    not (SUITE / "README.md").exists(), reason="racebench suite not present"
)

#: Certified by hand in docs/groundtruth-handcount.md. Chosen to be adversarial:
#: between them these five exercise every grammar and every known annotation
#: defect in the suite.
HAND_COUNT = {
    "svp_simple_001_001": (1, 2),
    "svp_simple_016_001": (3, 0),
    "svp_simple_019_001": (1, 4),
    "svp_simple_022_001": (4, 3),
    "svp_simple_031_001": (3, 0),
}


@pytest.fixture(scope="module")
def raw():
    return parse_suite(SUITE)


@pytest.fixture(scope="module")
def corrected():
    return load_suite(SUITE, ERRATA)


def test_suite_has_48_bug_points_and_38_traps(raw):
    assert (len(raw.bugs), len(raw.traps)) == (48, 38)


def test_all_31_simple_cases_are_parsed(raw):
    assert len(raw.cases) == 31


@pytest.mark.parametrize("case,counts", sorted(HAND_COUNT.items()))
def test_matches_the_hand_count(raw, case, counts):
    got = raw.by_case(case)
    assert (len(got.bugs), len(got.traps)) == counts


def test_every_annotation_is_a_triple(raw):
    for ann in raw.bugs + raw.traps:
        assert len(ann.accesses) == 3, f"{ann.case} {ann.kind}{ann.index}: {ann.raw}"


def test_every_annotation_names_a_variable(raw):
    for ann in raw.bugs + raw.traps:
        assert ann.variable, f"{ann.case} {ann.kind}{ann.index}: {ann.raw}"


def _projections_have_a_write(ann):
    """Both pair projections of a triple must contain at least one write."""
    a1, b, a2 = (a.kind for a in ann.accesses)
    return "write" in (a1, b) and "write" in (b, a2)


def test_every_corrected_triple_projects_onto_pairs_containing_a_write(corrected):
    """The empirical half of the argument in [[Pair-Triple Unification]].

    A projection of (R, R) is two reads: no race detector can flag it and no
    atomicity violation can arise from it. Every annotated triple in the suite
    satisfies this once the errata is applied.
    """
    for ann in corrected.bugs + corrected.traps:
        assert _projections_have_a_write(ann), (
            f"{ann.case} {ann.kind}{ann.index} {ann.pattern} has a read-only projection")


def test_exactly_one_shipped_annotation_breaks_that_property(raw):
    """svp_simple_016_001 bug 1, read literally, is (W, R, R) — and line 33 is a
    write. This is the independent evidence for that errata entry."""
    offenders = [a for a in raw.bugs + raw.traps if not _projections_have_a_write(a)]
    assert [(a.case, a.kind, a.index, a.pattern) for a in offenders] == [
        ("svp_simple_016_001", "bug", 1, "WRR")
    ]


def test_a_read_in_the_middle_is_normal(corrected):
    """Guards against re-deriving the invariant above too strongly. (W, R, W) —
    the ISR observing an intermediate value between two task writes — is a
    perfectly good atomicity violation, and 14 of the 86 annotations are that
    shape."""
    wrw = [a for a in corrected.bugs + corrected.traps if a.pattern == "WRW"]
    assert len(wrw) == 14
    assert all(a.accesses[1].kind == "read" for a in wrw)


# -- the four grammars, one test each ---------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("<R#45>,<W#65>,<R#54>", [("read", 45), ("write", 65), ("read", 54)]),
    ("<W#43><R#63><W#44>", [("write", 43), ("read", 63), ("write", 44)]),
    ("<R,#44>, <W,#79>, <W,#45>", [("read", 44), ("write", 79), ("write", 45)]),
    ("<#46,R> <#90,W>,<#83,R>", [("read", 46), ("write", 90), ("read", 83)]),
    ("<R, #25>, <W, #39>, <R, #35>", [("read", 25), ("write", 39), ("read", 35)]),
    ("<R, #27>, <W, 41>, <W, #28>", [("read", 27), ("write", 41), ("write", 28)]),
    ("<R#50>,<W#68>,<<R#52>", [("read", 50), ("write", 68), ("read", 52)]),
    ("<R#25>,<W#33,<R#26>", [("read", 25), ("write", 33), ("read", 26)]),
    ("<R#43>,<w#66>,<R#45>", [("read", 43), ("write", 66), ("read", 45)]),
])
def test_access_grammar(text, expected):
    got = [(m.group("type_first") or m.group("type_after"),
            m.group("line_after") or m.group("line_first")) for m in ACCESS.finditer(text)]
    got = [("read" if t.lower() == "r" else "write", int(n)) for t, n in got]
    assert got == expected


def test_a_strict_parser_would_undercount(raw):
    """Documents why the tolerance exists, in the units that matter.

    Requiring the single most common grammar -- `<R#45>` with no spaces, no
    reversal and no typos -- and a `//bug点:` header spelled with an ASCII colon
    loses a large share of the ground truth, and loses it *silently*: a strict
    parser returns a smaller number, not an error.
    """
    import re

    strict_access = re.compile(r"<([RW])#(\d+)>")
    readable = [a for a in raw.bugs if len(strict_access.findall(a.raw)) == 3]
    assert len(readable) < len(raw.bugs), (
        "the strict grammar now reads every bug point; the tolerance may be dead code")
    # Recorded rather than pinned to an exact figure, since it depends on where
    # the line is drawn; the point is the size of the gap, not its last digit.
    assert len(readable) <= 40, len(readable)


# -- errata -----------------------------------------------------------------


def test_errata_applies_cleanly_and_changes_no_count(raw):
    before = (len(raw.bugs), len(raw.traps))
    report = apply_errata(raw, load_errata(ERRATA))
    assert len(report) == 12
    assert (len(raw.bugs), len(raw.traps)) == before == (48, 38)


def test_errata_is_fail_fast_when_it_no_longer_applies(raw):
    """An errata entry that matches nothing means the suite moved underneath
    every number measured against it. That must raise, not be skipped."""
    corrections = load_errata(ERRATA)
    bad = [c.__class__(**{**vars(c), "index": 99}) for c in corrections[:1]]
    with pytest.raises(ErrataError, match="which the parser did not find"):
        apply_errata(raw, bad)


def test_errata_detects_a_changed_annotation(raw):
    corrections = load_errata(ERRATA)
    bad = [corrections[0].__class__(
        **{**vars(corrections[0]), "as_written": "something else entirely"})]
    with pytest.raises(ErrataError, match="quotes"):
        apply_errata(raw, bad)


def test_case_019_write_lines_are_repaired(corrected):
    """The correction that makes the recall gate attainable at all: the shipped
    annotation puts isr_1's write to global_var1 on line 65, which is
    `idlerun();`. The write is on line 71."""
    ann = corrected.by_case("svp_simple_019_001").bugs[0]
    assert ann.lines == (45, 71, 59)
    source = (SUITE / "svp_simple_019" / "svp_simple_019_001.c").read_text().splitlines()
    assert "svp_simple_019_001_global_var1 = 0x01;" in source[70]
    assert "idlerun" in source[64]


def test_every_corrected_line_actually_accesses_something(corrected):
    """No correction may point at a blank line or a closing brace."""
    for case in corrected.cases:
        source = case.path.read_text().splitlines()
        for ann in case.all:
            if "corrected by errata" not in " ".join(ann.anomalies):
                continue
            for a in ann.accesses:
                text = source[a.line - 1].strip()
                assert text and text not in ("{", "}"), (
                    f"{ann.case} {ann.kind}{ann.index} -> line {a.line}: {text!r}")
