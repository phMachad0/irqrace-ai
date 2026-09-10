#!/usr/bin/env python3
"""Build ``contracts/examples/run-fixture/`` — a hand-written C3 run directory.

Track C builds the dashboard against this from week 2, so it is never blocked on
Track A, and ``irqrace runstore check`` is verified against it by the test suite.
It deliberately contains no bitcode: the fixture is about the *layout*, and a
binary blob in the examples directory would be noise.

Regenerate with:  python3 scripts/make-run-fixture.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from irqrace import contracts  # noqa: E402
from irqrace.config import Config  # noqa: E402
from irqrace.runstore import RunStore  # noqa: E402

EXAMPLES = REPO / "contracts" / "examples"
FIXTURE = EXAMPLES / "run-fixture"
RUN_ID = "svp_simple_001_001-20260831T120000Z-f1x7ur"


def main() -> int:
    if FIXTURE.exists():
        shutil.rmtree(FIXTURE)

    cfg = Config.load(EXAMPLES / "c1-svp_simple_001_001.yaml")
    store = RunStore.create(cfg, run_root=FIXTURE.parent, run_id=FIXTURE.name)

    bug = json.loads((EXAMPLES / "c2-bugpoint.json").read_text())
    trap = json.loads((EXAMPLES / "c2-trap.json").read_text())
    for rec in (bug, trap):
        rec["emitted_by"]["run_id"] = RUN_ID

    # Stage 1 knows nothing about masking or preemption yet; those fields are
    # stage 2's. Stripping them here keeps the fixture honest about which stage
    # produces what, which is the thing a UI built against it will get wrong.
    def as_stage1(rec: dict) -> dict:
        r = json.loads(json.dumps(rec))
        r.pop("masking", None)
        r.pop("preemption", None)
        r.pop("solver_result", None)
        r["emitted_by"]["stage"] = "stage1"
        return r

    store.append_candidates("stage1", [as_stage1(bug), as_stage1(trap)])
    store.append_candidates("stage2", [bug, trap])

    # The trap is exactly what a solver is for: one critical section covers the
    # whole interval, so the interleaving is provably impossible and UNSAT is a
    # licence to discard it. The bug point stays inconclusive and goes on to the
    # LLM -- which is the population Track B actually sees.
    results = [
        {"candidate_id": bug["id"], "verdict": "inconclusive", "engine": "z3",
         "engine_version": "4.8.12", "reason": "timeout",
         "unconstrained": ["timing"], "wall_ms": 10000, "timeout_ms": 10000},
        {"candidate_id": trap["id"], "verdict": "unsat", "engine": "z3",
         "engine_version": "4.8.12", "reason": None, "wall_ms": 42, "timeout_ms": 10000},
    ]
    with (store.root / "solver" / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(contracts.canonical_json(r) + "\n")

    # Only the inconclusive candidate gets a context record. The discarded one
    # does not, and `runstore check` accepts that only because there is an
    # `unsat` line naming it.
    bug["solver_result"] = {
        "verdict": "inconclusive", "engine": "z3", "engine_version": "4.8.12",
        "reason": "timeout", "unconstrained": ["timing"],
        "wall_ms": 10000, "timeout_ms": 10000,
    }
    bug["emitted_by"]["stage"] = "stage3"
    store.write_context(bug)

    m = store.read_manifest()
    m["created"] = "2026-08-31T12:00:00Z"
    m["build"] = {
        "cc": "clang-14", "cc_version": "Ubuntu clang version 14.0.0-1ubuntu1.1",
        "linker": "llvm-link-14",
        "flags": ["-g", "-O0", "-Xclang", "-disable-O0-optnone"],
        "translation_units": 2, "functions_with_bodies": 5,
        "functions_declared_only": ["disable_isr", "enable_isr"],
        "bitcode": "build/whole.bc",
        "bitcode_sha256": "0" * 64,
    }
    m["solver"] = {"enabled": True, "engine_version": "4.8.12", "timeout_ms": 10000}
    m["stages"] = [
        {"name": "build",  "status": "ok", "wall_ms": 120},
        {"name": "stage1", "status": "ok", "wall_ms": 340, "candidates_in": None,
         "candidates_out": 2, "dropped_with_proof": 0},
        {"name": "stage2", "status": "ok", "wall_ms": 55, "candidates_in": 2,
         "candidates_out": 2, "dropped_with_proof": 0},
        {"name": "solver", "status": "ok", "wall_ms": 10042, "candidates_in": 2,
         "candidates_out": 1, "dropped_with_proof": 1},
        {"name": "context", "status": "ok", "candidates_in": 1, "candidates_out": 1},
        {"name": "triage", "status": "pending"},
        {"name": "repair", "status": "pending"},
        {"name": "reverify", "status": "pending"},
    ]
    store.write_manifest(m)

    (FIXTURE / "build").mkdir(exist_ok=True)
    (FIXTURE / "build" / "README.txt").write_text(
        "whole.bc is omitted from the fixture on purpose: this directory "
        "documents the C3 layout, not the bitcode.\n"
    )

    problems = store.check()
    if problems:
        for p in problems:
            print(f"FAIL {p}", file=sys.stderr)
        return 1
    print(f"wrote {FIXTURE.relative_to(REPO)} — runstore check passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
