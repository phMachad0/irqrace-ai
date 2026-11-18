"""Issues #13, #14, #15, #17: the candidate list and the panels around it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from irqrace.ui.candidate_list import (
    DISCARDED,
    PENDING,
    Row,
    group_rows,
    sort_rows,
    tab_states,
    variable_key,
    variable_label,
)


def row(cid: str, variable="x", pattern="RWR", bucket=PENDING, lines=(1, 2, 3), confidence=-1.0, repair="-") -> Row:
    return Row(cid=cid, pattern=pattern, variable=variable, locations=str(lines), feasibility="",
               bucket=bucket, repair=repair, lines=lines, confidence=confidence)


def ids(rows) -> list[str]:
    return [r.cid for r in rows]


def test_what_reaches_the_llm_comes_before_what_was_dropped_keeping_its_order() -> None:
    rows = [row("a", bucket=DISCARDED), row("b", bucket="uncertain"), row("c", bucket=DISCARDED),
            row("d", bucket="likely_real")]
    assert ids(sort_rows(rows)) == ["b", "d", "a", "c"]


def test_lines_sort_as_numbers_not_as_text() -> None:
    rows = [row("a", lines=(100, 1, 2)), row("b", lines=(9, 1, 2)), row("c", lines=(20, 1, 2))]
    assert ids(sort_rows(rows, "lines")) == ["b", "c", "a"]
    assert ids(sort_rows(rows, "lines", reverse=True)) == ["a", "c", "b"]


def test_feasibility_sorts_by_confidence() -> None:
    rows = [row("a", confidence=0.2), row("b", confidence=0.9), row("c")]
    assert ids(sort_rows(rows, "feas", reverse=True)) == ["b", "a", "c"]


def test_buckets_sort_by_meaning_not_alphabetically() -> None:
    names = [DISCARDED, "likely_benign", PENDING, "likely_real", "likely_infeasible", "uncertain"]
    rows = [row(n, bucket=n) for n in names]
    assert ids(sort_rows(rows, "bucket")) == [
        "likely_real", "uncertain", "likely_benign", "likely_infeasible", PENDING, DISCARDED]


def test_names_with_numbers_sort_as_a_person_expects() -> None:
    rows = [row("a", variable="obj_10"), row("b", variable="obj_9")]
    assert ids(sort_rows(rows, "var")) == ["b", "a"]


def test_a_group_says_what_its_candidates_add_up_to() -> None:
    rows = [row("a", "n", "RWR", "likely_benign"), row("b", "n", "RWR", DISCARDED), row("c", "n", "WWR", "likely_real"),
            row("d", "m", "RWR", "uncertain")]
    first, second = group_rows(rows)
    assert (first.label, first.reaching_llm, first.discarded, first.patterns, first.best_bucket) == (
        "n", 2, 1, "RWR:2 WWR:1", "likely_real")
    assert ids(first.rows) == ["a", "b", "c"]
    assert second.label == "m"


def test_grouping_loses_no_candidate() -> None:
    rows = [row(str(i), f"v{i % 3}") for i in range(10)]
    assert sorted(c for g in group_rows(rows) for c in ids(g.rows)) == sorted(ids(rows))


def test_two_locals_with_one_name_are_two_variables() -> None:
    one = {"name": "rate", "storage": "stack", "function": "taskLineSensor", "decl": {"file": "tasks.cpp", "line": 226}}
    two = {"name": "rate", "storage": "stack", "function": "taskControl", "decl": {"file": "tasks.cpp", "line": 301}}
    assert variable_key(one) != variable_key(two)
    assert variable_label(one) == "rate (local de taskLineSensor, tasks.cpp:226)"


def test_a_global_reads_as_its_name() -> None:
    assert variable_label({"name": "pending", "storage": "global", "decl": {"file": "isr.c", "line": 2}}) == "pending"
    assert variable_label({"name": "pending"}) == "pending"


def test_tab_states_come_from_the_stages_and_the_selected_candidate() -> None:
    stages = {"build": "ok", "stage1": "ok", "solver": "ok", "context": "ok", "triage": "ok", "repair": "pending"}
    assert tab_states({}) == dict.fromkeys(("log", "triage", "repair", "source", "history"), "idle")
    general = tab_states(stages)
    assert (general["log"], general["triage"], general["repair"]) == ("done", "done", "idle")
    picked = tab_states(stages, selected=True, verdict=True, turns=False)
    assert (picked["triage"], picked["history"]) == ("done", "idle")


def test_a_failed_or_running_stage_overrides_the_selected_candidate() -> None:
    assert tab_states({"triage": "failed"}, selected=True, verdict=True)["triage"] == "failed"
    assert tab_states({"triage": "running"}, selected=True, verdict=True)["triage"] == "running"
    assert tab_states({"build": "ok", "stage1": "failed"})["log"] == "failed"


# -- the widgets ------------------------------------------------------------


@pytest.fixture
def app(tk_root, tmp_path: Path):
    import tkinter as tk

    from irqrace.ui.desktop import IrqRaceWinApp

    source = tmp_path / "task.c"
    source.write_text("".join(f"int line{n};\n" for n in range(1, 21)), encoding="utf-8")

    def record(cid: str, name: str, a1: int) -> dict:
        return {
            "id": cid, "pattern": "RWR", "class": "atomicity-triple",
            "variable": {"name": name, "declared_type": "int"},
            "flows": [{"id": "main", "priority": 0}],
            "accesses": [
                {"role": role, "kind": "read", "flow": "main", "function": "f",
                 "source": {"file": "task.c", "line": line}}
                for role, line in (("A1", a1), ("B", a1 + 1), ("A2", a1 + 2))
            ],
        }

    class Store:  # only what the table reads
        root = tmp_path / "run"

        def read_candidates(self, _stage):
            return [record("c1", "gone", 100), record("c2", "kept", 9), record("c3", "kept", 2)]

        def read_drops(self):
            return [{"candidate_id": "c1", "reason": "masked", "proof": "p"}]

        def read_manifest(self):
            return {"stages": [{"name": "stage1", "status": "ok"}]}

    Store.root.mkdir()
    (Store.root / "manifest.json").write_text(json.dumps(Store().read_manifest()), encoding="utf-8")
    win = tk.Toplevel(tk_root)
    application = IrqRaceWinApp(win)
    application.source_files_list = [source]
    application._refresh_from_store(Store())
    win.update()
    yield application
    win.destroy()


def test_the_table_opens_with_the_dropped_candidate_last_and_sorts_on_click(app) -> None:
    assert list(app.tree.get_children()) == ["c2", "c3", "c1"]
    app._on_sort_column("lines")
    assert list(app.tree.get_children()) == ["c3", "c2", "c1"]
    assert app.tree.heading("lines", "text").endswith("▲")
    app._on_sort_column("lines")
    assert list(app.tree.get_children()) == ["c1", "c2", "c3"]
    assert app.tree.heading("lines", "text").endswith("▼")


def test_sorting_keeps_the_selected_candidate(app) -> None:
    app.tree.selection_set("c3")
    app._on_sort_column("var")
    assert app.tree.selection() == ("c3",)


def test_grouping_makes_expandable_parents_and_selection_still_works(app) -> None:
    app.group_by_variable_var.set(True)
    app.tree.selection_set("c3")
    app._draw_candidate_rows()
    parents = app.tree.get_children()
    assert len(parents) == 2
    kept = next(p for p in parents if "kept" in app.tree.set(p, "var"))
    assert list(app.tree.get_children(kept)) == ["c2", "c3"]
    assert app.tree.selection() == ("c3",)
    assert app.tree.item(kept, "open")
    app.tree.selection_set(kept)  # a variable is not a candidate: nothing to show, and no error
    app._on_candidate_selected()
    app.group_by_variable_var.set(False)
    app._draw_candidate_rows()
    assert len(app.tree.get_children()) == 3


def test_the_detail_shows_each_access_with_its_line_marked(app) -> None:
    app.tree.selection_set("c2")
    app._on_candidate_selected()
    text = app.txt_detail.get("1.0", "end")
    assert "A1  read em task.c:9" in text and "main, prioridade 0, função f" in text
    assert "    9 | int line9;" in text
    marked = app.txt_detail.tag_ranges("marked")
    assert len(marked) == 6, "one marked line per access"


def test_prose_wraps_and_code_does_not(app) -> None:
    assert str(app.txt_repair.cget("wrap")) == "word"
    assert str(app.txt_diff.cget("wrap")) == "none"
    app._display_repair_with_git_highlight(
        "c2",
        {"strategy": "mask_interval", "reasoning": "why", "diff": "--- a/task.c\n+++ b/task.c\n@@ -1 +1 @@\n-x\n+y\n"},
        None,
    )
    assert "why" in app.txt_repair.get("1.0", "end") and "@@ -1 +1 @@" not in app.txt_repair.get("1.0", "end")
    assert "@@ -1 +1 @@" in app.txt_diff.get("1.0", "end")


def test_the_tabs_carry_their_state_and_the_panel_can_be_hidden(app) -> None:
    assert app.notebook.tab(app.tab_source, "text").strip() == "✓ Código Fonte"
    assert app.notebook.tab(app.tab_triage, "text").strip() == "○ Triagem"
    assert app.notebook.tab(app.tab_triage, "image")
    app._toggle_bottom_panel()
    assert len(app.workspace_paned.panes()) == 1
    app._toggle_bottom_panel()
    assert len(app.workspace_paned.panes()) == 2
