"""The M3 artifact: the ablation table."""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "ablation_table", REPO / "scripts" / "ablation-table.py"
)
table = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(table)


def _row(name, backend, recall=1.0, trap=0.8, insp=0.6, **extra):
    return {
        "row": name, "backend": backend, "recall": recall, "gate_passed": recall == 1.0,
        "trap_rejection": trap, "inspection_ratio": insp, "buckets": {},
        "missed": [], "excluded": [], "caveats": [], "cost_usd": None, **extra,
    }


def test_rows_render_in_ablation_order(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([_row("+domain", "a:b"), _row("simple", "a:b")]))
    out = table.render(table.load([p]))
    assert out.index("`simple`") < out.index("`+domain`")


def test_two_result_files_become_two_column_groups(tmp_path):
    """The comparison LLift's claim needs: one prompt, two models."""
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps([_row("simple", "openai:m1", trap=0.8)]))
    b.write_text(json.dumps([_row("simple", "anthropic:m2", trap=0.9)]))
    out = table.render(table.load([a, b]))
    assert "openai:m1" in out and "anthropic:m2" in out
    assert "80.0%" in out and "90.0%" in out


def test_a_broken_recall_gate_is_marked_in_the_cell(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([_row("simple", "a:b", recall=0.9, missed=["c1"])]))
    out = table.render(table.load([p]))
    assert "⚠" in out
    assert "recall gate broken" in out


def test_benign_bug_points_are_surfaced_not_hidden(tmp_path):
    """They pass the gate and sink the Inspection Ratio, so the table says so."""
    p = tmp_path / "r.json"
    p.write_text(json.dumps([_row("simple", "a:b", bug_points_bucketed_benign=["c1"])]))
    assert "likely_benign" in table.render(table.load([p]))


def test_caveats_travel_with_the_table(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([_row("simple", "a:b", caveats=["no prompt caching"])]))
    assert "no prompt caching" in table.render(table.load([p]))


def test_a_missing_row_is_a_gap_not_a_zero(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([_row("simple", "a:b")]))
    out = table.render(table.load([p]))
    assert "`+domain`" not in out  # not run at all, so not invented


# -- credential loading ----------------------------------------------------


def _runner():
    spec = importlib.util.spec_from_file_location(
        "run_ablation", REPO / "scripts" / "run-ablation.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_env_file_is_read_but_never_overrides_an_export(tmp_path, monkeypatch):
    """Credentials belong in a gitignored file, not in shell history — but an
    explicit export still wins, so a one-off override works."""
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nFROM_FILE=yes\nALREADY_SET=from-file\nBAD LINE\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALREADY_SET", "from-export")
    monkeypatch.delenv("FROM_FILE", raising=False)

    loaded = _runner().load_env(env)
    import os

    assert os.environ["FROM_FILE"] == "yes"
    assert os.environ["ALREADY_SET"] == "from-export"
    assert loaded == ["FROM_FILE"]


def test_a_missing_env_file_is_not_an_error(tmp_path):
    assert _runner().load_env(tmp_path / "nope") == []


def test_an_incomplete_row_shows_coverage_instead_of_figures(tmp_path):
    """'100% / 100% / 100%' over three of twenty candidates is how a number
    that means nothing ends up quoted."""
    p = tmp_path / "r.json"
    p.write_text(json.dumps([
        _row("+progressive", "a:b", recall=1.0, trap=1.0, insp=1.0,
             n_scored=3, n_expected=20)
    ]))
    out = table.render(table.load([p]))
    assert "3/20 scored" in out
    assert "100.0%" not in out


def test_coverage_is_derived_for_results_written_before_it_was_recorded(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps([
        _row("simple", "a:b", buckets={"likely_real": 3},
             excluded=[{"candidate": "c", "reason": "r"}] * 17)
    ]))
    assert "3/20 scored" in table.render(table.load([p]))
