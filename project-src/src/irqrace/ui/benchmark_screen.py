"""The Racebench mode of the desktop app: run the benchmark cases unattended.

Every case in ``bench/configs`` is a ready C1 file, so nothing is configured
here: the user picks cases and how far the pipeline goes, and each case runs
through the same :class:`~irqrace.ui.desktop.PipelineStepper` the generic mode
uses, then is scored against the suite's annotated ground truth by
:func:`irqrace.run_evaluation.evaluate_run`. A failing case is recorded and the
batch continues; a recall figure is shown only for stages that actually ran.

The static depth (steps 1-4) is the default: it is what the recall gate is
defined on, and it costs no API calls. The full depth adds LLM triage and
repair, which rank and explain but never remove a candidate.

A batch has two lanes (:func:`run_batch`). The static steps run one case at a
time, which keeps their per-stage timings meaningful; a case that finishes them
goes to a pool of threads for its LLM steps, and the static lane moves on to
the next case without waiting. Parallelism is per case: inside a case the
candidates are still triaged in order.
"""

from __future__ import annotations

import datetime
import json
import queue
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Callable

from irqrace.evaluation import RACEBENCH_SIMPLE_BUG_POINTS, RACEBENCH_SIMPLE_TRAPS
from irqrace.llm.annotations import locate_suite
from irqrace.llm.prompts import BY_NAME, EXPERIMENTAL, ROW_HELP
from irqrace.run_evaluation import evaluate_run, triage_outcome

#: How far a benchmark run goes, as the key of the last pipeline step.
DEPTHS = {
    "static": ("context", "Estático — etapas 1 a 4 (build, stage 1, stages 2–3, contexto)"),
    "full": ("repair", "Completo — etapas 1 a 6 (inclui triagem e reparo pela LLM)"),
}

#: The last step of the static lane.
STATIC_LAST_STEP = DEPTHS["static"][0]

#: A case's status while it waits for a free LLM thread.
LLM_QUEUED = "🤖 fila LLM"

#: The suite's ground truth counts the interleaving, and most of its readers are
#: dead locals: without the benchmark semantics they are judged ``benign``.
DEFAULT_PROMPT = "+racebench+c4"

#: Totals of :func:`irqrace.run_evaluation.triage_outcome` kept in the batch summary.
LLM_TOTALS = ("bugs", "bugs_likely_real", "bugs_uncertain", "bugs_likely_benign", "bugs_likely_infeasible",
              "traps", "traps_likely_real", "c4_requests")

#: Cases in their LLM steps at once. They share the endpoint's tokens-per-minute
#: limit, so this is a choice on screen rather than a constant of the batch.
DEFAULT_LLM_WORKERS = 4
MAX_LLM_WORKERS = 16


def list_cases(configs_dir: Path) -> list[Path]:
    return sorted(configs_dir.glob("*.yaml"))


def start_case(
    yaml_path: Path,
    *,
    make_stepper: Callable[[Path], Any],
    on_stepper: Callable[[Any], None] = lambda _s: None,
) -> tuple[dict[str, Any], Any]:
    """The result row for one case and its stepper, ``None`` if it could not start."""
    t0 = time.perf_counter()
    out: dict[str, Any] = {"case": yaml_path.stem, "config": str(yaml_path), "status": "failed",
                           "run_dir": None, "error": None, "evals": None, "steps": [],
                           "not_triaged": 0, "llm": None, "wall_s": 0.0}
    stepper = None
    try:
        made = make_stepper(yaml_path)
        on_stepper(made)
        out["run_dir"] = str(made.init_run().root)
        stepper = made
    except Exception as e:  # a failing case is a row in the table, not the end of the batch
        out["error"] = f"{type(e).__name__}: {e}"
    out["wall_s"] = round(time.perf_counter() - t0, 2)
    return out, stepper


