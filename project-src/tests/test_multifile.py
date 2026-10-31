"""Issue #8: in a multi-file subject a line means nothing without its file.

The program is the issue's: ``task.c`` reads and clears ``pending``, ``isr.c``
increments it through ``extern``. Line 5 of ``isr.c`` must never mark, match or
patch line 5 of ``task.c``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from irqrace import contracts
from irqrace.candidate import access_locations, same_source
from irqrace.evaluation import match_subject
from irqrace.groundtruth import Access, Annotation
from irqrace.llm.repair import (
    Patch,
    Strategy,
    Witness,
    apply_unified_diff,
    diff_file,
    make_compile_checker,
    patch_file,
)

TASK = """\
/* the local flow */
extern volatile int pending;
int consume(int n);

int main(void) {
  for (;;) {
    int n;
    n = pending;
    consume(n);
    /* the increment between the two is lost */
    pending = 0;
  }
  return 0;
}

int consume(int n) { return n; }
"""
ISR = """\
/* the remote flow */
volatile int pending;

void timer_isr(void) {
  pending++;
}
"""


def _subject(tmp_path: Path) -> tuple[Path, list[Path]]:
    from irqrace.ui.c1_wizard import WizardState, save_c1, scan_functions, suggest_flows

    src = tmp_path / "src"
    src.mkdir()
    (src / "task.c").write_text(TASK, encoding="utf-8")
    (src / "isr.c").write_text(ISR, encoding="utf-8")
    sources = [src / "task.c", src / "isr.c"]
    defined, _ = scan_functions(sources)
    target = tmp_path / "cfg" / "two-files.c1.yaml"
    save_c1(WizardState(name="two_files", sources=sources, flows=suggest_flows(defined)), target)
    return target, sources


@pytest.fixture
def run(tmp_path: Path):
    PipelineStepper = pytest.importorskip("irqrace.ui.desktop").PipelineStepper
    target, sources = _subject(tmp_path)
    stepper = PipelineStepper(target, sources, work_root=tmp_path / "runs")
    store = stepper.init_run()
    for _ in range(4):
        stepper.run_next_step(log_fn=lambda _m: None)
    return target, store


def _rww(store) -> dict:
    return next(
        c for c in store.read_contexts()
        if c["pattern"] == "RWW" and [Path(a["source"]["file"]).name for a in c["accesses"]] == ["task.c", "isr.c", "task.c"]
    )


def test_a_triple_across_two_files_keeps_its_files(run) -> None:
    _, store = run
    assert access_locations(_rww(store)["accesses"]).startswith("task.c:8, isr.c:5, task.c:11")


def test_a_drop_record_locates_its_accesses(tmp_path: Path) -> None:
    PipelineStepper = pytest.importorskip("irqrace.ui.desktop").PipelineStepper
    case = Path(__file__).parents[1] / "bench" / "configs" / "svp_simple_001_001.yaml"
    stepper = PipelineStepper(case, None, work_root=tmp_path)
    store = stepper.init_run()
    for _ in range(3):
        stepper.run_next_step(log_fn=lambda _m: None)
    drops = store.read_drops()
    assert drops, "this case has stage 2 drops; without them the test says nothing"
    for drop in drops:
        contracts.validate("c3-drop", drop)
        assert [a["line"] for a in drop["accesses"]] == drop["lines"]
        assert all(a["file"] for a in drop["accesses"])


def test_an_access_marks_a_line_only_in_its_own_file(run, tk_root) -> None:
    import tkinter as tk

    from irqrace.ui.desktop import IrqRaceWinApp

    target, store = run
    win = tk.Toplevel(tk_root)
    try:
        app = IrqRaceWinApp(win)
        app.open_run_in_pipeline(target, store.root)
        cid = _rww(store)["id"]
        app.tree.selection_set(cid)
        win.update()

        def marked(name: str) -> list[int]:
            app.selected_source_view_var.set(str(next(p for p in app.source_files_list if p.name == name)))
            app._on_candidate_selected()
            lines = app.txt_source.get("1.0", tk.END).splitlines()
            start = next(i for i, ln in enumerate(lines) if ln.startswith("ARQUIVO VISUALIZADO"))
            return [int(ln.split()[0]) for ln in lines[start + 2:] if "[" in ln.split("|")[0]]

        assert marked("task.c") == [8, 11]
        assert marked("isr.c") == [5]
        assert app.tree.set(cid, "lines").startswith("task.c:8")
    finally:
        win.destroy()


# -- applying a patch ------------------------------------------------------


ISR_DIFF = """\
--- a/isr.c
+++ b/isr.c
@@ -4,3 +4,3 @@
 void timer_isr(void) {
-  pending++;
+  guarded_inc();
 }
