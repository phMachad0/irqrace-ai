"""The 18 real-world programs: priority.info, violation.info, errata, C1.

The ground-truth grammar is irregular (labels with and without a colon, indexed
array names, per-instance entries with alternative lines, one unlabelled file),
so the parser is pinned against the counts the wiki took by hand -- 45 true and
14 false violations -- and against the source files the configurations name.
"""
import re
from pathlib import Path

import pytest

from irqrace.config import Config
from irqrace.realworld import (
    ALT_SUFFIX,
    PROGRAMS,
    Entry,
    RealWorldError,
    config_for,
    load_errata,
    locate_suite,
    match,
    parse_priority,
    parse_violation_info,
    priorities_for,
)

SUITE = locate_suite()
pytestmark = pytest.mark.skipif(SUITE is None, reason="bench/realworld not present")


def entries(program, corrected=True):
    return parse_violation_info(SUITE / program / "violation.info", program,
                                load_errata(), corrected=corrected)[0]


def test_ground_truth_is_45_true_and_14_false():
    labels = [e.label for p in PROGRAMS for e in entries(p)]
    assert labels.count("bug") == 45
    assert labels.count("trap") == 14


def test_the_errata_never_change_a_count():
    for p in PROGRAMS:
        raw, fixed = entries(p, corrected=False), entries(p)
        assert [e.label for e in raw] == [e.label for e in fixed], p
        assert [e.pattern for e in raw] == [e.pattern for e in fixed], p


def test_logger2_has_no_entries_because_its_lines_are_unlabelled():
    assert entries("logger2") == []
    assert "test_global_var" not in (SUITE / "logger2" / "main.c").read_text()


def test_colon_and_array_index_are_tolerated():
    brake1 = entries("brake1")
    assert [(e.variable, e.pattern) for e in brake1] == [
        ("test_global_var1", "RWR"), ("test_global_var2", "RWR"), ("test_global_array", "WWR")]


def test_instance_entries_read_alternative_lines():
    e = entries("blink3", corrected=False)[0]
    assert e.is_instance and e.pattern == "RWW"
    assert e.accesses[1].lines == (123, 136) and e.accesses[1].kind == "write"


def test_every_corrected_line_has_the_access_it_claims():
    """A line erratum must point at a line that really performs that access on
    the named variable -- the defect it exists to fix is lines that do not."""
    for p in ("blink2", "blink3"):
        src = (SUITE / p / "main.c").read_text().splitlines()
        for e in entries(p):
            for a in e.accesses:
                for n in a.lines:
                    assert e.variable in src[n - 1], (p, e.index, n, src[n - 1])


def test_an_erratum_that_misquotes_the_file_is_refused():
    errata = load_errata()
    errata["corrections"] = [{**errata["corrections"][0], "as_written": "something else"}]
    with pytest.raises(RealWorldError):
        parse_violation_info(SUITE / "blink2" / "violation.info", "blink2", errata)


def test_entry_names_exist_in_the_source():
    """priority.info says `task_measure`; the function is `task_measure_isr`. A
    wrong entry contributes no accesses and loses every defect it touches."""
    for p in PROGRAMS:
        src = (SUITE / p / "main.c").read_text()
        for name, _ in parse_priority(SUITE / p / "priority.info"):
            assert re.search(rf"\bvoid\s+{name}_isr\s*\(", src), (p, name)
        assert re.search(r"\bint\s+main\s*\(|\bvoid\s+main\s*\(", src), p


def test_configs_validate_and_carry_the_errata():
    errata = load_errata()
    for p in PROGRAMS:
        cfg = Config.from_dict(config_for(p, SUITE, errata=errata))
        assert [f.entry for f in cfg.flows][0] == "main"
        assert cfg.data["masking"]["initial_state"] == "unknown"
    wdt3 = config_for("wdt_pci_3", SUITE, errata=errata)["subject"]["build"]
    assert "-Wno-error=return-type" in wdt3["flags"]
    assert "wdtpci_lock0=wdtpci_lock" in wdt3["defines"]


def test_alternative_priorities_name_the_same_flows():
    errata = load_errata()
    for p, alt in errata["priority_alternatives"].items():
        assert set(alt) == {n for n, _ in parse_priority(SUITE / p / "priority.info")}, p


def test_match_is_by_variable_and_pattern_or_by_lines():
    var = Entry("x", 1, "bug", "v", "RWW")
    inst = entries("blink3")[1]  # timerCount(136R,123W,136W)

    def cand(name, pattern, lines, kinds):
        return {"id": "c", "variable": {"name": name}, "pattern": pattern,
                "accesses": [{"source": {"line": n}, "kind": k} for n, k in zip(lines, kinds)]}

    assert match([var], [cand("v", "RWW", [1, 2, 3], ["read", "write", "write"])])[0].found
    assert not match([var], [cand("v", "RWR", [1, 2, 3], ["read", "write", "read"])])[0].found
    ok = cand("timerCount", "RWW", [136, 123, 136], ["read", "write", "write"])
    off = cand("timerCount", "RWW", [136, 109, 136], ["read", "write", "write"])
    assert match([inst], [ok])[0].found and not match([inst], [off])[0].found


def test_alt_suffix_is_not_a_program_name():
    assert all(ALT_SUFFIX not in p for p in PROGRAMS)


def test_priority_corrections_are_exactly_the_three_contradicted_programs():
    """Only where the shipped levels make the program's own ground truth
    unreachable (logger3, wdt_pci_1, wdt_pci_2); elsewhere the shipped file wins."""
    errata = load_errata()
    assert set(errata["priority_corrections"]) == {"logger3", "wdt_pci_1", "wdt_pci_2"}
    assert not set(errata["priority_corrections"]) & set(errata["priority_alternatives"])
    for p in PROGRAMS:
        shipped = parse_priority(SUITE / p / "priority.info")
        assert priorities_for(p, SUITE, errata, corrected=False) == shipped
        got = priorities_for(p, SUITE, errata)
        assert [n for n, _ in got] == [n for n, _ in shipped], p
        assert (got != shipped) == (p in errata["priority_corrections"]), p


def test_wdt_pci_1_writers_preempt_closers_after_correction():
    levels = dict(priorities_for("wdt_pci_1", SUITE, load_errata()))
    assert levels["writer1"] > levels["closer1"] and levels["writer2"] > levels["closer2"]
