"""The tolerant annotation reader, and what it found in the suite.

The grammar tests run anywhere. The suite tests skip when Racebench is not on
the machine — set ``IRQRACE_RACEBENCH`` or clone it to ``../racebench``.
"""

import pytest

from irqrace.llm.annotations import (
    DEFAULT_SECTION,
    counts,
    locate_suite,
    parse_accesses,
    parse_file,
    parse_suite,
    verify_against_source,
)

SUITE = locate_suite()
needs_suite = pytest.mark.skipif(SUITE is None, reason="racebench is not on this machine")


# -- the four grammars, and the errors ------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        # comma-separated, the common form
        ("var <W#32>,<R#55>,<W#35>", [("write", 32), ("read", 55), ("write", 35)]),
        # juxtaposed, no commas (001, 019)
        ("var<W#43><R#63><W#44>", [("write", 43), ("read", 63), ("write", 44)]),
        # comma inside the brackets (021, 022, 025)
        ("var <R,#44>, <W,#79>, <W,#45>", [("read", 44), ("write", 79), ("write", 45)]),
        # spaced (023-030)
        ("var <R, #25>, <W, #39>, <R, #35>", [("read", 25), ("write", 39), ("read", 35)]),
        # line-then-type, reversed fields (031)
        ("var <#46,R> <#90,W>,<#83,R>", [("read", 46), ("write", 90), ("read", 83)]),
    ],
)
def test_every_grammar_parses(text, expected):
    accesses, _ = parse_accesses(text)
    assert [(a.kind, a.line) for a in accesses] == expected


@pytest.mark.parametrize(
    "text,expected,why",
    [
        ("v <R#41>,<W#59>,<<R#52>", 3, "doubled bracket (004)"),
        ("v <R#25>,<W#33,<R#26>", 3, "missing closing bracket (016)"),
        ("v <R, #27>, <W, 41>, <W, #28>", 3, "missing '#' (027)"),
        ("v <R#43>,<w#66>,<R#45>", 3, "lowercase access type (013)"),
    ],
)
def test_the_malformed_ones_recover(text, expected, why):
    accesses, _ = parse_accesses(text)
    assert len(accesses) == expected, why


def test_lowercase_w_is_still_a_write():
    accesses, _ = parse_accesses("v <R#43>,<w#66>,<R#45>")
    assert accesses[1].kind == "write"


@pytest.mark.parametrize(
    "text,variable",
    [
        ("svp_simple_009_001_p<W#32>,<R#44>", "svp_simple_009_001_p"),
        ("*svp_simple_009_001_p<W#32>", "*svp_simple_009_001_p"),
        ("g_union.header<W#40>", "g_union.header"),
        ("g_array[1] <R, #56>", "g_array[1]"),
    ],
)
def test_the_variable_name_survives_verbatim(text, variable):
    """Deref, field and index forms all appear in the suite and all matter --
    they say which cases need alias or field-sensitive reasoning."""
    _, parsed = parse_accesses(text)
    assert parsed == variable


def test_a_line_with_no_brackets_yields_nothing():
    accesses, _ = parse_accesses("just a comment")
    assert accesses == []


# -- section handling -----------------------------------------------------


def test_a_headerless_numbered_block_defaults_to_bug_points():
    """svp_simple_022_001 has four entries under no header at all. Requiring
    one costs exactly those four, silently, and 48 becomes 44."""
    assert DEFAULT_SECTION == "bug_point"


@needs_suite
def test_case_022_yields_four_bug_points_from_its_headerless_block():
    anns = parse_file(next((SUITE / "svp_simple_022").glob("*.c")))
    assert sum(1 for a in anns if a.kind == "bug_point") == 4
    assert sum(1 for a in anns if a.kind == "trap") == 3


@needs_suite
def test_the_possible_false_positive_header_is_a_trap_section():
    anns = parse_file(next((SUITE / "svp_simple_022").glob("*.c")))
    assert any(a.kind == "trap" for a in anns), "'可能误报' was not read as a trap header"


# -- the certification ----------------------------------------------------


@needs_suite
def test_the_reader_reproduces_the_suites_48_and_38():
    """Roadmap W2's 'done when'. The wiki records 48/38 as measured; this is
    an independent reproduction from the files."""
    assert counts(parse_suite(SUITE)) == {
        "bug_points": 48,
        "traps": 38,
        "subjects": 31,
    }


@needs_suite
def test_every_annotation_is_a_triple():
    """The benchmark's ground truth is atomicity-violation shaped even for the
    papers that call these data races (Contradictions #5)."""
    assert all(a.is_triple for a in parse_suite(SUITE))


@needs_suite
def test_the_patterns_are_the_documented_four_plus_the_known_bad_one():
    patterns = {a.pattern for a in parse_suite(SUITE)}
    assert {"RWR", "RWW", "WRW", "WWR"} <= patterns
    # WRR exists once: svp_simple_016_001 bug point 1, whose middle access type
    # is wrong in the annotation -- line 33 is a write, not a read.
    assert patterns - {"RWR", "RWW", "WRW", "WWR"} == {"WRR"}


# -- what verification found ----------------------------------------------


@needs_suite
def test_the_001_trap_points_at_a_declaration():
    """<R#63> is `int reader2;`. The read is on line 64."""
    source = next((SUITE / "svp_simple_001").glob("*.c"))
    trap = next(a for a in parse_file(source) if a.kind == "trap" and a.index == 1)
    problems = verify_against_source(trap, source)
    assert any("int reader2" in p for p in problems)


@needs_suite
def test_case_019_is_annotated_against_the_other_copy_of_the_suite():
    """All five of svp_simple_019_001's annotations resolve cleanly against
    ``2.1`` and not against the ``2.1_remarks`` file they are written in.

    In the shipped file they point at ``idlerun();``, ``{`` and blank lines.
    Any match rule keyed on line numbers therefore loses one bug point and
    four traps on this case alone.
    """
    plain = SUITE.parent / "2.1" / "svp_simple_019"
    if not plain.is_dir():
        pytest.skip("the unannotated 2.1 copy is not present")

    remarks_source = next((SUITE / "svp_simple_019").glob("*.c"))
    plain_source = next(plain.glob("*.c"))
    anns = parse_file(remarks_source)

    assert len(anns) == 5
    assert all(verify_against_source(a, remarks_source) for a in anns), (
        "expected every annotation in 019 to be wrong against its own file"
    )
    assert not any(verify_against_source(a, plain_source) for a in anns), (
        "expected every annotation in 019 to be right against the 2.1 copy"
    )


@needs_suite
def test_case_019_is_the_only_case_annotated_against_the_other_copy():
    """Scoped deliberately: if a second case ever shows this, the defect is
    systematic rather than local and the match rule needs rethinking."""
    plain_root = SUITE.parent / "2.1"
    if not plain_root.is_dir():
        pytest.skip("the unannotated 2.1 copy is not present")

    affected = set()
    for a in parse_suite(SUITE):
        case = a.subject.rsplit("_", 1)[0]
        remarks_source = next((SUITE / case).glob("*.c"))
        plain_source = next((plain_root / case).glob("*.c"), None)
        if plain_source is None:
            continue
        if len(verify_against_source(a, plain_source)) < len(
            verify_against_source(a, remarks_source)
        ):
            affected.add(case)
    assert affected == {"svp_simple_019"}