"""


def test_a_diff_for_another_file_is_refused() -> None:
    """It used to apply, and overwrote whatever sat at those line numbers."""
    assert apply_unified_diff(TASK, ISR_DIFF) is None
    assert "guarded_inc();" in apply_unified_diff(ISR, ISR_DIFF)


def test_a_hunk_goes_where_its_lines_are_not_where_its_number_says() -> None:
    shifted = "/* one more line */\n" + ISR
    patched = apply_unified_diff(shifted, ISR_DIFF)
    assert patched == shifted.replace("pending++;", "guarded_inc();")


def test_tabs_rewritten_as_spaces_are_the_same_code() -> None:
    tabbed = ISR.replace("  pending++;", "\tpending++;")
    assert "guarded_inc();" in apply_unified_diff(tabbed, ISR_DIFF)


def test_a_stale_diff_is_refused() -> None:
    assert apply_unified_diff(ISR.replace("pending++", "pending += 2"), ISR_DIFF) is None


def test_lines_present_but_not_together_are_refused() -> None:
    apart = ISR.replace("  pending++;\n", "  log();\n  pending++;\n")
    assert apply_unified_diff(apart, ISR_DIFF) is None


def test_an_insertion_only_hunk_goes_after_the_line_it_names() -> None:
    diff = "--- a/isr.c\n+++ b/isr.c\n@@ -5,0 +6 @@\n+  extra();\n"
    assert apply_unified_diff(ISR, diff).splitlines()[5] == "  extra();"


def test_the_patch_says_which_file() -> None:
    assert diff_file(ISR_DIFF) == "isr.c"
    assert diff_file("--- a/data/x.c\n+++ b/data/x.c\t2026-01-01\n") == "data/x.c"
    record = {"accesses": [{"source": {"file": "task.c"}}]}
    assert patch_file({"file": "isr.c", "diff": "--- a/z.c\n+++ b/z.c\n"}, record) == "isr.c"
    assert patch_file({"file": "", "diff": ISR_DIFF}, record) == "isr.c"
    assert patch_file({"diff": "no headers"}, record) == "task.c"


def test_paths_are_compared_whole() -> None:
    assert same_source("/repo/src/a/util.c", "a/util.c")
    assert not same_source("/repo/src/b/util.c", "a/util.c")
    assert not same_source("/repo/src/myutil.c", "util.c")


def test_two_files_with_one_name_are_told_apart_on_screen() -> None:
    accesses = [{"source": {"file": f, "line": n}} for f, n in (("a/u.c", 1), ("b/u.c", 2), ("a/u.c", 3))]
    assert access_locations(accesses) == "a/u.c:1, b/u.c:2, a/u.c:3"
    assert access_locations(accesses[:1]) == "(1)"


@pytest.mark.skipif(not any(map(shutil.which, ("clang-14", "clang", "gcc"))), reason="no C compiler here")
def test_the_compile_check_uses_the_file_the_patch_names(tmp_path: Path) -> None:
    (tmp_path / "task.c").write_text(TASK, encoding="utf-8")
    (tmp_path / "isr.c").write_text(ISR.replace("pending++;", "pending++; /* x */"), encoding="utf-8")
    record = {
        "subject": {"name": "two_files"},
        "accesses": [{"source": {"file": "task.c"}}, {"source": {"file": "isr.c"}}],
        "variable": {"decl": {"file": "isr.c"}},
    }

    def patch(new_line: str) -> Patch:
        return Patch(
            reasoning="r",
            witness=Witness(firing_flow="f", preemption_point="p", access_order=["A1", "B", "A2"], divergence="d"),
            file="isr.c",
            strategy=Strategy.mask_interval,
            masked_irqs=[1],
            covers_from_line=1,
            covers_to_line=2,
            latency_note="n",
            diff=ISR_DIFF.replace("-  pending++;", "-  pending++; /* x */").replace("+  guarded_inc();", new_line),
        )

    check = make_compile_checker({}, suite=tmp_path)
    assert check(patch("+  pending = pending + 1;"), record) is True
    assert check(patch("+  pending = = 1;"), record) is False


# -- ground truth ----------------------------------------------------------


def test_the_ground_truth_compares_files_when_it_has_them() -> None:
    record = {
        "id": "c1", "class": "atomicity-triple", "variable": {"name": "pending"},
        "accesses": [
            {"role": "A1", "kind": "read", "source": {"file": "task.c", "line": 8}},
            {"role": "B", "kind": "write", "source": {"file": "isr.c", "line": 5}},
            {"role": "A2", "kind": "write", "source": {"file": "task.c", "line": 11}},
        ],
    }

    def annotation(*files) -> Annotation:
        accesses = tuple(
            Access(kind=k, line=n, raw="", file=f)
            for k, n, f in zip(("read", "write", "write"), (8, 5, 11), files)
        )
        return Annotation(case="c", kind="bug", index=1, variable="pending", accesses=accesses,
                          annotation_line=1, raw="")

    def detected(*files) -> bool:
        return match_subject([annotation(*files)], [record], subject="c").bugs_detected == 1

    assert detected(None, None, None), "a suite without files matches by line, as before"
    assert detected("task.c", "isr.c", "task.c")
    assert not detected("task.c", "other.c", "task.c")
