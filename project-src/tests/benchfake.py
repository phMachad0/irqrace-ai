"""Tiny fake Racebench run roots for the scorer and batch-runner tests.

A fake case run is a C3 run directory written by hand: a manifest, stage 1's
candidates, the stage 2 drops, solver verdicts, context records and (optionally)
triage verdicts. Candidates sit on the real annotated lines of real cases, so the
ground truth comes from the vendored suite through the harness's own match rule.
No toolchain, no model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Annotated triples of two real cases (53/33 labels), A1 B A2.
#: 001: bug 1 WRW (32,55,35) global_array, bug 2 WRW (43,64,44) global_var,
#:      trap 1 WRW (32,60,35) global_array.
#: 017: bugs RWR (29,39,29), RWR (29,39,32), RWW (32,39,30), WWR (30,39,29);
#:      trap 1 WWW (32,41,32) local_array.
ROLES = ("A1", "B", "A2")
STAGES = ("build", "stage1", "stage2", "solver", "context", "triage", "repair", "reverify")


def cand(cid: str, subject: str, pattern: str, lines: tuple[int, int, int], var: str) -> dict[str, Any]:
    n = subject[11:14]
    f = f"svp_simple_{n}/{subject}.c"
    return {
        "id": cid,
        "pattern": pattern,
        "variable": {"name": var, "aliases": []},
        "accesses": [
            {"role": r, "kind": "read" if k == "R" else "write", "source": {"file": f, "line": ln}}
            for r, k, ln in zip(ROLES, pattern, lines)
        ],
    }


def make_case(root: Path, subject: str, specs: list[dict[str, Any]], *, run_id: str | None = None,
              triaged: bool = True, model: str = "claude-cli:sonnet", row: str = "+racebench",
              triage_ms: int = 5000, calls_per_candidate: int = 2) -> Path:
    """One case run under ``root``. Each spec: ``id, pattern, lines, var, fate``
    (``llm`` | ``stage2`` | ``unsat``) and, for ``llm``, ``feas``, ``bucket``,
    optionally ``conf`` and ``not_triaged``."""
    run = root / (run_id or f"{subject}-20261112T000000Z-000000")
    for d in ("stage1", "stage2", "solver", "context", "llm", "eval"):
        (run / d).mkdir(parents=True, exist_ok=True)
    recs = [cand(s["id"], subject, s["pattern"], s["lines"], s["var"]) for s in specs]
    by_id = {r["id"]: r for r in recs}
    llm = [s for s in specs if s["fate"] == "llm"]
    stages = {n: {"name": n, "status": "pending"} for n in STAGES}
    stages["build"].update(status="ok", wall_ms=100)
    stages["stage1"].update(status="ok", candidates_out=len(specs), wall_ms=200)
    s2 = [s for s in specs if s["fate"] != "stage2"]
    stages["stage2"].update(status="ok", candidates_out=len(s2), wall_ms=30)
    stages["solver"].update(status="ok", candidates_out=len(llm), wall_ms=400)
    stages["context"].update(status="ok", candidates_out=len(llm), wall_ms=20)
    if triaged:
        stages["triage"].update(status="ok", candidates_out=len(llm), wall_ms=triage_ms)
    manifest = {
        "schema_version": "c3/1.1.0", "run_id": run.name,
        "subject": {"name": subject, "source_root": "/nowhere", "sources": []},
        "llm": ({"model": model, "prompt_config": row, "votes": 1} if triaged else None),
        "stages": list(stages.values()),
    }
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (run / "config.yaml").write_text("fake: true\n")
    (run / "stage1" / "candidates.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    (run / "stage2" / "candidates.jsonl").write_text(
        "".join(json.dumps(by_id[s["id"]]) + "\n" for s in s2))
    (run / "stage2" / "dropped.jsonl").write_text("".join(
        json.dumps({"candidate_id": s["id"], "reason": "masking", "proof": "masked"}) + "\n"
        for s in specs if s["fate"] == "stage2"))
    (run / "solver" / "results.jsonl").write_text("".join(
        json.dumps({"candidate_id": s["id"], "verdict": "unsat" if s["fate"] == "unsat" else "sat"}) + "\n"
        for s in s2))
    for s in llm:
        (run / "context" / f"{s['id']}.json").write_text(json.dumps(by_id[s["id"]]))
    if triaged:
        order = {"likely_real": 0, "uncertain": 1, "likely_benign": 2, "likely_infeasible": 3}
        verdicts = sorted(llm, key=lambda s: (order[s["bucket"]], s["id"]))
        with (run / "llm" / "triage.jsonl").open("w") as fh:
            for s in verdicts:
                fh.write(json.dumps({
                    "candidate_id": s["id"],
                    "feasibility": {"verdict": s["feas"], "confidence": s.get("conf", 0.9)},
                    "harmfulness": None, "bucket": s["bucket"], "not_triaged": s.get("not_triaged"),
                    "produced_by": {"backend": model},
                }) + "\n")
                d = run / "llm" / s["id"]
                d.mkdir(exist_ok=True)
                (d / "turns.jsonl").write_text("".join(
                    json.dumps({"role": role}) + "\n"
                    for role in ["user"] + ["assistant"] * calls_per_candidate))
    return run


def specs_001(*, trap_bucket: str = "likely_infeasible", bug2_feas: str = "feasible",
              extra_bucket: str = "likely_real") -> list[dict[str, Any]]:
    """001: both bug points reach the LLM, the trap reaches it too, one unannotated
    candidate reaches it and one is dropped by stage 2."""
    trap_feas = "infeasible" if trap_bucket == "likely_infeasible" else "feasible"
    return [
        {"id": "c001b1", "pattern": "WRW", "lines": (32, 55, 35), "var": "svp_simple_001_001_global_array",
         "fate": "llm", "feas": "feasible", "bucket": "likely_real"},
        {"id": "c001b2", "pattern": "WRW", "lines": (43, 64, 44), "var": "svp_simple_001_001_global_var",
         "fate": "llm", "feas": bug2_feas,
         "bucket": "likely_real" if bug2_feas == "feasible" else "likely_infeasible"},
        {"id": "c001t1", "pattern": "WRW", "lines": (32, 60, 35), "var": "svp_simple_001_001_global_array",
         "fate": "llm", "feas": trap_feas, "bucket": trap_bucket},
        {"id": "c001u1", "pattern": "RWR", "lines": (55, 32, 60), "var": "svp_simple_001_001_global_array",
         "fate": "llm", "feas": "feasible" if extra_bucket == "likely_real" else "uncertain",
         "bucket": extra_bucket},
        {"id": "c001u2", "pattern": "RWR", "lines": (60, 32, 55), "var": "svp_simple_001_001_global_array",
         "fate": "stage2"},
    ]


def specs_017() -> list[dict[str, Any]]:
    """017: the RWR, RWW and WWR bug points reach the LLM; bug 2 is never generated
    by stage 1; the WWW trap is refuted by the solver."""
    v = "svp_simple_017_001_global_var"
    return [
        {"id": "c017b1", "pattern": "RWR", "lines": (29, 39, 29), "var": v, "fate": "llm",
         "feas": "feasible", "bucket": "likely_real"},
        {"id": "c017b3", "pattern": "RWW", "lines": (32, 39, 30), "var": v, "fate": "llm",
         "feas": "uncertain", "bucket": "uncertain"},
        {"id": "c017b4", "pattern": "WWR", "lines": (30, 39, 29), "var": v, "fate": "llm",
         "feas": "feasible", "bucket": "likely_real"},
        {"id": "c017t1", "pattern": "WWW", "lines": (32, 41, 32), "var": "svp_simple_017_001_local_array",
         "fate": "unsat"},
        {"id": "c017u1", "pattern": "RWW", "lines": (29, 39, 30), "var": v, "fate": "llm",
         "feas": "infeasible", "bucket": "likely_infeasible"},
    ]


def make_root(root: Path, *, triaged: bool = True, row: str = "+racebench", **kw001) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    make_case(root, "svp_simple_001_001", specs_001(**kw001), triaged=triaged, row=row)
    make_case(root, "svp_simple_017_001", specs_017(), triaged=triaged, row=row)
    return root
