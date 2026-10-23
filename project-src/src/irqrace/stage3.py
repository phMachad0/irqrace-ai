"""Stage 3 — path feasibility, decided by Z3.

The only stage whose verdict may discard a candidate, and only an ``unsat`` one
([[Pipeline Design]], "Z3 and path feasibility"; Soundness Assumptions H1, H2).
The solving happens in ``analysis/src/irqrace-stage3.cpp``, over the LLVM IR,
because that is where the types, the data layout and SVF's points-to sets are.
This module is the bookkeeping around it:

* it writes the **query**: the flows, and for every instruction boundary of
  every flow the set of flows stage 2 says may run there -- which is how masking
  and priority reach the solver, without stage 3 recomputing either;
* it runs the binary and reads one verdict per candidate;
* it writes ``solver/results.jsonl`` (every verdict) and ``context/<id>.json``
  (the full C2 record of every candidate that is **not** ``unsat``: those are
  what Track B receives).

What a verdict means, precisely:

* ``unsat`` -- no execution of the over-approximate encoding reaches A1, then B
  inside [A1, A2] (or B at A, for a pair), then A2, touching one memory cell.
  Since every real execution is an execution of the encoding, none of those does
  either. A proof, and the only licence to drop.
* ``sat`` -- the encoding has such an execution. **Not** a confirmation: the
  encoding havocs everything a concurrently running flow may write, and
  everything a loop may write, so a SAT witness may be spurious. The record's
  ``unconstrained`` list says what was havocked.
* ``inconclusive`` -- timeout, exploration budget, or a construct the encoding
  cannot express soundly. Kept and passed on, with the reason (H2).
"""

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import Config
from .stage2 import Stage2, Stage2Error
from .toolchain import REPO_ROOT

STAGE3_PATH = REPO_ROOT / "analysis" / "build" / "bin" / "irqrace-stage3"

#: Per-candidate exploration budget, in symbolic states. Exceeding it is
#: `inconclusive`, never a verdict.
MAX_STATES = 40000

ROLES = ("A1", "B", "A2")


class Stage3Error(RuntimeError):
    pass


def _instruction(prog: dict[str, Any], access: dict[str, Any]) -> tuple[str, int, int]:
    """(function, block, instruction index) of a stage-1 access."""
    fn, b, k = access["function"], access["point"]["block"], access["point"]["event"]
    ev = prog[fn]["blocks"][b]["events"][k]
    if ev.get("k") != "access" or "i" not in ev:
        raise Stage3Error(f"access {access['id']} does not point at an access event; "
                          "re-run stage 1 with a W6+ irqrace-stage1")
    return fn, b, ev["i"]


