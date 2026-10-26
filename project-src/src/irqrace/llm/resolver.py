"""C4 resolvers — answering what the model asks for.

Track B owns C4 because the *consumer* should specify what it needs; Track A
implements the bitcode-backed resolver behind it in W8, while
:class:`SourceBackedResolver` answers directly from the C source tree ahead of
or without the LLVM/SVF toolchain. Swapping between the mock and a real
resolver changes nothing in the caller -- everything here returns a C4 reply
document rather than a Python object shaped for convenience.

**The recall-critical part is the status field, not the payload.** A
``not_found`` rendered to the model as an empty result reads as "this function
does not touch the shared variable", and that is an induced false negative --
the exact failure ``wiki/concepts/Soundness and False Negatives.md`` exists to
catalogue. So every non-``ok`` status carries the self-validation rule that
applies to it, verbatim, and :func:`render_reply` puts the rule in front of the
payload rather than after it.
"""

from __future__ import annotations

import collections
import json
import re
import time
from pathlib import Path
from typing import Any, Literal, Protocol

from irqrace import contracts
from irqrace.llm.annotations import locate_suite

#: The rule that travels with a status. Wording matches
#: ``prompts/self_validation.md`` on purpose: the model should recognise the
#: sentence, not have to reconcile two paraphrases of it.
#: The closed set C4 allows. Kept here so request_distribution() can report
#: which kinds were never asked for -- a kind nobody requests is a candidate
#: for removal at the next C4 version bump.
SUPPORTED_KINDS = frozenset(
    {
        "function_definition",
        "isr_body",
        "masking_state_at",
        "macro_expansion",
        "all_accesses_to",
        "all_call_paths",
        "type_definition",
        "global_declaration",
    }
)

RECALL_RULES: dict[str, str] = {
    "not_found": (
        "When you cannot obtain a function's definition, assume it may access "
        "the shared variable."
    ),
    "unsupported": (
        "This context could not be established. Treat the fact it would have "
        "settled as unknown, and prefer 'uncertain' over 'infeasible'."
    ),
    "truncated": (
        "You have been given part of the answer. Do not conclude anything from "
        "the absence of a construct in a truncated result."
    ),
    "ambiguous": (
        "Several definitions match. Until you disambiguate, assume the one "
        "least favourable to infeasibility."
    ),
    "declined": (
        "This request was outside the supported set or the budget. Treat the "
        "fact as unknown."
    ),
}

_FUNC_DEF = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_ *]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*$"
)


class Resolver(Protocol):
    """What Track A implements in W8 and Track B serves from record or source."""

    def resolve(self, request: dict[str, Any]) -> dict[str, Any]:
        """Take a C4 request document, return a C4 reply document."""
        ...


