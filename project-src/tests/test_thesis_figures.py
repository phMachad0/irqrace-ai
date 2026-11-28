"""scripts/thesis-figures.py on the SYNTHETIC fixture: every figure comes out,
and a missing input skips its figures instead of faking them."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "thesis-figures"

_spec = importlib.util.spec_from_file_location("thesis_figures", REPO / "scripts" / "thesis-figures.py")
thesis_figures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(thesis_figures)


def test_every_figure_is_produced(tmp_path):
    out = tmp_path / "figs"
    assert thesis_figures.main(["--data", str(FIXTURE), "--out", str(out)]) == 0
    for name in thesis_figures.FIGURE_FILES.values():
        pdf = out / f"{name}.pdf"
        assert pdf.exists(), name
        assert pdf.read_bytes()[:5] == b"%PDF-"
    record = json.loads((out / "thesis-figures.json").read_text(encoding="utf-8"))
    assert set(record["figures"]) == set(thesis_figures.FIGURES)
    assert not any("skipped" in f or "error" in f for f in record["figures"].values())
    assert record["manifest"]["commit"] == "SYNTHETIC"


def test_missing_inputs_skip_their_figures(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(FIXTURE, data)
    (data / "labels22.csv").unlink()
    (data / "published.csv").unlink()
    out = tmp_path / "figs"
    assert thesis_figures.main(["--data", str(data), "--out", str(out), "--only", "F1,F2,F10,F11"]) == 0
    record = json.loads((out / "thesis-figures.json").read_text(encoding="utf-8"))["figures"]
    assert "published.csv" in record["F1"]["skipped"]
    assert "labels22.csv" in record["F10"]["skipped"]
    assert "labels22.csv" in record["F11"]["skipped"]
    assert (out / "F2-funil.pdf").exists()
    assert not (out / "F10-composicao-2-2.pdf").exists()


def test_recall_veto_ignores_uncertain_bug_points(tmp_path):
    """F6 marks a prompt only when a bug point is called infeasible. The fixture
    leaves bug points in `uncertain` under every row, which is a ranking cost,
    and calls one infeasible only under +racebench+location."""
    out = tmp_path / "figs"
    assert thesis_figures.main(["--data", str(FIXTURE), "--out", str(out), "--only", "F6"]) == 0
    record = json.loads((out / "thesis-figures.json").read_text(encoding="utf-8"))["figures"]
    assert record["F6"]["recall_veto"] == ["+racebench+location"]