def build_query(analysis: dict[str, Any], cfg: Config, candidates: list[dict[str, Any]],
                s2: Stage2, *, timeout_ms: int, max_states: int = MAX_STATES) -> str:
    m, c = s2.m, s2.c
    prog = {f["name"]: f for f in analysis["program"]["functions"]}
    accesses = {a["id"]: a for a in analysis["accesses"]}
    out = [f"timeout_ms {timeout_ms}", f"max_states {max_states}"]
    out += [f"primitive {p.function}" for p in cfg.masking_primitives]
    out += [f"model {x['function']} {x['effect']}" for x in cfg.data["externals"]["models"]]
    out.append(f"externals {cfg.data['externals']['default']}")
    out += [f"flow {f.id} {f.kind} {f.entry}" for f in cfg.flows]
    out += [f"static {f.id} {','.join(sorted(c.static_run[f.id])) or '-'}" for f in cfg.flows]

    # Stage 2's run sets, moved from its points (before event k) onto the
    # instruction boundaries they cover: (event k-1, event k].
    for F in cfg.flows:
        for fn in m.reach[F.id]:
            for b, blk in enumerate(prog[fn]["blocks"]):
                evs, n = blk["events"], blk.get("n")
                if n is None:
                    raise Stage3Error("stage1/accesses.json has no instruction counts; "
                                      "re-run stage 1 with a W6+ irqrace-stage1")
                for k in range(len(evs) + 1):
                    lo = 0 if k == 0 else evs[k - 1]["i"] + 1
                    hi = evs[k]["i"] if k < len(evs) else n - 1
                    if lo > hi:
                        continue
                    run = c.run(F.id, m.state(F.id, (fn, b, k)))
                    out.append(f"run {F.id} {fn} {b} {lo} {hi} {','.join(sorted(run)) or '-'}")

    for rec in candidates:
        by_role = {a["role"]: accesses[a["ir"]["access"]] for a in rec["accesses"]}
        roles = ROLES if rec["class"] == "atomicity-triple" else ROLES[:2]
        where = {r: _instruction(prog, by_role[r]) for r in roles}
        if rec["class"] == "atomicity-triple":
            (f1, b1, i1), (fb, bb, ib), (f2, b2, i2) = where["A1"], where["B"], where["A2"]
            out.append(f"cand {rec['id']} triple {by_role['A1']['flow']} {f1} {b1} {i1} "
                       f"{by_role['B']['flow']} {fb} {bb} {ib} {f2} {b2} {i2} AB")
        else:
            (fa, ba, ia), (fb, bb, ib) = where["A1"], where["B"]
            low, high = by_role["A1"]["flow"], by_role["B"]["flow"]
            dirs = []
            if high in c.run(low, m.state(low, s2._pre(by_role["A1"]))):
                dirs.append("AB")
            if low in c.run(high, m.state(high, s2._pre(by_role["B"]))):
                dirs.append("BA")
            out.append(f"cand {rec['id']} pair {low} {fa} {ba} {ia} {high} {fb} {bb} {ib} "
                       f"{','.join(dirs) or 'AB,BA'}")
    return "\n".join(out) + "\n"


def run_stage3(bitcode: Path, query: str, *, n_candidates: int, timeout_ms: int,
               binary: Path | None = None) -> list[dict[str, Any]]:
    exe = Path(binary or STAGE3_PATH)
    if not exe.exists():
        raise Stage3Error(f"irqrace-stage3 not built at {exe}; run scripts/build-analysis.sh")
    with tempfile.NamedTemporaryFile("w", suffix=".query", delete=False) as fh:
        fh.write(query)
        qpath = fh.name
    try:
        # Each candidate has its own deadline inside the binary; this outer one
        # only catches a hang, and a hang is a failure, not a verdict.
        limit = 120 + n_candidates * (timeout_ms / 1000.0 + 1)
        proc = subprocess.run([str(exe), "--query", qpath, str(bitcode)],
                              capture_output=True, text=True, timeout=limit)
    finally:
        Path(qpath).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise Stage3Error(f"irqrace-stage3 failed ({proc.returncode}):\n"
                          f"{proc.stderr.strip()[:4000]}")
    out = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
    if len(out) != n_candidates:
        raise Stage3Error(f"irqrace-stage3 returned {len(out)} verdicts for "
                          f"{n_candidates} candidates")
    return out


SOLVER_FIELDS = ("verdict", "engine", "engine_version", "reason", "assignment",
                 "unconstrained", "wall_ms", "timeout_ms")


def _note(result: dict[str, Any]) -> dict[str, str]:
    unc = ", ".join(result.get("unconstrained") or []) or "nothing"
    if result["verdict"] == "sat":
        a = result.get("assignment") or {}
        at = a.get("preempted_at") or {}
        return {"fact": "solver_result", "status": "overapproximated", "note": (
            f"Z3 found an execution of the over-approximate encoding with the "
            f"preemption at line {at.get('line')} of {at.get('function')}. SAT means "
            f"NOT REFUTED, not confirmed: the encoding leaves unconstrained {unc}, so "
            f"the witness may not be a real execution.")}
    return {"fact": "solver_result", "status": "unknown", "note": (
        f"the solver did not settle this candidate ({result.get('reason')}); it is "
        f"kept, never dropped (Soundness Assumptions H2). Unconstrained so far: {unc}.")}