class RecordBackedResolver:
    """Serves requests from the candidate's own C2 record, and nothing else.

    This is the honest mock. The record already carries the enclosing function
    bodies, the flows, the call paths and the masking state, so a good fraction
    of real requests can be answered exactly. Everything else comes back
    ``not_found`` with its recall rule attached -- which is not a gap in the
    fixture era but a *feature* of it: it exercises self-validation rule 2 on
    every run, and rule 2 is the one that decides whether the model invents
    safety from missing evidence.

    :param record: the C2 context record for the candidate under triage.
    :param extra: optional map from ``(kind, key)`` to a payload, for hand-added
        context that is not in the record. Used to widen the mock without
        touching this class.
    """

    served_by = "mock"

    def __init__(
        self,
        record: dict[str, Any],
        extra: dict[tuple[str, str], dict[str, Any]] | None = None,
    ):
        self.record = record
        self.extra = extra or {}
        self.log: list[dict[str, Any]] = []

    def resolve(self, request: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        kind = request["kind"]
        args = request.get("args", {})

        payload, status = self._dispatch(kind, args)

        reply: dict[str, Any] = {
            "schema_version": "c4/1.0.0",
            "request_id": request["request_id"],
            "status": status,
            "payload": payload,
            "recall_rule": RECALL_RULES.get(status),
            "served_by": self.served_by,
            "wall_ms": int((time.perf_counter() - started) * 1000),
        }
        contracts.validate("c4-reply", reply, what=f"reply to {request['request_id']}")

        # D#2's measurement. What was asked for, how often, how deep -- this log
        # IS the specification of the context record, and it is the cheapest
        # experiment in the project.
        self.log.append(
            {
                "request_id": request["request_id"],
                "kind": kind,
                "args": args,
                "turn": request.get("turn"),
                "status": status,
            }
        )
        return reply

    def _dispatch(
        self, kind: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        key = _key_for(kind, args)
        if (kind, key) in self.extra:
            return self.extra[(kind, key)], "ok"

        if kind in ("function_definition", "isr_body"):
            return self._function_body(kind, args)
        if kind == "all_accesses_to":
            return self._accesses(args)
        if kind == "all_call_paths":
            return self._call_paths(args)
        if kind == "global_declaration":
            return self._declaration(args)
        if kind == "masking_state_at":
            return self._masking_at(args)
        # macro_expansion and type_definition need the source tree.
        return {}, "unsupported"

    def _function_body(
        self, kind: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        wanted = args.get("function")
        if kind == "isr_body":
            flow_id = args.get("flow")
            flow = next(
                (f for f in self.record["flows"] if f["id"] == flow_id), None
            )
            if flow is None:
                return {}, "not_found"
            wanted = flow["entry"]

        for entry in self.record.get("enclosing_source", []):
            if entry["function"] == wanted:
                return {
                    "code": entry["code"],
                    "file": entry["file"],
                    "line_start": entry["line_start"],
                    "line_end": entry["line_end"],
                }, ("truncated" if entry.get("truncated") else "ok")
        return {}, "not_found"

    def _accesses(self, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        if args.get("variable") != self.record["variable"]["name"]:
            # The record knows about one variable. Claiming completeness for
            # any other would be a fabrication.
            return {}, "not_found"
        # Truncated, not ok: these are the accesses in *this candidate*, not
        # every access to the variable in the program.
        return {"accesses": self.record["accesses"]}, "truncated"

    def _call_paths(self, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        paths = [
            p
            for p in self.record.get("call_paths", [])
            if args.get("function") in json.dumps(p)
        ]
        return ({"call_paths": paths}, "ok") if paths else ({}, "not_found")

    def _declaration(self, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        var = self.record["variable"]
        if args.get("variable") != var["name"]:
            return {}, "not_found"
        decl = var["decl"]
        return {
            "code": decl.get("snippet", ""),
            "file": decl["file"],
            "line_start": decl["line"],
            "line_end": decl.get("end_line", decl["line"]),
        }, "ok"

    def _masking_at(self, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
        line, file = args.get("line"), args.get("file")
        per_role = {
            m["role"]: m["state"]
            for m in (self.record.get("masking") or {}).get("per_access", [])
        }
        for access in self.record["accesses"]:
            src = access["source"]
            if src["line"] == line and (file is None or src["file"] == file):
                state = access.get("masking") or per_role.get(access["role"])
                if state is None:
                    # A stage-1 record: stage 2 has not computed masking yet.
                    # The state is unknown, not enabled and not disabled.
                    return {}, "unsupported"
                return {
                    "file": src["file"],
                    "line_start": line,
                    "line_end": line,
                    "masking": state,
                }, "ok"
        # Masking at an arbitrary line needs the CFG. Saying "unsupported" is
        # right; inventing 'enabled' would be a guess and inventing 'disabled'
        # would be a recall loss.
        return {}, "unsupported"


class SourceBackedResolver(RecordBackedResolver):
    """C4 resolver backed by the subject's C source tree.

    Unblocks ``+progressive`` (D#2) without waiting for an LLVM/SVF build.
    Where the candidate's C2 record already has the answer, it serves that;
    where the model asks for a caller body (such as ``SetSelfCtrlFlag`` in
    ``svp_simple_029_001``), a macro expansion, a type definition, another
    global declaration, or all accesses to a variable in the translation unit,
    it extracts the answer directly from the subject's ``.c`` and ``.h`` files.

    When a symbol has no definition in the source tree -- e.g. external stubs
    like ``init()``, ``idlerun()``, ``enable_isr()`` -- it still returns
    ``not_found`` with the recall rule attached.
    """

    served_by = "resolver"

    def __init__(
        self,
        record: dict[str, Any],
        *,
        source_root: Path | str | None = None,
        extra: dict[tuple[str, str], dict[str, Any]] | None = None,
    ):
        super().__init__(record, extra=extra)
        self.source_root = _resolve_source_root(record, source_root)
        self._sources: list[tuple[str, list[str]]] = (
            _load_subject_sources(record, self.source_root)
            if self.source_root is not None
            else []
        )

    @property
    def has_sources(self) -> bool:
        return bool(self._sources)

    def _dispatch(
        self, kind: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        key = _key_for(kind, args)
        if (kind, key) in self.extra:
            return self.extra[(kind, key)], "ok"

        if kind in ("function_definition", "isr_body"):
            payload, status = super()._function_body(kind, args)
            if status == "ok" or not self._sources:
                return payload, status
            return self._source_function_body(kind, args)

        if kind == "macro_expansion":
            return self._source_macro(args)

        if kind == "type_definition":
            return self._source_typedef(args)

        if kind == "global_declaration":
            payload, status = super()._declaration(args)
            if status == "ok" or not self._sources:
                return payload, status
            return self._source_declaration(args)

        if kind == "all_accesses_to":
            if self._sources:
                return self._source_accesses(args)
            return super()._accesses(args)

        if kind == "all_call_paths":
            payload, status = super()._call_paths(args)
            if status == "ok" or not self._sources:
                return payload, status
            return self._source_call_paths(args)

        if kind == "masking_state_at":
            return super()._masking_at(args)

        return {}, "unsupported"

    def _source_function_body(
        self, kind: str, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        wanted = args.get("function")
        if kind == "isr_body":
            flow_id = args.get("flow")
            flow = next(
                (f for f in self.record["flows"] if f["id"] == flow_id), None
            )
            if flow is None:
                return {}, "not_found"
            wanted = flow["entry"]
        if not wanted:
            return {}, "not_found"

        matches = []
        for rel, lines in self._sources:
            for name, start, end in _iter_functions(lines):
                if name == wanted:
                    matches.append(
                        {
                            "code": "\n".join(lines[start - 1 : end]),
                            "file": rel,
                            "line_start": start,
                            "line_end": end,
                        }
                    )
        if len(matches) == 1:
            return matches[0], "ok"
        if len(matches) > 1:
            return {
                "matches": [f"{m['file']}:{m['line_start']}" for m in matches],
                **matches[0],
            }, "ambiguous"
        return {}, "not_found"

    def _source_macro(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        if not self._sources:
            return {}, "unsupported"
        macro = args.get("macro")
        if not macro:
            return {}, "not_found"
        pat = re.compile(rf"^\s*#\s*define\s+{re.escape(macro)}\b(.*)$")
        for rel, lines in self._sources:
            i = 0
            while i < len(lines):
                m = pat.match(lines[i])
                if m:
                    start = i + 1
                    chunk = [lines[i]]
                    while chunk[-1].rstrip().endswith("\\") and i + 1 < len(lines):
                        i += 1
                        chunk.append(lines[i])
                    end = i + 1
                    code = "\n".join(chunk)
                    expansion = m.group(1).strip()
                    if len(chunk) > 1:
                        expansion = "\n".join(
                            [expansion.rstrip("\\").strip()]
                            + [ln.rstrip("\\").strip() for ln in chunk[1:]]
                        )
                    return {
                        "expansion": expansion or code,
                        "code": code,
                        "file": rel,
                        "line_start": start,
                        "line_end": end,
                    }, "ok"
                i += 1
        return {}, "not_found"

    def _source_typedef(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        if not self._sources:
            return {}, "unsupported"
        type_name = args.get("type_name")
        if not type_name:
            return {}, "not_found"
        single = re.compile(rf"^\s*typedef\b[^;{{}}]*\b{re.escape(type_name)}\s*;")
        block_start = re.compile(
            rf"^\s*(?:typedef\s+)?(?:struct|union|enum)\b[^{{;]*\b{re.escape(type_name)}?\b"
        )
        for rel, lines in self._sources:
            for i, text in enumerate(lines):
                if single.match(text):
                    return {
                        "code": text.strip(),
                        "file": rel,
                        "line_start": i + 1,
                        "line_end": i + 1,
                    }, "ok"
                if "{" in text and (
                    block_start.match(text) or text.strip().startswith("typedef")
                ):
                    depth = 0
                    for j in range(i, len(lines)):
                        depth += lines[j].count("{") - lines[j].count("}")
                        if depth == 0 and ";" in lines[j]:
                            snippet = "\n".join(lines[i : j + 1])
                            if re.search(rf"\b{re.escape(type_name)}\b", snippet):
                                return {
                                    "code": snippet,
                                    "file": rel,
                                    "line_start": i + 1,
                                    "line_end": j + 1,
                                }, "ok"
                            break
        return {}, "not_found"

    def _source_declaration(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        var = args.get("variable", "")
        bare = var.lstrip("*").split("[")[0].split(".")[0]
        if not bare:
            return {}, "not_found"
        pat = re.compile(rf"^\s*(.*\b{re.escape(bare)}\b\s*(\[[^\]]*\])?)\s*(=|;)")
        for rel, lines in self._sources:
            func_ranges = [(s, e) for _, s, e in _iter_functions(lines)]
            for i, text in enumerate(lines, 1):
                if any(s <= i <= e for s, e in func_ranges):
                    continue
                stripped = text.strip()
                if stripped.startswith(("//", "/*", "#", "typedef")):
                    continue
                if pat.match(text) and "(" not in stripped.split("=")[0]:
                    return {
                        "code": stripped,
                        "file": rel,
                        "line_start": i,
                        "line_end": i,
                    }, "ok"
        return {}, "not_found"

    def _source_accesses(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        var = args.get("variable", "")
        bare = var.lstrip("*").split("[")[0].split(".")[0]
        if not bare:
            return {}, "not_found"
        pat = re.compile(rf"\b{re.escape(bare)}\b")
        write_pat = re.compile(
            rf"\b{re.escape(bare)}\b(?:\s*\[[^\]]*\])*(?:\s*\.[A-Za-z0-9_]+)*"
            r"\s*(?:[+\-*/%&|^]?=(?!=)|\+\+|--)"
        )
        flows_by_entry = {f["entry"]: f["id"] for f in self.record.get("flows", [])}
        found: list[dict[str, Any]] = []
        for rel, lines in self._sources:
            if rel.endswith(".h"):
                continue
            for func, start, end in _iter_functions(lines):
                flow = flows_by_entry.get(func, "main")
                for ln in range(start, end + 1):
                    code = lines[ln - 1]
                    stripped = code.strip()
                    if stripped.startswith("//") or not pat.search(stripped):
                        continue
                    if ln == start and "(" in stripped:
                        continue
                    kind: Literal["read", "write"] = (
                        "write" if write_pat.search(stripped) else "read"
                    )
                    found.append(
                        {
                            "role": "B" if flow != "main" else "A1",
                            "kind": kind,
                            "flow": flow,
                            "function": func,
                            "source": {
                                "file": rel,
                                "line": ln,
                                "column": len(code) - len(code.lstrip()),
                                "end_line": ln,
                                "snippet": stripped,
                            },
                        }
                    )
        if not found:
            return super()._accesses(args)
        return {"accesses": found}, "ok"

    def _source_call_paths(
        self, args: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        target = args.get("function")
        if not target:
            return {}, "not_found"
        paths: list[dict[str, Any]] = []
        flows = self.record.get("flows", [])
        for rel, lines in self._sources:
            if rel.endswith(".h"):
                continue
            funcs = list(_iter_functions(lines))
            call_sites: dict[str, list[tuple[str, int]]] = {}
            for caller, start, end in funcs:
                for callee, _, _ in funcs:
                    if callee == caller:
                        continue
                    call_re = re.compile(rf"\b{re.escape(callee)}\s*\(")
                    for ln in range(start, end + 1):
                        if call_re.search(lines[ln - 1]):
                            call_sites.setdefault(caller, []).append((callee, ln))
            for flow in flows:
                entry = flow["entry"]
                if entry == target:
                    paths.append(
                        {"flow": flow["id"], "frames": [{"function": entry}]}
                    )
                    continue
                for caller, sites in call_sites.items():
                    if caller not in (entry, flow["id"]):
                        continue
                    for callee, ln in sites:
                        if callee == target:
                            paths.append(
                                {
                                    "flow": flow["id"],
                                    "frames": [
                                        {
                                            "function": entry,
                                            "call_site": {"file": rel, "line": ln},
                                        },
                                        {"function": target},
                                    ],
                                }
                            )
        return ({"call_paths": paths}, "ok") if paths else ({}, "not_found")


def resolver_for(
    record: dict[str, Any],
    *,
    source_root: Path | str | None = None,
    mode: Literal["mock", "source", "auto"] = "auto",
) -> RecordBackedResolver:
    """Construct the appropriate C4 resolver for ``record``.

    * ``"mock"`` always returns :class:`RecordBackedResolver` (the W1-W7 fixture
      behaviour).
    * ``"source"`` always returns :class:`SourceBackedResolver`.
    * ``"auto"`` returns :class:`SourceBackedResolver` when the subject's source
      files are reachable on disk, and falls back to :class:`RecordBackedResolver`
      otherwise.
    """
    if mode == "mock":
        return RecordBackedResolver(record)
    src = SourceBackedResolver(record, source_root=source_root)
    if mode == "source" or src.has_sources:
        return src
    return RecordBackedResolver(record)


def _resolve_source_root(
    record: dict[str, Any], override: Path | str | None
) -> Path | None:
    if override is not None:
        p = Path(override)
        return p if p.is_dir() else None
    raw = record.get("subject", {}).get("source_root")
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p
    return locate_suite()


def _load_subject_sources(
    record: dict[str, Any], root: Path
) -> list[tuple[str, list[str]]]:
    seen: set[Path] = set()
    files: list[tuple[str, list[str]]] = []

    rel_candidates: list[str] = []
    var_file = record.get("variable", {}).get("decl", {}).get("file")
    if var_file:
        rel_candidates.append(var_file)
    for acc in record.get("accesses", []):
        f = acc.get("source", {}).get("file")
        if f and f not in rel_candidates:
            rel_candidates.append(f)

    subject = record.get("subject", {}).get("name", "")
    case_prefix = "_".join(subject.split("_")[:3]) if subject.startswith("svp_simple_") else subject
    for sub in (subject, case_prefix):
        if sub and (root / sub).is_dir():
            for cfile in sorted((root / sub).glob("*.[ch]")):
                rel = f"{sub}/{cfile.name}"
                if rel not in rel_candidates:
                    rel_candidates.append(rel)

    for hfile in sorted(root.glob("*.h")):
        if hfile.name not in rel_candidates:
            rel_candidates.append(hfile.name)

    for rel in rel_candidates:
        full = (root / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
        if not full.is_file() or full in seen:
            continue
        seen.add(full)
        try:
            rel_norm = str(full.relative_to(root.resolve())).replace("\\", "/")
        except ValueError:
            rel_norm = str(rel).replace("\\", "/")
        lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
        files.append((rel_norm, lines))
    return files


def _iter_functions(lines: list[str]) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    i = 0
    while i < len(lines):
        text = lines[i]
        if (
            text
            and not text[0].isspace()
            and not text.lstrip().startswith(("//", "/*", "#"))
            and (m := _FUNC_DEF.match(text))
            and "{" in "".join(lines[i : i + 2])
        ):
            name = m.group(1)
            start = i + 1
            depth = 0
            end = start
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth == 0 and "{" in "".join(lines[i : j + 1]):
                    end = j + 1
                    i = j
                    break
            out.append((name, start, end))
        i += 1
    return out


def _key_for(kind: str, args: dict[str, Any]) -> str:
    for field in ("function", "flow", "variable", "macro", "type_name"):
        if field in args:
            return str(args[field])
    return f"{args.get('file', '')}:{args.get('line', '')}"


def request_distribution(log: list[dict[str, Any]]) -> dict[str, Any]:
    """What the model asked for, how often, and how deep.

    ``wiki/Roadmap.md`` W4's second deliverable, and the reason C4 is
    instrumented from day one: **this distribution is the specification of what
    the context record should contain**. A kind that is never requested is a
    field the record does not need; one requested on most candidates is a field
    that should ship in the record rather than costing a round trip.

    ``depth`` is the turn a request was issued on. A tail there means the model
    is discovering what it needs incrementally, which is an argument for
    progressive prompting; everything on turn 1 means the need is predictable,
    which is an argument against it.

    ``not_found_rate`` is the one to watch for a different reason: it is the
    share of answers that carry a recall rule instead of evidence, and a high
    value means the fixture era is measuring the model's handling of absence
    more than its reasoning.
    """
    if not log:
        return {"requests": 0}

    kinds = collections.Counter(e["kind"] for e in log)
    statuses = collections.Counter(e["status"] for e in log)
    depths = collections.Counter(e.get("turn") for e in log)
    per_candidate = collections.Counter(
        e["candidate_id"] for e in log if "candidate_id" in e
    )
    answered = sum(n for s, n in statuses.items() if s == "ok")

    return {
        "requests": len(log),
        "candidates_that_asked": len(per_candidate),
        "requests_per_candidate_max": max(per_candidate.values(), default=0),
        "by_kind": dict(kinds.most_common()),
        "by_status": dict(statuses.most_common()),
        "by_depth": {k: depths[k] for k in sorted(depths, key=lambda d: (d is None, d))},
        "answered_rate": answered / len(log),
        "not_found_rate": statuses["not_found"] / len(log),
        "never_requested": sorted(SUPPORTED_KINDS - set(kinds)),
    }


def render_distribution(dist: dict[str, Any]) -> str:
    """The distribution as a short report."""
    if not dist.get("requests"):
        return "no context requests were made"
    lines = [
        f"{dist['requests']} requests from {dist['candidates_that_asked']} "
        f"candidates (max {dist['requests_per_candidate_max']} on one)",
        "  by kind:   "
        + ", ".join(f"{k}={n}" for k, n in dist["by_kind"].items()),
        "  by depth:  "
        + ", ".join(f"turn {k}={n}" for k, n in dist["by_depth"].items()),
        "  by status: "
        + ", ".join(f"{k}={n}" for k, n in dist["by_status"].items()),
        f"  answered:  {dist['answered_rate']:.0%}"
        f"   not found: {dist['not_found_rate']:.0%}",
    ]
    if dist["never_requested"]:
        lines.append(
            "  never requested (candidates for removal from C4): "
            + ", ".join(dist["never_requested"])
        )
    return "\n".join(lines)


def render_reply(reply: dict[str, Any]) -> str:
    """Render a C4 reply for the model, rule first.

    Rule before payload is deliberate. If the rule trails a block of code the
    model has already read, it arrives after the conclusion has formed.
    """
    lines = [f"Reply to {reply['request_id']} — status: {reply['status']}"]
    if reply.get("recall_rule"):
        lines.append(f"\n**Apply this rule:** {reply['recall_rule']}")

    payload = reply.get("payload") or {}
    if code := payload.get("code"):
        loc = f"{payload.get('file', '?')}:{payload.get('line_start', '?')}"
        lines.append(f"\n<source location=\"{loc}\">\n{code}\n</source>")
    for field in ("masking", "accesses", "call_paths", "matches", "expansion"):
        if field in payload:
            lines.append(
                f"\n{field}:\n```json\n{json.dumps(payload[field], indent=2)}\n```"
            )
    if not payload:
        lines.append("\n(no payload)")
    return "\n".join(lines)
