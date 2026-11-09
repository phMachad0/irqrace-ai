"""The desktop app's two modes: the C1 wizard (generic) and the Racebench runner."""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from irqrace.config import Config
from irqrace.ui.benchmark_screen import STATIC_LAST_STEP, headline, run_batch, run_case, summarize
from irqrace.ui.c1_wizard import (
    WizardError,
    WizardState,
    save_c1,
    scan_functions,
    suggest_flows,
    suggest_primitives,
    validate_state,
)
from irqrace.ui.desktop import REPO_ROOT, IrqRaceWinApp, PipelineStepper

CASE = REPO_ROOT / "bench" / "configs" / "svp_simple_001_001.yaml"




def _project(tmp_path: Path) -> list[Path]:
    (tmp_path / "inc").mkdir()
    hdr = tmp_path / "inc" / "hw.h"
    hdr.write_text("void disable_isr(int); void enable_isr(int);\n", encoding="utf-8")
    main_c = tmp_path / "app.c"
    main_c.write_text(
        '#include "hw.h"\n'
        "int shared;\n"
        "/* not a definition: void fake_isr(void) { } */\n"
        "void timer_isr(void) { shared = 0; }\n"
        "void uart_irq_handler(void) { shared++; }\n"
        "int main(void) {\n"
        "  disable_isr(1); shared = 1; enable_isr(1);\n"
        "  if (shared) { return shared; }\n"
        "  return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    return [main_c, hdr]


def test_scan_and_suggestions_come_from_the_code(tmp_path: Path) -> None:
    defined, external = scan_functions(_project(tmp_path))
    assert defined == ["main", "timer_isr", "uart_irq_handler"]  # comment ignored, `if` not a function
    assert {"disable_isr", "enable_isr"} <= set(external)

    flows = suggest_flows(defined)
    assert flows[0] == {"id": "main", "kind": "task", "entry": "main", "irq": None, "priority": 0}
    assert {f["entry"] for f in flows if f["kind"] == "isr"} == {"timer_isr", "uart_irq_handler"}

    prims = {p["function"]: p for p in suggest_primitives(external)}
    assert prims["disable_isr"]["effect"] == "disable"
    assert prims["enable_isr"]["effect"] == "enable"
    assert suggest_primitives(["cli"])[0]["irq_arg"] is None  # bare cli(): affects all


def test_wizard_writes_a_file_the_pipeline_accepts(tmp_path: Path) -> None:
    sources = _project(tmp_path)
    defined, external = scan_functions(sources)
    st = WizardState(name="demo", sources=sources, flows=suggest_flows(defined),
                     primitives=suggest_primitives(external))
    target = tmp_path / "cfg" / "demo.c1.yaml"
    save_c1(st, target)

    cfg = Config.load(target)
    assert cfg.name == "demo"
    assert [p.name for p in cfg.source_files()] == ["app.c"]
    assert str((tmp_path / "inc").resolve()) in cfg.build["include_dirs"]
    assert raw_root(target) == "..", "source_root is written relative to the file"
    # Recall-safe defaults unless the user changed them
    assert cfg.semantics["isr_arrival"] == "unbounded"
    assert cfg.data["externals"]["default"] == "may-read-write-reachable"
    assert cfg.data["masking"]["initial_state"] == "all-enabled"
    # And the desktop stepper takes it as is
    PipelineStepper(target, None, work_root=tmp_path / "runs")


def raw_root(path: Path) -> str:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["subject"]["source_root"]


def test_wizard_rejects_what_the_contract_rejects(tmp_path: Path) -> None:
    sources = _project(tmp_path)
    with pytest.raises(WizardError):
        WizardState(name="x", sources=[sources[1]]).to_c1()  # only a header
    with pytest.raises(WizardError):
        WizardState(name="", sources=sources).to_c1()
    isr_without_irq = WizardState(name="x", sources=sources, flows=[
        {"id": "i", "kind": "isr", "entry": "timer_isr", "irq": None, "priority": 1}])
    with pytest.raises(Exception, match="irq"):
        validate_state(isr_without_irq)


def test_wizard_round_trips_a_racebench_config(tmp_path: Path) -> None:
    raw = yaml.safe_load(CASE.read_text(encoding="utf-8"))
    st = WizardState.from_c1(raw, CASE)
    assert {p.name for p in st.sources} >= {"svp_simple_001_001.c", "common.c", "common.h"}
    target = tmp_path / "again.yaml"
    again = save_c1(st, target)
    orig = Config.from_dict(raw, path=CASE)
    assert again.flows == orig.flows
    assert again.masking_primitives == orig.masking_primitives
    assert again.semantics == orig.semantics
    assert again.data["externals"] == orig.data["externals"]
    assert again.data["ground_truth"] == orig.data["ground_truth"]  # carried over unchanged
    assert {p.resolve() for p in again.source_files()} == {
        p.resolve() for p in orig.source_files()
    } | {(Path(orig.subject["source_root"]) / "common.c").resolve()}


def test_benchmark_case_runs_and_is_scored(tmp_path: Path) -> None:
    from irqrace.run_evaluation import case_ground_truth

    if case_ground_truth("svp_simple_001_001") is None:
        pytest.skip("Racebench is not on this machine")
    logs: list[str] = []
    res = run_case(
        CASE,
        make_stepper=lambda y: PipelineStepper(y, None, work_root=tmp_path),
        last_step="context",
        log_fn=logs.append,
        should_stop=lambda: False,
    )
    assert res["status"] == "ok", res["error"]
    assert res["steps"] == ["build", "stage1", "solver", "context"]
    h = headline(res)
    assert h["stage"] == "context" and h["recall_gate"] is True
    assert h["bugs_detected"] == h["bug_points"] == 2
    s = summarize([res])
    assert s["recall_gate_cases"] == s["evaluated_cases"] == 1


def test_without_the_api_triage_reuses_nothing(tmp_path: Path) -> None:
    """With the API off there is no verdict, not an earlier run's verdict."""
    stepper = PipelineStepper(CASE, None, work_root=tmp_path)
    stepper.init_run()
    while stepper.run_next_step(log_fn=lambda _m: None)[0] != "repair":
        pass
    stages = {s["name"]: s["status"] for s in stepper.store.read_manifest()["stages"]}
    assert stages["triage"] == stages["repair"] == "skipped"
    assert not (stepper.store.root / "llm" / "triage.jsonl").exists()


def _context_stepper(tmp_path: Path, monkeypatch, client_cls, **kwargs) -> PipelineStepper:
    from types import SimpleNamespace as NS

    import irqrace.ui.desktop as desktop

    monkeypatch.setattr(desktop, "build_backend_from_config", lambda *a, **k: NS(spec="fake:m"))
    monkeypatch.setattr(desktop, "TriageClient", client_cls)
    stepper = PipelineStepper(CASE, None, work_root=tmp_path, use_live_llm=True, **kwargs)
    stepper.init_run()
    for _ in range(4):
        stepper.run_next_step(log_fn=lambda _m: None)
    return stepper


def test_the_desktop_gives_the_llm_the_real_sources(tmp_path: Path, monkeypatch) -> None:
    """The source root was one level too deep, so C4 could only repeat the record."""
    from irqrace.llm.resolver import SourceBackedResolver

    seen = []

    class Spy:
        def __init__(self, *_a, **_k):
            pass

        def triage(self, _rec, *, resolver, run_dir):
            seen.append(type(resolver))
            raise RuntimeError("enough")

    with pytest.raises(Exception, match="falharam na API"):
        _context_stepper(tmp_path, monkeypatch, Spy).run_next_step(log_fn=lambda _m: None)
    assert seen and set(seen) == {SourceBackedResolver}


def test_a_malformed_answer_costs_one_candidate_not_the_case(tmp_path: Path, monkeypatch) -> None:
    class Bad:
        def __init__(self, *_a, **_k):
            pass

        def triage(self, *_a, **_k):
            raise ValueError("not what the schema wanted")

    stepper = _context_stepper(tmp_path, monkeypatch, Bad)
    with pytest.raises(Exception, match="falharam na API"):  # all failed: the stage says so
        stepper.run_next_step(log_fn=lambda _m: None)
    lines = (stepper.store.root / "llm" / "triage.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines and all(json.loads(x)["not_triaged"] for x in lines)


def test_triage_outcome_counts_the_ground_truth_by_bucket(tmp_path: Path) -> None:
    from irqrace.run_evaluation import case_ground_truth, triage_outcome

    if case_ground_truth(CASE.stem) is None:
        pytest.skip("Racebench is not on this machine")
    stepper = PipelineStepper(CASE, None, work_root=tmp_path)
    store = stepper.init_run()
    for _ in range(4):
        stepper.run_next_step(log_fn=lambda _m: None)
    assert triage_outcome(store) is None, "no triage yet"

    records = store.read_contexts()
    (store.root / "llm" / "triage.jsonl").write_text(
        "".join(json.dumps({"candidate_id": r["id"], "bucket": "likely_benign"}) + "\n" for r in records),
        encoding="utf-8",
    )
    turns = store.root / "llm" / records[0]["id"] / "turns.jsonl"
    turns.parent.mkdir(parents=True)
    turns.write_text(json.dumps({"requests": [{"kind": "isr_body"}]}) + "\n", encoding="utf-8")

    out = triage_outcome(store)
    assert out["bugs"] == out["bugs_likely_benign"] == 2
    assert out["c4_requests"] == 1


def test_a_failing_case_is_a_row_not_a_crash(tmp_path: Path) -> None:
    def boom(_y):
        raise RuntimeError("toolchain missing")

    res = run_case(CASE, make_stepper=boom, last_step="context", log_fn=lambda _m: None,
                   should_stop=lambda: False)
    assert res["status"] == "failed" and "toolchain missing" in res["error"]
    assert headline(res) is None
    assert summarize([res])["failed"] == 1


FULL_STEPS = ["build", "stage1", "solver", "context", "triage", "repair"]
WAIT_S = 5.0


class FakeStepper:
    """The steps of a PipelineStepper, with *hooks* run inside the named step."""

    def __init__(self, yaml_path: Path, root: Path, hooks: dict) -> None:
        self.case = yaml_path.stem
        self.hooks = hooks
        self.done: list[str] = []
        self.store = SimpleNamespace(root=root / self.case)
        self.store.root.mkdir(parents=True)

    def init_run(self):
        return self.store

    def run_next_step(self, log_fn=print):
        key = FULL_STEPS[len(self.done)]
        self.hooks.get((self.case, key), self.hooks.get(key, lambda: None))()
        self.done.append(key)
        log_fn(f"{key} ok\n")
        return key, ""


@pytest.fixture
def batch(tmp_path: Path, monkeypatch):
    """Run a fake batch; ``evaluate_run`` reports only that it was called."""
    from irqrace.ui import benchmark_screen

    monkeypatch.setattr(benchmark_screen, "evaluate_run", lambda _store: None)
    monkeypatch.setattr(benchmark_screen, "triage_outcome", lambda _store: None)
    steppers: dict[str, FakeStepper] = {}

    def _run(names, hooks=None, *, last_step="repair", llm_workers=2, should_stop=lambda: False):
        def make(yaml_path: Path) -> FakeStepper:
            steppers[yaml_path.stem] = FakeStepper(yaml_path, tmp_path, hooks or {})
            return steppers[yaml_path.stem]

        events: list[tuple[str, object]] = []
        results = run_batch(
            [Path(f"{n}.yaml") for n in names], make_stepper=make, last_step=last_step,
            llm_workers=llm_workers, emit=lambda k, p: events.append((k, p)), should_stop=should_stop,
        )
        return results, events, steppers

    return _run


def test_llm_lane_does_not_wait_for_the_static_lane(batch) -> None:
    second_case_static = threading.Event()

    def a_triage() -> None:  # only the next case's static steps can release this
        assert second_case_static.wait(WAIT_S), "the LLM steps waited for the static lane"

    results, _, _ = batch(["a", "b"], {("a", "triage"): a_triage, ("b", "build"): second_case_static.set})
    assert [r["status"] for r in results] == ["ok", "ok"], results
    assert results[0]["steps"] == FULL_STEPS


def test_candidate_progress_reaches_the_row(batch) -> None:
    box: dict = {}

    def report() -> None:
        cb = box["steppers"]["a"].event_cb
        cb("api_request_start", {"stage": "Triagem"})  # not a row update
        cb("api_candidate_progress", {"stage": "Triagem", "current": 2, "total": 6})

    def make_hooks():
        return {"triage": report}

    original = batch

    def run():
        # The steppers dict is the fixture's; capture it through a hook-free first look.
        results, events, steppers = original(["z"], {})
        box["steppers"] = steppers
        return original(["a"], make_hooks())

    _, events, _ = run()
    assert [p for k, p in events if k == "row_progress"] == [("a", "🤖 Triagem 2/6")]


def test_llm_steps_of_two_cases_overlap(batch) -> None:
    both_in_llm = threading.Barrier(2, timeout=WAIT_S)
    results, _, _ = batch(["a", "b"], {"triage": both_in_llm.wait})
    assert [r["status"] for r in results] == ["ok", "ok"], results


def test_results_are_ordered_even_when_they_finish_out_of_order(batch) -> None:
    b_done = threading.Event()

    def a_repair() -> None:
        assert b_done.wait(WAIT_S)

    results, events, _ = batch(["a", "b"], {("a", "repair"): a_repair, ("b", "repair"): b_done.set})
    finished = [p["case"] for k, p in events if k == "row_done"]
    assert finished == ["b", "a"]
    assert [r["case"] for r in results] == ["a", "b"]


def test_a_failing_llm_step_keeps_the_static_figures(batch, monkeypatch) -> None:
    from irqrace.ui import benchmark_screen

    row = SimpleNamespace(recall_gate=True)
    monkeypatch.setattr(benchmark_screen, "asdict", lambda _r: {"stage": "context"})
    monkeypatch.setattr(benchmark_screen, "evaluate_run", lambda _store: [row])

    def boom() -> None:
        raise RuntimeError("endpoint down")

    results, events, _ = batch(["a"], {"triage": boom})
    assert results[0]["status"] == "failed" and "endpoint down" in results[0]["error"]
    assert results[0]["evals"] == [{"stage": "context", "recall_gate": True}]
    static = next(p for k, p in events if k == "row_static")
    assert static["status"] == "ok" and static["steps"] == FULL_STEPS[:4], "a snapshot, not the live row"


def test_stop_leaves_queued_cases_out_of_the_llm(batch) -> None:
    stop = threading.Event()
    results, _, steppers = batch(["a"], {"context": stop.set}, should_stop=stop.is_set)
    # Stopping during the case's last static step still finishes that step
    # (it reaches the lane boundary), and the LLM lane then does nothing.
    assert results[0]["status"] == "stopped"
    assert steppers["a"].done == FULL_STEPS[:4]


def test_one_llm_worker_still_runs_every_case(batch) -> None:
    results, _, _ = batch(["a", "b", "c"], llm_workers=1)
    assert [r["steps"] for r in results] == [FULL_STEPS] * 3


def test_static_depth_never_reaches_the_llm(batch) -> None:
    results, events, _ = batch(["a"], last_step=STATIC_LAST_STEP)
    assert results[0]["status"] == "ok" and results[0]["steps"] == FULL_STEPS[:4]
    assert not {k for k, _ in events} & {"row_static", "row_llm"}


def test_candidates_without_a_verdict_reach_the_summary(batch, tmp_path: Path) -> None:
    def write_triage() -> None:
        llm = tmp_path / "a" / "llm"
        llm.mkdir()
        lines = [{"candidate_id": "c1", "not_triaged": "rate limited"}, {"candidate_id": "c2", "not_triaged": None}]
        (llm / "triage.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")

    results, _, _ = batch(["a"], {"triage": write_triage})
    assert results[0]["not_triaged"] == 1
    assert summarize(results)["not_triaged"] == 1


def test_llm_totals_do_not_replace_the_static_ones() -> None:
    head = {"stage": "context", "bug_points": 2, "bugs_detected": 2, "traps": 3, "traps_reported": 1,
            "candidates": 5, "recall_gate": True}
    s = summarize([{"status": "ok", "evals": [head], "llm": {"bugs": 2, "traps": 1, "bugs_likely_real": 2}}])
    assert s["traps"] == 3 and s["llm_traps"] == 1 and s["llm_bugs_likely_real"] == 2


def test_manifest_write_survives_a_reader_holding_the_file(tmp_path: Path, monkeypatch) -> None:
    store = PipelineStepper(CASE, None, work_root=tmp_path).init_run()
    real, failures = os.replace, [PermissionError(13, "in use"), PermissionError(13, "in use")]

    def flaky(src, dst):
        if failures:
            raise failures.pop()
        real(src, dst)

    monkeypatch.setattr("irqrace.runstore.os.replace", flaky)
    store.set_stage("build", "running")
    assert not failures
    assert next(s for s in store.read_manifest()["stages"] if s["name"] == "build")["status"] == "running"


def test_a_case_can_be_opened_before_its_first_step(batch) -> None:
    results, events, _ = batch(["a"])
    kinds = [k for k, _ in events]
    assert kinds.index("row_run") < kinds.index("log", kinds.index("row_run"))  # before any step logs
    assert next(p for k, p in events if k == "row_run")["run_dir"] == results[0]["run_dir"]


def test_a_failed_conversation_leaves_what_was_said(tmp_path: Path) -> None:
    from irqrace.llm.client import TriageClient
    from irqrace.llm.prompts import BY_NAME
    from test_llm_client import RECORD, FakeBackend, _feas

    # The second question fails: nothing is scripted for it.
    with pytest.raises(Exception):
        TriageClient(BY_NAME["+decomposition"], backend=FakeBackend(answers=[_feas()])).triage(
            RECORD, run_dir=tmp_path)
    turns = (tmp_path / "llm" / RECORD["id"] / "turns.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(t)["stage"] for t in turns][:2] == ["feasibility", "feasibility"]


def _verdict(cid: str, **over) -> dict:
    return {"candidate_id": cid, "bucket": "likely_real", "not_triaged": None,
            "feasibility": {"verdict": "feasible", "confidence": 0.9, "reasoning": "r"}, **over}


def test_a_running_case_is_watched_read_only_and_keeps_the_selection(tk_root, tmp_path: Path) -> None:
    stepper = PipelineStepper(CASE, None, work_root=tmp_path)
    store = stepper.init_run()
    for _ in range(4):
        stepper.run_next_step(log_fn=lambda _m: None)

    win = tk.Toplevel(tk_root)
    running = [True]
    try:
        app = IrqRaceWinApp(win)
        app.open_run_in_pipeline(CASE, store.root, origin="bench", is_live=lambda: running[0])
        token = app._live_token
        assert app.stepper is None, "a stepper on a run someone else is writing is a second writer"
        for button in (app.btn_reset, app.btn_step, app.btn_resume, app.btn_stop):
            assert str(button["state"]) == "disabled"

        ids = list(app.tree.get_children())
        assert len(ids) > 1
        app.tree.selection_set(ids[1])
        win.update()

        # A candidate in flight: its conversation exists, its verdict does not.
        turns = store.root / "llm" / ids[1] / "turns.jsonl"
        turns.parent.mkdir(parents=True, exist_ok=True)
        turns.write_text(json.dumps({"role": "user", "stage": "feasibility", "content": "pergunta"}) + "\n",
                         encoding="utf-8")
        app._live_tick(token)
        assert app.tree.selection() == (ids[1],)
        assert app.tree.set(ids[1], "feas") == "⏳ na LLM"
        assert "pergunta" in app.txt_turns.get("1.0", tk.END)

        triage = store.root / "llm" / "triage.jsonl"
        triage.write_text('{"candidate_id": "half a li', encoding="utf-8")  # caught mid-write
        app._live_tick(token)
        assert app.tree.set(ids[1], "feas") == "⏳ na LLM"

        triage.write_text(json.dumps(_verdict(ids[0])) + "\n", encoding="utf-8")
        app._live_tick(token)
        assert app.tree.selection() == (ids[1],), "a redraw moved the reader to another candidate"
        assert app.tree.set(ids[0], "bucket") == "likely_real"

        app.live_view_log(f"  [{CASE.stem}] linha do caso")
        app.live_view_log("  [outro_caso] linha de outro caso")
        log = app.log_text.get("1.0", tk.END)
        assert "linha do caso" in log and "outro caso" not in log

        running[0] = False
        app._live_tick(token)
        assert app._live_run is None and app.stepper is not None
        assert str(app.btn_resume["state"]) == "normal"
    finally:
        running[0] = False
        win.destroy()


def test_screen_navigation(tk_root) -> None:
    win = tk.Toplevel(tk_root)
    try:
        app = IrqRaceWinApp(win)
        assert app.current_screen == "home"
        app.show_screen("bench")
        assert app.current_screen == "bench"
        assert len(app.bench_screen.tree.get_children()) == len(list(app.BENCH_CONFIGS.glob("*.yaml")))
        screen = app.bench_screen
        assert screen.prompt_var.get() == "+racebench+c4" and "⚠" not in screen.prompt_help_var.get()
        screen.prompt_var.set("+self-validation")
        screen._prompt_changed()
        assert "leitores mortos" in screen.prompt_help_var.get()
        assert app.stepper_factory(live_llm=False, prompt="+c4")(CASE).llm_prompt == "+c4"
        app.open_llm_settings()
        assert app.current_screen == "llm"
        app._leave_llm_settings()
        assert app.current_screen == "bench"
        app.open_generic_mode()
        assert app.current_screen == "generic"
        assert app.top_notebook.select() == str(app.tab_setup)
    finally:
        win.destroy()
