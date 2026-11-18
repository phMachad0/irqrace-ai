"""The freeze-and-triage batch runner, on fake run trees: no toolchain, no model."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from benchfake import make_case, specs_001, specs_017
from irqrace import bench_batch as bb

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "freeze-and-triage.py"


def _frozen(root: Path) -> Path:
    make_case(root, "svp_simple_001_001", specs_001(), triaged=False)
    make_case(root, "svp_simple_017_001", specs_017(), triaged=False)
    (root / "freeze.json").write_text(json.dumps({"git_commit": "abc", "status": "ok"}))
    return root


class FakeTriage:
    """Stands in for ``irqrace llm triage``: writes a verdict file into the case run."""

    def __init__(self, fail: dict[str, str] | None = None):
        self.calls: list[list[str]] = []
        self.fail = fail or {}

    def __call__(self, cmd, *, log_path, timeout, env, cwd):
        self.calls.append(list(cmd))
        case_dir = Path(cmd[cmd.index("triage") + 1])
        subject = bb.subject_of(case_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("spend: requests=1 tokens_in=10 tokens_out=2 cache_read=0 cache_write=0 latency_s=1.0\n")
        mode = self.fail.get(subject)
        if mode == "timeout":
            return bb.TIMEOUT_RC
        if mode == "exit":
            return 1
        if mode == "no-file":
            return 0
        ids = [p.stem for p in (case_dir / "context").glob("*.json")]
        (case_dir / "llm" / "triage.jsonl").write_text("".join(
            json.dumps({"candidate_id": i, "bucket": "uncertain",
                        "not_triaged": "backend error" if mode == "untriaged" else None}) + "\n" for i in ids))
        return 0


def test_plan_interleaves_samples_and_names_one_directory_per_pair(tmp_path):
    pairs = bb.plan(tmp_path / "out", ["+racebench", "+racebench+c4"], 3)
    assert [p.run_id for p in pairs] == ["+racebench/1", "+racebench+c4/1", "+racebench/2",
                                         "+racebench+c4/2", "+racebench/3", "+racebench+c4/3"]
    assert pairs[1].dest == (tmp_path / "out" / "+racebench+c4" / "1").resolve()
    with pytest.raises(bb.BatchError):
        bb.plan(tmp_path, ["a/b"], 1)
    with pytest.raises(bb.BatchError):
        bb.plan(tmp_path, ["r", "r"], 1)
    with pytest.raises(bb.BatchError):
        bb.plan(tmp_path, ["r"], 0)


def test_the_triage_command_never_votes(tmp_path):
    cmd = bb.triage_command("py", tmp_path / "case", "+racebench", "claude-cli:sonnet", 4)
    assert cmd[1:5] == ["-m", "irqrace", "llm", "triage"]
    assert cmd[cmd.index("--samples") + 1] == "1"
    assert cmd[cmd.index("--workers") + 1] == "4"
    assert cmd[cmd.index("--row") + 1] == "+racebench"


def test_frozen_root_is_checked(tmp_path):
    root = _frozen(tmp_path / "frozen")
    assert [bb.subject_of(r) for r in bb.frozen_cases(root)] == ["svp_simple_001_001", "svp_simple_017_001"]
    make_case(tmp_path / "tri", "svp_simple_001_001", specs_001(), triaged=True)
    with pytest.raises(bb.BatchError, match="already triaged"):
        bb.frozen_cases(tmp_path / "tri")
    make_case(root, "svp_simple_001_001", specs_001(), triaged=False, run_id="svp_simple_001_001-later")
    with pytest.raises(bb.BatchError, match="two runs"):
        bb.frozen_cases(root)
    with pytest.raises(bb.BatchError, match="no run directories"):
        bb.frozen_cases(tmp_path / "empty")


def test_a_pair_triages_its_own_copy_and_leaves_the_frozen_root_alone(tmp_path):
    frozen = _frozen(tmp_path / "frozen")
    before = sorted(p.relative_to(frozen) for p in frozen.rglob("*"))
    runner = FakeTriage()
    pairs = bb.plan(tmp_path / "out", ["+racebench"], 2)
    docs = bb.run_plan(pairs, frozen, backend="fake:m", workers=2, case_timeout=5, python="py",
                       runner=runner, env={}, log=lambda _m: None)
    assert [d["status"] for d in docs] == ["ok", "ok"]
    assert sorted(p.relative_to(frozen) for p in frozen.rglob("*")) == before
    assert not list(frozen.rglob("triage.jsonl"))
    for p in pairs:
        assert len(list(p.dest.glob("*/llm/triage.jsonl"))) == 2
        lines = (p.dest / "timings.tsv").read_text().splitlines()
        assert [ln.split("\t")[0] for ln in lines] == ["svp_simple_001_001", "svp_simple_017_001"]
        assert all(ln.split("\t")[3] == "0" for ln in lines)
        assert (p.dest / "freeze.json").exists() and (p.dest / "start.txt").exists()
        assert json.loads((p.dest / "batch.json").read_text())["sample"] == p.sample
    assert len(runner.calls) == 4
    assert {Path(c[c.index("triage") + 1]).parent for c in runner.calls} == {p.dest for p in pairs}


@pytest.mark.parametrize("mode,reason", [("timeout", "timeout"), ("exit", "exit 1"),
                                         ("no-file", "no llm/triage.jsonl"), ("untriaged", "not triaged")])
def test_any_failing_case_fails_the_pair_and_stops_the_plan(tmp_path, mode, reason):
    frozen = _frozen(tmp_path / "frozen")
    runner = FakeTriage({"svp_simple_017_001": mode})
    pairs = bb.plan(tmp_path / "out", ["r"], 2)
    docs = bb.run_plan(pairs, frozen, backend="fake:m", workers=1, case_timeout=5, python="py",
                       runner=runner, env={}, log=lambda _m: None)
    assert len(docs) == 1 and docs[0]["status"] == "failed"
    assert docs[0]["failures"][0]["case"] == "svp_simple_017_001"
    assert reason in docs[0]["failures"][0]["reason"]
    assert json.loads((pairs[0].dest / "batch.json").read_text())["status"] == "failed"
    assert not pairs[1].dest.exists()


def test_existing_pairs_are_never_overwritten_and_resume_skips_only_ok_ones(tmp_path):
    frozen = _frozen(tmp_path / "frozen")
    pairs = bb.plan(tmp_path / "out", ["r"], 2)
    kw = dict(backend="fake:m", workers=1, case_timeout=5, python="py", env={}, log=lambda _m: None)
    bb.run_plan(pairs[:1], frozen, runner=FakeTriage(), **kw)
    with pytest.raises(bb.BatchError, match="already exist"):
        bb.run_plan(pairs, frozen, runner=FakeTriage(), **kw)
    runner = FakeTriage()
    docs = bb.run_plan(pairs, frozen, runner=runner, resume=True, **kw)
    assert [d["run_id"] for d in docs] == ["r/2"] and len(runner.calls) == 2
    bad = bb.Pair("r", 3, tmp_path / "out" / "r" / "3")
    bad.dest.mkdir(parents=True)  # a half-made copy: no batch.json
    with pytest.raises(bb.BatchError, match="incomplete"):
        bb.run_plan([bad], frozen, runner=FakeTriage(), resume=True, **kw)


def test_freeze_runs_the_pipeline_per_config_and_checks_the_result(tmp_path):
    configs = [tmp_path / "svp_simple_001_001.yaml", tmp_path / "svp_simple_017_001.yaml"]
    for c in configs:
        c.write_text("fake: true\n")
    seen = []

    def pipeline(cmd, *, log_path, timeout, env, cwd):
        seen.append(cmd)
        assert cmd[cmd.index("--through") + 1] == "context"
        root = Path(cmd[cmd.index("--run-root") + 1])
        subject = Path(cmd[4]).stem
        make_case(root, subject, specs_001() if subject.endswith("001_001") else specs_017(), triaged=False)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok\n")
        return 0

    out = tmp_path / "frozen"
    doc = bb.freeze(configs, out, python="py", runner=pipeline, env={}, log=lambda _m: None)
    assert doc["status"] == "ok" and doc["failures"] == [] and len(seen) == 2
    assert json.loads((out / "freeze.json").read_text())["status"] == "ok"
    assert len((out / "timings.tsv").read_text().splitlines()) == 2
    with pytest.raises(bb.BatchError, match="not empty"):
        bb.freeze(configs, out, python="py", runner=pipeline, env={}, log=lambda _m: None)


def test_freeze_marks_a_failing_case(tmp_path):
    cfg = tmp_path / "svp_simple_001_001.yaml"
    cfg.write_text("fake: true\n")
    doc = bb.freeze([cfg], tmp_path / "frozen", python="py", runner=lambda *a, **k: 1, env={},
                    log=lambda _m: None)
    assert doc["status"] == "failed"
    assert {f["reason"].split(":")[0] for f in doc["failures"]} >= {"exit 1"}


def test_children_get_this_checkout_and_no_racebench_override(monkeypatch):
    monkeypatch.setenv("IRQRACE_RACEBENCH", "/mnt/c/Users/x/racebench")
    env = bb.child_env()
    assert "IRQRACE_RACEBENCH" not in env
    assert env["PYTHONPATH"].split(";" if sys.platform == "win32" else ":")[0] == str(REPO / "src")
    assert bb.child_env(keep_racebench_env=True)["IRQRACE_RACEBENCH"] == "/mnt/c/Users/x/racebench"


def test_run_logged_enforces_the_timeout(tmp_path):
    log = tmp_path / "logs" / "c.log"
    rc = bb.run_logged([sys.executable, "-c", "import time; print('hi', flush=True); time.sleep(30)"],
                       log_path=log, timeout=2)
    assert rc == bb.TIMEOUT_RC
    text = log.read_text()
    assert "hi" in text and "timeout" in text
    assert bb.run_logged([sys.executable, "-c", "raise SystemExit(3)"], log_path=log, timeout=30) == 3


def test_dry_run_prints_the_plan_and_touches_nothing(tmp_path, capsys):
    frozen = _frozen(tmp_path / "frozen")
    spec = importlib.util.spec_from_file_location("freeze_and_triage", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path / "out"
    rc = mod.main(["triage", "--frozen", str(frozen), "--out", str(out), "--rows", "+racebench,+racebench+c4",
                   "--samples", "3", "--backend", "claude-cli:sonnet", "--dry-run"])
    text = capsys.readouterr().out
    assert rc == 0 and not out.exists()
    assert "6 pair(s)" in text and "+racebench+c4/3" in text and "--samples 1" in text
    assert mod.main(["triage", "--frozen", str(tmp_path / "nope"), "--out", str(out), "--rows", "r",
                     "--backend", "b", "--dry-run"]) == 2
