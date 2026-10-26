"""Tests for the Streamlit Pipeline Visualizer & Inter-Stage Metrics helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from irqrace.runstore import RunStore
from irqrace.ui.app import (
    FIXTURE_RUN,
    _compute_run_funnel,
    _discover_all_runs,
    _highlight_c_source,
    compare_runs,
    export_funnel_latex,
    export_funnel_markdown,
    read_human_labels,
    set_human_label,
)


def test_discover_runs_includes_fixture() -> None:
    runs = _discover_all_runs(Path("nonexistent-dir-for-test"))
    assert FIXTURE_RUN in runs


def test_compute_run_funnel_on_fixture_run() -> None:
    store = RunStore(FIXTURE_RUN)
    rows = _compute_run_funnel(store)
    assert len(rows) == 8
    stage_names = [r["Estágio"] for r in rows]
    assert any("Stage 1" in s for s in stage_names)
    assert any("Z3" in s for s in stage_names)
    assert any("LLM Stage A" in s for s in stage_names)


def test_export_funnel_markdown_and_latex() -> None:
    store = RunStore(FIXTURE_RUN)
    rows = _compute_run_funnel(store)
    md = export_funnel_markdown(rows)
    assert "| Estágio |" in md
    assert "1. Stage 1 (SVF + Co-exec)" in md

    tex = export_funnel_latex(rows, caption="Teste TCC")
    assert "\\begin{table}" in tex
    assert "Teste TCC" in tex
    assert "\\bottomrule" in tex


def test_human_labels_roundtrip(tmp_path: Path) -> None:
    run_copy = tmp_path / "run-copy"
    shutil.copytree(FIXTURE_RUN, run_copy)
    store = RunStore(run_copy)
    assert read_human_labels(store) == {}

    set_human_label(store, "cf8fd11d0783ef732", "confirmed", "Real WRW bug via isr_1")
    loaded = read_human_labels(store)
    assert loaded["cf8fd11d0783ef732"] == {
        "label": "confirmed",
        "note": "Real WRW bug via isr_1",
    }


def test_compare_runs_on_identical_and_modified(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    shutil.copytree(FIXTURE_RUN, run_a)
    shutil.copytree(FIXTURE_RUN, run_b)

    diff_same = compare_runs(RunStore(run_a), RunStore(run_b))
    assert len(diff_same["shared"]) == len(RunStore(run_a).read_candidates("stage1"))
    assert diff_same["only_in_a"] == []
    assert diff_same["only_in_b"] == []
    assert all(not r["Mudou?"] for r in diff_same["rows"])


def test_highlight_c_source_renders_badges() -> None:
    html_out = _highlight_c_source(
        "int x = 0;\nx = 1;\n",
        10,
        {11: ("A1: WRITE", "#ef4444")},
    )
    assert "A1: WRITE" in html_out
    assert "x = 1;" in html_out


def test_full_streamlit_interactive_walkthrough() -> None:
    """Exercise every page, button, radio, and selectbox in the Streamlit app via AppTest."""
    from streamlit.testing.v1 import AppTest

    app_file = Path(__file__).resolve().parents[1] / "src" / "irqrace" / "ui" / "app.py"
    at = AppTest.from_file(str(app_file), default_timeout=30)
    at.run()
    assert not at.exception, f"Home page exception: {at.exception}"

    # 1. Click the '🚀 Abrir Demonstração Passo a Passo' button on the Home page
    at.button[0].click().run()
    assert not at.exception, f"Demo button click exception: {at.exception}"
    assert at.session_state["nav_page"] == "🔬 Pipeline (Demo)"

    # 2. Walk through all 7 clickable pipeline blocks in the Demo page
    for idx in range(7):
        at.button(key=f"blk_btn_{idx}").click().run()
        assert not at.exception, f"Block {idx} click exception: {at.exception}"
        # If on Block 5 (index 4: Contexto C2 & C4), test all C4 query kinds
        if idx == 4:
            c4_options = list(at.selectbox(key="c4_select").options)
            for c4_opt in c4_options:
                at.selectbox(key="c4_select").set_value(c4_opt).run()
                assert not at.exception, f"C4 {c4_opt} exception: {at.exception}"

    # 3. Switch candidate in the Demo page and re-check Block 6 & Block 7
    cand_options = list(at.selectbox(key="cand_select").options)
    if len(cand_options) > 1:
        at.selectbox(key="cand_select").set_value(cand_options[1]).run()
        assert not at.exception, f"Candidate switch exception: {at.exception}"
        for idx in (5, 6):
            at.button(key=f"blk_btn_{idx}").click().run()
            assert not at.exception, f"Cand 2 block {idx} exception: {at.exception}"

    # 4. Switch to a Racebench run in the sidebar and verify Demo & Metrics pages
    run_options = list(at.selectbox(key="run_select").options)
    if len(run_options) > 1:
        at.selectbox(key="run_select").set_value(run_options[1]).run()
        assert not at.exception, f"Run switch exception: {at.exception}"

    # 5. Navigate back to Home and click '📊 Ver Métricas Inter-Estágios'
    at.radio(key="nav_page").set_value("🏠 Início").run()
    assert not at.exception
    at.button[1].click().run()
    assert not at.exception, f"Metrics button click exception: {at.exception}"
    assert at.session_state["nav_page"] == "📊 Métricas & Funil"

    # 6. Also test selecting the frozen C3 example run (last option) across all 7 blocks
    at.radio(key="nav_page").set_value("🔬 Pipeline (Demo)").run()
    run_options = list(at.selectbox(key="run_select").options)
    at.selectbox(key="run_select").set_value(run_options[-1]).run()
    assert not at.exception, f"Fixture run select exception: {at.exception}"
    for idx in range(7):
        at.button(key=f"blk_btn_{idx}").click().run()
        assert not at.exception, f"Fixture run block {idx} exception: {at.exception}"

