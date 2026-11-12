"""Freeze the static stages once, then triage independent copies of them.

``scripts/freeze-and-triage.py`` is the command; this module is its logic, kept
here so the plan and the copies can be tested without a model.

**Why copies.** ``irqrace llm triage --samples N`` is majority *voting* inside
one run (the manifest records ``"votes": N``), not N independent runs, and
``triage_store`` writes its verdicts into the run directory it is given. So each
(prompt row, sample) pair triages its own copy of one frozen static run root:
``<out>/<row>/<k>/`` is a copy of the frozen root, and only the prompt and the
sample differ between pairs. The static stages are then identical by
construction, and S1 is the same in every pair.

**Order.** Pairs run strictly one after another, interleaved by sample --
(row A, 1), (row B, 1), (row A, 2), ... -- so that whatever drifts over an
evening (backend load, rate limiting) touches every row alike rather than
landing on whichever row ran last. Inside a pair the cases also run one at a
time; ``--workers`` is the number of conversations inside one case.

**Failure.** A pair is ``failed`` when any case exits non-zero, times out,
leaves no ``llm/triage.jsonl``, or reports a not-triaged candidate (a backend
failure kept as uncertain). ``batch.json`` says so, and the scorer refuses a
failed pair unless told otherwise: a partial run is never averaged in silently.

**There is no LLM result cache.** It was removed on 2026-10-30 (diary, Semana 8
§3.19): every triage is a fresh call. The old ``.llm-cache/`` directory may
still sit in a checkout's ``project-src/`` (outside git, 458 files, last written
2026-10-30); nothing reads it. Provider-side prompt caching (Anthropic's
``cache_control``) is not a result cache -- the model answers again.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .runstore import find_runs

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS = REPO_ROOT / "bench" / "configs"
TIMEOUT_RC = 124

#: ``runner(cmd, log_path=..., timeout=..., env=..., cwd=...) -> exit code``.
Runner = Callable[..., int]


class BatchError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Running one command, logged, with a hard timeout
# ---------------------------------------------------------------------------


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill ``proc`` and its children (the Claude CLI spawns its own)."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()


def run_logged(cmd: Sequence[str], *, log_path: Path, timeout: float, env: dict[str, str] | None = None,
               cwd: Path | None = None) -> int:
    """Run ``cmd`` with stdout and stderr into ``log_path``; :data:`TIMEOUT_RC` on timeout."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as fh:
        fh.write("$ " + " ".join(cmd) + "\n")
        fh.flush()
        kwargs: dict[str, Any] = {"start_new_session": True} if os.name != "nt" else {}
        proc = subprocess.Popen(list(cmd), stdout=fh, stderr=subprocess.STDOUT, env=env,
                                cwd=str(cwd) if cwd else None, **kwargs)
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            proc.wait()
            fh.write(f"\n[freeze-and-triage] killed after the {timeout:.0f} s timeout\n")
            return TIMEOUT_RC