def stage3(cfg: Config, store, bitcode: Path) -> dict[str, Any]:
    """Run stage 3 over a run store whose stage 2 has completed."""
    t0 = time.perf_counter()
    candidates = store.read_candidates("stage2")
    solver_cfg = cfg.analysis["solver"]
    timeout_ms = int(solver_cfg["timeout_ms"])

    if not solver_cfg["enabled"]:
        store.set_stage("solver", "skipped")
        for rec in candidates:
            out = copy.deepcopy(rec)
            out["solver_result"] = {"verdict": "not_run", "engine": "z3"}
            out["emitted_by"] = {**rec.get("emitted_by", {}), "stage": "stage3"}
            store.write_context(out)
        store.set_stage("context", "ok", candidates_in=len(candidates),
                        candidates_out=len(candidates))
        return {"in": len(candidates), "verdicts": {"not_run": len(candidates)},
                "kept": len(candidates), "dropped": 0, "wall_ms": 0}

    store.set_stage("solver", "running")
    try:
        analysis = json.loads((store.root / "stage1" / "accesses.json").read_text())
        s2 = Stage2(analysis, cfg)
        query = build_query(analysis, cfg, candidates, s2, timeout_ms=timeout_ms)
        (store.root / "solver" / "query.txt").write_text(query)
        results = run_stage3(bitcode, query, n_candidates=len(candidates),
                             timeout_ms=timeout_ms)
    except (Stage2Error, Stage3Error, OSError, KeyError, subprocess.TimeoutExpired) as e:
        store.set_stage("solver", "failed", error=str(e))
        store.log("error", "solver", "stage3-failed", str(e))
        raise Stage3Error(str(e)) from e

    by_id = {r["candidate_id"]: r for r in results}
    counts: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    stats = []
    with (store.root / "solver" / "results.jsonl").open("w", encoding="utf-8") as fh:
        for rec in candidates:
            r = by_id[rec["id"]]
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
            solver_result = {k: r[k] for k in SOLVER_FIELDS if k in r}
            fh.write(json.dumps({"candidate_id": rec["id"], **solver_result},
                                sort_keys=True, ensure_ascii=False) + "\n")
            stats.append({"candidate_id": rec["id"], "verdict": r["verdict"],
                          "method": r.get("method"), "states": r.get("states"),
                          "solver_calls": r.get("solver_calls"), "wall_ms": r.get("wall_ms")})
            if r["verdict"] == "unsat":
                continue  # the solver's exclusive privilege: no context record
            out = copy.deepcopy(rec)
            out["solver_result"] = solver_result
            out["emitted_by"] = {**rec.get("emitted_by", {}), "stage": "stage3"}
            entries = [e for e in out["provenance"]["entries"] if e["fact"] != "solver_result"]
            entries.append(_note(r))
            out["provenance"]["entries"] = entries
            kept.append(out)
    (store.root / "solver" / "stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n")

    wall = int((time.perf_counter() - t0) * 1000)
    engine = results[0]["engine_version"] if results else ""
    m = store.read_manifest()
    m["solver"] = {"enabled": True, "engine_version": engine, "timeout_ms": timeout_ms}
    store.write_manifest(m)
    store.set_stage("solver", "ok", candidates_in=len(candidates), candidates_out=len(kept),
                    dropped_with_proof=counts.get("unsat", 0), wall_ms=wall)

    t1 = time.perf_counter()
    for rec in kept:
        store.write_context(rec)
    store.set_stage("context", "ok", candidates_in=len(kept), candidates_out=len(kept),
                    wall_ms=int((time.perf_counter() - t1) * 1000))
    store.log("info", "solver", "verdicts",
              ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "no candidates",
              wall_ms=wall)
    methods: dict[str, int] = {}
    for st in stats:
        if st["method"]:
            methods[st["method"]] = methods.get(st["method"], 0) + 1
    return {"in": len(candidates), "verdicts": counts, "kept": len(kept), "methods": methods,
            "dropped": counts.get("unsat", 0), "wall_ms": wall,
            "triples_kept": sum(1 for r in kept if r["class"] == "atomicity-triple"),
            "pairs_kept": sum(1 for r in kept if r["class"] == "race-pair")}