def run_steps(
    out: dict[str, Any],
    stepper: Any,
    last_step: str,
    log_fn: Callable[[str], None],
    should_stop: Callable[[], bool],
) -> bool:
    """Advance *stepper* through *last_step*, recording in *out*. Never raises.

    Returns whether it got there. Runs once per lane on the same *out*, so the
    wall time adds up and leaves out the time a case spent queued between them.
    """
    t0 = time.perf_counter()
    out["status"] = "failed"
    try:
        while True:
            if should_stop():
                out["status"] = "stopped"
                return False
            key, _ = stepper.run_next_step(log_fn=log_fn)
            out["steps"].append(key)
            if key in (last_step, "done"):
                out["status"] = "ok"
                return True
    except InterruptedError:
        out["status"] = "stopped"
    except Exception as e:  # a failing case is a row in the table, not the end of the batch
        out["error"] = f"{type(e).__name__}: {e}"
    finally:
        out["wall_s"] = round(out["wall_s"] + time.perf_counter() - t0, 2)
    return False


def evaluate_case(out: dict[str, Any], stepper: Any) -> None:
    """Score the stages that ran. Never raises.

    Runs even after a failure: a case whose LLM step failed still has its static
    stages, and the recall gate is defined on those.
    """
    try:
        rows = evaluate_run(stepper.store)
        out["evals"] = [asdict(r) | {"recall_gate": r.recall_gate} for r in rows] if rows is not None else None
        triage = stepper.store.root / "llm" / "triage.jsonl"
        if triage.exists():
            lines = triage.read_text(encoding="utf-8").splitlines()
            out["not_triaged"] = sum(bool(json.loads(ln).get("not_triaged")) for ln in lines if ln.strip())
            out["llm"] = triage_outcome(stepper.store)
    except Exception as e:
        out["error"] = out["error"] or f"{type(e).__name__}: {e}"


def run_case(
    yaml_path: Path,
    *,
    make_stepper: Callable[[Path], Any],
    last_step: str,
    log_fn: Callable[[str], None],
    should_stop: Callable[[], bool],
    on_stepper: Callable[[Any], None] = lambda _s: None,
) -> dict[str, Any]:
    """Run one case up to *last_step* and evaluate it. Never raises."""
    out, stepper = start_case(yaml_path, make_stepper=make_stepper, on_stepper=on_stepper)
    if stepper is not None:
        run_steps(out, stepper, last_step, log_fn, should_stop)
        evaluate_case(out, stepper)
    return out


def run_batch(
    cases: list[Path],
    *,
    make_stepper: Callable[[Path], Any],
    last_step: str,
    llm_workers: int,
    emit: Callable[[str, Any], None],
    should_stop: Callable[[], bool],
    on_stepper: Callable[[Any], None] = lambda _s: None,
) -> list[dict[str, Any]]:
    """Run *cases* in two lanes and return their results, ordered by case.

    The calling thread runs the static steps of one case at a time; each case
    that clears them is handed to a pool of *llm_workers* threads, so its LLM
    steps start at once, alongside the static steps of the cases after it. A
    case is only ever in one lane, so nothing it owns is touched by two threads.

    *emit* receives ``(kind, payload)`` progress events, from any thread.
    """
    results: list[dict[str, Any]] = []

    def finish(res: dict[str, Any]) -> None:
        results.append(res)
        emit("row_done", res)

    def llm_lane(res: dict[str, Any], stepper: Any, log_fn: Callable[[str], None]) -> None:
        emit("row_llm", res["case"])
        run_steps(res, stepper, last_step, log_fn, should_stop)
        evaluate_case(res, stepper)
        finish(res)

    def case_log(case: str) -> Callable[[str], None]:
        return lambda m: emit("log", f"  [{case}] {m.rstrip()}")

    def case_events(case: str) -> Callable[[str, dict[str, Any]], None]:
        def on_event(kind: str, data: dict[str, Any]) -> None:
            if kind == "api_candidate_progress":
                emit("row_progress", (case, f"🤖 {data['stage']} {data['current']}/{data['total']}"))

        return on_event

    with ThreadPoolExecutor(max_workers=max(llm_workers, 1), thread_name_prefix="irqrace-llm") as pool:
        for i, yaml_path in enumerate(cases, start=1):
            if should_stop():
                break
            emit("row_running", yaml_path.stem)
            emit("log", f"\n▶ [{i}/{len(cases)}] {yaml_path.stem}")
            log_fn = case_log(yaml_path.stem)
            res, stepper = start_case(yaml_path, make_stepper=make_stepper, on_stepper=on_stepper)
            if stepper is None:
                finish(res)
                continue
            stepper.event_cb = case_events(yaml_path.stem)
            emit("row_run", dict(res))  # the run exists from here on, so it can be watched
            reached = run_steps(res, stepper, STATIC_LAST_STEP, log_fn, should_stop)
            evaluate_case(res, stepper)
            if reached and last_step != STATIC_LAST_STEP:
                emit("row_static", dict(res))  # a copy: the pool writes to *res* from here on
                pool.submit(llm_lane, res, stepper, log_fn)
            else:
                finish(res)
    return sorted(results, key=lambda r: r["case"])