def child_env(*, keep_racebench_env: bool = False) -> dict[str, str]:
    """The environment of every ``irqrace`` the batch starts.

    This checkout's ``src`` goes first on ``PYTHONPATH``: a venv's editable
    install may point at another checkout. ``IRQRACE_RACEBENCH`` is dropped
    unless asked for, because it silently redirects the ground truth and the
    C4 source resolver away from the vendored suite -- the WSL environment's
    ``/etc/profile.d/irqrace.sh`` sets it to the pristine ``../racebench``
    checkout, which has neither the 006 patch nor the 2026-10-28 relabel.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "src"), *filter(None, [env.get("PYTHONPATH")])])
    env["PYTHONUTF8"] = "1"
    if not keep_racebench_env:
        env.pop("IRQRACE_RACEBENCH", None)
    return env


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True,
                             timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _append_timing(root: Path, case: str, t0: float, t1: float, rc: int) -> None:
    with (root / "timings.tsv").open("a", encoding="utf-8") as fh:
        fh.write(f"{case}\t{t0:.3f}\t{t1:.3f}\t{rc}\n")


# ---------------------------------------------------------------------------
# The frozen static root
# ---------------------------------------------------------------------------


def _stage_status(manifest: dict[str, Any]) -> dict[str, str]:
    return {s["name"]: s.get("status") for s in manifest.get("stages", [])}


def frozen_cases(frozen: Path) -> list[Path]:
    """The case run directories of a frozen root, checked; raises listing every problem.

    Each must have gone through ``context`` and not through ``triage``, and a
    subject may appear only once -- two runs of one case would make "which
    one was triaged" a question.
    """
    frozen = Path(frozen)
    runs = find_runs(frozen)
    if not runs:
        raise BatchError(f"{frozen}: no run directories (nothing with a manifest.json)")
    problems, seen = [], {}
    for run in runs:
        m = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        subj = m["subject"]["name"]
        st = _stage_status(m)
        if subj in seen:
            problems.append(f"{subj}: two runs ({seen[subj].name}, {run.name})")
        seen[subj] = run
        if st.get("context") != "ok":
            problems.append(f"{run.name}: context stage is {st.get('context')!r}, not 'ok'")
        if st.get("triage") == "ok" or (run / "llm" / "triage.jsonl").exists():
            problems.append(f"{run.name}: already triaged -- a frozen root must be static only")
    if problems:
        raise BatchError(f"{frozen} is not a frozen static root:\n  " + "\n  ".join(problems))
    return runs


def subject_of(run: Path) -> str:
    return json.loads((run / "manifest.json").read_text(encoding="utf-8"))["subject"]["name"]


def freeze(configs: Sequence[Path], run_root: Path, *, python: str = sys.executable,
           case_timeout: float = 900.0, runner: Runner = run_logged, env: dict[str, str] | None = None,
           log: Callable[[str], None] = print) -> dict[str, Any]:
    """Run the static stages (``--through context``) once per config into ``run_root``.

    Writes per-case logs, ``timings.tsv``, ``start.txt`` / ``end.txt`` and
    ``freeze.json`` (the commit, whether the tree was dirty, the platform, the
    command), then checks the result with :func:`frozen_cases`.
    """
    run_root = Path(run_root).resolve()
    if run_root.exists() and any(run_root.iterdir()):
        raise BatchError(f"{run_root} is not empty: a frozen root is written once")
    run_root.mkdir(parents=True, exist_ok=True)
    env = env if env is not None else child_env()
    doc: dict[str, Any] = {
        "kind": "frozen-static-root", "status": "running", "started": _now(),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "platform": platform.platform(), "python": python,
        "irqrace_racebench": env.get("IRQRACE_RACEBENCH"),
        "through": "context", "configs": [Path(c).name for c in configs], "failures": [],
    }
    _write_json(run_root / "freeze.json", doc)
    (run_root / "start.txt").write_text(f"{time.time():.3f}")
    for n, cfg in enumerate(configs, 1):
        case = Path(cfg).stem
        cmd = [python, "-m", "irqrace", "pipeline", str(Path(cfg).resolve()), "--through", "context", "--run-root", str(run_root)]
        log(f"[freeze {n}/{len(configs)}] {case} ...")
        t0 = time.time()
        rc = runner(cmd, log_path=run_root / "logs" / f"{case}.log", timeout=case_timeout, env=env,
                    cwd=REPO_ROOT)
        t1 = time.time()
        _append_timing(run_root, case, t0, t1, rc)
        log(f"[freeze {n}/{len(configs)}] {case} exit {rc} in {t1 - t0:.0f} s")
        if rc != 0:
            doc["failures"].append({"case": case, "reason": "timeout" if rc == TIMEOUT_RC else f"exit {rc}"})
    (run_root / "end.txt").write_text(f"{time.time():.3f}")
    try:
        found = frozen_cases(run_root)
        if len(found) != len(configs):
            doc["failures"].append({"case": None, "reason": f"{len(found)} runs for {len(configs)} configs"})
    except BatchError as e:
        doc["failures"].append({"case": None, "reason": str(e)})
    doc["status"] = "failed" if doc["failures"] else "ok"
    doc["finished"] = _now()
    _write_json(run_root / "freeze.json", doc)
    return doc


# ---------------------------------------------------------------------------
# The plan: (row, sample) pairs over copies of the frozen root
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    row: str
    sample: int
    dest: Path

    @property
    def run_id(self) -> str:
        return f"{self.row}/{self.sample}"


def check_row_name(row: str) -> str:
    if not row or any(c in row for c in '/\\:*?"<>|') or row in (".", ".."):
        raise BatchError(f"prompt row {row!r} cannot name a directory")
    return row


def plan(out: Path, rows: Sequence[str], samples: int) -> list[Pair]:
    """Every (row, sample) pair, interleaved by sample, each with its own directory."""
    if samples < 1:
        raise BatchError("--samples must be at least 1")
    if len(set(rows)) != len(rows):
        raise BatchError(f"a prompt row is listed twice: {list(rows)}")
    out = Path(out).resolve()
    return [Pair(row, k, out / check_row_name(row) / str(k))
            for k in range(1, samples + 1) for row in rows]


def triage_command(python: str, case_dir: Path, row: str, backend: str, workers: int) -> list[str]:
    """One case's triage. ``--samples 1``: independence comes from the copies, not from voting."""
    return [python, "-m", "irqrace", "llm", "triage", str(case_dir), "--row", row,
            "--backend", backend, "--samples", "1", "--workers", str(workers)]


