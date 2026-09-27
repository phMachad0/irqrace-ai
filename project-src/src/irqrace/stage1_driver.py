"""Running the stage-1 binary and writing its output into a C3 run store."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .config import Config
from .stage1 import derive_candidates
from .toolchain import REPO_ROOT

STAGE1_PATH = REPO_ROOT / "analysis" / "build" / "bin" / "irqrace-stage1"


class Stage1Error(RuntimeError):
    pass


def run_stage1(bitcode: Path, cfg: Config, *, binary: Path | None = None,
               timeout: int = 900) -> dict[str, Any]:
    exe = Path(binary or STAGE1_PATH)
    if not exe.exists():
        raise Stage1Error(f"irqrace-stage1 not built at {exe}; "
                          "run scripts/build-analysis.sh")

    cmd = [str(exe)]
    for f in cfg.flows:
        cmd += ["--flow", f"{f.id}:{f.kind}:{f.entry}:"
                          f"{-1 if f.irq is None else f.irq}:{f.priority}"]
    for p in cfg.masking_primitives:
        cmd += ["--primitive", p.function]
    # Externals modelled as touching nothing are not descended into. Which ones
    # were modelled is part of the abstraction the soundness claim rests on, so
    # it travels in the configuration rather than being hard-coded here.
    for m in cfg.data["externals"]["models"]:
        if m["effect"] == "none":
            cmd += ["--transparent", m["function"]]
    cmd += ["--indirect-calls", cfg.analysis["indirect_calls"]]
    cmd.append(str(bitcode))

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise Stage1Error(f"irqrace-stage1 failed ({proc.returncode}):\n"
                          f"{proc.stderr.strip()[:4000]}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise Stage1Error("irqrace-stage1 did not produce JSON:\n"
                          f"{proc.stdout[:2000]}") from e


def stage1(cfg: Config, store, bitcode: Path) -> dict[str, Any]:
    """Run stage 1 into an open run store. Returns a summary."""
    store.set_stage("stage1", "running")
    try:
        analysis = run_stage1(bitcode, cfg)
    except Stage1Error as e:
        store.set_stage("stage1", "failed", error=str(e))
        store.log("error", "stage1", "stage1-failed", str(e))
        raise

    (store.root / "stage1" / "accesses.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False) + "\n")

    for w in analysis.get("warnings", []):
        store.log(w.get("severity", "warn"), "stage1", w["code"], w["message"])

    candidates = derive_candidates(analysis, cfg)
    n = store.append_candidates("stage1", candidates)

    triples = sum(1 for c in candidates if c["class"] == "atomicity-triple")
    store.set_stage(
        "stage1", "ok",
        candidates_out=n,
        # Stage 1 never discards: it is the generator, and only a proof may drop
        # a candidate anywhere downstream.
        dropped_with_proof=0,
    )
    store.log("info", "stage1", "candidates-derived",
              f"{n} candidates ({triples} triples, {n - triples} pairs) over "
              f"{len(analysis['accesses'])} accesses to "
              f"{len(analysis['objects'])} shared object(s)")
    return {
        "candidates": n,
        "triples": triples,
        "pairs": n - triples,
        "accesses": len(analysis["accesses"]),
        "objects": len(analysis["objects"]),
        "warnings": analysis.get("warnings", []),
    }
