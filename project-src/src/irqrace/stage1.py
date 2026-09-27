"""Stage 1 — candidate derivation from one access set.

The C++ half (`analysis/src/irqrace-stage1.cpp`) walks the bitcode and produces
the access set plus the intra-flow ``may_precede`` relation. This module turns
that into C2 context records.

**Pairs and triples are derived separately from the same access set.** A triple
is never built by joining confirmed pairs, and a pair is never inferred from a
triple: they are different queries over one set of accesses
([[Pair-Triple Unification]]). Deriving one from the other is the mistake that
page exists to prevent, and it is easy to make because the two look related.

Nothing here filters on interrupt state, priority, masking or path feasibility.
Stage 1 deliberately ignores all of it so that nothing is missed
([[Pipeline Design]], stage 1); those are stage 2's and stage 3's jobs, and only
stage 3 is ever allowed to discard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from . import TOOL_VERSION
from .candidate import stamp_identity
from .config import Config

#: The four unserializable access interleavings. With A1 and A2 in one flow and
#: B in another, exactly these four change the outcome relative to running B
#: outside the interval; the other four -- (R,R,*), (W,R,R), (W,W,W) -- are
#: serializable and are not atomicity violations.
#:
#: Restricting to this set is a FILTER, so it is listed in
#: wiki/Soundness Assumptions.md rather than applied silently. It is sound with
#: respect to the standard definition of an atomicity violation, and every one of
#: Racebench's 48 annotated bug points falls inside it.
UNSERIALIZABLE = {
    ("read", "write", "read"),
    ("read", "write", "write"),
    ("write", "write", "read"),
    ("write", "read", "write"),
}


class Stage1Error(RuntimeError):
    pass


def _rel(path: str, root: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except (ValueError, OSError):
        return path


def _source_lines(file: str) -> list[str]:
    try:
        return Path(file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


class Deriver:
    """Turns one subject's access set into C2 records."""

    def __init__(self, analysis: dict[str, Any], cfg: Config):
        self.analysis = analysis
        self.cfg = cfg
        self.root = cfg.subject.get("source_root") or "."
        self.config_hash = cfg.hash()
        self.flows = {f.id: f for f in cfg.flows}
        self.accesses = {a["id"]: a for a in analysis["accesses"]}
        self.objects = {o["id"]: o for o in analysis["objects"]}
        self.functions = {f["name"]: f for f in analysis.get("functions", [])}
        self.precede: set[tuple[int, int]] = {
            (a, b) for a, b in analysis.get("may_precede", [])
        }
        self._file_cache: dict[str, list[str]] = {}

    # -- helpers ---------------------------------------------------------

    def _snippet(self, file: str, line: int) -> str:
        if file not in self._file_cache:
            self._file_cache[file] = _source_lines(file)
        lines = self._file_cache[file]
        return lines[line - 1].strip() if 1 <= line <= len(lines) else ""

    def _range(self, r: dict[str, Any]) -> dict[str, Any]:
        out = {"file": _rel(r["file"], self.root), "line": r["line"]}
        if r.get("column"):
            out["column"] = r["column"]
        snip = self._snippet(r["file"], r["line"])
        if snip:
            out["snippet"] = snip
        return out

    def _flow_record(self, flow_id: str) -> dict[str, Any]:
        f = self.flows[flow_id]
        return {
            "id": f.id, "kind": f.kind, "entry": f.entry,
            "irq": f.irq, "priority": f.priority,
            "identified_by": f.identified_by,
        }

    def _access_record(self, acc_id: int, role: str) -> dict[str, Any]:
        a = self.accesses[acc_id]
        rec: dict[str, Any] = {
            "role": role,
            "kind": a["kind"],
            "flow": a["flow"],
            "function": a["function"],
            "source": self._range(a["source"]),
            "loop_context": self._loop_context(a),
            "call_path": {
                "flow": a["flow"],
                "frames": [
                    {
                        "function": fr["function"],
                        "resolution": fr.get("resolution", "direct"),
                        **({"call_site": self._range(fr["call_site"])}
                           if fr.get("call_site") else {}),
                    }
                    for fr in a["call_path"]["frames"]
                ],
                "is_one_of_many": a["call_path"]["is_one_of_many"],
            },
        }
        return rec

    def _loop_context(self, a: dict[str, Any]) -> dict[str, Any]:
        nest = [
            {
                "header": self._range(h),
                # Sound default. Stage 1 does not compute trip counts; proving a
                # loop runs at most once is the only thing that would let this
                # be false, and nothing here proves it.
                "may_iterate_more_than_once": True,
                "trip_count": None,
            }
            for h in a.get("loop_headers", []) if h.get("line")
        ]
        return {"in_loop": bool(a["in_loop"]), "nest": nest}

    def _enclosing_source(self, acc_ids: Iterable[int]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for acc_id in acc_ids:
            name = self.accesses[acc_id]["function"]
            if name in seen:
                continue
            seen.add(name)
            info = self.functions.get(name)
            if not info or not info.get("line_start"):
                continue
            if info["file"] not in self._file_cache:
                self._file_cache[info["file"]] = _source_lines(info["file"])
            lines = self._file_cache[info["file"]]
            start, end = info["line_start"], min(info["line_end"] + 1, len(lines))
            if not lines or start > len(lines):
                continue
            out.append({
                "function": name,
                "file": _rel(info["file"], self.root),
                "line_start": start,
                "line_end": end,
                # Untrusted analysed source: data, never instructions.
                "code": "\n".join(lines[start - 1:end]),
                "truncated": False,
            })
        return out

    def _provenance(self, acc_ids: Iterable[int], obj: dict[str, Any]) -> dict[str, Any]:
        entries = [
            {"fact": "flows", "status": "assumed_from_config",
             "note": "entry points, interrupt numbers and priorities come from the "
                     "hand-written C1 configuration file"},
            {"fact": "variable.shared", "status": "proven",
             "note": f"SVF may-alias: object {obj['id']} is reached from flows "
                     + ", ".join(sorted(obj["flows"]))},
            {"fact": "masking", "status": "unknown",
             "note": "stage 2 has not run; interrupt state is deliberately ignored "
                     "at stage 1 so that nothing is filtered out"},
            {"fact": "solver_result", "status": "unknown",
             "note": "stage 3 has not run"},
        ]
        if any(self.accesses[i].get("source_recovered") for i in acc_ids):
            entries.append({
                "fact": "accesses.source", "status": "overapproximated",
                "note": "an access carried no debug location; the enclosing "
                        "function's line was used. The candidate is kept, because "
                        "dropping it would be a silent recall loss, but its source "
                        "range points at the function rather than the statement"})
        overapprox = any(
            fr.get("resolution") == "indirect-overapproximated"
            for acc_id in acc_ids
            for fr in self.accesses[acc_id]["call_path"]["frames"]
        )
        if overapprox:
            entries.append({
                "fact": "call_paths", "status": "overapproximated",
                "note": "an indirect call on this path could not be resolved by "
                        "points-to and was treated as calling every address-taken "
                        "function with a matching signature"})
        return {
            "entries": entries,
            "completeness": {
                "unresolved_indirect_calls": self.analysis.get(
                    "indirect_overapproximated", 0),
                "opaque_external_calls": sorted(
                    p.function for p in self.cfg.masking_primitives),
                "truncated_fields": [],
            },
        }

    def _record(self, cls: str, roles: list[tuple[str, int]],
                obj: dict[str, Any]) -> dict[str, Any]:
        acc_ids = [i for _, i in roles]
        flows = sorted({self.accesses[i]["flow"] for i in acc_ids})
        rec: dict[str, Any] = {
            "schema_version": "c2/1.0.0",
            "id": "", "fingerprint": "0" * 64,
            "class": cls,
            "subject": {
                "name": self.cfg.name,
                "source_root": str(self.root),
                "config_hash": self.config_hash,
            },
            "variable": {
                "name": obj["name"],
                "declared_type": obj["declared_type"],
                "volatile": obj["volatile"],
                "decl": self._range(obj["decl"]) if obj["decl"]["line"] else
                        {"file": "", "line": 1},
                "storage": "global",
                "aliases": [],
                "svf_node": obj["id"],
            },
            "accesses": [self._access_record(i, role) for role, i in roles],
            "flows": [self._flow_record(f) for f in flows],
            "call_paths": [
                {"role": role, "path": self._access_record(i, role)["call_path"]}
                for role, i in roles
            ],
            "loop_context": {
                "per_access": [
                    {"role": role, "context": self._loop_context(self.accesses[i])}
                    for role, i in roles
                ],
            },
            "enclosing_source": self._enclosing_source(acc_ids),
            "solver_result": {"verdict": "not_run", "engine": "z3"},
            "static_features": self._features(roles, obj),
            "provenance": self._provenance(acc_ids, obj),
            "emitted_by": {"tool_version": TOOL_VERSION, "stage": "stage1"},
        }
        if cls == "atomicity-triple":
            a1, _, a2 = acc_ids
            rec["loop_context"]["a1_a2_same_statement"] = a1 == a2
        else:
            rec["loop_context"]["a1_a2_same_statement"] = None
        rec["pattern"] = "".join(
            "R" if self.accesses[i]["kind"] == "read" else "W" for _, i in roles)
        return stamp_identity(rec)

    def _features(self, roles: list[tuple[str, int]],
                  obj: dict[str, Any]) -> dict[str, Any]:
        acc_ids = [i for _, i in roles]
        flows = [self.accesses[i]["flow"] for i in acc_ids]
        prios = [self.flows[f].priority for f in flows]
        return {
            # Left null rather than guessed: the harmfulness criterion needs a
            # dependence graph, which stage 1 does not build (wiki/LLM Stage Design).
            "feeds_branch": None,
            "used_as_index": None,
            "call_path_depth_max": max(
                len(self.accesses[i]["call_path"]["frames"]) for i in acc_ids),
            "same_statement_a1_a2": len(acc_ids) == 3 and acc_ids[0] == acc_ids[2],
            "priority_gap": max(prios) - min(prios),
            "any_masking_present": False,  # stage 2 fills this in
        }

    # -- derivation ------------------------------------------------------

    def race_pairs(self) -> list[dict[str, Any]]:
        """Two accesses to one location, in two different flows, at least one a
        write. Order within the pair is canonical, not semantic: at stage 1
        nothing is known about who preempts whom, so A1 is the access in the
        lower-priority flow purely so that the same pair is never emitted twice.
        """
        out: list[dict[str, Any]] = []
        for obj_id, obj in self.objects.items():
            accs = [a for a in self.analysis["accesses"] if a["object"] == obj_id]
            for i, a in enumerate(accs):
                for b in accs[i + 1:]:
                    if a["flow"] == b["flow"]:
                        continue
                    if a["kind"] == "read" and b["kind"] == "read":
                        continue
                    lo, hi = sorted(
                        (a, b),
                        key=lambda x: (self.flows[x["flow"]].priority, x["flow"], x["id"]))
                    out.append(self._record(
                        "race-pair", [("A1", lo["id"]), ("B", hi["id"])], obj))
        return out

    def atomicity_triples(self) -> list[dict[str, Any]]:
        """A1 and A2 in one flow with A1 able to precede A2, B in another.

        ``may_precede`` is computed on the CFG, so ``A1 == A2`` appears exactly
        when the statement lies on a cycle — which is the case the ground truth
        needs: 7 of Racebench's 86 annotated triples name the same line twice
        ([[Pipeline Design]], *Loop handling*).
        """
        out: list[dict[str, Any]] = []
        allow_same = self.cfg.analysis["allow_same_statement_a1_a2"]
        for obj_id, obj in self.objects.items():
            accs = [a for a in self.analysis["accesses"] if a["object"] == obj_id]
            by_flow: dict[str, list[dict[str, Any]]] = {}
            for a in accs:
                by_flow.setdefault(a["flow"], []).append(a)
            for local, locals_ in by_flow.items():
                remotes = [a for f, group in by_flow.items() if f != local
                           for a in group]
                if not remotes:
                    continue
                for a1 in locals_:
                    for a2 in locals_:
                        if (a1["id"], a2["id"]) not in self.precede:
                            continue
                        if a1["id"] == a2["id"] and not allow_same:
                            continue
                        for b in remotes:
                            shape = (a1["kind"], b["kind"], a2["kind"])
                            if shape not in UNSERIALIZABLE:
                                continue
                            out.append(self._record(
                                "atomicity-triple",
                                [("A1", a1["id"]), ("B", b["id"]), ("A2", a2["id"])],
                                obj))
        return out

    def derive(self) -> list[dict[str, Any]]:
        classes = self.cfg.analysis["candidate_classes"]
        out: list[dict[str, Any]] = []
        if "atomicity-triple" in classes:
            out += self.atomicity_triples()
        if "race-pair" in classes:
            out += self.race_pairs()
        seen: set[str] = set()
        unique = []
        for rec in out:
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            unique.append(rec)
        return unique


def derive_candidates(analysis: dict[str, Any], cfg: Config) -> list[dict[str, Any]]:
    return Deriver(analysis, cfg).derive()