def copy_frozen(frozen: Path, dest: Path, cases: Sequence[Path]) -> list[Path]:
    """Copy the frozen case runs (and ``freeze.json``) to ``dest``; ``dest`` must not exist."""
    if dest.exists():
        raise BatchError(f"{dest} exists: a copy is made once, never refreshed in place")
    dest.mkdir(parents=True)
    out = []
    for run in cases:
        shutil.copytree(run, dest / run.name)
        out.append(dest / run.name)
    if (Path(frozen) / "freeze.json").exists():
        shutil.copy2(Path(frozen) / "freeze.json", dest / "freeze.json")
    return out


def not_triaged(case_dir: Path) -> int | None:
    """Candidates kept as uncertain without a verdict; ``None`` if triage left no file."""
    path = case_dir / "llm" / "triage.jsonl"
    if not path.exists():
        return None
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and json.loads(line).get("not_triaged"))


def run_pair(pair: Pair, frozen: Path, cases: Sequence[Path], *, backend: str, workers: int,
             case_timeout: float, python: str = sys.executable, runner: Runner = run_logged,
             env: dict[str, str] | None = None, log: Callable[[str], None] = print) -> dict[str, Any]:
    """Copy the frozen root to ``pair.dest`` and triage every case there, in series."""
    env = env if env is not None else child_env()
    copies = copy_frozen(frozen, pair.dest, cases)
    doc: dict[str, Any] = {
        "run_id": pair.run_id, "row": pair.row, "sample": pair.sample, "backend": backend,
        "workers": workers, "case_timeout_s": case_timeout, "frozen_root": str(Path(frozen).resolve()),
        "triaged_with_commit": _git("rev-parse", "HEAD"), "status": "running", "started": _now(),
        "failures": [],
    }
    _write_json(pair.dest / "batch.json", doc)
    (pair.dest / "start.txt").write_text(f"{time.time():.3f}")
    for n, case_dir in enumerate(copies, 1):
        case = subject_of(case_dir)
        log(f"[{pair.run_id} {n}/{len(copies)}] {case} ...")
        t0 = time.time()
        rc = runner(triage_command(python, case_dir, pair.row, backend, workers),
                    log_path=pair.dest / "logs" / f"{case}.log", timeout=case_timeout, env=env, cwd=REPO_ROOT)
        t1 = time.time()
        _append_timing(pair.dest, case, t0, t1, rc)
        missing = not_triaged(case_dir)
        reason = None
        if rc == TIMEOUT_RC:
            reason = f"timeout after {case_timeout:.0f} s"
        elif rc != 0:
            reason = f"exit {rc}"
        elif missing is None:
            reason = "no llm/triage.jsonl"
        elif missing:
            reason = f"{missing} candidate(s) not triaged"
        if reason:
            doc["failures"].append({"case": case, "reason": reason})
        log(f"[{pair.run_id} {n}/{len(copies)}] {case} exit {rc} in {t1 - t0:.0f} s"
            + (f" -- FAILED: {reason}" if reason else ""))
        _write_json(pair.dest / "batch.json", doc)
    (pair.dest / "end.txt").write_text(f"{time.time():.3f}")
    doc["status"] = "failed" if doc["failures"] else "ok"
    doc["finished"] = _now()
    _write_json(pair.dest / "batch.json", doc)
    return doc


