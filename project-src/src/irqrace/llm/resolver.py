"""C4 resolvers — answering what the model asks for.

Track B owns C4 because the *consumer* should specify what it needs; Track A
implements the real resolver behind it in W8. Until then this module serves the
same protocol from static data, and the swap must change nothing else -- which
is why everything here returns a C4 reply document rather than a Python object
shaped for convenience.

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
import time
from typing import Any, Protocol

from irqrace import contracts

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


class Resolver(Protocol):
    """What Track A will implement in W8 and the mock implements now."""

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
        for access in self.record["accesses"]:
            src = access["source"]
            if src["line"] == line and (file is None or src["file"] == file):
                return {
                    "file": src["file"],
                    "line_start": line,
                    "line_end": line,
                    "masking": access["masking"],
                }, "ok"
        # Masking at an arbitrary line needs the CFG. Saying "unsupported" is
        # right; inventing 'enabled' would be a guess and inventing 'disabled'
        # would be a recall loss.
        return {}, "unsupported"


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
