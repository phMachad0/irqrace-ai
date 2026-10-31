"""Simple native Win32/Tkinter MVP GUI for the irqrace pipeline.

Window sequence:

* **Início** -- choose a mode.
* **Benchmarks Racebench** -- pick cases from ``bench/configs`` and run them
  unattended, scored against the ground truth (:mod:`irqrace.ui.benchmark_screen`).
* **Modo genérico** -- the program under analysis. Its C1 file is never edited
  by hand: it is imported, or written by the wizard (:mod:`irqrace.ui.c1_wizard`).
  Then the Pipeline tab: step-by-step / automatic runner, real-time progress,
  and LLM triage & repair inspection.
* **Configuração da LLM** -- shared by both modes: OpenAI-compatible presets
  (ChatGPT/OpenAI, Groq, OpenRouter, vLLM), Ollama, Anthropic and the Claude
  CLI, with .env persistence and a live connection test.
"""

from __future__ import annotations

import copy
import dataclasses
import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

# Ensure Tcl/Tk paths are explicitly set on Windows to prevent Tcl file handle lookup errors
_tcl_base = Path(sys.base_prefix) / "tcl"
if (_tcl_base / "tcl8.6").exists():
    os.environ.setdefault("TCL_LIBRARY", str(_tcl_base / "tcl8.6"))
if (_tcl_base / "tk8.6").exists():
    os.environ.setdefault("TK_LIBRARY", str(_tcl_base / "tk8.6"))
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any, Callable

import yaml

from irqrace.build import BuildError, build
from irqrace.candidate import access_locations, same_source
from irqrace.config import Config, ConfigError, resolve_source_root
from irqrace.llm.backends import BackendError, ChatRequest, RefusalError, from_spec
from irqrace.llm.backends.openai_backend import (
    OpenAICompatibleBackend,
    _RateLimited,
    _Transient,
)
from irqrace.llm.annotations import locate_suite
from irqrace.llm.client import TriageClient
from irqrace.llm.intervals import Budget
from irqrace.llm.pipeline import (
    prepare_context,
    read_triages,
    repair_store,
    triage_records,
    triage_settings,
    triage_store,
)
from irqrace.llm.prompts import BY_NAME, DEFERRED, EXPERIMENTAL, FULL, ROW_HELP
from irqrace.llm.repair import RepairClient, apply_unified_diff, patch_file, witness_problems
from irqrace.llm.resolver import resolver_for
from irqrace.llm.verdict import INSPECTION_ORDER, Bucket, Triage
from irqrace.probe import ProbeError, probe
from irqrace.run_evaluation import evaluate_run, write_report
from irqrace.runstore import RunStore
from irqrace.stage1_driver import Stage1Error, stage1
from irqrace.stage2 import stage2
from irqrace.stage3 import Stage3Error, stage3
from irqrace.ui.benchmark_screen import BenchmarkScreen
from irqrace.ui.c1_wizard import ConfigWizard, WizardState
from irqrace.ui.candidate_list import (
    COLOURS,
    DISCARDED,
    PENDING,
    SYMBOLS,
    Row,
    group_rows,
    sort_rows,
    tab_states,
    variable_key,
    variable_label,
)
from irqrace.ui.llm_history import build_history, load_turns
from irqrace.ui.pdf_report import PDFReportBuilder

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = REPO_ROOT / ".env"
WORKSPACE_ENV_FILE = WORKSPACE_ROOT / ".env"

#: How often the Pipeline tab looks at a run that is still being written.
LIVE_REFRESH_MS = 1000

PIPELINE_STEPS: list[tuple[str, str]] = [
    ("build", "Etapa 1/6: Build & Probe (Clang/LLVM Bitcode + Globais SVF)"),
    ("stage1", "Etapa 2/6: Stage 1 (Grafo de Chamadas, Alias SVF & Candidatos)"),
    ("solver", "Etapa 3/6: Stage 2 & 3 (Filtro de Mascaramento & Solver Z3)"),
    ("context", "Etapa 4/6: Contexto C2 (Empacotamento dos Candidatos Sobreviventes)"),
    ("triage", "Etapa 5/6: LLM Triagem (Viabilidade, Nocividade & Pedidos C4)"),
    ("repair", "Etapa 6/6: LLM Reparo & Reverificação (Testemunha + Patch C)"),
]

#: Pre-configured provider presets for the generic LLM API configuration tab.
LLM_PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "Groq (OpenAI-Compatible)": {
        "adapter": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "openai/gpt-oss-120b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen-qwq-32b",
        ],
    },
    "ChatGPT / OpenAI Oficial": {
        "adapter": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "o3-mini",
            "gpt-4.1",
        ],
    },
    "Genérico OpenAI-Compatible (OpenRouter / vLLM / LM Studio)": {
        "adapter": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "openai/gpt-4o-mini",
            "meta-llama/llama-3.3-70b-instruct",
            "qwen/qwen-2.5-coder-32b-instruct",
        ],
    },
    "Ollama (Local)": {
        "adapter": "ollama",
        "base_url": "http://localhost:11434",
        "models": [
            "qwen2.5-coder:32b",
            "llama3.1:8b",
            "deepseek-coder-v2:16b",
        ],
    },
    "Claude Code CLI (assinatura Pro/Max)": {
        # `claude -p` on the user's subscription login: drawn from the plan's
        # usage limits, no API key and no per-token billing. No endpoint either --
        # the CLI is the endpoint.
        "adapter": "claude-cli",
        "base_url": "",
        "models": [
            "sonnet",
            "opus",
            "haiku",
            "claude-opus-5-5",
            "claude-sonnet-5-5",
        ],
    },
    "Anthropic (Claude SDK)": {
        "adapter": "anthropic",
        "base_url": "https://api.anthropic.com",
        "models": [
            "claude-opus-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ],
    },
}


def load_dotenv_into_environ(env_path: Path | None = None) -> dict[str, str]:
    """Load key=value pairs from .env into os.environ and return them.

    Checks WORKSPACE_ENV_FILE, ENV_FILE, and current working directory .env.
    """
    candidate_paths: list[Path] = []
    if env_path is not None:
        candidate_paths.append(env_path)
    else:
        for p in (WORKSPACE_ENV_FILE, ENV_FILE, Path.cwd() / ".env"):
            if p not in candidate_paths:
                candidate_paths.append(p)

    loaded: dict[str, str] = {}
    for p in reversed(candidate_paths):
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if v and v != "gsk_valid_key_test_123":
                    os.environ[k] = v
                    loaded[k] = v
                elif not v:
                    os.environ[k] = ""
                    loaded[k] = ""

    return loaded