def headline(result: dict[str, Any]) -> dict[str, Any] | None:
    """The last static stage's evaluation: the set that reaches the LLM."""
    evals = [e for e in (result.get("evals") or []) if e["stage"] != "triage"]
    return evals[-1] if evals else None


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    heads = [h for h in (headline(r) for r in results) if h]
    return {
        "cases": len(results),
        "ok": sum(r["status"] == "ok" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "stopped": sum(r["status"] == "stopped" for r in results),
        "bug_points": sum(h["bug_points"] for h in heads),
        "bugs_detected": sum(h["bugs_detected"] for h in heads),
        "traps": sum(h["traps"] for h in heads),
        "traps_reported": sum(h["traps_reported"] for h in heads),
        "candidates": sum(h["candidates"] for h in heads),
        "recall_gate_cases": sum(bool(h["recall_gate"]) for h in heads),
        "evaluated_cases": len(heads),
        "not_triaged": sum(r.get("not_triaged", 0) for r in results),
        **{f"llm_{key}": sum((r.get("llm") or {}).get(key, 0) for r in results) for key in LLM_TOTALS},
    }


class BenchmarkScreen(ttk.Frame):
    """Pick Racebench cases, run them, read recall and traps per case."""

    COLS = (
        ("case", "Caso", 150), ("status", "Status", 120), ("s1", "Stage 1", 65), ("s2", "Stage 2", 65),
        ("ctx", "Contexto", 70), ("bugs", "Bugs detectados", 105), ("traps", "Armadilhas", 85),
        ("gate", "Recall", 70), ("llm", "LLM: reais", 80), ("time", "Tempo (s)", 70),
    )

    def __init__(self, parent: tk.Misc, app: Any) -> None:
        super().__init__(parent, padding=6)
        self.app = app
        self.configs_dir: Path = app.BENCH_CONFIGS
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.results: dict[str, dict[str, Any]] = {}
        #: Cases of the current batch that have a run, finished or not.
        self.started: dict[str, dict[str, Any]] = {}
        self.running = False
        self.stop_requested = False
        self.steppers: list[Any] = []
        self.batch_ids: list[str] = []
        self.batch_depth = "static"
        self.depth_var = tk.StringVar(value="static")
        self.llm_workers_var = tk.IntVar(value=DEFAULT_LLM_WORKERS)
        self.prompt_var = tk.StringVar(value=DEFAULT_PROMPT)
        self.prompt_help_var = tk.StringVar()
        self.summary_var = tk.StringVar(value="Selecione os casos e clique em Executar.")
        self.progress_var = tk.DoubleVar(value=0.0)
        self._build()
        self.after(100, self._poll)

    # -- layout ----------------------------------------------------------

    def _build(self) -> None:
        nav = ttk.Frame(self)
        nav.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(nav, text="⌂ Início", command=lambda: self.app.show_screen("home")).pack(side=tk.LEFT)
        ttk.Label(nav, text="Benchmarks Racebench — execução automatizada",
                  font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=10)
        suite = locate_suite()
        ttk.Label(nav, foreground="gray",
                  text=f"Suíte: {suite}" if suite else "Suíte Racebench não encontrada").pack(side=tk.RIGHT)

        opts = ttk.LabelFrame(self, text=" Profundidade ", padding=6)
        opts.pack(fill=tk.X)
        for key, (_, label) in DEPTHS.items():
            ttk.Radiobutton(opts, text=label, value=key, variable=self.depth_var,
                            command=self._depth_changed).pack(anchor=tk.W)
        llm_row = ttk.Frame(opts)
        llm_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(llm_row, textvariable=self.app.llm_header_summary_var, foreground="gray").pack(side=tk.LEFT)
        ttk.Button(llm_row, text="Configurar LLM...",
                   command=lambda: self.app.open_llm_settings(return_to="bench")).pack(side=tk.RIGHT)
        ttk.Spinbox(llm_row, from_=1, to=MAX_LLM_WORKERS, width=4,
                    textvariable=self.llm_workers_var).pack(side=tk.RIGHT, padx=(0, 12))
        ttk.Label(llm_row, text="Casos na LLM em paralelo:").pack(side=tk.RIGHT, padx=(0, 4))

        prompt_row = ttk.Frame(opts)
        prompt_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(prompt_row, text="Prompt:").pack(side=tk.LEFT, padx=(0, 4))
        prompt_cb = ttk.Combobox(prompt_row, textvariable=self.prompt_var, state="readonly", width=18,
                                 values=[*BY_NAME, *EXPERIMENTAL])
        prompt_cb.pack(side=tk.LEFT, padx=(0, 8))
        prompt_cb.bind("<<ComboboxSelected>>", lambda _e: self._prompt_changed())
        ttk.Label(prompt_row, textvariable=self.prompt_help_var, foreground="gray").pack(side=tk.LEFT)
        self._prompt_changed()

        ctrl = ttk.Frame(self, padding=(0, 6))
        ctrl.pack(fill=tk.X)
        ttk.Button(ctrl, text="Selecionar todos", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="Limpar seleção", command=lambda: self.tree.selection_set(())).pack(
            side=tk.LEFT, padx=4)
        self.btn_stop = ttk.Button(ctrl, text="(STOP)", command=self._stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.RIGHT)
        self.btn_run_all = ttk.Button(ctrl, text="Executar todos", command=lambda: self._run(all_cases=True))
        self.btn_run_all.pack(side=tk.RIGHT, padx=4)
        self.btn_run_sel = ttk.Button(ctrl, text="Executar selecionados", command=self._run)
        self.btn_run_sel.pack(side=tk.RIGHT)

        prog = ttk.Frame(self)
        prog.pack(fill=tk.X)
        self.progressbar = ttk.Progressbar(prog, variable=self.progress_var, maximum=1.0, length=260)
        self.progressbar.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(prog, textvariable=self.summary_var, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        top = ttk.Frame(paned)
        bottom = ttk.Frame(paned)
        paned.add(top, weight=3)
        paned.add(bottom, weight=2)

        self.tree = ttk.Treeview(top, columns=[c for c, _, _ in self.COLS], show="headings",
                                 selectmode="extended")
        for c, t, w in self.COLS:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=tk.W if c == "case" else tk.CENTER)
        sb = ttk.Scrollbar(top, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.tag_configure("ok", foreground="#1a7f37")
        self.tree.tag_configure("miss", foreground="#a33")
        self.tree.bind("<Double-1>", self._open_selected)
        for y in list_cases(self.configs_dir):
            self.tree.insert("", tk.END, iid=y.stem, values=(y.stem, "—", "", "", "", "", "", "", "", ""))

        ttk.Label(bottom, foreground="gray",
                  text="Duplo clique num caso abre o run no Pipeline para inspeção, também enquanto ele roda."
                  ).pack(anchor=tk.W)
        self.log = scrolledtext.ScrolledText(bottom, font=("Consolas", 9), height=8, state=tk.DISABLED)
        self.log.pack(fill=tk.BOTH, expand=True)

    # -- actions ---------------------------------------------------------

    def _prompt_changed(self) -> None:
        name = self.prompt_var.get()
        row = {**BY_NAME, **EXPERIMENTAL}.get(name)
        warn = "" if row and row.extra else "  ⚠ sem a semântica do Racebench: leitores mortos viram 'benign'."
        self.prompt_help_var.set(ROW_HELP.get(name, "") + warn)

    def _depth_changed(self) -> None:
        if self.depth_var.get() == "full" and not self.app.llm_ready():
            messagebox.showwarning(
                "LLM não configurada",
                "A profundidade completa chama a API da LLM em todos os casos. Configure a LLM antes "
                "de executar (botão 'Configurar LLM...').",
            )

    def _select_all(self) -> None:
        self.tree.selection_set(self.tree.get_children())

    def _append(self, msg: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def _llm_workers(self) -> int:
        try:
            return min(max(int(self.llm_workers_var.get()), 1), MAX_LLM_WORKERS)
        except (tk.TclError, ValueError):  # the field is free text while being typed in
            return DEFAULT_LLM_WORKERS

    def _run(self, all_cases: bool = False) -> None:
        if self.running:
            return
        ids = list(self.tree.get_children()) if all_cases else list(self.tree.selection())
        if not ids:
            messagebox.showinfo("Nenhum caso", "Selecione ao menos um caso (ou use 'Executar todos').")
            return
        depth = self.depth_var.get()
        if depth == "full" and not self.app.llm_ready():
            messagebox.showerror("LLM não configurada",
                                 "Configure a LLM (chave e modelo) para a profundidade completa.")
            return
        # Read every Tk variable here, on the main thread; the worker gets plain values.
        make_stepper = self.app.stepper_factory(live_llm=(depth == "full"), prompt=self.prompt_var.get())
        last_step = DEPTHS[depth][0]
        llm_workers = self._llm_workers()
        cases = [self.configs_dir / f"{cid}.yaml" for cid in ids]
        for cid in ids:
            self.tree.item(cid, values=(cid, "na fila", "", "", "", "", "", "", "", ""), tags=())
        self.results = {k: v for k, v in self.results.items() if k not in ids}
        self.running, self.stop_requested = True, False
        self.steppers = []
        self.started = {}
        self.batch_ids, self.batch_depth = ids, depth
        self._set_running(True)
        self.progress_var.set(0.0)
        self.progressbar.configure(maximum=len(cases))
        lanes = f", {llm_workers} caso(s) na LLM em paralelo" if depth == "full" else ""
        prompt = f", prompt {self.prompt_var.get()}" if depth == "full" else ""
        self._append(f"=== {len(cases)} caso(s), profundidade: {DEPTHS[depth][1]}{lanes}{prompt} ===")
        threading.Thread(target=self._worker, args=(cases, make_stepper, last_step, depth, llm_workers),
                         daemon=True).start()

    def _worker(self, cases: list[Path], make_stepper, last_step: str, depth: str, llm_workers: int) -> None:
        t0 = time.perf_counter()
        results = run_batch(
            cases, make_stepper=make_stepper, last_step=last_step, llm_workers=llm_workers,
            emit=lambda kind, payload: self.queue.put((kind, payload)),
            should_stop=lambda: self.stop_requested,
            on_stepper=self.steppers.append,
        )
        self.queue.put(("done", (results, depth, llm_workers, round(time.perf_counter() - t0, 2))))

    def _stop(self) -> None:
        self.stop_requested = True
        for stepper in list(self.steppers):
            stepper.request_stop()
        self._append("⏹ Interrupção solicitada: os casos em curso param no fim da chamada atual; "
                     "os que estão na fila não chamam a API.")

    def _set_running(self, running: bool) -> None:
        state = tk.DISABLED if running else tk.NORMAL
        self.btn_run_sel.configure(state=state)
        self.btn_run_all.configure(state=state)
        self.btn_stop.configure(state=tk.NORMAL if running else tk.DISABLED)

    def _open_selected(self, _e=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        case = sel[0]
        res = self.results.get(case) or self.started.get(case)
        if not res or not res.get("run_dir"):
            return
        if self.app.is_running_async:
            messagebox.showinfo("Pipeline em uso", "Aguarde a execução em curso na aba Pipeline terminar.")
            return
        self.app.open_run_in_pipeline(Path(res["config"]), Path(res["run_dir"]), origin="bench",
                                      is_live=lambda: self.running and case not in self.results)

    # -- results ---------------------------------------------------------

    def _fill_row(self, res: dict[str, Any], status: str | None = None) -> None:
        by_stage = {e["stage"]: e for e in (res.get("evals") or [])}
        h = headline(res)
        status = status or {"ok": "✔ ok", "failed": "✖ falhou", "stopped": "⏹ parado"}[res["status"]]
        cand = lambda s: by_stage[s]["candidates"] if s in by_stage else ""  # noqa: E731
        bugs = f"{h['bugs_detected']}/{h['bug_points']}" if h else ""
        traps = f"{h['traps_reported']}/{h['traps']}" if h else ""
        gate = ("✔" if h["recall_gate"] else "✖") if h else ("sem GT" if res["status"] == "ok" else "")
        tag = ("ok",) if h and h["recall_gate"] else (("miss",) if h or res["status"] == "failed" else ())
        llm = res.get("llm")
        reais = f"{llm.get('bugs_likely_real', 0)}/{llm['bugs']}" if llm else ""
        self.tree.item(res["case"], values=(res["case"], status, cand("stage1"), cand("stage2"), cand("context"),
                                            bugs, traps, gate, reais, res["wall_s"]), tags=tag)

    def _show_progress(self) -> None:
        """The batch so far: a long LLM step must not look like a hung one."""
        done = f"{int(self.progress_var.get())}/{len(self.batch_ids)} concluídos"
        if self.batch_depth != "full":
            self.summary_var.set(f"{done} · profundidade estática: a LLM não é chamada")
            return
        statuses = [self.tree.set(cid, "status") for cid in self.batch_ids]
        queued = statuses.count(LLM_QUEUED)
        active = sum(s.startswith("🤖") for s in statuses) - queued
        self.summary_var.set(f"{done} · {active} na LLM · {queued} na fila da LLM")

    def _finish(self, results: list[dict[str, Any]], depth: str, llm_workers: int, batch_wall_s: float) -> None:
        self.running = False
        self.steppers = []
        self._set_running(False)
        self.results.update({r["case"]: r for r in results})
        s = summarize(list(self.results.values()))
        self.summary_var.set(
            f"{s['ok']}/{s['cases']} ok · bugs {s['bugs_detected']}/{s['bug_points']} · armadilhas "
            f"{s['traps_reported']}/{s['traps']} · recall gate em {s['recall_gate_cases']}/"
            f"{s['evaluated_cases']} casos"
            + (f" · LLM: {s['llm_bugs_likely_real']}/{s['llm_bugs']} bugs como reais, {s['llm_bugs_uncertain']} incertos, "
               f"{s['llm_bugs_likely_benign']} benignos, {s['llm_bugs_likely_infeasible']} inviáveis · "
               f"{s['llm_traps_likely_real']}/{s['llm_traps']} armadilhas como reais · {s['llm_c4_requests']} pedidos C4"
               if s["llm_bugs"] else "")
            + (f" · {s['not_triaged']} sem veredicto" if s["not_triaged"] else "")
        )
        all_cases = len(self.tree.get_children())
        if s["evaluated_cases"] == all_cases:
            self._append(f"Suíte completa: referência {RACEBENCH_SIMPLE_BUG_POINTS} bug points / "
                         f"{RACEBENCH_SIMPLE_TRAPS} armadilhas.")
        out_dir = self.app.RUNS_ROOT / "benchmarks"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"racebench-{depth}-{stamp}.json"
        # llm_workers travels with the numbers: it changes how often the endpoint
        # rate-limits, and so how many candidates end up without a verdict.
        doc = {"depth": depth, "llm_workers": llm_workers if depth == "full" else None,
               "prompt": self.prompt_var.get() if depth == "full" else None,
               "batch_wall_s": batch_wall_s, "summary": summarize(results), "cases": results}
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._append(f"\nResumo salvo em {path}")

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._append(payload)
                    self.app.live_view_log(payload)
                elif kind == "row_run":
                    self.started[payload["case"]] = payload
                elif kind == "row_running":
                    self.tree.item(payload, values=(payload, "⏳ estático", "", "", "", "", "", "", "", ""))
                    self.tree.see(payload)
                elif kind == "row_static":
                    self._fill_row(payload, status=LLM_QUEUED)
                elif kind == "row_llm":
                    self.tree.set(payload, "status", "🤖 LLM")
                elif kind == "row_progress":
                    self.tree.set(payload[0], "status", payload[1])
                elif kind == "row_done":
                    self.results[payload["case"]] = payload
                    self._fill_row(payload)
                    self.progress_var.set(self.progress_var.get() + 1)
                    if payload.get("error"):
                        self._append(f"  ✖ {payload['error']}")
                elif kind == "done":
                    self._finish(*payload)
        except queue.Empty:
            pass
        if self.running:
            self._show_progress()
        self.after(100, self._poll)