def pair_status(pair: Pair) -> str | None:
    """``batch.json``'s status for an existing pair directory, ``"incomplete"`` without one."""
    if not pair.dest.exists():
        return None
    path = pair.dest / "batch.json"
    if not path.exists():
        return "incomplete"
    return json.loads(path.read_text(encoding="utf-8")).get("status", "incomplete")


def run_plan(pairs: Sequence[Pair], frozen: Path, *, backend: str, workers: int, case_timeout: float,
             python: str = sys.executable, resume: bool = False, keep_going: bool = False,
             runner: Runner = run_logged, env: dict[str, str] | None = None,
             log: Callable[[str], None] = print) -> list[dict[str, Any]]:
    """Run ``pairs`` in series. An existing pair is skipped only with ``resume`` and
    only if it finished ``ok``; anything else in the way is an error, never overwritten."""
    cases = frozen_cases(frozen)
    blocking = [(p, s) for p in pairs if (s := pair_status(p)) is not None and not (resume and s == "ok")]
    if blocking:
        raise BatchError("these pair directories already exist; move them away (or --resume to skip "
                         "the ones that finished ok):\n  " + "\n  ".join(f"{p.dest} ({s})" for p, s in blocking))
    done = []
    for i, pair in enumerate(pairs, 1):
        if pair_status(pair) == "ok":
            log(f"== pair {i}/{len(pairs)} {pair.run_id}: already ok, skipped")
            continue
        log(f"== pair {i}/{len(pairs)} {pair.run_id} -> {pair.dest}")
        doc = run_pair(pair, frozen, cases, backend=backend, workers=workers, case_timeout=case_timeout,
                       python=python, runner=runner, env=env, log=log)
        done.append(doc)
        log(f"== pair {pair.run_id}: {doc['status']}"
            + (f" ({len(doc['failures'])} failing case(s))" if doc["failures"] else ""))
        if doc["status"] != "ok" and not keep_going:
            log("stopping: a failed pair usually means the backend is down or rate-limited "
                "(--keep-going to continue)")
            break
    return done


def describe_plan(pairs: Sequence[Pair], cases: Sequence[Path], *, backend: str, workers: int,
                  case_timeout: float, python: str) -> str:
    lines = [f"{len(pairs)} pair(s), in this order, each a copy of {len(cases)} case run(s); "
             f"backend {backend}, {workers} conversation(s) per case, {case_timeout:.0f} s per case:"]
    for i, p in enumerate(pairs, 1):
        lines.append(f"  {i}. {p.run_id:<24} -> {p.dest}   [{pair_status(p) or 'new'}]")
    if cases:
        example = triage_command(python, pairs[0].dest / cases[0].name, pairs[0].row, backend, workers) if pairs else []
        lines.append("per case, e.g.: " + " ".join(example))
    return "\n".join(lines)
