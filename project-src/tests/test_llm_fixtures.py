"""The labelled set, and the honesty of its coverage report."""

import pytest

from irqrace.llm import fixtures
from irqrace.llm.fixtures import TARGET_PER_LABEL, coverage, load_all


def test_every_fixture_conforms_to_c2():
    """Strict by default. A fixture Track A could never emit measures nothing."""
    assert load_all(strict=True)


def test_labels_live_outside_the_records():
    """The record must not leak the answer into the prompt.

    This caught a real leak: an early builder wrote a ``ground_truth``
    provenance entry naming the annotation's section, which is the label. A
    real stage 2 does not know whether a candidate is annotated at all, so a
    fixture carrying that is not indistinguishable from emitter output.
    """
    for f in load_all():
        flat = str(f.record)
        for leak in ("bug_point", "ground_truth", '"label"', "误报", "planted"):
            assert leak not in flat, f"{f.path.name} leaks {leak!r}"


def test_every_label_is_traceable_to_the_suite():
    for f in load_all():
        assert f.annotation.strip(), f"{f.path.name} has no annotation"


def test_candidate_ids_are_unique():
    ids = [f.candidate_id for f in load_all()]
    assert len(ids) == len(set(ids))


def test_coverage_reports_the_set_as_incomplete_until_it_is():
    """W1 asks for 10 + 10. Two is not twenty, and the report must say so."""
    cov = coverage()
    if cov.bug_points >= TARGET_PER_LABEL and cov.traps >= TARGET_PER_LABEL:
        assert cov.complete
    else:
        assert not cov.complete
        assert "INCOMPLETE" in cov.report()


def test_the_seed_pair_is_adversarial():
    """The two seeded fixtures differ in label but not in shape.

    Same subject, same pattern, same class -- the only thing separating them is
    whether a flow running inside the masked interval re-enables the interrupt.
    A prompt that gets both right has learned the rule rather than the surface,
    which is why this pair is the first thing in the set.
    """
    pair = [f for f in load_all() if f.subject == "svp_simple_001_001"]
    assert len(pair) == 2
    bug, trap = sorted(pair, key=lambda f: f.label)
    assert (bug.label, trap.label) == ("bug_point", "trap")
    assert bug.record["pattern"] == trap.record["pattern"]
    assert bug.record["class"] == trap.record["class"]
    assert bug.record["variable"]["name"] != trap.record["variable"]["name"]


def test_the_generated_fixtures_on_disk_are_current():
    """A spec edit that was never rebuilt would score the prompt against a
    record nobody intended. Same guard Track A put on its generated configs."""
    import subprocess
    import sys

    repo = fixtures.FIXTURES_DIR.parent
    result = subprocess.run(
        [sys.executable, str(repo / "scripts" / "build-fixtures.py"), "--check"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 2:
        pytest.skip("racebench is not on this machine")
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_set_spans_every_access_pattern_the_suite_uses():
    """Twenty fixtures that were all WRW would score one interrupt pattern."""
    assert {f.record["pattern"] for f in load_all()} == {
        "RWR",
        "RWW",
        "WRW",
        "WWR",
    }


def test_adversarial_pairs_share_a_subject_and_differ_in_label():
    """The set's value is in the pairs, not the count: for a case contributing
    both a bug point and a trap, a prompt cannot score well by shape alone."""
    by_subject: dict[str, set[str]] = {}
    for f in load_all():
        by_subject.setdefault(f.subject, set()).add(f.label)
    paired = {s for s, labels in by_subject.items() if len(labels) == 2}
    assert len(paired) >= 6, f"only {len(paired)} subjects contribute both labels"


def test_missing_file_named_in_the_manifest_is_an_error(monkeypatch, tmp_path):
    manifest = tmp_path / "labels.json"
    manifest.write_text(
        '{"fixtures": [{"path": "nope.json", "label": "trap", "annotation": "x"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(fixtures, "MANIFEST", manifest)
    monkeypatch.setattr(fixtures, "FIXTURES_DIR", tmp_path)
    with pytest.raises(fixtures.FixtureError, match="does not exist"):
        load_all()