def save_dotenv_settings(settings: dict[str, str], env_path: Path | None = None) -> None:
    """Persist LLM configuration keys to .env files and update os.environ."""
    targets: list[Path] = []
    if env_path is not None:
        targets.append(env_path)
    else:
        for p in (WORKSPACE_ENV_FILE, ENV_FILE):
            if p not in targets:
                targets.append(p)

    for target in targets:
        existing: dict[str, str] = {}
        if target.is_file():
            for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    k, v = s.split("=", 1)
                    existing[k.strip()] = v.strip().strip("'").strip('"')
        for k, v in settings.items():
            existing[k] = v
            os.environ[k] = v
        lines = [f"{k}={v}" for k, v in sorted(existing.items())]
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TrackedOpenAIBackend(OpenAICompatibleBackend):
    """OpenAICompatibleBackend with real-time GUI telemetry for requests & 429 rate-limits."""

    def __init__(
        self,
        *args: Any,
        event_cb: Any = None,
        stop_checker: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.event_cb = event_cb
        self.stop_checker = stop_checker

    def _emit(self, kind: str, **payload: Any) -> None:
        if self.event_cb is not None:
            try:
                self.event_cb(kind, payload)
            except Exception:
                pass

    def chat(self, request: ChatRequest):
        if self.stop_checker and self.stop_checker():
            raise InterruptedError("Execução interrompida pelo usuário antes da chamada à LLM.")
        self._emit("request_start", model=self.model, base_url=self.base_url)
        resp = super().chat(request)
        self._emit(
            "request_done",
            model=self.model,
            elapsed_s=resp.usage.latency_s,
            in_tokens=resp.usage.input_tokens,
            out_tokens=resp.usage.output_tokens,
            structured_mode=resp.structured_mode.value if resp.structured_mode else "raw",
        )
        return resp

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        deadline = time.monotonic() + self.request_budget_s
        for attempt in range(self.max_retries + 1):
            if self.stop_checker and self.stop_checker():
                raise InterruptedError("Execução interrompida pelo usuário.")
            try:
                self._emit(
                    "http_attempt",
                    model=self.model,
                    base_url=self.base_url,
                    attempt=attempt + 1,
                    max_retries=self.max_retries + 1,
                )
                return self._post_once(body)
            except (_RateLimited, _Transient) as e:
                wait = min(e.retry_after, self.max_backoff_s)
                if attempt == self.max_retries or time.monotonic() + wait > deadline:
                    raise BackendError(
                        f"{type(e).__name__[1:].lower()} from {self.base_url}; "
                        f"gave up after {attempt + 1} attempt(s) within a "
                        f"{self.request_budget_s:.0f}s budget: {e.detail[:160]}"
                    ) from None
                self._emit(
                    "rate_limit_wait",
                    wait_s=wait,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    detail=e.detail[:140],
                )
                if self.event_cb is None:
                    time.sleep(wait)
                else:
                    end_t = time.monotonic() + wait
                    while True:
                        if self.stop_checker and self.stop_checker():
                            raise InterruptedError("Interrompido pelo usuário durante espera de rate-limit.")
                        rem = end_t - time.monotonic()
                        if rem <= 0:
                            break
                        self._emit(
                            "rate_limit_tick",
                            remaining_s=rem,
                            total_s=wait,
                            attempt=attempt + 1,
                            max_retries=self.max_retries,
                        )
                        time.sleep(min(0.3, rem))
        raise AssertionError("unreachable")


def build_backend_from_config(
    adapter: str,
    model: str,
    base_url: str,
    api_key: str,
    timeout_s: float = 120.0,
    event_cb: Any = None,
    stop_checker: Any = None,
):
    """Instantiate a generic Backend from the GUI configuration fields."""
    adapter = adapter.strip().lower()
    model = model.strip()
    base_url = base_url.strip()
    api_key = api_key.strip()

    if adapter == "openai":
        if base_url:
            os.environ["IRQRACE_OPENAI_BASE_URL"] = base_url
        if api_key:
            os.environ["IRQRACE_OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key
        return TrackedOpenAIBackend(
            model,
            base_url=base_url or None,
            api_key=api_key or None,
            timeout_s=timeout_s,
            event_cb=event_cb,
            stop_checker=stop_checker,
        )
    if adapter == "ollama":
        if base_url:
            os.environ["IRQRACE_OLLAMA_HOST"] = base_url
        return from_spec(f"ollama:{model}")
    if adapter == "anthropic":
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        return from_spec(f"anthropic:{model}")
    if adapter == "claude-cli":
        # No key and no URL: the CLI signs in with the subscription. The key
        # field is ignored on purpose -- the backend strips API credentials so
        # a stray ANTHROPIC_API_KEY cannot turn a plan run into a billed one.
        return from_spec(f"claude-cli:{model}", timeout_s=timeout_s, stop_checker=stop_checker)
    return from_spec(f"{adapter}:{model}")


def resolve_c_source_files(raw_cfg: dict[str, Any], yaml_path: Path | None = None) -> list[Path]:
    """Locate all .c and .h files referenced by a C1 configuration dict.

    Pass the file the dict came from: a relative ``source_root`` is relative to
    it, not to the working directory (``bench/configs`` say
    ``../racebench/2.1_remarks``, which from the vault root names a different
    checkout).
    """
    if yaml_path is not None:
        raw_cfg = resolve_source_root(copy.deepcopy(raw_cfg), Path(yaml_path))
    subj = raw_cfg.get("subject", {})
    sources = subj.get("sources", [])
    extra_bc = subj.get("build", {}).get("extra_bitcode", [])
    src_root = subj.get("source_root", "")

    found: list[Path] = []
    seen: set[Path] = set()

    search_bases = []
    if src_root:
        search_bases.append(Path(src_root))
    if (suite := locate_suite()) is not None:
        search_bases.append(suite)

    for rel in list(sources) + list(extra_bc):
        p_rel = Path(rel)
        candidates: list[Path] = []
        if p_rel.is_absolute():
            candidates.append(p_rel)
        for base in search_bases:
            candidates.append(base / p_rel)
            candidates.append(base / p_rel.name)
        for c in candidates:
            if c.is_file():
                rc = c.resolve()
                if rc not in seen:
                    seen.add(rc)
                    found.append(rc)
                # Also check for headers in the same directory (e.g. common.h)
                for h in sorted(rc.parent.glob("*.h")):
                    rh = h.resolve()
                    if rh not in seen:
                        seen.add(rh)
                        found.append(rh)
                break
    return found


def apply_source_list_to_c1_dict(
    raw: dict[str, Any], source_paths: list[Path]
) -> dict[str, Any]:
    """Update a raw C1 dict with a list of .c and .h file paths.

    * All ``.c`` files go into ``subject.sources`` (and if >1 `.c` file, sets
      ``subject.build.mode = "multi-tu"``).
    * All directories containing ``.h`` files (or ``.c`` files) go into
      ``subject.build.include_dirs`` so ``clang -I<dir>`` and the C4 resolver
      find every header.
    """
    out = copy.deepcopy(raw)
    existing_Paths = [Path(p).resolve() for p in source_paths if Path(p).exists()]
    if not existing_Paths:
        return out

    c_files = [p for p in existing_Paths if p.suffix.lower() == ".c"]
    h_files = [p for p in existing_Paths if p.suffix.lower() in (".h", ".hpp")]

    out.setdefault("subject", {})
    out["subject"].setdefault("build", {})

    if c_files:
        # The deepest directory holding every .c file: for a Racebench case
        # (the case file plus common.c) that is the suite's 2.1_remarks, so
        # access paths -- and candidate ids -- read svp_simple_NNN/<file>.c.
        common_parent = Path(os.path.commonpath([p.parent for p in c_files]))
        out["subject"]["source_root"] = str(common_parent)
        out["subject"]["sources"] = [str(p) for p in c_files]
        out["subject"]["build"]["extra_bitcode"] = []
        if len(c_files) > 1:
            out["subject"]["build"]["mode"] = "link"

    include_dirs: list[str] = list(out["subject"]["build"].get("include_dirs") or [])
    for p in h_files + c_files:
        parent_str = str(p.parent)
        if parent_str not in include_dirs:
            include_dirs.append(parent_str)
    out["subject"]["build"]["include_dirs"] = include_dirs
    return out


def run_signature(run_dir: Path) -> list[tuple[str, int, int]]:
    """What a run's files look like now: unchanged means nothing to redraw."""
    out = []
    for dirpath, dirs, files in os.walk(run_dir):
        if "build" in dirs:
            dirs.remove("build")
        for name in files:
            path = os.path.join(dirpath, name)
            st = os.stat(path)
            out.append((path, st.st_mtime_ns, st.st_size))
    return sorted(out)


class PipelineStepper:
    """Executes the 6 pipeline steps one by one into a working C3 RunStore."""

    def __init__(
        self,
        yaml_path: Path,
        source_paths: list[Path] | Path | None = None,
        *,
        work_root: Path | None = None,
        use_live_llm: bool = False,
        llm_adapter: str = "openai",
        llm_model: str = "openai/gpt-oss-120b",
        llm_base_url: str = "https://api.groq.com/openai/v1",
        llm_api_key: str = "",
        llm_prompt: str = "+self-validation",
        llm_timeout_s: float = 120.0,
        llm_workers: int = 1,
        llm_by_interval: bool = False,
        llm_budget: Budget | None = None,
        event_cb: Any = None,
    ) -> None:
        self.yaml_path = Path(yaml_path).resolve()
        if source_paths is None:
            self.source_paths: list[Path] = []
        elif isinstance(source_paths, (str, Path)):
            self.source_paths = [Path(source_paths).resolve()]
        else:
            self.source_paths = [Path(p).resolve() for p in source_paths]

        self.work_root = work_root or (REPO_ROOT / "runs")
        self.use_live_llm = use_live_llm
        self.llm_adapter = llm_adapter
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key
        self.llm_prompt = llm_prompt
        self.llm_timeout_s = llm_timeout_s
        self.llm_workers = llm_workers
        self.llm_by_interval = llm_by_interval
        self.llm_budget = llm_budget
        self.event_cb = event_cb

        raw = resolve_source_root(
            yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")), self.yaml_path)
        if not self.source_paths:
            self.source_paths = resolve_c_source_files(raw)

        if self.source_paths:
            raw = apply_source_list_to_c1_dict(raw, self.source_paths)

        self.cfg = Config.from_dict(raw, path=self.yaml_path)
        self.store: RunStore | None = None
        self.current_step_idx: int = 0
        self.stop_requested: bool = False

    def request_stop(self) -> None:
        """Signal to interrupt processing mid-stage."""
        self.stop_requested = True

    @property
    def primary_c_path(self) -> Path | None:
        for p in self.source_paths:
            if p.suffix.lower() == ".c" and p.name != "common.c":
                return p
        for p in self.source_paths:
            if p.suffix.lower() == ".c":
                return p
        return None

    def init_run(self) -> RunStore:
        """Create a fresh C3 RunStore with all stages set to pending."""
        self.store = RunStore.create(self.cfg, run_root=self.work_root)
        self.current_step_idx = 0
        return self.store

    def load_existing_run(self, run_dir: Path) -> RunStore:
        """Attach to an existing C3 RunStore."""
        self.store = RunStore(run_dir)
        m = self.store.read_manifest()
        stages = {s["name"]: s["status"] for s in m.get("stages", [])}
        done = 0
        for key, _ in PIPELINE_STEPS:
            if stages.get(key) in ("ok", "skipped"):
                done += 1
            else:
                break
        self.current_step_idx = done
        return self.store

    def run_next_step(self, log_fn=print) -> tuple[str, str]:
        """Execute the next pending step and return (step_key, summary_message)."""
        if self.store is None:
            self.init_run()
        assert self.store is not None

        if self.current_step_idx >= len(PIPELINE_STEPS):
            return ("done", "Todas as 6 etapas já foram concluídas.")

        step_key, step_title = PIPELINE_STEPS[self.current_step_idx]
        log_fn(f"▶ Iniciando {step_title}...")
        t0 = time.perf_counter()

        if step_key == "build":
            msg = self._step_build(log_fn)
        elif step_key == "stage1":
            msg = self._step_stage1(log_fn)
        elif step_key == "solver":
            msg = self._step_solver(log_fn)
        elif step_key == "context":
            msg = self._step_context(log_fn)
        elif step_key == "triage":
            msg = self._step_triage(log_fn)
        elif step_key == "repair":
            msg = self._step_repair(log_fn)
        else:
            msg = "Etapa desconhecida."

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        self.current_step_idx += 1
        log_fn(f"✔ Concluído ({elapsed_ms} ms): {msg}\n")
        return (step_key, msg)

    def _step_build(self, log_fn) -> str:
        assert self.store is not None
        self.store.set_stage("build", "running")
        build_dir = self.store.root / "build"
        build_dir.mkdir(parents=True, exist_ok=True)

        c_files = [p for p in self.source_paths if p.suffix.lower() == ".c"]
        h_files = [p for p in self.source_paths if p.suffix.lower() in (".h", ".hpp")]
        log_fn(
            f"  Compilando {len(c_files)} arquivo(s) .c (e {len(h_files)} .h) via {self.cfg.build['cc']}..."
        )
        for cf in c_files:
            log_fn(f"    - {cf}")

        t0 = time.perf_counter()
        try:
            result = build(self.cfg, build_dir)
        except BuildError as e:
            wall_ms = int((time.perf_counter() - t0) * 1000)
            self.store.set_stage("build", "failed", wall_ms=wall_ms, error=str(e))
            self.store.log("error", "build", "build-failed", str(e))
            log_fn(f"  ✖ ERRO DE COMPILAÇÃO:\n{e}")
            raise

        for line in result.log.splitlines():
            log_fn(f"    {line}")

        m = self.store.read_manifest()
        m["build"] = {
            "cc": self.cfg.build["cc"],
            "linker": self.cfg.build["linker"],
            "flags": list(self.cfg.build["flags"]),
            "translation_units": result.translation_units,
            "bitcode": str(result.bitcode.relative_to(self.store.root)),
            "bitcode_sha256": result.bitcode_sha256,
        }

        try:
            rep = probe(result.bitcode, self.cfg)
            (build_dir / "probe.json").write_text(
                json.dumps(rep, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            m["build"].update(
                functions_with_bodies=rep.get("functions_with_bodies", 0),
                functions_declared_only=rep.get("functions_declared_only", []),
            )
            for w in rep.get("warnings", []):
                sev = w.get("severity", "warn")
                self.store.log(sev, "build", w["code"], w["message"])
                log_fn(f"  ! [{sev.upper()}] {w['code']}: {w['message']}")
        except ProbeError as e:
            wall_ms = int((time.perf_counter() - t0) * 1000)
            self.store.set_stage("build", "failed", wall_ms=wall_ms, error=str(e))
            log_fn(f"  ✖ ERRO NO PROBE SVF:\n{e}")
            raise

        wall_ms = int((time.perf_counter() - t0) * 1000)
        self.store.write_manifest(m)
        self.store.set_stage("build", "ok", wall_ms=wall_ms)
        return (
            f"whole.bc compilado ({result.translation_units} TU, "
            f"{rep.get('globals_count', 0)} globais, {rep.get('functions_with_bodies', 0)} funções)"
        )

    def _step_stage1(self, log_fn) -> str:
        assert self.store is not None
        bitcode = self.store.root / "build" / "whole.bc"
        if not bitcode.exists():
            raise Stage1Error(f"Bitcode não encontrado em {bitcode}; execute a Etapa 1 primeiro.")

        log_fn(f"  Executando irqrace-stage1 (SVF May-Alias + CFG) sobre {bitcode.name}...")
        summary = stage1(self.cfg, self.store, bitcode)
        for w in summary.get("warnings", []):
            log_fn(f"  ! [{w.get('severity', 'warn').upper()}] {w['code']}: {w['message']}")
        n = summary["candidates"]
        log_fn(
            f"  SVF enumerou {summary['accesses']} acessos em {summary['objects']} objetos compartilhados: "
            f"{n} trincas candidatas (A1, B, A2)."
        )
        return f"{n} trincas candidatas extraídas"

    def _step_solver(self, log_fn) -> str:
        """Stages 2 and 3, the same functions ``irqrace stage3`` runs.

        Both may drop a candidate, and only with a proof: stage 2 writes one line
        per drop to ``stage2/dropped.jsonl``, and stage 3 drops only on ``unsat``.
        Stage 3 also writes the context records -- with the solver's verdict and
        its provenance note -- so the context step only reads them back.

        When the subject is a Racebench case with ground truth on this machine,
        the run is then evaluated the way ``irqrace stage3-all`` evaluates it, and
        ``eval/report.json`` records the recall gate on what reaches the LLM.
        """
        assert self.store is not None
        bitcode = self.store.root / "build" / "whole.bc"
        if not bitcode.exists():
            raise Stage3Error(f"Bitcode não encontrado em {bitcode}; execute a Etapa 1 primeiro.")

        log_fn("  Stage 2: análise de máscara de interrupções e prioridade (ponto fixo)...")
        s2 = stage2(self.cfg, self.store)
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(s2["reasons"].items())) or "nenhum"
        log_fn(
            f"  Stage 2: {s2['in']} entrada -> {s2['kept']} mantidos, "
            f"{s2['dropped']} descartados com prova ({reasons}) [{s2['wall_ms']} ms]"
        )
        for d in self.store.read_drops():
            log_fn(f"    - {d['candidate_id']} {d['pattern']} {d['lines']} [{d['reason']}]")

        log_fn("  Stage 3: execução simbólica sobre o IR com Z3...")
        s3 = stage3(self.cfg, self.store, bitcode)
        verdicts = ", ".join(f"{k}: {v}" for k, v in sorted(s3["verdicts"].items())) or "nenhum"
        log_fn(
            f"  Stage 3: {s3['in']} entrada -> {verdicts}; "
            f"{s3['kept']} chegam à LLM [{s3['wall_ms']} ms]"
        )

        report = write_report(self.store)
        if report is None:
            log_fn("  Avaliação: caso sem ground truth nesta máquina; recall não calculado.")
        else:
            gate = "PASS" if report["recall_gate"] else "FALHOU"
            log_fn(
                f"  Avaliação (ground truth): recall {report['bugs_detected']}/{report['bug_points']} "
                f"[{gate}], armadilhas vivas {report['traps_reported']}/{report['traps']}."
            )
        return (
            f"{s3['kept']}/{s2['in']} candidatos sobreviveram "
            f"({s2['dropped']} descartados no stage 2, {s3['dropped']} UNSAT no Z3, todos com prova)"
        )

    def _step_context(self, log_fn) -> str:
        assert self.store is not None
        # Stage 3 already wrote context/ with the solver's verdict and provenance
        # note; prepare_context reads those back rather than rebuilding them.
        promoted = prepare_context(self.store)
        log_fn(f"  {len(promoted)} registros de contexto C2 em context/*.json.")
        return f"{len(promoted)} registros C2 prontos para a LLM"

    def _emit_event(self, kind: str, **payload: Any) -> None:
        if self.event_cb is not None:
            try:
                self.event_cb(kind, payload)
            except Exception:
                pass

    def _make_backend_event_handler(self, log_fn, stage_label: str):
        def _on_backend_event(kind: str, payload: dict[str, Any]) -> None:
            if kind == "request_start":
                self._emit_event("api_request_start", stage=stage_label, **payload)
            elif kind == "rate_limit_wait":
                wait_s = payload.get("wait_s", 0.0)
                att = payload.get("attempt", 1)
                max_r = payload.get("max_retries", 6)
                log_fn(
                    f"    ⚠️ [RATE LIMIT 429] Limite de taxa da API atingido! "
                    f"Aguardando {wait_s:.1f}s antes da tentativa {att}/{max_r}..."
                )
                self._emit_event("api_rate_limit_wait", stage=stage_label, **payload)
            elif kind == "rate_limit_tick":
                self._emit_event("api_rate_limit_tick", stage=stage_label, **payload)
            elif kind == "request_done":
                el = payload.get("elapsed_s", 0.0)
                in_tok = payload.get("in_tokens", 0)
                out_tok = payload.get("out_tokens", 0)
                log_fn(
                    f"    ✔ Resposta da API recebida em {el:.1f}s "
                    f"({in_tok} tokens in / {out_tok} tokens out)"
                )
                self._emit_event("api_request_done", stage=stage_label, **payload)

        return _on_backend_event

    def _step_triage(self, log_fn) -> str:
        assert self.store is not None
        if self.use_live_llm:
            started = time.perf_counter()
            all_rows = {**BY_NAME, **DEFERRED, **EXPERIMENTAL}
            p_cfg = all_rows.get(self.llm_prompt, FULL)
            backend = build_backend_from_config(
                self.llm_adapter,
                self.llm_model,
                self.llm_base_url,
                self.llm_api_key,
                timeout_s=self.llm_timeout_s,
                event_cb=self._make_backend_event_handler(log_fn, "Triagem"),
                stop_checker=lambda: self.stop_requested,
            )
            records = prepare_context(self.store)
            total = len(records)
            log_fn(
                f"  Iniciando Triagem via API Real ({backend.spec} @ {self.llm_base_url}, prompt={p_cfg.name}) "
                f"para {total} candidato(s)..."
            )
            client = TriageClient(p_cfg, backend=backend)
            manifest = self.store.read_manifest()
            manifest["llm"] = {
                "model": backend.spec,
                "prompt_config": p_cfg.name,
                "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
                "votes": 1,
                "seed": None,
                **triage_settings(self.llm_workers, self.llm_by_interval, self.llm_budget),
            }
            self.store.write_manifest(manifest)
            self.store.set_stage("triage", "running", candidates_in=total)

            llm_dir = self.store.root / "llm"
            llm_dir.mkdir(parents=True, exist_ok=True)

            def _write_triages(items: list[Triage]) -> None:
                ordered_so_far = sorted(items, key=lambda item: (item.rank_key, item.candidate_id))
                with (llm_dir / "triage.jsonl").open("w", encoding="utf-8") as fh:
                    for item in ordered_so_far:
                        cand_dir = llm_dir / item.candidate_id
                        cand_dir.mkdir(parents=True, exist_ok=True)
                        verdict_doc = {**item.model_dump(mode="json"), "bucket": item.bucket.value}
                        (cand_dir / "verdict.json").write_text(
                            json.dumps(verdict_doc, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8",
                        )
                        fh.write(json.dumps(verdict_doc, ensure_ascii=False) + "\n")

            triages: list[Triage] = []
            finished = {"n": 0}

            def _on_start(rec: dict[str, Any]) -> None:
                vname = (rec.get("variable") or {}).get("name") or (rec.get("symbol") or {}).get("name", "?")
                pat = rec.get("pattern") or rec.get("pattern_id", "?")
                log_fn(f"  -> Enviando {rec['id']} (var='{vname}', padrão={pat}) para a API...")
                self._emit_event(
                    "api_candidate_progress",
                    stage="Triagem",
                    current=finished["n"],
                    total=total,
                    cid=rec["id"],
                    var=vname,
                    status="running",
                )

            def _on_done(group: list[dict[str, Any]], outcomes: dict[str, Triage | str]) -> None:
                lead = group[0]
                finished["n"] += len(group)
                result = outcomes[lead["id"]]
                progress = f"[Candidato {finished['n']}/{total}]"
                extra = f" (intervalo de {len(group)} triplas)" if len(group) > 1 else ""
                if isinstance(result, Triage):
                    log_fn(
                        f"  ✔ {progress} {lead['id']} concluído{extra}: "
                        f"bucket={result.bucket.value} (viabilidade={result.feasibility.verdict.value}, "
                        f"nocividade={result.harmfulness.verdict.value if result.harmfulness else '-'})"
                    )
                    triages.extend(t for t in outcomes.values() if isinstance(t, Triage))
                else:
                    log_fn(f"  ✖ {progress} {lead['id']}{extra} mantido como uncertain: {result}")
                    triages.extend(Triage.untriaged(m, result) for m in group)
                # Incremental, so the GUI table updates after every conversation
                _write_triages(triages)
                self._emit_event(
                    "api_candidate_progress",
                    stage="Triagem",
                    current=finished["n"],
                    total=total,
                    cid=lead["id"],
                    var=(lead.get("variable") or {}).get("name", "?"),
                    status="done",
                )

            triage_records(
                client,
                records,
                make_resolver=lambda rec: resolver_for(rec, mode="auto"),
                run_dir=self.store.root,
                workers=self.llm_workers,
                by_interval=self.llm_by_interval,
                budget=self.llm_budget,
                should_stop=lambda: self.stop_requested,
                on_start=_on_start,
                on_done=_on_done,
            )
            n_answered = sum(1 for t in triages if not t.not_triaged)
            if self.stop_requested:
                log_fn(f"  ⏹ Interrompido pelo usuário na Triagem ({n_answered}/{total} concluídos).")

            wall_ms = int((time.perf_counter() - started) * 1000)
            if self.stop_requested and n_answered == 0:
                msg = f"Triagem interrompida pelo usuário antes da conclusão (0/{total})."
                self.store.set_stage("triage", "pending", wall_ms=wall_ms, error=msg)
                return msg

            if n_answered == 0 and triages:
                msg = f"Todos os {len(triages)} candidato(s) falharam na API: {triages[0].not_triaged}"
                self.store.set_stage("triage", "failed", wall_ms=wall_ms, error=msg)
                raise BackendError(msg)

            # Triage never drops: a candidate the run did not reach stays in the
            # report as uncertain, with the reason.
            reached = {t.candidate_id for t in triages}
            for rec in records:
                if rec["id"] not in reached:
                    triages.append(
                        Triage.untriaged(rec, "the run was interrupted before this candidate was triaged")
                    )
            _write_triages(triages)
            n_untriaged = sum(1 for t in triages if t.not_triaged)
            for t in triages:
                if t.not_triaged:
                    self.store.log("warn", "triage", "candidate-not-triaged",
                                   f"{t.candidate_id}: {t.not_triaged}", candidate_id=t.candidate_id)

            ordered = sorted(triages, key=lambda item: (item.rank_key, item.candidate_id))
            self.store.set_stage(
                "triage",
                "ok",
                wall_ms=wall_ms,
                candidates_in=total,
                candidates_out=len(ordered),
                dropped_with_proof=0,
            )
            b_counts = {b.value: sum(1 for item in ordered if item.bucket is b) for b in INSPECTION_ORDER}
            log_fn(f"  Triagem concluída: {b_counts}")
            if n_untriaged:
                log_fn(f"  ⚠ {n_untriaged} candidato(s) sem veredicto da LLM, mantidos como 'uncertain' com o motivo.")
            return (
                f"{n_answered}/{total} candidatos triados ({b_counts})"
                + (f"; {n_untriaged} sem veredicto, mantidos como uncertain" if n_untriaged else "")
            )

        ctx_files = list((self.store.root / "context").glob("*.json")) if (self.store.root / "context").exists() else []
        msg = (
            "LLM não executada: 'Usar API de LLM Real' está desmarcado. "
            f"Os {len(ctx_files)} candidato(s) seguem em context/, sem veredicto."
        )
        self.store.set_stage("triage", "skipped", candidates_in=len(ctx_files), error=msg)
        log_fn(f"  [Sem LLM] {msg}")
        return f"0/{len(ctx_files)} triados (ative 'Usar API de LLM Real')"

    def _step_repair(self, log_fn) -> str:
        assert self.store is not None
        reverify_reason = (
            "not implemented: re-verifying a patch means applying it, rebuilding, "
            "re-running stages 1-3 on the patched program and mapping the candidate "
            "across the shifted lines; none of that is wired yet"
        )
        if self.use_live_llm:
            started = time.perf_counter()
            all_rows = {**BY_NAME, **DEFERRED, **EXPERIMENTAL}
            p_cfg = all_rows.get(self.llm_prompt, FULL)
            backend = build_backend_from_config(
                self.llm_adapter,
                self.llm_model,
                self.llm_base_url,
                self.llm_api_key,
                timeout_s=self.llm_timeout_s,
                event_cb=self._make_backend_event_handler(log_fn, "Reparo"),
                stop_checker=lambda: self.stop_requested,
            )
            records = {r["id"]: r for r in prepare_context(self.store)}
            triages = read_triages(self.store)
            if triages:
                target_ids = [t.candidate_id for t in triages if t.bucket in (Bucket.likely_real,)]
            else:
                target_ids = sorted(records)

            total = len(target_ids)
            log_fn(
                f"  Solicitando patch de reparo e testemunha à LLM ({backend.spec}) para {total} candidato(s) likely_real..."
            )
            client = RepairClient(p_cfg, backend=backend)
            self.store.set_stage("repair", "running", candidates_in=total)

            patches = {}
            excluded: list[tuple[str, str]] = []
            for idx, cid in enumerate(target_ids, start=1):
                if self.stop_requested:
                    log_fn(f"  ⏹ Interrompido pelo usuário no Reparo ({len(patches)}/{total} concluídos).")
                    break
                rec = records.get(cid)
                if rec is None:
                    continue
                vname = (rec.get("variable") or {}).get("name") or (rec.get("symbol") or {}).get("name", "?")
                log_fn(f"  -> [Reparo {idx}/{total}] Gerando testemunha e patch C para {cid} ('{vname}')...")
                self._emit_event(
                    "api_candidate_progress",
                    stage="Reparo",
                    current=idx - 1,
                    total=total,
                    cid=cid,
                    var=vname,
                    status="running",
                )
                try:
                    patch = client.repair(rec, run_dir=self.store.root)
                    patches[cid] = patch
                    log_fn(f"  ✔ [Reparo {idx}/{total}] Patch gerado para {cid} (estratégia={patch.strategy.value})")
                except InterruptedError:
                    log_fn(f"  ⏹ Interrompido pelo usuário durante geração de patch para {cid}.")
                    break
                except (RefusalError, BackendError, RuntimeError, ValueError) as e:
                    excluded.append((cid, str(e)))
                    log_fn(f"  ✖ [Reparo {idx}/{total}] Falha ao gerar patch para {cid}: {e}")

                self._emit_event(
                    "api_candidate_progress",
                    stage="Reparo",
                    current=idx,
                    total=total,
                    cid=cid,
                    var=vname,
                    status="done",
                )

            wall_ms = int((time.perf_counter() - started) * 1000)
            n_rep = len(patches)
            if self.stop_requested and n_rep == 0 and total > 0:
                msg = f"Reparo interrompido pelo usuário antes da conclusão (0/{total})."
                self.store.set_stage("repair", "pending", wall_ms=wall_ms, error=msg)
                return msg

            self.store.set_stage(
                "repair",
                "ok",
                wall_ms=wall_ms,
                candidates_in=total,
                candidates_out=n_rep,
                dropped_with_proof=0,
            )
            self.store.set_stage("reverify", "skipped", candidates_in=n_rep, error=reverify_reason)
            log_fn(f"  {n_rep}/{total} patch(es) gerados. Reverificação não implementada.")
            return f"{n_rep} correção(ões) gerada(s) com testemunha, sem reverificação"

        msg = (
            "Reparo não executado: 'Usar API de LLM Real' está desmarcado."
        )
        self.store.set_stage("repair", "skipped", error=msg)
        log_fn(f"  [Sem LLM] {msg}")
        return msg


class IrqRaceWinApp:
    """Classic Windows (ttk) Desktop MVP for irqrace."""

    BENCH_CONFIGS = REPO_ROOT / "bench" / "configs"
    RUNS_ROOT = REPO_ROOT / "runs"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("irqrace — Detector e Reparador de Concorrência em Interrupções (MVP)")
        self.root.geometry("1220x840")
        self.root.minsize(1000, 700)

        # Standard Windows look and feel
        style = ttk.Style(self.root)
        for theme in ("vista", "winnative", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        load_dotenv_into_environ()

        self.log_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.stepper: PipelineStepper | None = None
        self.is_running_async = False
        # The run shown read-only while the Racebench screen is still writing it.
        self._live_run: Path | None = None
        self._live_case = ""
        self._live_is_running: Callable[[], bool] = lambda: False
        self._live_token = 0
        self._live_signature: list[tuple[str, int, int]] | None = None
        self._live_rendered: tuple[Any, ...] | None = None
        self.stop_requested = False
        self.candidates_data: dict[str, dict[str, Any]] = {}
        self.candidate_rows: list[Row] = []
        self._sort_column: str | None = None
        self._sort_reverse = False
        self.group_by_variable_var = tk.BooleanVar(value=False)
        self._open_groups: set[str] = set()
        self._tab_images: dict[str, tk.PhotoImage] = {}
        self._run_stages: dict[str, str] = {}
        self.source_files_list: list[Path] = []
        self.pipeline_header_info_var = tk.StringVar(value="")

        # Generic mode starts empty: the C1 file is imported or made by the wizard.
        self.yaml_path_var = tk.StringVar(value="")
        self.selected_source_view_var = tk.StringVar(value="")
        self.screens: dict[str, ttk.Frame] = {}
        self.current_screen = ""
        self._pipeline_origin = "generic"
        self._llm_return_screen = "home"

        # LLM Configuration Variables (loaded from .env if present)
        env_base_url = os.environ.get("IRQRACE_OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
        env_api_key = os.environ.get("IRQRACE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        env_model = os.environ.get("IRQRACE_LLM_MODEL", "openai/gpt-oss-120b")
        env_adapter = os.environ.get("IRQRACE_LLM_ADAPTER", "openai")
        saved_preset = os.environ.get("IRQRACE_LLM_PRESET")
        if saved_preset and saved_preset in LLM_PROVIDER_PRESETS:
            env_preset = saved_preset
        else:
            env_preset = "ChatGPT / OpenAI Oficial" if "api.openai.com" in env_base_url else "Groq (OpenAI-Compatible)"
        env_prompt = os.environ.get("IRQRACE_LLM_PROMPT", "+self-validation")
        env_timeout = os.environ.get("IRQRACE_LLM_TIMEOUT", "120")

        self.llm_preset_var = tk.StringVar(value=env_preset)
        self.llm_adapter_var = tk.StringVar(value=env_adapter)
        self.llm_base_url_var = tk.StringVar(value=env_base_url)
        self.llm_api_key_var = tk.StringVar(value=env_api_key)
        self.llm_model_var = tk.StringVar(value=env_model)
        self.llm_prompt_var = tk.StringVar(value=env_prompt)
        self.llm_timeout_var = tk.StringVar(value=env_timeout)
        self.llm_workers_var = tk.StringVar(value=os.environ.get("IRQRACE_LLM_WORKERS", "1"))
        self.llm_by_interval_var = tk.BooleanVar(value=os.environ.get("IRQRACE_LLM_BY_INTERVAL", "") == "1")
        self.llm_max_requests_var = tk.StringVar(value=os.environ.get("IRQRACE_LLM_MAX_REQUESTS", ""))
        self.llm_max_usd_var = tk.StringVar(value=os.environ.get("IRQRACE_LLM_MAX_USD", ""))
        self.use_live_llm_var = tk.BooleanVar(value=bool(env_api_key))
        self.show_api_key_var = tk.BooleanVar(value=False)
        self.llm_header_summary_var = tk.StringVar(value="")

        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(
            value="Pronto. Importe ou crie a configuração do projeto e avance etapa a etapa."
        )

        # Real-time API / Sub-task Loading Bar state
        self.api_progress_var = tk.DoubleVar(value=0.0)
        self.api_status_var = tk.StringVar(
            value="API LLM: Inativa (aguardando execução das Etapas 5 e 6)."
        )
        self.api_call_active: bool = False
        self.api_rate_limited: bool = False
        self.api_req_started_t: float = 0.0
        self.api_cand_current: int = 0
        self.api_cand_total: int = 0
        self.api_cand_cid: str = ""
        self.api_cand_var: str = ""
        self.api_stage_label: str = ""
        self.api_tokens_in_total: int = 0
        self.api_tokens_out_total: int = 0
        self.api_pulse_phase: float = 0.0

        self._build_ui()
        self._update_llm_header_summary()
        self._refresh_source_listbox()
        self.show_screen("home")
        self.root.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=4)
        outer.pack(fill=tk.BOTH, expand=True)
        self.screen_host = outer

        # Screen sequence: Início -> (Benchmarks Racebench | Modo genérico), plus
        # the LLM settings shared by both. Only one screen is packed at a time.
        self.screen_home = ttk.Frame(outer, padding=16)
        self.screen_llm = ttk.Frame(outer, padding=8)
        self.screen_generic = ttk.Frame(outer)
        self.bench_screen = BenchmarkScreen(outer, self)
        self.screens = {
            "home": self.screen_home,
            "bench": self.bench_screen,
            "generic": self.screen_generic,
            "llm": self.screen_llm,
        }

        # Generic mode: Projeto -> Pipeline
        self.top_notebook = ttk.Notebook(self.screen_generic)
        self.top_notebook.pack(fill=tk.BOTH, expand=True)
        self.tab_setup = ttk.Frame(self.top_notebook, padding=8)
        self.tab_pipeline = ttk.Frame(self.top_notebook, padding=4)
        self.top_notebook.add(self.tab_setup, text="  1. Projeto  ")
        self.top_notebook.add(self.tab_pipeline, text="  2. Pipeline  ")

        self._build_home_screen(self.screen_home)
        self._build_llm_screen(self.screen_llm)
        # Compatibility alias
        self.tab_llm_config = self.screen_llm
        self._build_setup_screen(self.tab_setup)
        self._build_pipeline_screen(self.tab_pipeline)

    # -------------------------------------------------------------------------
    # NAVEGAÇÃO ENTRE TELAS
    # -------------------------------------------------------------------------

    def show_screen(self, name: str) -> None:
        for frame in self.screens.values():
            frame.pack_forget()
        self.screens[name].pack(fill=tk.BOTH, expand=True)
        self.current_screen = name
        self._update_llm_header_summary()

    def open_generic_mode(self) -> None:
        self._end_live_view()
        self._pipeline_origin = "generic"
        self.top_notebook.select(self.tab_setup)
        self.show_screen("generic")

    def open_llm_settings(self, return_to: str | None = None) -> None:
        self._llm_return_screen = return_to or self.current_screen or "home"
        self.show_screen("llm")

    def _leave_llm_settings(self) -> None:
        self._update_llm_header_summary()
        self.show_screen(self._llm_return_screen if self._llm_return_screen != "llm" else "home")

    def _pipeline_back(self) -> None:
        self._end_live_view()
        if self._pipeline_origin == "bench":
            self.show_screen("bench")
        else:
            self.top_notebook.select(self.tab_setup)

    def llm_ready(self) -> bool:
        adapter = self.llm_adapter_var.get().strip() or "openai"
        if not self.llm_model_var.get().strip():
            return False
        if adapter in ("openai", "anthropic") and not self.llm_api_key_var.get().strip():
            return False
        return adapter == "claude-cli" or bool(self.llm_base_url_var.get().strip())

    def _llm_kwargs(self) -> dict[str, Any]:
        """The LLM settings as plain values, safe to hand to a worker thread."""
        try:
            timeout_s = float(self.llm_timeout_var.get().strip() or "120")
        except ValueError:
            timeout_s = 120.0

        def number(var: tk.StringVar, kind: type) -> Any:
            try:
                return kind(var.get().strip())
            except ValueError:  # blank means no limit
                return None

        max_requests, max_usd = number(self.llm_max_requests_var, int), number(self.llm_max_usd_var, float)
        return {
            "llm_adapter": self.llm_adapter_var.get().strip() or "openai",
            "llm_model": self.llm_model_var.get().strip() or "openai/gpt-oss-120b",
            "llm_base_url": self.llm_base_url_var.get().strip() or "https://api.groq.com/openai/v1",
            "llm_api_key": self.llm_api_key_var.get().strip(),
            "llm_prompt": self.llm_prompt_var.get().strip() or "+self-validation",
            "llm_timeout_s": timeout_s,
            "llm_workers": max(number(self.llm_workers_var, int) or 1, 1),
            "llm_by_interval": self.llm_by_interval_var.get(),
            "llm_budget": Budget(max_requests=max_requests, max_usd=max_usd)
            if max_requests is not None or max_usd is not None
            else None,
        }

    def _triage_env(self) -> dict[str, str]:
        return {
            "IRQRACE_LLM_WORKERS": self.llm_workers_var.get().strip(),
            "IRQRACE_LLM_BY_INTERVAL": "1" if self.llm_by_interval_var.get() else "",
            "IRQRACE_LLM_MAX_REQUESTS": self.llm_max_requests_var.get().strip(),
            "IRQRACE_LLM_MAX_USD": self.llm_max_usd_var.get().strip(),
        }

    def stepper_factory(self, *, live_llm: bool, prompt: str | None = None):
        """A ``yaml_path -> PipelineStepper`` callable for the benchmark worker.

        Each case resolves its own sources from its C1 file (``source_paths=None``).
        *prompt* overrides the saved prompt row for this batch.
        """
        kwargs = self._llm_kwargs()
        if prompt:
            kwargs["llm_prompt"] = prompt
        # The batch already runs cases in parallel: calls inside each would multiply.
        kwargs["llm_workers"] = 1
        runs_root = self.RUNS_ROOT

        def _make(yaml_path: Path) -> PipelineStepper:
            return PipelineStepper(yaml_path, None, work_root=runs_root, use_live_llm=live_llm, **kwargs)

        return _make

    def open_run_in_pipeline(
        self,
        yaml_path: Path,
        run_dir: Path,
        *,
        origin: str = "generic",
        is_live: Callable[[], bool] = lambda: False,
    ) -> None:
        """Show a run in the Pipeline tab (used by the benchmark table).

        While *is_live* holds, the run belongs to the benchmark's threads: the
        view is read-only and follows the files, and no stepper is attached,
        because a second writer on the same run would corrupt it.
        """
        self._end_live_view()
        raw = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
        self.yaml_path_var.set(str(yaml_path))
        self.source_files_list = resolve_c_source_files(raw, yaml_path)
        self.stepper = None
        self._refresh_source_listbox()
        self._update_pipeline_header_info()
        self._clear_live_log()
        if is_live():
            self._start_live_view(Path(yaml_path).stem, run_dir, is_live)
        else:
            self._load_run_into_ui(run_dir, note=f"Run carregado: {run_dir}")
            self.api_status_var.set("API LLM: run já executado, aberto só para inspeção.")
        self._pipeline_origin = origin
        self.show_screen("generic")
        self.top_notebook.select(self.tab_pipeline)

    def _start_live_view(self, case: str, run_dir: Path, is_live: Callable[[], bool]) -> None:
        self._live_run, self._live_case, self._live_is_running = run_dir, case, is_live
        self._live_signature = self._live_rendered = None
        self._live_token += 1
        for button in (self.btn_reset, self.btn_step, self.btn_resume, self.btn_stop):
            button.configure(state=tk.DISABLED)
        self._append_log(f"Inspeção ao vivo de {case}: {run_dir}")
        self.api_status_var.set("👁 Inspeção ao vivo: atualiza sozinha enquanto o caso roda. Somente leitura.")
        self._live_tick(self._live_token)

    def _live_tick(self, token: int) -> None:
        if token != self._live_token:  # another view replaced this one
            return
        running = self._live_is_running()
        try:
            signature = run_signature(self._live_run)
            if signature != self._live_signature:
                self._refresh_from_store(RunStore(self._live_run))
                self._live_signature = signature
        except (OSError, ValueError, KeyError):
            pass  # a file caught half written: the next tick reads it whole
        if running:
            self.root.after(LIVE_REFRESH_MS, self._live_tick, token)
        else:
            self._finish_live_view()

    def _finish_live_view(self) -> None:
        run_dir, case = self._live_run, self._live_case
        self._end_live_view()
        stepper = self._create_stepper()
        if stepper:
            self.stepper = stepper
            self.stepper.load_existing_run(run_dir)
        self._append_log(f"{case} terminou.")
        self.api_status_var.set("API LLM: caso terminou, run aberto só para inspeção.")

    def _end_live_view(self) -> None:
        if self._live_run is None:
            return
        self._live_run = None
        self._live_token += 1
        self._set_buttons_state(tk.NORMAL)

    def live_view_log(self, msg: str) -> None:
        """Mirror the watched case's lines of the benchmark log into the Pipeline tab."""
        if self._live_run is not None and msg.lstrip().startswith(f"[{self._live_case}]"):
            self._append_log(msg)

    # -------------------------------------------------------------------------
    # TELA INICIAL
    # -------------------------------------------------------------------------

    def _build_home_screen(self, parent: ttk.Frame) -> None:
        center = ttk.Frame(parent)
        center.place(relx=0.5, rely=0.45, anchor=tk.CENTER)
        ttk.Label(center, text="irqrace", font=("Segoe UI", 26, "bold")).pack()
        ttk.Label(
            center,
            text="Detecção e reparo de violações de atomicidade em programas embarcados com interrupções",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 24))

        cards = ttk.Frame(center)
        cards.pack()
        modes = (
            (
                "Benchmarks Racebench",
                "Executa os casos da suíte Racebench de forma automatizada e compara o resultado "
                "com o gabarito anotado: recall, armadilhas e tempo por caso. As configurações "
                "dos casos já vêm prontas.",
                "Abrir benchmarks >>",
                lambda: self.show_screen("bench"),
            ),
            (
                "Analisar um projeto",
                "Configura o programa e o ambiente sob análise: arquivos-fonte, tarefas, ISRs, "
                "primitivas de mascaramento e semântica do processador. A configuração é importada "
                "de um arquivo existente ou criada por um assistente.",
                "Configurar projeto >>",
                self.open_generic_mode,
            ),
        )
        for col, (title, desc, btn, cmd) in enumerate(modes):
            card = ttk.LabelFrame(cards, text=f" {title} ", padding=14)
            card.grid(row=0, column=col, padx=10, sticky=tk.NSEW)
            ttk.Label(card, text=desc, wraplength=330, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 12))
            ttk.Button(card, text=btn, command=cmd).pack(anchor=tk.E, ipady=4)
        cards.columnconfigure((0, 1), weight=1, uniform="card")

        llm_row = ttk.Frame(center, padding=(0, 20, 0, 0))
        llm_row.pack(fill=tk.X)
        ttk.Label(llm_row, textvariable=self.llm_header_summary_var, foreground="gray").pack(side=tk.LEFT)
        ttk.Button(
            llm_row, text="Configurar LLM...", command=lambda: self.open_llm_settings(return_to="home")
        ).pack(side=tk.RIGHT)

    # -------------------------------------------------------------------------
    # CONFIGURAÇÃO DA LLM (compartilhada pelos dois modos)
    # -------------------------------------------------------------------------

    def _build_llm_screen(self, parent: ttk.Frame) -> None:
        nav = ttk.Frame(parent)
        nav.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(nav, text="<< Voltar", command=self._leave_llm_settings).pack(side=tk.LEFT)
        ttk.Label(nav, text="Configuração da LLM", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=10)

        cfg_box = ttk.LabelFrame(
            parent,
            text=" Provedor, modelo e credenciais ",
            padding=10,
        )
        cfg_box.pack(fill=tk.X, pady=(0, 8))

        # Row 0: Provider Preset
        r0 = ttk.Frame(cfg_box)
        r0.pack(fill=tk.X, pady=3)
        ttk.Label(r0, text="Provedor:", width=22).pack(side=tk.LEFT)
        preset_cb = ttk.Combobox(
            r0,
            textvariable=self.llm_preset_var,
            values=list(LLM_PROVIDER_PRESETS.keys()),
            state="readonly",
            width=36,
        )
        preset_cb.pack(side=tk.LEFT, padx=(0, 8))
        preset_cb.bind("<<ComboboxSelected>>", self._on_llm_preset_changed)

        ttk.Label(r0, text="Adaptador:").pack(side=tk.LEFT, padx=(6, 4))
        adapter_cb = ttk.Combobox(
            r0,
            textvariable=self.llm_adapter_var,
            values=["openai", "ollama", "anthropic", "claude-cli"],
            state="readonly",
            width=14,
        )
        adapter_cb.pack(side=tk.LEFT)

        # Row 1: Base URL
        r1 = ttk.Frame(cfg_box)
        r1.pack(fill=tk.X, pady=3)
        ttk.Label(r1, text="Endpoint URL:", width=22).pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.llm_base_url_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # Row 2: API Key (Mandatory)
        r2 = ttk.Frame(cfg_box)
        r2.pack(fill=tk.X, pady=3)
        ttk.Label(r2, text="API Key (Obrigatória):", width=22, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.api_key_entry = ttk.Entry(r2, textvariable=self.llm_api_key_var, show="*")
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Checkbutton(
            r2,
            text="Mostrar",
            variable=self.show_api_key_var,
            command=lambda: self.api_key_entry.configure(show="" if self.show_api_key_var.get() else "*"),
        ).pack(side=tk.LEFT)

        # Row 3: Model Name & Prompt
        r3 = ttk.Frame(cfg_box)
        r3.pack(fill=tk.X, pady=3)
        ttk.Label(r3, text="Modelo:", width=22).pack(side=tk.LEFT)
        preset_info = LLM_PROVIDER_PRESETS.get(self.llm_preset_var.get(), LLM_PROVIDER_PRESETS["Groq (OpenAI-Compatible)"])
        self.model_cb = ttk.Combobox(
            r3,
            textvariable=self.llm_model_var,
            values=preset_info["models"],
            width=36,
        )
        self.model_cb.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(r3, text="Prompt:").pack(side=tk.LEFT, padx=(6, 4))
        prompt_rows = list({**BY_NAME, **DEFERRED, **EXPERIMENTAL}.keys())
        ttk.Combobox(
            r3,
            textvariable=self.llm_prompt_var,
            values=prompt_rows,
            state="readonly",
            width=18,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(r3, text="Timeout (s):").pack(side=tk.LEFT, padx=(4, 2))
        ttk.Entry(r3, textvariable=self.llm_timeout_var, width=6).pack(side=tk.LEFT)

        r4 = ttk.Frame(cfg_box)
        r4.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(r4, text="Chamadas simultâneas:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(r4, textvariable=self.llm_workers_var, width=4).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(r4, text="Triar por intervalo", variable=self.llm_by_interval_var).pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Label(r4, text="Máx. chamadas:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(r4, textvariable=self.llm_max_requests_var, width=6).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(r4, text="Máx. US$:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(r4, textvariable=self.llm_max_usd_var, width=6).pack(side=tk.LEFT)

        prompt_help = tk.StringVar(value=ROW_HELP.get(self.llm_prompt_var.get(), ""))
        self.llm_prompt_var.trace_add(
            "write", lambda *_: prompt_help.set(ROW_HELP.get(self.llm_prompt_var.get(), "")))
        ttk.Label(cfg_box, textvariable=prompt_help, foreground="gray").pack(anchor=tk.W, pady=(0, 3))


        # Row 4: Buttons for Save & Test
        r4 = ttk.Frame(cfg_box)
        r4.pack(fill=tk.X, pady=(6, 2))
        self.btn_test_api = ttk.Button(
            r4,
            text="Testar Conexão",
            command=self._on_test_llm_connection,
            width=20,
        )
        self.btn_test_api.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(
            r4,
            text="Salvar no .env",
            command=self._on_save_llm_config,
            width=18,
        ).pack(side=tk.LEFT)

        # Connection diagnostic box
        self.txt_api_test = scrolledtext.ScrolledText(parent, font=("Consolas", 9), height=3, wrap=tk.WORD)
        self.txt_api_test.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self._set_text(
            self.txt_api_test,
            "Pronto para testar a API LLM. A chave é obrigatória para prosseguir.",
        )

    # -------------------------------------------------------------------------
    # MODO GENÉRICO, TELA 1: PROJETO SOB ANÁLISE (C1 importado ou criado pelo assistente)
    # -------------------------------------------------------------------------

    def _build_setup_screen(self, parent: ttk.Frame) -> None:
        nav = ttk.Frame(parent)
        nav.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(nav, text="⌂ Início", command=lambda: self.show_screen("home")).pack(side=tk.LEFT)
        ttk.Label(nav, text="Analisar um projeto", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=10)

        # Group 1: the C1 configuration -- imported or made by the wizard, never typed
        input_box = ttk.LabelFrame(
            parent,
            text=" 1. Configuração do projeto (contrato C1) ",
            padding=10,
        )
        input_box.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            input_box,
            wraplength=900,
            justify=tk.LEFT,
            text="A configuração descreve o programa e o ambiente: fontes, tarefas, ISRs, prioridades, "
            "primitivas de mascaramento e semântica do processador. Importe um arquivo existente ou "
            "crie um pelo assistente — o arquivo não é editado à mão.",
        ).pack(anchor=tk.W, pady=(0, 6))

        r_yaml = ttk.Frame(input_box)
        r_yaml.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(r_yaml, text="Configuração:", width=22).pack(side=tk.LEFT)
        ttk.Entry(r_yaml, textvariable=self.yaml_path_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )

        r_btns = ttk.Frame(input_box)
        r_btns.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r_btns, text="", width=22).pack(side=tk.LEFT)
        ttk.Button(r_btns, text="Importar .yaml...", command=self._browse_yaml_file).pack(side=tk.LEFT)
        ttk.Button(
            r_btns, text="Criar com o assistente...", command=lambda: self._open_config_wizard(edit=False)
        ).pack(side=tk.LEFT, padx=4)
        self.btn_edit_wizard = ttk.Button(
            r_btns, text="Editar no assistente...", command=lambda: self._open_config_wizard(edit=True)
        )
        self.btn_edit_wizard.pack(side=tk.LEFT)
        ttk.Button(r_btns, text="Ver C1...", command=self._show_stage1_inputs_dialog).pack(
            side=tk.LEFT, padx=4
        )

        # Multi-file list row
        r_files = ttk.Frame(input_box)
        r_files.pack(fill=tk.X, pady=2)
        ttk.Label(r_files, text="Arquivos (.c / .h):", width=22).pack(side=tk.LEFT, anchor=tk.N, pady=2)

        list_frame = ttk.Frame(r_files)
        list_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.src_listbox = tk.Listbox(list_frame, height=6, font=("Consolas", 9), selectmode=tk.EXTENDED)
        src_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.src_listbox.yview)
        self.src_listbox.configure(yscrollcommand=src_scroll.set)
        self.src_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        src_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        btns_col = ttk.Frame(r_files)
        btns_col.pack(side=tk.LEFT)
        ttk.Button(
            btns_col, text="+ Arquivos...", width=16, command=self._add_source_files
        ).pack(side=tk.TOP, pady=1)
        ttk.Button(
            btns_col, text="+ Pasta...", width=16, command=self._add_source_folder
        ).pack(side=tk.TOP, pady=1)
        ttk.Button(
            btns_col, text="- Remover", width=16, command=self._remove_selected_sources
        ).pack(side=tk.TOP, pady=1)

        # Group 2: LLM summary (the settings live on their own screen)
        llm_box = ttk.LabelFrame(parent, text=" 2. LLM ", padding=10)
        llm_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(llm_box, textvariable=self.llm_header_summary_var).pack(side=tk.LEFT)
        ttk.Button(
            llm_box, text="Configurar LLM...", command=lambda: self.open_llm_settings(return_to="generic")
        ).pack(side=tk.RIGHT)

        # Bottom Bar: Advance to Screen 2
        bottom_bar = ttk.Frame(parent, padding=4)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.btn_proceed = ttk.Button(
            bottom_bar,
            text="Avançar para o Pipeline >>",
            command=self._on_proceed_to_pipeline,
        )
        self.btn_proceed.pack(side=tk.RIGHT, padx=4, ipady=4)

    def import_c1(self, path: Path) -> bool:
        """Load a C1 file into generic mode, refusing one the pipeline would refuse."""
        path = Path(path).resolve()
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ConfigError("o arquivo não contém um mapeamento YAML")
            files = resolve_c_source_files(raw, path)
            Config.from_dict(apply_source_list_to_c1_dict(resolve_source_root(raw, path), files), path=path)
        except Exception as e:
            messagebox.showerror(
                "Configuração inválida",
                f"{path}\n\nnão é uma configuração C1 válida:\n{e}\n\n"
                "Use 'Editar no assistente' depois de corrigir, ou crie uma nova pelo assistente.",
            )
            return False
        self.yaml_path_var.set(str(path))
        self.source_files_list = files
        self.stepper = None
        self._refresh_source_listbox()
        self._update_pipeline_header_info()
        return True

    def _open_config_wizard(self, *, edit: bool) -> None:
        yaml_str = self.yaml_path_var.get().strip()
        target = Path(yaml_str) if yaml_str else None
        if edit:
            if not target or not target.exists():
                messagebox.showinfo("Nada para editar", "Importe ou crie uma configuração primeiro.")
                return
            try:
                state = WizardState.from_c1(yaml.safe_load(target.read_text(encoding="utf-8")), target)
            except Exception as e:
                messagebox.showerror("Não foi possível abrir no assistente", str(e))
                return
        else:
            target = None
            state = WizardState(sources=list(self.source_files_list))
            if state.c_files:
                state.name = state.c_files[0].parent.name

        def _done(path: Path, sources: list[Path]) -> None:
            self.yaml_path_var.set(str(path))
            self.source_files_list = list(sources)
            self.stepper = None
            self._refresh_source_listbox()
            self._update_pipeline_header_info()
            self.status_var.set(f"Configuração salva em {path.name}. Avance para o Pipeline.")

        ConfigWizard(self.root, state, on_finish=_done, target=target)

    # -------------------------------------------------------------------------
    # TELA 2: VISÃO DO PIPELINE SENDO EXECUTADO (CONCISO, NÃO VERBOSO)
    # -------------------------------------------------------------------------

    def _build_pipeline_screen(self, parent: ttk.Frame) -> None:
        # Top Header Bar in Screen 2: Back button + Info
        nav_bar = ttk.Frame(parent, padding=(2, 2, 2, 4))
        nav_bar.pack(fill=tk.X)

        ttk.Button(
            nav_bar,
            text="⌂ Início",
            command=lambda: self.show_screen("home"),
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            nav_bar,
            text="<< Voltar",
            command=self._pipeline_back,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(
            nav_bar,
            textvariable=self.pipeline_header_info_var,
            font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Button(
            nav_bar,
            text="📄 Exportar PDF",
            command=self._on_export_pdf_report,
        ).pack(side=tk.RIGHT, padx=4)

        # Vertical PanedWindow so the workspace below can be expanded freely
        self.main_vpaned = ttk.PanedWindow(parent, orient=tk.VERTICAL)
        self.main_vpaned.pack(fill=tk.BOTH, expand=True)

        top_controls_pane = ttk.Frame(self.main_vpaned)
        bottom_workspace_pane = ttk.Frame(self.main_vpaned)
        self.main_vpaned.add(top_controls_pane, weight=0)
        self.main_vpaned.add(bottom_workspace_pane, weight=5)

        # Controls & Stage Blocks (BEM menos verboso!)
        ctrl_frame = ttk.Frame(top_controls_pane, padding=(2, 2, 2, 4))
        ctrl_frame.pack(fill=tk.X)

        self.btn_reset = ttk.Button(
            ctrl_frame, text="(RESET)", command=self._on_reset_run, width=11
        )
        self.btn_reset.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_step = ttk.Button(
            ctrl_frame, text="(STEP)", command=self._on_step_once, width=11
        )
        self.btn_step.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_resume = ttk.Button(
            ctrl_frame, text="(RESUME)", command=self._on_resume_run, width=11
        )
        self.btn_resume.pack(side=tk.LEFT, padx=(0, 4))
        # Alias for backward compatibility
        self.btn_auto = self.btn_resume

        self.btn_stop = ttk.Button(
            ctrl_frame, text="(STOP)", command=self._on_stop_run, width=11, state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 10))

        # Concise Stage Indicators
        self.step_labels: list[ttk.Label] = []
        steps_bar = ttk.Frame(ctrl_frame)
        steps_bar.pack(side=tk.RIGHT)
        short_names = [
            "1.Build",
            "2.Stage1",
            "3.Solver",
            "4.Contexto",
            "5.LLM Triagem",
            "6.LLM Reparo",
        ]
        for sname in short_names:
            lbl = ttk.Label(steps_bar, text=f"[ {sname} ]", relief=tk.GROOVE, padding=(3, 2))
            lbl.pack(side=tk.LEFT, padx=1)
            self.step_labels.append(lbl)

        # Progress indicators
        prog_frame = ttk.Frame(top_controls_pane, padding=(2, 2, 2, 4))
        prog_frame.pack(fill=tk.X)

        row_p1 = ttk.Frame(prog_frame)
        row_p1.pack(fill=tk.X, pady=1)
        ttk.Label(row_p1, text="Pipeline:", width=10).pack(side=tk.LEFT)
        self.progressbar = ttk.Progressbar(
            row_p1, variable=self.progress_var, maximum=len(PIPELINE_STEPS), mode="determinate", length=260
        )
        self.progressbar.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(row_p1, textvariable=self.status_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row_p2 = ttk.Frame(prog_frame)
        row_p2.pack(fill=tk.X, pady=1)
        ttk.Label(row_p2, text="API LLM:", width=10).pack(side=tk.LEFT)
        self.api_progressbar = ttk.Progressbar(
            row_p2, variable=self.api_progress_var, maximum=100.0, mode="determinate", length=260
        )
        self.api_progressbar.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(row_p2, textvariable=self.api_status_var, font=("Segoe UI", 9, "bold")).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # Workspace, as in an editor: candidates and their detail side by side,
        # with the inspection tabs in a panel below that can be resized or hidden.
        panel_bar = ttk.Frame(bottom_workspace_pane)
        panel_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.btn_toggle_panel = ttk.Button(
            panel_bar, text="▾ Recolher painel", width=18, command=self._toggle_bottom_panel
        )
        self.btn_toggle_panel.pack(side=tk.RIGHT)

        self.workspace_paned = ttk.PanedWindow(bottom_workspace_pane, orient=tk.VERTICAL)
        self.workspace_paned.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        self.main_paned = ttk.PanedWindow(self.workspace_paned, orient=tk.HORIZONTAL)
        self.workspace_paned.add(self.main_paned, weight=3)

        # Left pane: Candidates Table
        left_frame = ttk.Frame(self.main_paned, padding=(0, 0, 4, 0))
        self.main_paned.add(left_frame, weight=1)

        list_bar = ttk.Frame(left_frame)
        list_bar.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(list_bar, text="Candidatos (clique para inspecionar):").pack(side=tk.LEFT)
        ttk.Checkbutton(
            list_bar,
            text="Agrupar por variável",
            variable=self.group_by_variable_var,
            command=self._draw_candidate_rows,
        ).pack(side=tk.RIGHT)
        cols = ("id", "pattern", "var", "lines", "feas", "bucket", "repair")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        self._heading_titles = {
            "id": "ID",
            "pattern": "Padrão",
            "var": "Variável",
            "lines": "Acessos (A1, B, A2)",
            "feas": "Viabilidade",
            "bucket": "Grupo (Bucket)",
            "repair": "Reparo",
        }
        for col, title in self._heading_titles.items():
            self.tree.heading(col, text=title, command=lambda c=col: self._on_sort_column(c))

        self.tree.column("#0", width=28, stretch=False)
        self.tree.column("id", width=85, anchor=tk.W)
        self.tree.column("pattern", width=45, anchor=tk.CENTER)
        self.tree.column("var", width=110, anchor=tk.W)
        self.tree.column("lines", width=130, anchor=tk.CENTER)
        self.tree.column("feas", width=75, anchor=tk.CENTER)
        self.tree.column("bucket", width=100, anchor=tk.CENTER)
        self.tree.column("repair", width=80, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_candidate_selected)
        self.tree.bind("<<TreeviewOpen>>", self._on_group_toggled)
        self.tree.bind("<<TreeviewClose>>", self._on_group_toggled)

        # Right pane: where each access of the selected candidate is
        right_frame = ttk.Frame(self.main_paned, padding=(4, 0, 0, 0))
        self.main_paned.add(right_frame, weight=1)
        ttk.Label(right_frame, text="Detalhe do candidato:").pack(anchor=tk.W, pady=(0, 2))
        self.txt_detail = scrolledtext.ScrolledText(right_frame, font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        self.txt_detail.pack(fill=tk.BOTH, expand=True)
        self.txt_detail.tag_configure("title", foreground="#004085", font=("Segoe UI", 10, "bold"))
        self.txt_detail.tag_configure("access", font=("Consolas", 9, "bold"), spacing1=6)
        self.txt_detail.tag_configure("marked", background="#fff3cd", font=("Consolas", 9, "bold"))

        # Bottom panel: Unified Inspection Tabs (Log, Triage, Repair, Source, Turns)
        self.bottom_panel = ttk.Frame(self.workspace_paned, padding=(0, 2, 0, 0))
        self.workspace_paned.add(self.bottom_panel, weight=2)

        self.notebook = ttk.Notebook(self.bottom_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Real-time Execution Log (Large & Expandable)
        self.tab_live_log = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(self.tab_live_log, text=" Log ")
        log_toolbar = ttk.Frame(self.tab_live_log)
        log_toolbar.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(
            log_toolbar,
            text="Saída do Pipeline:",
        ).pack(side=tk.LEFT)
        ttk.Button(log_toolbar, text="Exportar PDF", width=12, command=self._on_export_pdf_report).pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        ttk.Button(log_toolbar, text="Limpar", width=8, command=self._clear_live_log).pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        ttk.Button(log_toolbar, text="Copiar", width=8, command=self._copy_live_log).pack(
            side=tk.RIGHT
        )
        self.log_text = scrolledtext.ScrolledText(
            self.tab_live_log, font=("Consolas", 10), wrap=tk.WORD, state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Tab 2: LLM Triage & Reasoning
        self.tab_triage = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(self.tab_triage, text=" Triagem ")
        self.txt_triage = scrolledtext.ScrolledText(self.tab_triage, font=("Consolas", 9), wrap=tk.WORD)
        self.txt_triage.pack(fill=tk.BOTH, expand=True)

        # Tab 3: LLM Repair Patch & Witness (com destaque Git e botão de aplicação direta)
        self.tab_repair = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(self.tab_repair, text=" Correção (Diff) ")

        rep_toolbar = ttk.Frame(self.tab_repair)
        rep_toolbar.pack(fill=tk.X, pady=(0, 4))

        self.btn_apply_patch = ttk.Button(
            rep_toolbar,
            text="✔ Aplicar Correção",
            command=self._on_apply_selected_patch,
            state=tk.DISABLED,
        )
        self.btn_apply_patch.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_revert_patch = ttk.Button(
            rep_toolbar,
            text="↺ Reverter (.bak)",
            command=self._on_revert_selected_patch,
            state=tk.DISABLED,
        )
        self.btn_revert_patch.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_patch_status = ttk.Label(
            rep_toolbar,
            text="Selecione um candidato para inspecionar e aplicar o patch.",
            font=("Segoe UI", 9, "italic"),
        )
        self.lbl_patch_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Prose wraps, code does not: the same widget cannot do both.
        repair_paned = ttk.PanedWindow(self.tab_repair, orient=tk.VERTICAL)
        repair_paned.pack(fill=tk.BOTH, expand=True)
        self.txt_repair = scrolledtext.ScrolledText(repair_paned, font=("Consolas", 9), wrap=tk.WORD, height=10)
        repair_paned.add(self.txt_repair, weight=1)
        self._configure_diff_tags(self.txt_repair)

        diff_frame = ttk.Frame(repair_paned)
        repair_paned.add(diff_frame, weight=2)
        diff_hbar = ttk.Scrollbar(diff_frame, orient=tk.HORIZONTAL)
        diff_hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_diff = scrolledtext.ScrolledText(
            diff_frame, font=("Consolas", 9), wrap=tk.NONE, height=10, xscrollcommand=diff_hbar.set
        )
        self.txt_diff.pack(fill=tk.BOTH, expand=True)
        diff_hbar.configure(command=self.txt_diff.xview)
        self._configure_diff_tags(self.txt_diff)

        # Tab 4: C/H Source Files & Static Context C2
        self.tab_source = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(self.tab_source, text=" Código Fonte ")
        src_top = ttk.Frame(self.tab_source)
        src_top.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(src_top, text="Arquivo:").pack(side=tk.LEFT, padx=(0, 4))
        self.src_view_cb = ttk.Combobox(
            src_top, textvariable=self.selected_source_view_var, state="readonly", width=50
        )
        self.src_view_cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.src_view_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_candidate_selected())
        self.txt_source = scrolledtext.ScrolledText(self.tab_source, font=("Consolas", 9), wrap=tk.NONE)
        self.txt_source.pack(fill=tk.BOTH, expand=True)

        # Tab 5: Full LLM Conversation Transcript (Turns)
        self.tab_turns = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(self.tab_turns, text=" Histórico LLM ")
        self.txt_turns = scrolledtext.ScrolledText(self.tab_turns, font=("Consolas", 9), wrap=tk.WORD)
        self.txt_turns.pack(fill=tk.BOTH, expand=True)
        self._configure_history_tags(self.txt_turns)

        self._tabs = {
            "log": (self.tab_live_log, "Log"),
            "triage": (self.tab_triage, "Triagem"),
            "repair": (self.tab_repair, "Correção (Diff)"),
            "source": (self.tab_source, "Código Fonte"),
            "history": (self.tab_turns, "Histórico LLM"),
        }
        self._show_tab_states({})

    def _toggle_bottom_panel(self) -> None:
        if str(self.bottom_panel) in map(str, self.workspace_paned.panes()):
            self.workspace_paned.forget(self.bottom_panel)
            self.btn_toggle_panel.configure(text="▴ Mostrar painel")
        else:
            self.workspace_paned.add(self.bottom_panel, weight=2)
            self.btn_toggle_panel.configure(text="▾ Recolher painel")

    def _tab_image(self, state: str) -> tk.PhotoImage:
        """A coloured square: a ttk tab has no per-tab text colour."""
        if state not in self._tab_images:
            image = tk.PhotoImage(master=self.root, width=9, height=9)
            image.put(COLOURS[state], to=(0, 0, 9, 9))
            self._tab_images[state] = image
        return self._tab_images[state]

    def _show_tab_states(self, states: dict[str, str]) -> None:
        for key, (tab, title) in self._tabs.items():
            state = states.get(key, "idle")
            self.notebook.tab(tab, text=f" {SYMBOLS[state]} {title} ", image=self._tab_image(state), compound=tk.LEFT)

    def _on_proceed_to_pipeline(self) -> bool:
        yaml_str = self.yaml_path_var.get().strip()
        yaml_p = Path(yaml_str) if yaml_str else None
        if not yaml_p or not yaml_p.exists():
            messagebox.showerror(
                "Configuração Obrigatória",
                "Importe uma configuração C1 (.yaml) ou crie uma pelo assistente antes de avançar."
                + (f"\n\nArquivo atual: {yaml_str}" if yaml_str else ""),
            )
            return False

        if not self.source_files_list:
            messagebox.showerror(
                "Arquivos C/Header Obrigatórios",
                "Por favor, adicione pelo menos um arquivo .c ou pasta do projeto antes de avançar.",
            )
            return False

        adapter = self.llm_adapter_var.get().strip() or "openai"
        base_url = self.llm_base_url_var.get().strip()
        api_key = self.llm_api_key_var.get().strip()
        model = self.llm_model_var.get().strip()

        # LLM Configuration is MANDATORY
        if adapter in ("openai", "anthropic") and not api_key:
            messagebox.showerror(
                "Configuração de LLM Obrigatória",
                "A configuração da LLM é OBRIGATÓRIA!\n\n"
                "Por favor, preencha a chave de API (API Key) para prosseguir (ex.: chave Groq ou OpenAI).\n"
                "Se precisar de uma chave gratuita da Groq, gere em https://console.groq.com/keys",
            )
            return False

        if not model or (not base_url and adapter != "claude-cli"):
            messagebox.showerror(
                "Configuração de LLM Obrigatória",
                "Por favor, informe a URL do endpoint e o Modelo da LLM.",
            )
            return False

        # Persist settings to .env
        save_dotenv_settings({
            "IRQRACE_LLM_PRESET": self.llm_preset_var.get().strip(),
            "IRQRACE_LLM_ADAPTER": adapter,
            "IRQRACE_LLM_MODEL": model,
            "IRQRACE_OPENAI_BASE_URL": base_url,
            "IRQRACE_OPENAI_API_KEY": api_key,
            "OPENAI_API_KEY": api_key,
            "IRQRACE_LLM_PROMPT": self.llm_prompt_var.get().strip(),
            "IRQRACE_LLM_TIMEOUT": self.llm_timeout_var.get().strip(),
            **self._triage_env(),
        })
        self.use_live_llm_var.set(True)
        self._update_pipeline_header_info()
        self._update_llm_header_summary()

        # Switch to Screen 2
        self._pipeline_origin = "generic"
        self.top_notebook.select(self.tab_pipeline)
        return True

    def _update_pipeline_header_info(self) -> None:
        yaml_str = getattr(self, "yaml_path_var", None) and self.yaml_path_var.get().strip()
        case_name = Path(yaml_str).stem if yaml_str and Path(yaml_str).exists() else "Sem configuração"
        model = getattr(self, "llm_model_var", None) and self.llm_model_var.get().strip() or "openai/gpt-oss-120b"
        adapter = getattr(self, "llm_adapter_var", None) and self.llm_adapter_var.get().strip() or "openai"
        url = getattr(self, "llm_base_url_var", None) and self.llm_base_url_var.get().strip() or ""
        host = "Groq" if "groq.com" in url else ("OpenAI" if "openai.com" in url else adapter)
        n_files = len(getattr(self, "source_files_list", []))
        if hasattr(self, "pipeline_header_info_var"):
            self.pipeline_header_info_var.set(
                f"Caso: {case_name} | {n_files} arquivo(s) .c/.h | LLM: {host} ({model})"
            )

    def _on_llm_preset_changed(self, _event=None) -> None:
        preset_name = self.llm_preset_var.get()
        info = LLM_PROVIDER_PRESETS.get(preset_name)
        if not info:
            return
        self.llm_adapter_var.set(info["adapter"])
        self.llm_base_url_var.set(info["base_url"])
        models = info["models"]
        self.model_cb.configure(values=models)
        if models:
            self.llm_model_var.set(models[0])
        self._update_llm_header_summary()

    def _update_llm_header_summary(self) -> None:
        mode_txt = "API Real (Online)" if self.use_live_llm_var.get() else "Sem LLM (Offline)"
        adapter = self.llm_adapter_var.get()
        model = self.llm_model_var.get()
        url = self.llm_base_url_var.get()
        host = "Groq" if "groq.com" in url else ("OpenAI/ChatGPT" if "openai.com" in url else url)
        self.llm_header_summary_var.set(
            f"LLM: {host} ({adapter}:{model}) | Modo: {mode_txt}")
        self._update_pipeline_header_info()

    def _on_save_llm_config(self) -> None:
        preset = self.llm_preset_var.get().strip()
        adapter = self.llm_adapter_var.get().strip()
        base_url = self.llm_base_url_var.get().strip()
        api_key = self.llm_api_key_var.get().strip()
        model = self.llm_model_var.get().strip()
        prompt = self.llm_prompt_var.get().strip()
        timeout = self.llm_timeout_var.get().strip()

        settings = {
            "IRQRACE_LLM_PRESET": preset,
            "IRQRACE_LLM_ADAPTER": adapter,
            "IRQRACE_LLM_MODEL": model,
            "IRQRACE_OPENAI_BASE_URL": base_url,
            "IRQRACE_OPENAI_API_KEY": api_key,
            "OPENAI_API_KEY": api_key,
            "IRQRACE_LLM_PROMPT": prompt,
            "IRQRACE_LLM_TIMEOUT": timeout,
            **self._triage_env(),
        }
        save_dotenv_settings(settings)
        self._update_llm_header_summary()
        key_masked = (
            ("*" * (len(api_key) - 4) + api_key[-4:])
            if len(api_key) >= 4
            else ("(vazia)" if not api_key else "****")
        )
        messagebox.showinfo(
            "Configuração Salva",
            f"Configuração de LLM salva com sucesso!\n\n"
            f"Arquivos sincronizados:\n- {WORKSPACE_ENV_FILE}\n- {ENV_FILE}\n\n"
            f"Provedor: {preset}\nAdaptador: {adapter}\nBase URL: {base_url}\nModelo: {model}\nAPI Key: {key_masked}",
        )

    def _on_test_llm_connection(self) -> None:
        adapter = self.llm_adapter_var.get().strip()
        base_url = self.llm_base_url_var.get().strip()
        api_key = self.llm_api_key_var.get().strip()
        model = self.llm_model_var.get().strip()
        try:
            timeout_s = float(self.llm_timeout_var.get().strip() or "60")
        except ValueError:
            timeout_s = 60.0

        self.btn_test_api.configure(state=tk.DISABLED)
        self._set_text(
            self.txt_api_test,
            f"Testando conexão com {adapter}:{model} em {base_url}...\nAguarde resposta do endpoint...",
        )

        def _worker():
            t0 = time.perf_counter()
            try:
                backend = build_backend_from_config(adapter, model, base_url, api_key, timeout_s=timeout_s)
                req = ChatRequest(
                    system="You are a concise assistant for the irqrace static analyzer.",
                    messages=[{"role": "user", "content": "Reply with 'OK' and the name of your model in one short line."}],
                    max_tokens=64,
                    temperature=0.0,
                )
                resp = backend.chat(req)
                dt = (time.perf_counter() - t0) * 1000
                report = (
                    f"✔ CONEXÃO BEM-SUCEDIDA ({dt:.0f} ms)\n"
                    f"============================================================\n"
                    f"Especificação:       {backend.spec}\n"
                    f"Endpoint Base URL:   {base_url}\n"
                    f"Saída Estruturada:   {backend.capabilities.structured.value}\n"
                    f"Tokens (in / out):   {resp.usage.input_tokens} in / {resp.usage.output_tokens} out\n"
                    f"Resposta do Modelo:  {resp.text.strip()}\n"
                )
                self.log_queue.put(("api_test_done", report))
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                report = (
                    f"✖ FALHA NA CONEXÃO ({dt:.0f} ms)\n"
                    f"============================================================\n"
                    f"Endpoint Base URL:   {base_url}\n"
                    f"Modelo:              {adapter}:{model}\n"
                    f"Erro detalhado:\n{e}\n"
                )
                self.log_queue.put(("api_test_done", report))

        threading.Thread(target=_worker, daemon=True).start()

    # -------------------------------------------------------------------------
    # Multi-file C / H List Management
    # -------------------------------------------------------------------------

    def _refresh_source_listbox(self) -> None:
        self.src_listbox.delete(0, tk.END)
        display_paths: list[str] = []
        for p in self.source_files_list:
            self.src_listbox.insert(tk.END, str(p))
            display_paths.append(str(p))
        self.src_view_cb.configure(values=display_paths)
        if display_paths and self.selected_source_view_var.get() not in display_paths:
            self.selected_source_view_var.set(display_paths[0])
        elif not display_paths:
            self.selected_source_view_var.set("")

    def _add_source_files(self) -> None:
        initial_dir = locate_suite() or REPO_ROOT
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="Selecionar um ou mais arquivos C / Header (.c, .h)",
            initialdir=str(initial_dir),
            filetypes=[("Arquivos C e Headers", "*.c *.h *.hpp"), ("Todos os arquivos", "*.*")],
        )
        if not paths:
            return
        seen = {p.resolve() for p in self.source_files_list}
        for p_str in paths:
            rp = Path(p_str).resolve()
            if rp not in seen:
                seen.add(rp)
                self.source_files_list.append(rp)
        self.stepper = None
        self._refresh_source_listbox()
        self._append_log(f"Lista atualizada ({len(self.source_files_list)} arquivos .c/.h). Próxima execução compilará os novos arquivos.")

    def _add_source_folder(self) -> None:
        suite = locate_suite()
        initial_dir = suite.parent if suite else REPO_ROOT
        folder = filedialog.askdirectory(
            parent=self.root,
            title="Selecionar pasta do projeto contendo arquivos .c, .h e opcionalmente .yaml",
            initialdir=str(initial_dir),
        )
        if not folder:
            return
        self.load_project_folder(Path(folder))

    def load_project_folder(self, folder_path: Path) -> None:
        folder_path = folder_path.resolve()
        new_files: list[Path] = []
        seen: set[Path] = set()
        for ext in ("*.c", "*.h"):
            for fp in sorted(folder_path.rglob(ext)):
                rfp = fp.resolve()
                if rfp not in seen:
                    seen.add(rfp)
                    new_files.append(rfp)

        self.source_files_list = new_files
        self.stepper = None

        # Auto-detect any .yaml / .yml inside the selected folder
        yaml_candidates = sorted(list(folder_path.glob("*.yaml")) + list(folder_path.glob("*.yml")))
        if not yaml_candidates:
            yaml_candidates = sorted(list(folder_path.rglob("*.yaml")) + list(folder_path.rglob("*.yml")))
        if yaml_candidates:
            self.yaml_path_var.set(str(yaml_candidates[0].resolve()))

        self._refresh_source_listbox()
        self._update_pipeline_header_info()
        self._append_log(
            f"\n[Nova Pasta Carregada] {folder_path}\n"
            f"  -> {len(new_files)} arquivo(s) .c/.h definidos na lista: {[p.name for p in new_files]}\n"
            f"  -> YAML C1 ativo: {self.yaml_path_var.get()}"
        )
        self.status_var.set(
            f"Pasta carregada ({len(new_files)} arquivos .c/.h). Use (STEP) ou (RESUME) para executar o pipeline."
        )

    def _remove_selected_sources(self) -> None:
        sel = list(self.src_listbox.curselection())
        if not sel:
            return
        for idx in reversed(sel):
            if 0 <= idx < len(self.source_files_list):
                self.source_files_list.pop(idx)
        self.stepper = None
        self._refresh_source_listbox()

    # -------------------------------------------------------------------------
    # Event handlers & Preset/YAML selection
    # -------------------------------------------------------------------------

    def _append_log(self, msg: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_live_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _copy_live_log(self) -> None:
        content = self.log_text.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_var.set("Log copiado para a área de transferência.")

    def _browse_yaml_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Importar configuração C1 (.yaml)",
            initialdir=str(Path.home()),
            filetypes=[("Configuração YAML (C1)", "*.yaml *.yml"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.import_c1(Path(path))

    def _show_stage1_inputs_dialog(self) -> None:
        yaml_p = Path(self.yaml_path_var.get())
        if not yaml_p.exists():
            messagebox.showerror("Arquivo não encontrado", f"O arquivo YAML não existe:\n{yaml_p}")
            return
        win = tk.Toplevel(self.root)
        win.title(f"Dados Fornecidos à 1ª Etapa — {yaml_p.name}")
        win.geometry("780x580")
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10), wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        raw_text = yaml_p.read_text(encoding="utf-8")
        try:
            raw_dict = apply_source_list_to_c1_dict(yaml.safe_load(raw_text), self.source_files_list)
            cfg = Config.from_dict(raw_dict, path=yaml_p)
            flows_summary = "\n".join(
                f"  - id={f.id:<8} kind={f.kind:<5} entry={f.entry:<28} irq={str(f.irq):<4} priority={f.priority}"
                for f in cfg.flows
            )
            prims_summary = "\n".join(
                f"  - function={p.function:<15} effect={p.effect:<8} irq_arg={p.irq_arg} all_value={p.all_value}"
                for p in cfg.masking_primitives
            )
            files_summary = "\n".join(f"  - [{p.suffix}] {p}" for p in self.source_files_list)
            header = (
                "=== RESUMO DOS DADOS DE ENTRADA DA 1ª ETAPA (CONTRATO C1) ===\n"
                f"1. Programa / Sujeito: {cfg.name}\n"
                f"2. Lista de Arquivos (.c e .h) ({len(self.source_files_list)} arquivos):\n{files_summary}\n"
                f"3. Diretórios de Include (-I): {cfg.build.get('include_dirs', [])}\n"
                f"4. Convenção de Prioridade: {cfg.data.get('priority_convention')} (maior número = maior prioridade)\n"
                f"5. Fluxos de Execução (Tasks + ISRs):\n{flows_summary}\n"
                f"6. Primitivas de Mascaramento de IRQ:\n{prims_summary}\n"
                f"7. Semântica do Processador: {json.dumps(cfg.semantics, ensure_ascii=False)}\n"
                "=============================================================\n\n"
                "--- Conteúdo Completo do YAML (Contrato C1) ---\n"
            )
        except Exception as e:
            header = f"Erro ao validar YAML: {e}\n\n"

        txt.insert(tk.END, header + raw_text)
        txt.configure(state=tk.DISABLED)

    # -------------------------------------------------------------------------
    # Pipeline Step-by-Step and Automatic Execution
    # -------------------------------------------------------------------------

    def _create_stepper(self) -> PipelineStepper | None:
        yaml_str = self.yaml_path_var.get().strip()
        yaml_p = Path(yaml_str)
        if not yaml_str or not yaml_p.exists():
            messagebox.showerror("Erro", "Importe ou crie a configuração do projeto primeiro.")
            return None
        try:
            return PipelineStepper(
                yaml_p,
                list(self.source_files_list),
                use_live_llm=self.use_live_llm_var.get(),
                event_cb=lambda k, p: self.log_queue.put(("api_event", (k, p))),
                **self._llm_kwargs(),
            )
        except (ConfigError, Exception) as e:
            messagebox.showerror("Erro na Configuração C1", str(e))
            return None

    def _on_reset_run(self) -> None:
        if self.is_running_async:
            return
        stepper = self._create_stepper()
        if not stepper:
            return
        self.stepper = stepper
        store = self.stepper.init_run()
        self.notebook.select(self.tab_live_log)
        self._clear_live_log()
        self.api_progress_var.set(0.0)
        self.api_status_var.set("API LLM: Pronta para iniciar.")
        self._append_log(f"Nova execução preparada em: {store.root}")
        self._append_log(f"  Arquivos (.c/.h): {len(self.source_files_list)} arquivo(s) na lista")
        self._append_log(f"  Arquivo YAML:     {self.yaml_path_var.get()}")
        self._append_log("Clique em '2. Avançar Próxima Etapa >' ou '3. Executar Tudo Automaticamente >>'.\n")
        self._refresh_from_store(store)

    def _on_step_once(self) -> None:
        if self.is_running_async:
            return
        if self.stepper is None or self.stepper.store is None or self.stepper.current_step_idx >= len(PIPELINE_STEPS):
            stepper = self._create_stepper()
            if not stepper:
                return
            self.stepper = stepper
            self.stepper.init_run()
            self._append_log(f"Iniciando nova execução passo a passo: {self.stepper.store.root}")

        self.notebook.select(self.tab_live_log)
        self._set_buttons_state(tk.DISABLED)
        threading.Thread(target=self._worker_run_steps, args=(1,), daemon=True).start()

    def _on_run_all_auto(self) -> None:
        self._on_resume_run()

    def _on_resume_run(self) -> None:
        if self.is_running_async:
            return
        if self.stepper is None or self.stepper.store is None or self.stepper.current_step_idx >= len(PIPELINE_STEPS):
            stepper = self._create_stepper()
            if not stepper:
                return
            self.stepper = stepper
            self.stepper.init_run()
            self._append_log(f"Iniciando nova execução do pipeline: {self.stepper.store.root}")

        self.notebook.select(self.tab_live_log)
        remaining = len(PIPELINE_STEPS) - self.stepper.current_step_idx
        self.stop_requested = False
        self._set_buttons_state(tk.DISABLED)
        threading.Thread(target=self._worker_run_steps, args=(remaining,), daemon=True).start()

    def _on_stop_run(self) -> None:
        if not self.is_running_async:
            return
        self.stop_requested = True
        if self.stepper:
            self.stepper.request_stop()
        self.status_var.set("⏹ Interrupção solicitada pelo usuário...")
        self.api_status_var.set("⏹ Interrompendo execução mid-block...")
        self._append_log("⏹ [STOP] Interrupção imediata solicitada pelo usuário...")

    def _worker_run_steps(self, count: int) -> None:
        self.is_running_async = True
        self.stop_requested = False
        try:
            for _ in range(count):
                if self.stop_requested:
                    self.log_queue.put(("log", "⏹ Execução interrompida pelo usuário."))
                    break
                if self.stepper is None or self.stepper.current_step_idx >= len(PIPELINE_STEPS):
                    break
                step_idx = self.stepper.current_step_idx
                step_key, step_title = PIPELINE_STEPS[step_idx]
                self.log_queue.put(("status", f"Executando {step_title}..."))
                if step_key not in ("triage", "repair"):
                    self.log_queue.put(
                        ("api_stage_status", f"Processando localmente: {step_title}...")
                    )
                self.stepper.run_next_step(log_fn=lambda m: self.log_queue.put(("log", m)))
                self.log_queue.put(("refresh", None))
                if self.stop_requested:
                    self.log_queue.put(("log", "⏹ Execução interrompida após término do bloco."))
                    break
                if count > 1:
                    time.sleep(0.18)
            self.log_queue.put(("done", None))
        except InterruptedError:
            self.log_queue.put(("log", "⏹ Execução interrompida imediatamente no meio do bloco."))
            self.log_queue.put(("refresh", None))
            self.log_queue.put(("done", None))
        except Exception as e:
            self.log_queue.put(("refresh", None))
            self.log_queue.put(("error", str(e)))
        finally:
            self.is_running_async = False

    def _handle_api_event(self, ev_kind: str, data: dict[str, Any]) -> None:
        if ev_kind == "api_candidate_progress":
            self.api_stage_label = str(data.get("stage", "LLM"))
            self.api_cand_current = int(data.get("current", 0))
            self.api_cand_total = max(int(data.get("total", 1)), 1)
            self.api_cand_cid = str(data.get("cid", ""))
            self.api_cand_var = str(data.get("var", ""))
            st = data.get("status", "running")
            pct = (self.api_cand_current / self.api_cand_total) * 100.0
            self.api_progress_var.set(pct)
            if st == "done":
                self.api_call_active = False
                self.api_rate_limited = False
                self.api_status_var.set(
                    f"✔ {self.api_stage_label}: Candidato {self.api_cand_current}/{self.api_cand_total} concluído "
                    f"({self.api_cand_cid} - '{self.api_cand_var}') | Tokens acumulados: "
                    f"{self.api_tokens_in_total} in / {self.api_tokens_out_total} out"
                )
                if self.stepper and self.stepper.store:
                    self._refresh_from_store(self.stepper.store)
            else:
                self.api_status_var.set(
                    f"⏳ {self.api_stage_label} [{self.api_cand_current + 1}/{self.api_cand_total}]: "
                    f"Analisando {self.api_cand_cid} ('{self.api_cand_var}')..."
                )
        elif ev_kind == "api_request_start":
            self.api_call_active = True
            self.api_rate_limited = False
            self.api_req_started_t = time.perf_counter()
        elif ev_kind == "api_rate_limit_wait":
            self.api_rate_limited = True
            wait_s = float(data.get("wait_s", 0.0))
            att = int(data.get("attempt", 1))
            max_r = int(data.get("max_retries", 6))
            self.api_status_var.set(
                f"⚠️ Rate-Limit da API (HTTP 429) — Aguardando {wait_s:.1f}s para liberar cota "
                f"(tentativa {att}/{max_r})..."
            )
        elif ev_kind == "api_rate_limit_tick":
            self.api_rate_limited = True
            rem = float(data.get("remaining_s", 0.0))
            tot = max(float(data.get("total_s", 1.0)), 0.1)
            att = int(data.get("attempt", 1))
            max_r = int(data.get("max_retries", 6))
            waited_pct = max(0.0, min(100.0, ((tot - rem) / tot) * 100.0))
            self.api_progress_var.set(waited_pct)
            cand_tag = (
                f"[{self.api_cand_current + 1}/{self.api_cand_total}] " if self.api_cand_total > 0 else ""
            )
            self.api_status_var.set(
                f"⚠️ Rate-Limit da API (429) {cand_tag}— Aguardando liberação de tokens: "
                f"faltam {rem:.1f}s de {tot:.0f}s ({waited_pct:.0f}% da espera, tentativa {att}/{max_r})"
            )
        elif ev_kind == "api_request_done":
            self.api_call_active = False
            self.api_rate_limited = False
            el = float(data.get("elapsed_s", 0.0))
            in_tok = int(data.get("in_tokens", 0))
            out_tok = int(data.get("out_tokens", 0))
            self.api_tokens_in_total += in_tok
            self.api_tokens_out_total += out_tok
            cand_tag = (
                f"[{self.api_cand_current + 1}/{self.api_cand_total}] " if self.api_cand_total > 0 else ""
            )
            self.api_status_var.set(
                f"✔ Resposta recebida em {el:.1f}s {cand_tag}({in_tok} in / {out_tok} out tokens | "
                f"Total: {self.api_tokens_in_total} in / {self.api_tokens_out_total} out)"
            )

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "api_stage_status":
                    if not self.api_call_active and not self.api_rate_limited:
                        self.api_status_var.set(str(payload))
                elif kind == "api_event":
                    ev_kind, ev_data = payload
                    self._handle_api_event(ev_kind, ev_data)
                elif kind == "refresh":
                    if self.stepper and self.stepper.store:
                        self._refresh_from_store(self.stepper.store)
                elif kind == "done":
                    self.api_call_active = False
                    self.api_rate_limited = False
                    self.api_progress_var.set(100.0)
                    self._set_buttons_state(tk.NORMAL)
                    if self.stepper and self.stepper.store:
                        self._refresh_from_store(self.stepper.store)
                        done_c = int(self.progress_var.get())
                        if done_c >= len(PIPELINE_STEPS):
                            self.api_status_var.set(
                                f"✔ Pipeline e API concluídos (6/6 etapas | Tokens totais: "
                                f"{self.api_tokens_in_total} in / {self.api_tokens_out_total} out)."
                            )
                elif kind == "api_test_done":
                    self.btn_test_api.configure(state=tk.NORMAL)
                    self._set_text(self.txt_api_test, str(payload))
                elif kind == "error":
                    self.api_call_active = False
                    self.api_rate_limited = False
                    self._set_buttons_state(tk.NORMAL)
                    self._append_log(f"[ERRO] {payload}")
                    self.status_var.set(f"Erro: {payload}")
                    self.api_status_var.set(f"✖ Interrompido por erro: {str(payload)[:90]}")
                    messagebox.showerror("Erro durante execução", str(payload))
        except queue.Empty:
            pass

        # Animate the API Loading Bar and live elapsed clock while waiting for an HTTP response
        if self.api_call_active and not self.api_rate_limited:
            elapsed = time.perf_counter() - self.api_req_started_t
            self.api_pulse_phase = (self.api_pulse_phase + 4.5) % 100.0
            if self.api_cand_total > 0:
                base_pct = (self.api_cand_current / self.api_cand_total) * 100.0
                slice_pct = (1.0 / self.api_cand_total) * 100.0
                sub_fill = min(0.92, (elapsed / 12.0)) * slice_pct
                self.api_progress_var.set(min(99.0, base_pct + sub_fill))
            else:
                self.api_progress_var.set(self.api_pulse_phase)

            spinner = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")[
                int(elapsed * 8) % 10
            ]
            cand_tag = (
                f"[Candidato {self.api_cand_current + 1}/{self.api_cand_total}: {self.api_cand_cid}] "
                if self.api_cand_total > 0
                else ""
            )
            model_name = self.llm_model_var.get()
            self.api_status_var.set(
                f"{spinner} API Respondendo ({ self.api_stage_label }) {cand_tag}— "
                f"Aguardando {model_name}... [⏱ {elapsed:.1f}s decorridos]"
            )

        self.root.after(80, self._poll_queue)

    def _set_buttons_state(self, state: str) -> None:
        if state == tk.DISABLED:
            self.btn_reset.configure(state=tk.DISABLED)
            self.btn_step.configure(state=tk.DISABLED)
            self.btn_resume.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)
        else:
            self.btn_reset.configure(state=tk.NORMAL)
            self.btn_step.configure(state=tk.NORMAL)
            self.btn_resume.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)

    # -------------------------------------------------------------------------
    # Loading RunStore State into the UI
    # -------------------------------------------------------------------------

    def _load_run_into_ui(self, run_dir: Path, *, note: str = "") -> None:
        stepper = self._create_stepper()
        if stepper:
            self.stepper = stepper
            self.stepper.load_existing_run(run_dir)
        store = RunStore(run_dir)
        if note:
            self._append_log(note)
        self._refresh_from_store(store)

    def _refresh_from_store(self, store: RunStore) -> None:
        manifest = store.read_manifest()
        stages_map = {s["name"]: s for s in manifest.get("stages", [])}

        done_count = 0
        short_names = [
            "1.Build",
            "2.Stage1",
            "3.Solver",
            "4.Contexto",
            "5.LLM Triagem",
            "6.LLM Reparo",
        ]
        for idx, (skey, _) in enumerate(PIPELINE_STEPS):
            st = stages_map.get(skey, {}).get("status", "pending")
            if st == "ok":
                done_count += 1
                mark = "✔"
            elif st == "running":
                mark = "⏳"
            elif st == "failed":
                mark = "✖"
            else:
                mark = "○"
            self.step_labels[idx].configure(text=f"{mark} {short_names[idx]}")

        self._run_stages = {name: s.get("status", "pending") for name, s in stages_map.items()}
        self.progress_var.set(float(done_count))
        if self._live_run is not None:
            self.status_var.set(f"Ao vivo: {done_count}/6 etapas concluídas.")
        elif done_count == 0:
            self.status_var.set("0/6 etapas concluídas. Clique em '2. Avançar Próxima Etapa >' para começar.")
        elif done_count < len(PIPELINE_STEPS):
            next_title = PIPELINE_STEPS[done_count][1]
            self.status_var.set(f"Progresso: {done_count}/6 etapas concluídas. Próxima: {next_title}")
        else:
            self.status_var.set(
                "Concluído (6/6 etapas). Selecione um candidato abaixo para ver o que a LLM fez e a correção."
            )

        self._populate_candidates_table(store)

    def _populate_candidates_table(self, store: RunStore) -> None:
        s1_cands = {c["id"]: c for c in store.read_candidates("stage1")}
        ctx_dir = store.root / "context"
        ctx_cands = {}
        if ctx_dir.exists():
            for p in sorted(ctx_dir.glob("*.json")):
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    ctx_cands[doc["id"]] = doc
                except Exception:
                    pass

        solver_map: dict[str, dict[str, Any]] = {}
        solver_file = store.root / "solver" / "results.jsonl"
        if solver_file.exists():
            for line in solver_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    solver_map[r["candidate_id"]] = r

        # Stage 2's drops, each with its proof. Without this a candidate stage 2
        # discarded would read as "pendente", as if it were still waiting.
        drop_map = {d["candidate_id"]: d for d in store.read_drops()}

        triage_map: dict[str, dict[str, Any]] = {}
        triage_file = store.root / "llm" / "triage.jsonl"
        if triage_file.exists():
            for line in triage_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    triage_map[d["candidate_id"]] = d

        repair_map: dict[str, dict[str, Any]] = {}
        repair_root = store.root / "repair"
        if repair_root.exists():
            for p in sorted(repair_root.glob("*/patch.json")):
                try:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    repair_map[p.parent.name] = d
                except Exception:
                    pass

        # A live view redraws under a reader: keep what they were looking at.
        kept = next(iter(self.tree.selection()), None) if self._live_run is not None else None
        self.candidates_data.clear()
        self.candidate_rows = []

        all_ids = list(triage_map.keys()) + [cid for cid in s1_cands if cid not in triage_map]

        for cid in all_ids:
            rec = ctx_cands.get(cid) or s1_cands.get(cid) or {}
            accs = rec.get("accesses", [])
            lines_str = access_locations(accs)
            pat = rec.get("pattern", "?")
            variable = rec.get("variable", {})

            t_doc = triage_map.get(cid)
            s_doc = solver_map.get(cid)
            r_doc = repair_map.get(cid)
            d_doc = drop_map.get(cid)

            conf = -1.0
            if t_doc:
                feas_v = t_doc.get("feasibility", {}).get("verdict", "?")
                conf = t_doc.get("feasibility", {}).get("confidence", 0.0)
                feas_str = f"{feas_v} ({conf:.2f})"
                bucket_str = t_doc.get("bucket", "?")
            elif d_doc:
                feas_str = f"Stage 2 ({d_doc['reason']})"
                bucket_str = DISCARDED
            elif s_doc and s_doc.get("verdict") == "unsat":
                feas_str = "UNSAT (Z3)"
                bucket_str = DISCARDED
            elif self._live_run is not None and (store.root / "llm" / cid / "turns.jsonl").exists():
                feas_str = "⏳ na LLM"
                bucket_str = PENDING
            else:
                feas_str = PENDING
                bucket_str = PENDING

            rep_str = r_doc.get("strategy", "sim") if r_doc else ("-" if bucket_str != "likely_real" else "pendente")

            self.candidates_data[cid] = {
                "record": rec,
                "solver": s_doc,
                "drop": d_doc,
                "triage": t_doc,
                "repair": r_doc,
                "run_root": store.root,
            }
            self.candidate_rows.append(
                Row(
                    cid=cid,
                    pattern=pat,
                    variable=variable_label(variable) if variable else "?",
                    locations=lines_str,
                    feasibility=feas_str,
                    bucket=bucket_str,
                    repair=rep_str,
                    lines=tuple(a.get("source", {}).get("line", 0) for a in accs),
                    confidence=conf,
                    group=variable_key(variable),
                )
            )

        self._draw_candidate_rows(kept)

    def _draw_candidate_rows(self, kept: str | None = None) -> None:
        """Lay the rows out in the tree, in the chosen order and grouping."""
        kept = kept or next(iter(self.tree.selection()), None)
        scroll_top = self.tree.yview()[0]
        grouped = self.group_by_variable_var.get()
        self.tree.configure(show="tree headings" if grouped else "headings")
        for col, title in self._heading_titles.items():
            arrow = (" ▼" if self._sort_reverse else " ▲") if col == self._sort_column else ""
            self.tree.heading(col, text=title + arrow)

        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = sort_rows(self.candidate_rows, self._sort_column, self._sort_reverse)
        if grouped:
            groups = group_rows(rows, self._sort_column, self._sort_reverse)
            for group in groups:
                self.tree.insert("", tk.END, iid=group.iid, values=group.values, open=group.iid in self._open_groups)
                for row in group.rows:
                    self.tree.insert(group.iid, tk.END, iid=row.cid, values=row.values)
            first_item = groups[0].rows[0].cid if groups else None
        else:
            for row in rows:
                self.tree.insert("", tk.END, iid=row.cid, values=row.values)
            first_item = rows[0].cid if rows else None

        target = kept if kept and self.tree.exists(kept) else first_item
        if target:
            if self.tree.parent(target):
                self.tree.item(self.tree.parent(target), open=True)
                self._open_groups.add(self.tree.parent(target))
            self.tree.selection_set(target)
            self.tree.focus(target)
            if self._live_run is not None or kept == target:
                self.tree.yview_moveto(scroll_top)
            self._on_candidate_selected()
        elif self._live_run is not None:
            self._clear_detail_tabs("Aguardando o Stage 1 listar os candidatos deste caso.")
        else:
            self._clear_detail_tabs("Execute pelo menos até a Etapa 2 (Stage 1) para listar os candidatos.")

    def _on_sort_column(self, column: str) -> None:
        self._sort_reverse = column == self._sort_column and not self._sort_reverse
        self._sort_column = column
        self._draw_candidate_rows()

    def _on_group_toggled(self, _event=None) -> None:
        item = self.tree.focus()
        if not item or self.tree.parent(item):
            return
        if self.tree.item(item, "open"):
            self._open_groups.discard(item)  # the event fires before the flag changes
        else:
            self._open_groups.add(item)

    def _clear_detail_tabs(self, msg: str) -> None:
        if hasattr(self, "btn_apply_patch"):
            self.btn_apply_patch.configure(state=tk.DISABLED)
        if hasattr(self, "btn_revert_patch"):
            self.btn_revert_patch.configure(state=tk.DISABLED)
        if hasattr(self, "lbl_patch_status"):
            self.lbl_patch_status.configure(text=msg, foreground="#57606a")
        for widget in (self.txt_detail, self.txt_triage, self.txt_repair, self.txt_diff, self.txt_source, self.txt_turns):
            widget.configure(state=tk.NORMAL)
            widget.delete("1.0", tk.END)
            widget.insert(tk.END, msg)
            widget.configure(state=tk.DISABLED)
        self._show_tab_states(tab_states(self._run_stages))

    def _on_candidate_selected(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        cid = sel[0]
        info = self.candidates_data.get(cid)
        if not info:
            return
        if self._live_run is None:
            self._render_candidate(cid, info)
            return

        # Live: redraw only what changed, and leave the reader where they were.
        run_root: Path = info["run_root"]
        turn_files = [run_root / "llm" / cid / n for n in ("turns.jsonl", "repair-turns.jsonl")]
        stamp = (cid, self.selected_source_view_var.get(), json.dumps(info["triage"]), json.dumps(info["repair"]),
                 [p.stat().st_mtime_ns if p.exists() else 0 for p in turn_files])
        if stamp == self._live_rendered:
            return
        same_candidate = self._live_rendered is not None and self._live_rendered[0] == cid
        self._live_rendered = stamp
        widgets = (self.txt_detail, self.txt_triage, self.txt_repair, self.txt_diff, self.txt_source, self.txt_turns)
        views = [w.yview() for w in widgets]
        self._render_candidate(cid, info)
        if same_candidate:
            for w, (top, bottom) in zip(widgets, views):
                w.yview_moveto(1.0 if bottom >= 0.999 else top)  # at the end, follow the end
        self.btn_apply_patch.configure(state=tk.DISABLED)  # the benchmark is reading these sources

    def _render_candidate(self, cid: str, info: dict[str, Any]) -> None:
        rec = info["record"]
        s_doc = info["solver"]
        t_doc = info["triage"]
        r_doc = info["repair"]
        run_root: Path = info["run_root"]

        self._render_detail(rec)
        self._show_tab_states(
            tab_states(
                self._run_stages,
                selected=True,
                verdict=bool(t_doc),
                patch=bool(r_doc),
                turns=(run_root / "llm" / cid / "turns.jsonl").exists(),
            )
        )

        # --- Tab 1: Triage & Reasoning ---
        triage_lines: list[str] = []
        triage_lines.append(f"CANDIDATO: {cid}")
        triage_lines.append(
            f"Variável compartilhada: {rec.get('variable', {}).get('name', '?')} ({rec.get('variable', {}).get('declared_type', '?')})"
        )
        triage_lines.append(f"Classe / Padrão:        {rec.get('class', '?')} / {rec.get('pattern', '?')}")
        triage_lines.append("=" * 78)

        if t_doc:
            feas = t_doc.get("feasibility", {})
            harm = t_doc.get("harmfulness")
            prod = t_doc.get("produced_by") or {}  # null in a triage the CLI backend wrote
            # Only what the verdict and the manifest record. The prompt row is a
            # run-level fact (manifest llm.prompt_config); C4 request counts are
            # not recorded per verdict, so they are not shown rather than shown as 0.
            run_llm = {}
            try:
                run_llm = json.loads((run_root / "manifest.json").read_text(encoding="utf-8")).get("llm") or {}
            except (OSError, ValueError):
                pass
            triage_lines.append("\n[RESUMO DA TRIAGEM PELA LLM]")
            triage_lines.append(
                f"  Modelo / Backend:         {prod.get('backend', '-')} "
                f"(saída estruturada: {prod.get('structured_mode') or '-'})"
            )
            triage_lines.append(f"  Configuração de Prompt:   {run_llm.get('prompt_config', '-')}")
            triage_lines.append(f"  Grupo Final (Bucket):     {t_doc.get('bucket', '?').upper()}")
            if t_doc.get("not_triaged"):
                triage_lines.append(f"  NÃO TRIADO:               {t_doc['not_triaged']}")
            if t_doc.get("interval_of"):
                triage_lines.append(f"  Veredicto do intervalo:   conversa em {t_doc['interval_of']}")

            triage_lines.append("\n1. PERGUNTA DE VIABILIDADE (A intercalação pode ocorrer?)")
            triage_lines.append(
                f"   Veredicto:  {feas.get('verdict', '?')} (Confiança: {feas.get('confidence', 0.0):.2f})"
            )
            if feas.get("blocking_element"):
                triage_lines.append(f"   Elemento Bloqueador: {feas.get('blocking_element')}")
            triage_lines.append(f"   Raciocínio da LLM:\n   {feas.get('reasoning', '')}")

            triage_lines.append("\n2. PERGUNTA DE NOCIVIDADE (Se ocorrer, causa estado inconsistente/dano?)")
            if harm:
                triage_lines.append(
                    f"   Veredicto:  {harm.get('verdict', '?')} (Confiança: {harm.get('confidence', 0.0):.2f})"
                )
                triage_lines.append(f"   Critério:   {harm.get('criterion_matched', '-')}")
                triage_lines.append(f"   Raciocínio da LLM:\n   {harm.get('reasoning', '')}")
            else:
                triage_lines.append("   Não aplicável (candidato já classificado como inviável na etapa 1).")
        elif info.get("drop"):
            d_doc = info["drop"]
            triage_lines.append(f"\n[DESCARTADO ANTES DA LLM PELO STAGE 2 — motivo: {d_doc['reason']}]")
            triage_lines.append(f"  Fluxos: {d_doc.get('local_flow', '?')} (local) x {d_doc.get('remote_flow', '?')} (remoto)")
            triage_lines.append(f"  Prova:\n  {d_doc.get('proof', '')}")
            if d_doc.get("relies_on"):
                triage_lines.append(f"  Hipóteses de soundness usadas: {', '.join(d_doc['relies_on'])}")
        elif s_doc and s_doc.get("verdict") == "unsat":
            triage_lines.append("\n[DESCARTADO ANTES DA LLM PELO SOLVER Z3]")
            triage_lines.append("  Este candidato teve prova formal UNSAT no estágio estático e não precisou")
            triage_lines.append("  ser enviado para a LLM (Regra C3 #6: descarte apenas com prova formal).")
        elif self._live_run is not None:
            triage_lines.append("\n[Triagem em andamento: sem veredicto ainda.]")
            triage_lines.append("A conversa aparece na aba Histórico LLM, turno a turno.")
        else:
            triage_lines.append("\n[Triagem da LLM ainda não executada para este candidato.]")
            triage_lines.append("Avance até a Etapa 5 (LLM Triagem) para ver a análise detalhada.")

        self._set_text(self.txt_triage, "\n".join(triage_lines))

        # --- Tab 2: Repair & Witness (com cores do Git e botão de aplicação) ---
        self._display_repair_with_git_highlight(cid, r_doc, t_doc)

        # --- Tab 3: Source Files (.c / .h) & C2 Accesses ---
        src_lines: list[str] = []
        accs = rec.get("accesses", [])
        src_lines.append("ACESSOS DO CANDIDATO (C2):")
        for a in accs:
            ln = a.get("source", {}).get("line", 0)
            role = a.get("role", "?")
            rw = a.get("kind", "?")
            fl = a.get("flow", "?")
            fn = a.get("function", "?")
            snip = a.get("source", {}).get("snippet", "")
            src_lines.append(f"  [{role}] Linha {ln:<4} ({rw} em {fl} / {fn}): {snip}")

        src_lines.append("\nPROVENIÊNCIA ESTÁTICA (O que foi provado vs. assumido):")
        for p_entry in rec.get("provenance", {}).get("entries", []):
            src_lines.append(f"  - [{p_entry.get('status')}] {p_entry.get('fact')}: {p_entry.get('note', '')}")

        chosen_file, file_text = self._read_selected_source_file()
        if file_text is not None and chosen_file is not None:
            # An access marks a line only in its own file: line 5 of isr.c says
            # nothing about line 5 of task.c.
            role_by_line: dict[int, list[str]] = {}
            for a in accs:
                if same_source(chosen_file, a.get("source", {}).get("file", "")):
                    role_by_line.setdefault(a["source"]["line"], []).append(
                        f"{a.get('role', '?')}:{a.get('kind', '?')}@{a.get('flow', '?')}")
            src_lines.append(f"\nARQUIVO VISUALIZADO: {chosen_file}")
            src_lines.append("-" * 78)
            for idx, line in enumerate(file_text.splitlines(), start=1):
                badges = ",".join(role_by_line.get(idx, []))
                marker = f"[{badges:<12}]" if badges else "              "
                src_lines.append(f"{idx:4d} {marker} | {line}")
        self._set_text(self.txt_source, "\n".join(src_lines))

        # --- Tab 4: the conversations, with every code read highlighted ---
        try:
            run_manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            run_manifest = {}
        prompt_name = (run_manifest.get("llm") or {}).get("prompt_config")
        p_cfg = next(
            (c for c in {**BY_NAME, **DEFERRED, **EXPERIMENTAL}.values() if c.name == prompt_name),
            FULL if prompt_name == FULL.name else None,
        )
        history = build_history(
            load_turns(run_root / "llm" / cid / "turns.jsonl"),
            load_turns(run_root / "llm" / cid / "repair-turns.jsonl"),
            prompt_name=prompt_name,
            progressive=p_cfg.progressive if p_cfg else None,
        )
        self.txt_turns.configure(state=tk.NORMAL)
        self.txt_turns.delete("1.0", tk.END)
        for text, tag in history.segments:
            self.txt_turns.insert(tk.END, text, tag)
        self.txt_turns.configure(state=tk.DISABLED)
        self.txt_turns.see("1.0")

    def _render_detail(self, rec: dict[str, Any]) -> None:
        """Where the candidate is: each access with its file, flow and code."""
        w = self.txt_detail
        w.configure(state=tk.NORMAL)
        w.delete("1.0", tk.END)

        variable = rec.get("variable") or {}
        decl = variable.get("decl") or {}
        w.insert(tk.END, f"{variable_label(variable)}\n", "title")
        w.insert(tk.END, f"Tipo: {variable.get('declared_type') or '?'}")
        if decl.get("file"):
            w.insert(tk.END, f"  |  Declarada em {decl['file']}:{decl.get('line', '?')}")
        w.insert(tk.END, "\n")

        flows = {f.get("id"): f for f in rec.get("flows", [])}
        for access in rec.get("accesses", []):
            source = access.get("source") or {}
            rel, line = source.get("file", ""), source.get("line", 0)
            flow = flows.get(access.get("flow")) or {}
            priority = f", prioridade {flow['priority']}" if flow.get("priority") is not None else ""
            w.insert(
                tk.END,
                f"\n{access.get('role', '?')}  {access.get('kind', '?')} em {rel or '?'}:{line}\n",
                "access",
            )
            w.insert(tk.END, f"{access.get('flow', '?')}{priority}, função {access.get('function', '?')}\n")
            shown = self._source_excerpt(rel, line)
            if shown:
                for number, text in shown:
                    tag = "marked" if number == line else ()
                    w.insert(tk.END, f"{number:5d} | {text}\n", tag)
            elif source.get("snippet"):
                w.insert(tk.END, f"{line:5d} | {source['snippet']}\n", "marked")
        w.configure(state=tk.DISABLED)

    def _source_excerpt(self, rel: str, line: int, around: int = 2) -> list[tuple[int, str]]:
        """Numbered lines around *line* of the file a record names, if it is here."""
        target = self._source_file_named(rel)
        if target is None or line < 1:
            return []
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        first = max(line - around, 1)
        return list(enumerate(lines[first - 1 : line + around], start=first))

    def _read_primary_c_source(self) -> str | None:
        for p in self.source_files_list:
            if p.suffix.lower() == ".c" and p.name != "common.c" and p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        for p in self.source_files_list:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        return None

    def _read_selected_source_file(self) -> tuple[Path | None, str | None]:
        sel_str = self.selected_source_view_var.get().strip()
        if sel_str and Path(sel_str).is_file():
            p = Path(sel_str)
            return p, p.read_text(encoding="utf-8", errors="replace")
        for p in self.source_files_list:
            if p.is_file():
                return p, p.read_text(encoding="utf-8", errors="replace")
        return None, None

    @staticmethod
    def _set_text(widget: scrolledtext.ScrolledText, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state=tk.DISABLED)

    def _configure_diff_tags(self, w: scrolledtext.ScrolledText) -> None:
        """Configure Git-like color tags on a ScrolledText widget."""
        w.tag_configure("diff_add", foreground="#155724", background="#d4edda", font=("Consolas", 10, "bold"))
        w.tag_configure("diff_del", foreground="#721c24", background="#f8d7da", font=("Consolas", 10))
        w.tag_configure("diff_hunk", foreground="#004085", background="#cce5ff", font=("Consolas", 10, "bold"))
        w.tag_configure("diff_header", foreground="#383d41", background="#e2e3e5", font=("Consolas", 10, "bold"))
        w.tag_configure("sec_title", foreground="#004085", font=("Segoe UI", 10, "bold"))
        w.tag_configure("sec_bar", foreground="#6c757d", font=("Consolas", 9))
        w.tag_configure("code_line", foreground="#212529", font=("Consolas", 10))
        w.tag_configure("preview_add", foreground="#155724", background="#d4edda", font=("Consolas", 10, "bold"))

    def _configure_history_tags(self, w: scrolledtext.ScrolledText) -> None:
        """Colours for the LLM history: what was given, asked for, read, refused."""
        w.tag_configure("title", foreground="#004085", font=("Segoe UI", 11, "bold"), spacing1=6)
        w.tag_configure("summary", font=("Segoe UI", 9, "bold"))
        w.tag_configure("hdr", foreground="#383d41", background="#e2e3e5", font=("Consolas", 9, "bold"))
        w.tag_configure("given", foreground="#0b3d91", background="#e7f0ff")
        w.tag_configure("request", foreground="#664d03", background="#fff3cd", font=("Consolas", 10, "bold"))
        w.tag_configure("read_ok", foreground="#155724", background="#d4edda")
        w.tag_configure("read_miss", foreground="#721c24", background="#f8d7da")
        w.tag_configure("muted", foreground="#6c757d")
        w.tag_configure("text", foreground="#212529")

    def _find_target_file_for_patch(self, cid: str, r_doc: dict[str, Any]) -> Path | None:
        """The file on disk this patch is for, or ``None`` rather than a guess."""
        return self._source_file_named(patch_file(r_doc, self.candidates_data.get(cid, {}).get("record")))

    def _source_file_named(self, rel: str | None) -> Path | None:
        if not rel:
            return None
        exact = [p for p in self.source_files_list if same_source(p, rel) and p.is_file()]
        if exact:
            return exact[0]
        by_name = [p for p in self.source_files_list if p.name == Path(rel).name and p.is_file()]
        return by_name[0] if len(by_name) == 1 else None

    def _display_repair_with_git_highlight(
        self, cid: str, r_doc: dict[str, Any] | None, t_doc: dict[str, Any] | None
    ) -> None:
        w = self.txt_repair
        code = self.txt_diff
        for widget in (w, code):
            widget.configure(state=tk.NORMAL)
            widget.delete("1.0", tk.END)

        if not r_doc:
            if hasattr(self, "btn_apply_patch"):
                self.btn_apply_patch.configure(state=tk.DISABLED)
            if hasattr(self, "btn_revert_patch"):
                self.btn_revert_patch.configure(state=tk.DISABLED)
            if t_doc and t_doc.get("bucket") == "likely_infeasible":
                if hasattr(self, "lbl_patch_status"):
                    self.lbl_patch_status.configure(
                        text="Candidato classificado como 'likely_infeasible' (Armadilha / Falso Positivo). Sem correção.",
                        foreground="#57606a",
                    )
                w.insert(
                    tk.END,
                    "Candidato classificado como 'likely_infeasible' (Armadilha / Falso Positivo).\n"
                    "Nenhuma modificação de código é necessária.\n",
                    "code_line",
                )
            else:
                if hasattr(self, "lbl_patch_status"):
                    self.lbl_patch_status.configure(
                        text="Nenhum patch gerado ainda para este candidato.",
                        foreground="#57606a",
                    )
                w.insert(
                    tk.END,
                    "Nenhum patch gerado ainda para este candidato.\n"
                    "Avance até a Etapa 6 (LLM Reparo) para gerar a sugestão de correção.\n",
                    "code_line",
                )
            w.configure(state=tk.DISABLED)
            code.configure(state=tk.DISABLED)
            return

        target_file = self._find_target_file_for_patch(cid, r_doc)
        target_name = target_file.name if target_file else "código C"
        bak_file = target_file.with_name(f"{target_file.name}.bak") if target_file else None

        if hasattr(self, "btn_apply_patch"):
            self.btn_apply_patch.configure(state=tk.NORMAL)
        if hasattr(self, "btn_revert_patch"):
            if bak_file and bak_file.exists():
                self.btn_revert_patch.configure(state=tk.NORMAL)
                if hasattr(self, "lbl_patch_status"):
                    self.lbl_patch_status.configure(
                        text=f"Alvo: {target_name} (Backup .bak disponível para reversão)",
                        foreground="#0969da",
                    )
            else:
                self.btn_revert_patch.configure(state=tk.DISABLED)
                if hasattr(self, "lbl_patch_status"):
                    self.lbl_patch_status.configure(
                        text=f"Alvo: {target_name} | Pronto para aplicar patch",
                        foreground="#1a7f37",
                    )

        wit = r_doc.get("witness", {})
        strat = r_doc.get("strategy", "?")
        irqs = r_doc.get("masked_irqs", [])
        c_from = r_doc.get("covers_from_line", "?")
        c_to = r_doc.get("covers_to_line", "?")
        lat = r_doc.get("latency_note", "-")
        reason = r_doc.get("reasoning", "")
        diff_txt = r_doc.get("diff", "")

        # 1. Header Box
        w.insert(tk.END, f"SUGESTÃO DE CORREÇÃO DA LLM PARA {cid}\n", "sec_title")
        w.insert(tk.END, "=" * 80 + "\n", "sec_bar")
        w.insert(tk.END, f"Estratégia Escolhida:   {strat}\n", "code_line")
        w.insert(tk.END, f"IRQs Mascaradas:        {irqs}\n", "code_line")
        w.insert(tk.END, f"Intervalo Protegido:    Linha {c_from} até Linha {c_to}\n", "code_line")
        w.insert(tk.END, f"Arquivo Alvo Detectado: {target_file}\n", "code_line")
        w.insert(tk.END, f"Nota de Latência/Custo: {lat}\n", "code_line")

        # 2. Reasoning
        w.insert(tk.END, "\n[JUSTIFICATIVA DO REPARO PELA LLM]\n", "sec_title")
        w.insert(tk.END, f"  {reason}\n", "code_line")

        # 3. Witness
        w.insert(tk.END, "\n[TESTEMUNHA DE INTERCALAÇÃO EXIGIDA (Validada Mecanicamente)]\n", "sec_title")
        w.insert(tk.END, f"  • ISR / Fluxo Preemptor: {wit.get('firing_flow', '?')}\n", "code_line")
        w.insert(tk.END, f"  • Ponto de Preempção:    {wit.get('preemption_point', '?')}\n", "code_line")
        w.insert(tk.END, f"  • Ordem de Acessos:      {' -> '.join(wit.get('access_order', []))}\n", "code_line")
        w.insert(tk.END, f"  • Divergência de Estado: {wit.get('divergence', '?')}\n", "code_line")

        w.configure(state=tk.DISABLED)

        # 4. Git Diff with Syntax/Color Highlighting
        w = code
        w.insert(tk.END, "[PATCH UNIFIED DIFF COM DESTAQUE GIT (patch.diff)]\n", "sec_title")
        w.insert(tk.END, "-" * 80 + "\n", "sec_bar")

        for line in diff_txt.splitlines():
            if line.startswith("@@"):
                tag = "diff_hunk"
            elif line.startswith("+") and not line.startswith("+++"):
                tag = "diff_add"
            elif line.startswith("-") and not line.startswith("---"):
                tag = "diff_del"
            elif line.startswith("---") or line.startswith("+++") or line.startswith("diff "):
                tag = "diff_header"
            else:
                tag = "code_line"
            w.insert(tk.END, line + "\n", tag)

        w.insert(tk.END, "-" * 80 + "\n", "sec_bar")

        # 5. Preview of Patched C Code
        c_source = None
        if target_file and target_file.exists():
            c_source = target_file.read_text(encoding="utf-8", errors="replace")
        elif self._read_primary_c_source():
            c_source = self._read_primary_c_source()

        if c_source and diff_txt:
            try:
                patched = apply_unified_diff(c_source, diff_txt)
                if patched:
                    w.insert(tk.END, "\n[PRÉVIA DO CÓDIGO C APÓS APLICAR O PATCH]\n", "sec_title")
                    w.insert(tk.END, "-" * 80 + "\n", "sec_bar")
                    orig_lines = set(c_source.splitlines())
                    for idx, line in enumerate(patched.splitlines(), start=1):
                        is_new = line not in orig_lines and ("disable_isr" in line or "enable_isr" in line)
                        tag = "preview_add" if is_new else "code_line"
                        marker = "[+]" if is_new else "   "
                        w.insert(tk.END, f"{idx:4d} {marker} | {line}\n", tag)
                    w.insert(tk.END, "-" * 80 + "\n", "sec_bar")
            except Exception:
                pass

        w.configure(state=tk.DISABLED)

    def _on_apply_selected_patch(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um candidato likely_real na tabela para aplicar o patch.")
            return
        cid = sel[0]
        info = self.candidates_data.get(cid)
        if not info or not info.get("repair"):
            messagebox.showwarning("Aviso", f"O candidato {cid} não possui patch de reparo disponível.")
            return

        r_doc = info["repair"]
        diff_txt = r_doc.get("diff", "")
        if not diff_txt:
            messagebox.showerror("Erro", "O patch não contém texto de diff unificado.")
            return

        target_file = self._find_target_file_for_patch(cid, r_doc)
        if not target_file or not target_file.exists():
            messagebox.showerror(
                "Arquivo Alvo Não Encontrado",
                f"Não foi possível localizar o arquivo de código fonte C para aplicar o patch de {cid}."
            )
            return

        confirm = messagebox.askyesno(
            "Confirmar Aplicação de Correção",
            f"Deseja aplicar a correção gerada pela LLM no arquivo:\n{target_file}\n\n"
            f"Candidato: {cid}\n"
            f"Estratégia: {r_doc.get('strategy')}\n"
            f"IRQs Mascaradas: {r_doc.get('masked_irqs')}\n\n"
            f"Um backup automático ({target_file.name}.bak) será criado antes de modificar.",
        )
        if not confirm:
            return

        original_text = target_file.read_text(encoding="utf-8", errors="replace")
        patched_text = apply_unified_diff(original_text, diff_txt)
        if patched_text is None:
            messagebox.showerror(
                "Falha ao Aplicar Diff",
                "O diff não pôde ser aplicado de forma limpa no arquivo atual.\n"
                "Verifique se o arquivo já foi modificado ou se os números de linha divergiram.",
            )
            return

        bak_file = target_file.with_name(f"{target_file.name}.bak")
        try:
            bak_file.write_text(original_text, encoding="utf-8")
            target_file.write_text(patched_text, encoding="utf-8")
        except Exception as e:
            messagebox.showerror("Erro de Gravação", f"Erro ao gravar alterações no arquivo:\n{e}")
            return

        self._append_log(
            f"✔ [CORREÇÃO APLICADA] Patch {cid} gravado com sucesso em {target_file.name} (backup: {bak_file.name})"
        )
        if hasattr(self, "lbl_patch_status"):
            self.lbl_patch_status.configure(
                text=f"✔ Patch {cid} aplicado em {target_file.name} (backup .bak salvo)",
                foreground="#1a7f37",
            )
        if hasattr(self, "btn_revert_patch"):
            self.btn_revert_patch.configure(state=tk.NORMAL)
        self._on_candidate_selected()
        messagebox.showinfo(
            "Correção Aplicada com Sucesso!",
            f"A correção do candidato {cid} foi aplicada no arquivo:\n{target_file}\n\n"
            f"Backup original salvo em:\n{bak_file}\n\n"
            f"Você pode reverter a qualquer momento com o botão 'Reverter Arquivo (.bak)' "
            f"ou recompilar o projeto com (RESET) e (STEP).",
        )

    def _on_revert_selected_patch(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        cid = sel[0]
        info = self.candidates_data.get(cid)
        r_doc = info.get("repair", {}) if info else {}
        target_file = self._find_target_file_for_patch(cid, r_doc)
        if not target_file:
            return
        bak_file = target_file.with_name(f"{target_file.name}.bak")
        if not bak_file.exists():
            messagebox.showinfo("Sem Backup", f"Não há arquivo de backup (.bak) para {target_file.name}.")
            return

        confirm = messagebox.askyesno(
            "Reverter Correção",
            f"Deseja restaurar o arquivo original a partir do backup:\n{bak_file}\n\n"
            f"Isso desfaz a correção aplicada em {target_file.name}."
        )
        if not confirm:
            return

        try:
            target_file.write_text(bak_file.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            bak_file.unlink()
        except Exception as e:
            messagebox.showerror("Erro ao Reverter", f"Erro ao restaurar backup:\n{e}")
            return

        self._append_log(f"↺ [REVERTIDO] {target_file.name} restaurado ao estado original.")
        if hasattr(self, "lbl_patch_status"):
            self.lbl_patch_status.configure(
                text=f"↺ {target_file.name} restaurado ao estado original.",
                foreground="#57606a",
            )
        if hasattr(self, "btn_revert_patch"):
            self.btn_revert_patch.configure(state=tk.DISABLED)
        self._on_candidate_selected()
        messagebox.showinfo("Arquivo Restaurado", f"{target_file.name} foi restaurado com sucesso a partir do backup.")

    def _on_export_pdf_report(self) -> None:
        yaml_str = self.yaml_path_var.get().strip()
        case_name = Path(yaml_str).stem if yaml_str and Path(yaml_str).exists() else "irqrace_analise"
        now_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"relatorio_{case_name}_{now_tag}.pdf"

        initial_dir = REPO_ROOT / "runs"
        if not initial_dir.exists():
            initial_dir = REPO_ROOT

        save_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Salvar Relatório Técnico em PDF (irqrace TCC)",
            initialdir=str(initial_dir),
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("Documento PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
        )
        if not save_path:
            return

        stages_data = {}
        evaluation = None
        if self.stepper and self.stepper.store:
            m = self.stepper.store.read_manifest()
            stages_data = {s["name"]: s for s in m.get("stages", [])}
            rows = evaluate_run(self.stepper.store)
            evaluation = [dataclasses.asdict(r) for r in rows] if rows else None

        report_data = {
            "case_name": case_name,
            "yaml_path": yaml_str,
            "source_files": list(self.source_files_list),
            "llm_model": self.llm_model_var.get().strip(),
            "llm_adapter": self.llm_adapter_var.get().strip(),
            "llm_base_url": self.llm_base_url_var.get().strip(),
            "llm_prompt": self.llm_prompt_var.get().strip(),
            "stages": stages_data,
            "evaluation": evaluation,
            "candidates": self.candidates_data,
        }

        try:
            builder = PDFReportBuilder(Path(save_path), report_data)
            out_pdf = builder.build()
            self._append_log(f"📄 [PDF EXPORTADO] Relatório técnico gerado em: {out_pdf}")
            self.status_var.set(f"Relatório PDF salvo em: {out_pdf.name}")

            open_now = messagebox.askyesno(
                "Relatório PDF Gerado!",
                f"O relatório técnico da análise foi exportado com sucesso em:\n{out_pdf}\n\n"
                f"Deseja abrir o arquivo PDF agora?",
            )
            if open_now:
                _open_with_default_app(out_pdf)
        except Exception as e:
            messagebox.showerror("Erro ao Exportar PDF", f"Falha ao gerar relatório PDF:\n{e}")


def _open_with_default_app(path: Path) -> None:
    """Open *path* in the OS default viewer. `os.startfile` exists only on Windows."""
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _find_monografia_figura(filename: str) -> Path | None:
    for base in (
        WORKSPACE_ROOT / "monografia" / "figuras",
        REPO_ROOT.parent / "monografia" / "figuras",
        Path.cwd() / "monografia" / "figuras",
    ):
        p = base / filename
        if p.is_file():
            return p
    return None


class AcademicIntroSplash:
    """Clean-view, formal Light-Theme Academic Splash Screen for the TCC Defense (POLI-USP / PCS).

    Displays:
    - Official Logo da Universidade de São Paulo (USP)
    - Official Logo da Escola Politécnica (POLI-USP) com a Minerva Clássica
    - Department of Computer Engineering & Digital Systems (PCS)
    - Concise official TCC title
    - Alunos: Lucas de Oliveira Martim & Pedro Henrique Machado Almeida
    - Orientador: Prof. Dr. Carlos Cugnasca
    - Minimal clean-view design (Light Theme, zero clutter, no loading bar)
    - Stays open indefinitely until user presses ENTER or ESC (or clicks).
    """

    def __init__(self, root: tk.Tk | tk.Toplevel, duration_ms: int | None = None, on_complete=None) -> None:
        self.root = root
        self.duration_ms = duration_ms
        self.on_complete = on_complete
        self.dismissed = False
        self._img_refs: list[Any] = []

        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("IRQRACE_NO_SPLASH"):
            if self.on_complete:
                self.on_complete()
            return

        self.w, self.h = 760, 490
        self.splash = tk.Toplevel(root)
        self.splash.overrideredirect(True)
        try:
            self.splash.attributes("-topmost", True)
        except Exception:
            pass

        sw = self.splash.winfo_screenwidth()
        sh = self.splash.winfo_screenheight()
        x = max(0, (sw - self.w) // 2)
        y = max(0, (sh - self.h) // 2)
        self.splash.geometry(f"{self.w}x{self.h}+{x}+{y}")
        self.splash.configure(bg="#FFFFFF")

        self.canvas = tk.Canvas(
            self.splash,
            width=self.w,
            height=self.h,
            bg="#FFFFFF",
            highlightthickness=1,
            highlightbackground="#E2E8F0",
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)

        self._load_logos()
        self.start_t = time.perf_counter()

        # Dismiss on ENTER, ESC, SPACE or Left Click
        self.splash.bind("<Return>", lambda _e: self.dismiss())
        self.splash.bind("<KP_Enter>", lambda _e: self.dismiss())
        self.splash.bind("<Escape>", lambda _e: self.dismiss())
        self.splash.bind("<space>", lambda _e: self.dismiss())
        self.splash.bind("<Button-1>", lambda _e: self.dismiss())
        self.canvas.bind("<Button-1>", lambda _e: self.dismiss())

        self._draw_screen()
        try:
            self.splash.focus_force()
        except Exception:
            pass

        if self.duration_ms and self.duration_ms > 0:
            self.splash.after(self.duration_ms, self.dismiss)

    def _load_logos(self) -> None:
        try:
            from PIL import Image, ImageTk

            p_usp = _find_monografia_figura("logo-usp.png")
            if p_usp and p_usp.is_file():
                im_u = Image.open(p_usp).convert("RGBA")
                tgt_w = 130
                tgt_h = int(tgt_w * im_u.height / im_u.width)
                self.tk_usp = ImageTk.PhotoImage(im_u.resize((tgt_w, tgt_h), Image.Resampling.LANCZOS))
                self._img_refs.append(self.tk_usp)
            else:
                self.tk_usp = None

            p_poli = _find_monografia_figura("logo-poli.png")
            if p_poli and p_poli.is_file():
                im_p = Image.open(p_poli).convert("RGBA")
                tgt_h = 75
                tgt_w = int(tgt_h * im_p.width / im_p.height)
                self.tk_poli = ImageTk.PhotoImage(im_p.resize((tgt_w, tgt_h), Image.Resampling.LANCZOS))
                self._img_refs.append(self.tk_poli)
            else:
                self.tk_poli = None
        except Exception:
            self.tk_usp = None
            self.tk_poli = None

    def _draw_screen(self) -> None:
        self.canvas.delete("all")
        w, h = self.w, self.h

        # 1. Top Logos (USP & Minerva da Poli)
        if getattr(self, "tk_usp", None):
            self.canvas.create_image(95, 50, image=self.tk_usp)
        else:
            self.canvas.create_text(95, 50, text="[ USP ]", fill="#0F172A", font=("Segoe UI", 11, "bold"))

        if getattr(self, "tk_poli", None):
            self.canvas.create_image(w - 95, 50, image=self.tk_poli)
        else:
            self.canvas.create_text(w - 95, 50, text="[ POLI ]", fill="#0F172A", font=("Segoe UI", 11, "bold"))

        # 2. Institution Header (Clean & Centered)
        self.canvas.create_text(
            w // 2, 40,
            text="UNIVERSIDADE DE SÃO PAULO",
            fill="#0F172A",
            font=("Segoe UI", 11, "bold"),
        )
        self.canvas.create_text(
            w // 2, 60,
            text="ESCOLA POLITÉCNICA — PCS",
            fill="#475569",
            font=("Segoe UI", 9, "bold"),
        )

        # Subtle divider
        self.canvas.create_line(60, 95, w - 60, 95, fill="#E2E8F0", width=1)

        # 3. TCC Header Badge
        self.canvas.create_text(
            w // 2, 126,
            text="TRABALHO DE CONCLUSÃO DE CURSO • ENGENHARIA DE COMPUTAÇÃO 2026",
            fill="#1D4ED8",
            font=("Segoe UI", 9, "bold"),
        )

        # 4. Concise Title & System Name
        self.canvas.create_text(
            w // 2, 168,
            text="Detecção de Defeitos de Concorrência em Software Embarcado",
            fill="#0F172A",
            font=("Segoe UI", 15, "bold"),
        )
        self.canvas.create_text(
            w // 2, 196,
            text="com Triagem e Reparo Assistidos por LLM",
            fill="#0F172A",
            font=("Segoe UI", 14, "bold"),
        )
        self.canvas.create_text(
            w // 2, 230,
            text="IRQRACE - AI",
            fill="#64748B",
            font=("Segoe UI", 10, "bold"),
        )

        # 5. Formal Presentation Card (Clean View)
        card_x1, card_y1, card_x2, card_y2 = 60, 260, w - 60, 425
        self.canvas.create_rectangle(
            card_x1, card_y1, card_x2, card_y2,
            fill="#F8FAFC",
            outline="#E2E8F0",
            width=1,
        )

        # Alunos com NUSP
        nusp_lucas = os.environ.get("NUSP_LUCAS") or os.environ.get("IRQRACE_NUSP_LUCAS", "").strip()
        nusp_pedro = os.environ.get("NUSP_PEDRO") or os.environ.get("IRQRACE_NUSP_PEDRO", "").strip()
        txt_lucas = f"Lucas de Oliveira Martim (NUSP: {nusp_lucas})" if nusp_lucas else "Lucas de Oliveira Martim (NUSP: ________)"
        txt_pedro = f"Pedro Henrique Machado Almeida (NUSP: {nusp_pedro})" if nusp_pedro else "Pedro Henrique Machado Almeida (NUSP: ________)"

        self.canvas.create_text(
            w // 2, card_y1 + 24,
            text="ALUNOS FORMANDOS",
            fill="#64748B",
            font=("Segoe UI", 8, "bold"),
        )
        self.canvas.create_text(
            w // 2, card_y1 + 48,
            text=f"{txt_lucas}    •    {txt_pedro}",
            fill="#0F172A",
            font=("Segoe UI", 10, "bold"),
        )

        # Orientador
        self.canvas.create_text(
            w // 2, card_y1 + 86,
            text="PROFESSOR ORIENTADOR",
            fill="#64748B",
            font=("Segoe UI", 8, "bold"),
        )
        self.canvas.create_text(
            w // 2, card_y1 + 108,
            text="Prof. Dr. Carlos Cugnasca",
            fill="#1E293B",
            font=("Segoe UI", 10, "bold"),
        )
        self.canvas.create_text(
            w // 2, card_y1 + 130,
            text="Departamento de Engenharia de Computação e Sistemas Digitais (PCS / EPUSP)",
            fill="#64748B",
            font=("Segoe UI", 8),
        )

        # 6. Bottom Clean Action Hint (No loading bar, ENTER, ESC or Left Click)
        self.canvas.create_text(
            w // 2, 458,
            text="[ Pressione ENTER, ESC ou Clique para continuar ]",
            fill="#475569",
            font=("Segoe UI", 9, "bold"),
        )
        self.canvas.tag_bind("all", "<Button-1>", lambda _e: self.dismiss())

    def dismiss(self) -> None:
        if self.dismissed:
            return
        self.dismissed = True
        try:
            self.splash.destroy()
        except Exception:
            pass
        if self.on_complete:
            self.on_complete()

    _tick = dismiss


UniversalIntroSplash = AcademicIntroSplash


def main() -> None:
    root = tk.Tk()
    root.withdraw()  # Keeps main window hidden until intro splash completes

    def _show_app():
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
        except Exception:
            pass

    app = IrqRaceWinApp(root)

    # Show Clean Academic TCC Splash screen (infinite until ENTER or ESC)
    if not os.environ.get("PYTEST_CURRENT_TEST") and not os.environ.get("IRQRACE_NO_SPLASH"):
        AcademicIntroSplash(root, duration_ms=None, on_complete=_show_app)
    else:
        _show_app()

    root.mainloop()


if __name__ == "__main__":
    main()
