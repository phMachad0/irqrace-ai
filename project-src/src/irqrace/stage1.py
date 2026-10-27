"""Stage 1 — candidate derivation from one access set.

The C++ half (`analysis/src/irqrace-stage1.cpp`) walks the bitcode and produces
the access set plus the intra-flow ``may_precede`` relation. This module turns
that into C2 context records.

**Every candidate is an atomicity-violation triple** ``(A1, B, A2)``: A1 and A2
in one flow with A1 able to precede A2, B in another flow, all three on one
shared location, in one of the four unserializable shapes ([[Triples Only]]).

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
from .source_context import (
    find_definition,
    function_extent,
    identifiers,
    macro_definitions,
)

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


#: Size limits on the source shipped in one record. A body longer than the
#: per-function cap is cut and marked ``truncated``; functions beyond the total
#: are left out and the record lists ``enclosing_source`` as truncated.
MAX_FUNCTION_LINES = 200
MAX_TOTAL_LINES = 600
#: A called function is shipped alongside its caller only when it is this short:
#: enough for helpers and stubs, not for whole subsystems.
MAX_CALLEE_LINES = 30


def _rel(path: str, root: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except (ValueError, OSError):
        return path


def _source_lines(file: str, root: str = ".") -> list[str]:
    """The lines of *file*, or ``[]`` when it cannot be found.

    Debug info may name a file relative to the compilation directory, which the
    analysis does not emit: clang splits ``/a/b/racebench/x.c`` into directory
    ``/a/b`` and filename ``racebench/x.c``. Such a name resolves against no
    fixed directory, so try the working directory, then ``root`` and each of its
    ancestors. Without this the record silently ships no source at all.
    """
    path = Path(file)
    if path.is_absolute():
        candidates = [path]
    else:
        base = Path(root).resolve()
        candidates = [path, base / path, *(d / path for d in base.parents)]
    for c in candidates:
        try:
            return c.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
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
        self.program = {
            f["name"]: f for f in analysis.get("program", {}).get("functions", [])
        }
        self.primitives = {p.function: p for p in cfg.masking_primitives}
        ext = cfg.data.get("externals", {})
        self.external_models = {m["function"]: m for m in ext.get("models", [])}
        self.external_default = ext.get("default", "may-read-write-reachable")
        self._macros: dict[str, tuple[str, int, str]] | None = None

    # -- helpers ---------------------------------------------------------

    def _lines(self, file: str) -> list[str]:
        if file not in self._file_cache:
            self._file_cache[file] = _source_lines(file, self.root)
        return self._file_cache[file]

    def _snippet(self, file: str, line: int) -> str:
        lines = self._lines(file)
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
        if a.get("point"):
            # Back-pointer into the event CFG of stage1/accesses.json, so stage 2
            # can place the access without re-matching source lines. Outside the
            # fingerprint, and not shown to the model (C2 Access.ir).
            rec["ir"] = {"function": a["function"], "block": a["point"]["block"],
                         "index": a["point"]["event"], "access": a["id"]}
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

    # -- the code that decides the case -----------------------------------

    def _callees(self, name: str) -> list[str]:
        out: list[str] = []
        for block in self.program.get(name, {}).get("blocks", []):
            for ev in block.get("events", []):
                if ev.get("k") == "call":
                    out.extend(c for c in ev.get("callees", []) if c not in out)
        return out

    def _reachable(self, entry: str) -> list[str]:
        seen, todo = [entry], [entry]
        while todo:
            for c in self._callees(todo.pop()):
                if c in self.program and c not in seen:
                    seen.append(c)
                    todo.append(c)
        return seen

    def _calls_primitive(self, name: str) -> bool:
        return any(c in self.primitives for c in self._callees(name))

    def _extent(self, name: str) -> tuple[str, int, int] | None:
        """(file, first line, last line) of ``name``'s definition.

        The end is the brace that closes the body (:func:`function_extent`),
        never a line past it -- the line after a function is not part of it,
        and on an annotated benchmark it is the ground truth.
        """
        info = self.functions.get(name)
        file = (info or {}).get("file") or self.program.get(name, {}).get("file")
        if not file:
            return None
        lines = self._lines(file)
        if not lines:
            return None
        start = (info or {}).get("line_start") or find_definition(lines, name)
        if not start or start > len(lines):
            return None
        hint = (info or {}).get("line_end")
        end = function_extent(lines, start, hint_end=hint) or hint or start
        return file, start, min(end, len(lines))

    def _deciding_functions(self, acc_ids: list[int], obj: dict[str, Any]) -> list[str]:
        """Functions whose code can decide the candidate, most direct first.

        1. the functions containing A1, B and A2;
        2. every function on their call paths;
        3. for every configured flow that touches the variable or can change the
           interrupt mask: its entry, and the functions it reaches that do either.
           A flow that re-enables an interrupt inside the interval is named by
           stage 2's masking facts, and its code is what makes the interval
           breakable -- without it the model is told the fact and denied the
           evidence;
        4. short functions called directly from the ones in 1.
        """
        order: list[str] = []

        def add(name: str) -> None:
            if name and name not in order:
                order.append(name)

        for i in acc_ids:
            add(self.accesses[i]["function"])
        for i in acc_ids:
            for fr in self.accesses[i]["call_path"]["frames"]:
                add(fr["function"])
        touching = {a["function"] for a in self.accesses.values() if a["object"] == obj["id"]}
        for flow in self.flows.values():
            reach = self._reachable(flow.entry)
            relevant = [f for f in reach if f in touching or self._calls_primitive(f)]
            if relevant:
                add(flow.entry)
                for f in relevant:
                    add(f)
        for i in acc_ids:
            for c in self._callees(self.accesses[i]["function"]):
                ext = self._extent(c) if c in self.program else None
                if ext and ext[2] - ext[1] + 1 <= MAX_CALLEE_LINES:
                    add(c)
        return order

    def _enclosing_source(self, names: list[str]) -> tuple[list[dict[str, Any]], bool]:
        out: list[dict[str, Any]] = []
        total, dropped = 0, False
        for name in names:
            ext = self._extent(name)
            if ext is None:
                continue
            file, start, end = ext
            if total >= MAX_TOTAL_LINES:
                dropped = True
                continue
            lines = self._lines(file)
            cut = min(end, start + MAX_FUNCTION_LINES - 1)
            total += cut - start + 1
            out.append({
                "function": name,
                "file": _rel(file, self.root),
                "line_start": start,
                "line_end": cut,
                # Untrusted analysed source: data, never instructions.
                "code": "\n".join(lines[start - 1:cut]),
                "truncated": cut < end,
            })
        return out, dropped

    # -- facts the code relies on -------------------------------------------

    def _macro_table(self) -> dict[str, tuple[str, int, str]]:
        """Every ``#define`` in the program's sources and their local headers."""
        if self._macros is None:
            table: dict[str, tuple[str, int, str]] = {}
            files = {f.get("file") for f in self.program.values()} | {
                f.get("file") for f in self.functions.values()}
            seen: set[str] = set()
            todo = [f for f in files if f]
            while todo:
                f = todo.pop()
                if f in seen:
                    continue
                seen.add(f)
                lines = self._lines(f)
                for name, (line, text) in macro_definitions(lines).items():
                    table.setdefault(name, (f, line, text))
                for raw in lines:
                    raw = raw.strip()
                    if raw.startswith("#") and "include" in raw and '"' in raw:
                        inc = raw.split('"')[1]
                        for d in [str(Path(f).parent), *self.cfg.build.get("include_dirs", [])]:
                            cand = str(Path(d) / inc)
                            if self._lines(cand):
                                todo.append(cand)
                                break
            self._macros = table
        return self._macros

    def _context_facts(self, names: list[str], code: str,
                       obj: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
        """Provenance entries for the facts the shipped code depends on.

        * ``writers.<variable>``: every store to each shared variable the shipped
          functions read (the candidate's own included), with its declaration.
          A guard is never-true only over a complete writer set, so the status
          says whether the set is complete: ``proven`` when no unresolved
          indirect call and no unmodelled external could add a writer,
          ``unknown`` otherwise.
        * ``masking_primitives.<fn>`` / ``externals.<fn>``: what the C1 file
          says a called function does -- the analysis's assumption, stated.
        * ``macros``: the definitions of macros the shipped code uses.

        Returns the entries and the called externals no model covers.
        """
        entries: list[dict[str, Any]] = []
        called: list[str] = []
        for n in names:
            for c in self._callees(n):
                if c not in self.program and c not in called:
                    called.append(c)
        every_external = {
            c for f in self.program for c in self._callees(f) if c not in self.program}
        unmodelled_anywhere = sorted(
            c for c in every_external
            if c not in self.primitives and c not in self.external_models)
        indirect = self.analysis.get("indirect_overapproximated", 0)
        complete = not indirect and not unmodelled_anywhere

        read_objects = [obj["id"]] + [
            a["object"] for a in self.accesses.values()
            if a["function"] in names and a["kind"] == "read" and a["object"] != obj["id"]]
        for oid in dict.fromkeys(read_objects):
            o = self.objects.get(oid)
            if o is None:
                continue
            sites: list[str] = []
            for a in sorted(self.accesses.values(),
                            key=lambda a: (a["flow"], a["source"]["line"])):
                if a["object"] != oid or a["kind"] != "write":
                    continue
                site = (f"{a['flow']}: {a['function']} "
                        f"{_rel(a['source']['file'], self.root)}:{a['source']['line']} "
                        f"`{self._snippet(a['source']['file'], a['source']['line'])}`")
                if site not in sites:
                    sites.append(site)
            decl = o.get("decl") or {}
            decl_text = (f"declared at {_rel(decl['file'], self.root)}:{decl['line']} "
                         f"`{self._snippet(decl['file'], decl['line'])}`"
                         if decl.get("line") else "declaration not located")
            why = ("complete: no unresolved indirect call and every called external is "
                   "modelled" if complete else
                   "may be incomplete: " + "; ".join(filter(None, [
                       f"{indirect} indirect call(s) over-approximated" if indirect else "",
                       ("unmodelled externals may write it: " + ", ".join(unmodelled_anywhere))
                       if unmodelled_anywhere else ""])))
            entries.append({
                "fact": f"writers.{o['name']}",
                "status": "proven" if complete else "unknown",
                "note": (f"every store to {o['name']} the analysis found "
                         f"({len(sites)}): " + ("; ".join(sites) if sites else "none")
                         + f". {decl_text}. The list is {why}."),
            })

        for c in called:
            if c in self.primitives:
                prim = self.primitives[c]
                entries.append({
                    "fact": f"masking_primitives.{c}", "status": "assumed_from_config",
                    "note": (f"{c}(n) {prim.effect}s interrupt number n (n is argument "
                             f"{prim.irq_arg} of the call); n = {prim.all_value} means every "
                             "interrupt. Its effect is modelled by the analysis, not opaque."),
                })
            elif c in self.external_models:
                m = self.external_models[c]
                entries.append({
                    "fact": f"externals.{c}", "status": "assumed_from_config",
                    "note": f"C1 models {c} as effect '{m.get('effect')}'"
                            + (f": {m['note']}" if m.get("note") else ""),
                })
            else:
                entries.append({
                    "fact": f"externals.{c}", "status": "unknown",
                    "note": f"no definition and no C1 model; treated as "
                            f"'{self.external_default}'",
                })

        used = identifiers(code)
        macros = self._macro_table()
        defs = [f"{n} = {macros[n][2]} ({_rel(macros[n][0], self.root)}:{macros[n][1]})"
                for n in sorted(used & set(macros))]
        if defs:
            entries.append({"fact": "macros", "status": "proven",
                            "note": "definitions of macros the shipped code uses: "
                                    + "; ".join(defs)})
        opaque = [c for c in called
                  if c not in self.primitives and c not in self.external_models]
        return entries, opaque

    def _provenance(self, acc_ids: Iterable[int], obj: dict[str, Any],
                    context: list[dict[str, Any]] | None = None,
                    opaque: list[str] | None = None,
                    truncated: bool = False) -> dict[str, Any]:
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
        entries.extend(context or [])
        return {
            "entries": entries,
            "completeness": {
                "unresolved_indirect_calls": self.analysis.get(
                    "indirect_overapproximated", 0),
                # Only what is genuinely unknown: the masking primitives and the
                # externals the C1 file models are stated above, not opaque.
                "opaque_external_calls": sorted(opaque or []),
                "truncated_fields": ["enclosing_source"] if truncated else [],
            },
        }

    def _record(self, roles: list[tuple[str, int]],
                obj: dict[str, Any]) -> dict[str, Any]:
        acc_ids = [i for _, i in roles]
        names = self._deciding_functions(acc_ids, obj)
        source, dropped = self._enclosing_source(names)
        shipped = [e["function"] for e in source]
        context, opaque = self._context_facts(
            shipped, "\n".join(e["code"] for e in source), obj)
        rec: dict[str, Any] = {
            "schema_version": "c2/2.0.0",
            "id": "", "fingerprint": "0" * 64,
            "class": "atomicity-triple",
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
            # Every configured flow: a fact about any of them (one that re-enables
            # an interrupt, one that writes a guard) is unreadable without it.
            "flows": [self._flow_record(f) for f in self.flows],
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
            "enclosing_source": source,
            "solver_result": {"verdict": "not_run", "engine": "z3"},
            "static_features": self._features(roles, obj),
            "provenance": self._provenance(acc_ids, obj, context, opaque, dropped),
            "emitted_by": {"tool_version": TOOL_VERSION, "stage": "stage1"},
        }
        a1, _, a2 = acc_ids
        rec["loop_context"]["a1_a2_same_statement"] = a1 == a2
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
            "same_statement_a1_a2": acc_ids[0] == acc_ids[2],
            "priority_gap": max(prios) - min(prios),
            "any_masking_present": False,  # stage 2 fills this in
        }

    # -- derivation ------------------------------------------------------

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
                                [("A1", a1["id"]), ("B", b["id"]), ("A2", a2["id"])],
                                obj))
        return out

    def derive(self) -> list[dict[str, Any]]:
        out = self.atomicity_triples()
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
