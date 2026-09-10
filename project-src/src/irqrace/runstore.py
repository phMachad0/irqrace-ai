"""C3 — the run store.

A run is a directory, not a session. See ``contracts/c3-run-store.md`` for the
layout and the rules; this module is the only thing that writes it.

The invariant worth restating here, because it is the one a future refactor is
most likely to break: **only the solver may record a drop.** Every candidate
that leaves the funnel must leave a trace explaining why, and a candidate that
merely vanishes is a silent recall loss.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import TOOL_VERSION, contracts
from .config import Config

STAGE_NAMES = [
    "build", "stage1", "stage2", "solver", "context", "triage", "repair", "reverify",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id(subject: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{subject}-{stamp}-{secrets.token_hex(3)}"


class RunStore:
    """One ``runs/<run_id>/`` directory."""

    def __init__(self, root: Path):
        self.root = Path(root)

    # -- creation --------------------------------------------------------

    @classmethod
    def create(cls, cfg: Config, run_root: Path | None = None,
               run_id: str | None = None) -> "RunStore":
        run_root = Path(run_root or cfg.data["output"]["run_root"])
        run_id = run_id or cfg.data["output"].get("run_id") or new_run_id(cfg.name)
        store = cls(run_root / run_id)
        for sub in ("build", "stage1", "stage2", "solver", "context", "llm",
                    "repair", "eval"):
            (store.root / sub).mkdir(parents=True, exist_ok=True)

        # The configuration is copied verbatim, resolved: what the run used, not
        # what the user typed. Reproducing a run must not depend on the defaults
        # of whatever version of the tool is installed later.
        (store.root / "config.yaml").write_text(cfg.dump())

        manifest: dict[str, Any] = {
            "schema_version": "c3/1.0.0",
            "run_id": run_id,
            "created": _utcnow(),
            "tool_version": TOOL_VERSION,
            "git_revision": None,
            "subject": {
                "name": cfg.name,
                "source_root": cfg.subject.get("source_root", ""),
                "sources": list(cfg.subject["sources"]),
            },
            "config_hash": cfg.hash(),
            "semantics": {
                "priority_convention": cfg.data["priority_convention"],
                "equal_priority_preemption": cfg.semantics["equal_priority_preemption"],
                "isr_arrival": cfg.semantics["isr_arrival"],
                "isr_reentrant": cfg.semantics["isr_reentrant"],
                "nesting": cfg.semantics["nesting"],
                "timing_model": cfg.semantics["timing_model"],
                "externals_default": cfg.data["externals"]["default"],
                "indirect_calls": cfg.analysis["indirect_calls"],
                "allow_same_statement_a1_a2": cfg.analysis["allow_same_statement_a1_a2"],
                # Both are W2 blockers and deliberately null until decided, so
                # that any number produced before then is visibly unquotable.
                "counting_unit": None,
                "match_rule": None,
            },
            "solver": {
                "enabled": cfg.analysis["solver"]["enabled"],
                "engine_version": "",
                "timeout_ms": cfg.analysis["solver"]["timeout_ms"],
            },
            "llm": None,
            "stages": [{"name": n, "status": "pending"} for n in STAGE_NAMES],
        }
        store.write_manifest(manifest)
        for note in cfg.notes:
            store.log("info", "config", "config-note", note)
        return store

    # -- manifest --------------------------------------------------------

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    def read_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text())

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        contracts.validate("c3-manifest", manifest, what=str(self.manifest_path))
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, self.manifest_path)  # atomic: the UI polls this file

    def update_manifest(self, **fields: Any) -> dict[str, Any]:
        m = self.read_manifest()
        m.update(fields)
        self.write_manifest(m)
        return m

    def set_stage(self, name: str, status: str, **fields: Any) -> None:
        if name not in STAGE_NAMES:
            raise ValueError(f"unknown stage {name!r}")
        m = self.read_manifest()
        for st in m["stages"]:
            if st["name"] == name:
                st["status"] = status
                if status == "running":
                    st["started"] = _utcnow()
                elif status in ("ok", "failed", "skipped"):
                    st["finished"] = _utcnow()
                st.update(fields)
                break
        self.write_manifest(m)

    # -- streams ---------------------------------------------------------

    def log(self, level: str, stage: str, event: str, message: str = "",
            **data: Any) -> None:
        entry: dict[str, Any] = {
            "ts": _utcnow(), "level": level, "stage": stage, "event": event,
        }
        if message:
            entry["message"] = message
        if data:
            entry["data"] = data
        contracts.validate("c3-log-event", entry, what="log entry")
        with (self.root / "log.ndjson").open("a", encoding="utf-8") as fh:
            fh.write(contracts.canonical_json(entry) + "\n")

    def append_candidates(self, stage: str, records: Iterable[dict[str, Any]],
                          *, validate: bool = True) -> int:
        """Append C2 records to ``<stage>/candidates.jsonl``."""
        if stage not in ("stage1", "stage2"):
            raise ValueError(f"candidates.jsonl is only written by stage1/stage2, not {stage!r}")
        n = 0
        path = self.root / stage / "candidates.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            for rec in records:
                if validate:
                    contracts.validate("c2", rec, what=f"{stage} candidate {rec.get('id')}")
                fh.write(contracts.canonical_json(rec) + "\n")
                n += 1
        return n

    def read_candidates(self, stage: str) -> list[dict[str, Any]]:
        path = self.root / stage / "candidates.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def write_context(self, record: dict[str, Any], *, validate: bool = True) -> Path:
        if validate:
            contracts.validate("c2", record, what=f"context record {record.get('id')}")
        path = self.root / "context" / f"{record['id']}.json"
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        return path

    # -- integrity -------------------------------------------------------

    def check(self) -> list[str]:
        """Verify a run against contract C3. Returns a list of violations.

        Rule 6 is the one that matters: a candidate may only disappear behind a
        proof. Everything else here is structural.
        """
        problems: list[str] = []
        if not self.manifest_path.exists():
            return [f"{self.root}: no manifest.json"]
        try:
            manifest = self.read_manifest()
            contracts.validate("c3-manifest", manifest, what=str(self.manifest_path))
        except Exception as e:  # noqa: BLE001
            return [str(e)]

        if not (self.root / "config.yaml").exists():
            problems.append("config.yaml missing; the run is not reproducible")

        s1 = {c["id"] for c in self.read_candidates("stage1")}
        s2 = {c["id"] for c in self.read_candidates("stage2")}

        unknown = s2 - s1
        if unknown:
            problems.append(
                f"{len(unknown)} candidate(s) appear in stage2 but not stage1: "
                "stage 2 filters, it does not create"
            )

        solver_path = self.root / "solver" / "results.jsonl"
        verdicts: dict[str, str] = {}
        if solver_path.exists():
            for line in solver_path.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    verdicts[r["candidate_id"]] = r["verdict"]

        contexts = {p.stem for p in (self.root / "context").glob("*.json")}
        if contexts or verdicts:
            survivors = s2 or s1
            for cid in sorted(survivors - contexts):
                if verdicts.get(cid) != "unsat":
                    problems.append(
                        f"candidate {cid} has no context record and no 'unsat' "
                        "solver verdict: it was dropped without a proof, which "
                        "is a silent recall loss (C3 rule 6)"
                    )
        return problems


def find_runs(run_root: Path) -> list[Path]:
    root = Path(run_root)
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if (p / "manifest.json").exists())
