"""Assembling C2 fixtures from the suite, annotation plus hand analysis.

``wiki/Roadmap.md`` W1 asks Track B to **hand-build** twenty context records,
because doing so is how schema gaps get found while they are still cheap. This
module keeps that intent while removing the part of the work that is
transcription rather than analysis.

The split is deliberate and it is where the honesty of the fixture set lives:

**Mechanical, and taken from the files** -- the variable's declaration and
type, each access's line, column, snippet and enclosing function, the flow each
access belongs to, the enclosing function bodies, the loop nest around each
access, the call paths, and the derived static features. None of it is a
judgement, all of it is checkable against the source, and getting it by hand
would only introduce typos.

**Analytical, and written per fixture by a person** -- the masking state at
each access and across the interval, whether the remote flow can preempt, and
the provenance note explaining why. These are the claims a real stage 2 would
have to prove, and they are exactly what the fixture is asserting. They live in
``fixture_specs.py`` next to the reasoning that produced them.

**Where the annotation is wrong, the fixture follows the source and says so.**
Two suite defects need this: ``svp_simple_001_001`` trap 1 points at a
declaration one line above its read, and several cases name a global whose
annotated line reaches it through a pointer. The spec carries an explicit
override plus the reason, so the correction is visible in the record's
provenance rather than silently applied (``wiki/benchmarks/Racebench.md``).

Flows come from the suite README through Track A's :mod:`irqrace.racebench`,
including its ``ENTRY_OVERRIDES`` -- the fixture set inherits the two wrongly
named entry points rather than rediscovering them.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any, Literal

from irqrace import racebench
from irqrace.candidate import stamp_identity
from irqrace.llm.annotations import Annotation

ROLES = ("A1", "B", "A2")

#: ``void svp_simple_003_001_isr_1() {`` at column 0.
_FUNC = re.compile(r"^[A-Za-z_][A-Za-z0-9_ *]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*$")
_LOOP = re.compile(r"\b(for|while)\s*\(")


@dataclasses.dataclass(frozen=True)
class AccessSpec:
    """Per-access hand analysis, and any correction to the annotation."""

    #: Overrides the annotated line when the annotation points at the wrong
    #: one. Always paired with ``correction`` so the change is auditable.
    line: int | None = None
    kind: Literal["read", "write"] | None = None
    correction: str = ""
    #: Required where the access sits in a function that is not itself a flow
    #: entry -- ``svp_simple_029_001`` reaches ``SetTmData`` from both the task
    #: and the ISR, so the enclosing function does not determine the flow.
    flow: str | None = None
    #: Entry-point-to-access call path, outermost first, for the same reason.
    #: Each frame is ``{"function": ..., "call_site": {...}, "resolution": ...}``.
    frames: tuple[dict[str, Any], ...] = ()
    #: irq numbers provably disabled / enabled / unknown at this access.
    disabled: tuple[int, ...] = ()
    enabled: tuple[int, ...] = ()
    unknown: tuple[int, ...] = ()


@dataclasses.dataclass(frozen=True)
class FixtureSpec:
    """One fixture: which annotation, plus the analysis a stage 2 would do."""

    case: str
    kind: Literal["bug_point", "trap"]
    index: int
    label: Literal["bug_point", "trap"]
    #: Why this one is in the set -- the rule or construct it exercises.
    exercises: str
    accesses: tuple[AccessSpec, AccessSpec, AccessSpec]
    #: Interval masking between A1 and A2.
    interval_disabled: tuple[int, ...] = ()
    interval_enabled: tuple[int, ...] = ()
    interval_unknown: tuple[int, ...] = ()
    reenabled_within_interval_by: tuple[str, ...] = ()
    critical_sections: tuple[dict[str, Any], ...] = ()
    #: Provenance entries beyond the ones the builder always emits.
    provenance: tuple[dict[str, str], ...] = ()
    #: Set when the variable is reached through a pointer or a field.
    aliases: tuple[str, ...] = ()
    #: Overrides the variable name taken from the annotation, for the cases
    #: whose annotation writes ``*p`` or a bare ``p``.
    variable: str | None = None
    feeds_branch: bool = False
    used_as_index: bool = False


def build(
    spec: FixtureSpec,
    annotation: Annotation,
    suite: Path,
    *,
    tool_version: str = "0.1.0",
) -> dict[str, Any]:
    """Assemble one C2 record. Identity is stamped by Track A's function."""
    source = next((suite / spec.case).glob("*.c"))
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    rel = f"{spec.case}/{source.name}"
    subject = source.stem

    row = _readme_row(suite, spec.case)
    flows_by_entry = _flows(row)

    accesses = []
    functions: dict[str, tuple[int, int]] = {}
    for role, annotated, aspec in zip(ROLES, annotation.accesses, spec.accesses):
        line = aspec.line or annotated.line
        kind = aspec.kind or annotated.kind
        func, start, end = _enclosing_function(lines, line)
        functions.setdefault(func, (start, end))
        flow = aspec.flow or _flow_of(func, row)
        frames = (
            [dict(f) for f in aspec.frames]
            if aspec.frames
            else [{"function": func}]
        )
        accesses.append(
            {
                "role": role,
                "kind": kind,
                "flow": flow,
                "function": func,
                "source": {
                    "file": rel,
                    "line": line,
                    "column": _indent(lines[line - 1]),
                    "end_line": line,
                    "snippet": lines[line - 1].strip(),
                },
                "loop_context": _loop_context(lines, start, line, rel),
                "call_path": {"flow": flow, "frames": frames},
                "masking": {
                    "disabled": list(aspec.disabled),
                    "enabled": list(aspec.enabled),
                    "unknown": list(aspec.unknown),
                },
            }
        )

    variable = spec.variable or annotation.variable
    involved = sorted({a["flow"] for a in accesses})

    record: dict[str, Any] = {
        "schema_version": "c2/1.0.0",
        "id": "cPLACEHOLDER0000",
        "fingerprint": "0" * 64,
        "class": "atomicity-triple",
        "pattern": "".join(
            "R" if a["kind"] == "read" else "W" for a in accesses
        ),
        "subject": {"name": subject, "source_root": str(suite)},
        "variable": _variable(lines, variable, rel, spec.aliases),
        "accesses": accesses,
        "flows": [f for f in flows_by_entry.values() if f["id"] in involved],
        "preemption": _preemption(accesses, flows_by_entry),
        "masking": {
            "per_access": [
                {"role": a["role"], "state": a["masking"]} for a in accesses
            ],
            "interval": {
                "from_role": "A1",
                "to_role": "A2",
                "disabled_throughout": list(spec.interval_disabled),
                "enabled_somewhere": list(spec.interval_enabled),
                "unknown": list(spec.interval_unknown),
                "reenabled_within_interval_by": list(
                    spec.reenabled_within_interval_by
                ),
                "critical_sections": [dict(c) for c in spec.critical_sections],
            },
        },
        "call_paths": [
            {"role": a["role"], "path": a["call_path"]} for a in accesses
        ],
        "loop_context": {
            "per_access": [
                {"role": a["role"], "context": a["loop_context"]} for a in accesses
            ],
            "a1_a2_same_statement": (
                accesses[0]["source"]["line"] == accesses[2]["source"]["line"]
            ),
        },
        "enclosing_source": [
            {
                "function": name,
                "file": rel,
                "line_start": start,
                "line_end": end,
                "code": "\n".join(lines[start - 1 : end]),
                "truncated": False,
            }
            for name, (start, end) in functions.items()
        ],
        "solver_result": {"verdict": "not_run", "engine": "z3"},
        "static_features": {
            "feeds_branch": spec.feeds_branch,
            "used_as_index": spec.used_as_index,
            "call_path_depth_max": max(
                len(a["call_path"]["frames"]) for a in accesses
            ),
            "same_statement_a1_a2": (
                accesses[0]["source"]["line"] == accesses[2]["source"]["line"]
            ),
            "priority_gap": _priority_gap(accesses, flows_by_entry),
            "any_masking_present": bool(
                spec.interval_disabled
                or any(a["masking"]["disabled"] for a in accesses)
            ),
        },
        "provenance": {
            "entries": _provenance(spec, annotation),
            "completeness": {
                "unresolved_indirect_calls": 0,
                "opaque_external_calls": ["init", "idlerun"],
                "truncated_fields": [],
            },
        },
        "emitted_by": {
            "tool_version": tool_version,
            "stage": "stage2",
            "run_id": f"{subject}-fixture",
            "timestamp": "2026-09-26T00:00:00Z",
        },
    }
    return stamp_identity(record)


# -- mechanical extraction -------------------------------------------------


def _indent(text: str) -> int:
    """Column of the first non-space character, 0-based, as C2 records it."""
    return len(text) - len(text.lstrip())


def _readme_row(suite: Path, case: str) -> dict[str, Any]:
    rows = racebench.parse_readme(suite / "README.md")
    row = next((r for r in rows if r["case"] == case), None)
    if row is None:
        raise KeyError(f"{case} is not in the suite README")
    return row


def _flows(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Flows for a case, honouring Track A's ENTRY_OVERRIDES."""
    main_entry = racebench.ENTRY_OVERRIDES.get(row["name"], row["main"])
    flows = {
        main_entry: {
            "id": "main",
            "kind": "task",
            "entry": main_entry,
            "irq": None,
            "priority": 0,
            "identified_by": "config",
        }
    }
    for isr in sorted(row["isrs"], key=lambda h: h["irq"]):
        flows[isr["entry"]] = {
            "id": f"isr_{isr['irq']}",
            "kind": "isr",
            "entry": isr["entry"],
            "irq": isr["irq"],
            "priority": isr["priority"],
            "identified_by": "config",
        }
    return flows


def _flow_of(function: str, row: dict[str, Any]) -> str:
    for isr in row["isrs"]:
        if isr["entry"] == function:
            return f"isr_{isr['irq']}"
    return "main"


def _enclosing_function(lines: list[str], line: int) -> tuple[str, int, int]:
    """Name and extent of the function containing ``line``.

    Scans back for a definition at column 0, then forward matching braces.
    Adequate for this suite, where every function is top level and K&R style
    does not appear in the annotated cases.
    """
    start = None
    for i in range(line - 1, -1, -1):
        text = lines[i]
        if text and not text[0].isspace() and _FUNC.match(text) and "{" in "".join(
            lines[i : i + 2]
        ):
            start = i + 1
            break
    if start is None:
        raise ValueError(f"no enclosing function found for line {line}")

    name = _FUNC.match(lines[start - 1]).group(1)  # type: ignore[union-attr]
    depth, end = 0, None
    for i in range(start - 1, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth == 0 and "{" in "".join(lines[start - 1 : i + 1]):
            end = i + 1
            break
    return name, start, end or len(lines)


def _loop_context(
    lines: list[str], func_start: int, line: int, rel: str
) -> dict[str, Any]:
    """Loop headers enclosing ``line``, **innermost first** as C2 requires.

    Brace-counting from the function header. ``may_iterate_more_than_once`` is
    left unset so the schema's sound default of ``true`` applies: claiming a
    trip count of one is a claim, and the two fixtures that rely on a guard
    firing once say so in provenance instead of asserting it here.
    """
    open_loops: list[tuple[int, int]] = []  # (depth at header, header line)
    depth = 0
    for i in range(func_start - 1, line - 1):
        text = lines[i]
        if _LOOP.search(text):
            open_loops.append((depth, i + 1))
        depth += text.count("{") - text.count("}")
        open_loops = [(d, ln) for d, ln in open_loops if d < depth or ln == i + 1]

    nest = [
        {
            "header": {
                "file": rel,
                "line": header,
                "column": _indent(lines[header - 1]),
                "snippet": lines[header - 1].strip(),
            }
        }
        for _, header in reversed(open_loops)
    ]
    return {"in_loop": bool(nest), "nest": nest}


def _variable(
    lines: list[str], name: str, rel: str, aliases: tuple[str, ...]
) -> dict[str, Any]:
    """The declaration, found by name. Deref and index forms are stripped."""
    bare = name.lstrip("*").split("[")[0].split(".")[0]
    pattern = re.compile(rf"^\s*(.*\b{re.escape(bare)}\b\s*(\[[^\]]*\])?)\s*(=|;)")
    for i, text in enumerate(lines, 1):
        if text.strip().startswith(("volatile", "int ", "unsigned", "void ")) and (
            m := pattern.match(text)
        ):
            decl = m.group(1).strip()
            declared = decl[: decl.rfind(bare)].strip() + (
                "[]" if m.group(2) else ""
            )
            return {
                "name": bare,
                "declared_type": declared or "int",
                "volatile": "volatile" in decl,
                "decl": {
                    "file": rel,
                    "line": i,
                    "column": 0,
                    "end_line": i,
                    "snippet": text.strip(),
                },
                "storage": "global",
                "aliases": list(aliases),
                "svf_node": None,
            }
    raise ValueError(f"no declaration found for {name!r}")


def _preemption(
    accesses: list[dict[str, Any]], flows: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    by_id = {f["id"]: f for f in flows.values()}
    local, remote = accesses[0]["flow"], accesses[1]["flow"]
    lp, rp = by_id[local]["priority"], by_id[remote]["priority"]
    relation = (
        "strictly-higher" if rp > lp else "equal" if rp == lp else "strictly-lower"
    )
    return {
        "preempting_flow": remote,
        "preempted_flow": local,
        "priority_relation": relation,
        # Equal priority is unresolved in the assumption list, so it is
        # recorded as assumed preemptible rather than silently resolved.
        "equal_priority_assumed_preemptible": True if relation == "equal" else None,
        "nesting_depth": 1 if local == "main" else 2,
        "timing": "unconstrained",
    }


def _priority_gap(
    accesses: list[dict[str, Any]], flows: dict[str, dict[str, Any]]
) -> int:
    by_id = {f["id"]: f for f in flows.values()}
    return by_id[accesses[1]["flow"]]["priority"] - by_id[accesses[0]["flow"]]["priority"]


def _provenance(spec: FixtureSpec, annotation: Annotation) -> list[dict[str, str]]:
    entries = [
        {
            "fact": "flows",
            "status": "assumed_from_config",
            "note": (
                "entry points, interrupt numbers and priorities come from the "
                "suite README table, which also states the convention that a "
                "larger number is a higher priority"
            ),
        },
        # No ground-truth entry, deliberately. A real stage 2 does not know
        # whether a candidate is annotated, so a fixture carrying that would
        # not be indistinguishable from the emitter's output -- and naming the
        # annotation's *section* would hand the model the label it is being
        # asked to produce. Traceability to the suite lives in the manifest
        # (``fixtures/labels.json``), which is never rendered into a prompt.
        {
            "fact": "solver_result",
            "status": "unknown",
            "note": "stage 3 has not run; this is a stage-2 record",
        },
    ]
    for role, aspec in zip(ROLES, spec.accesses):
        if aspec.correction:
            entries.append(
                {
                    "fact": f"accesses[{ROLES.index(role)}].source",
                    "status": "proven",
                    "note": f"corrected against the source: {aspec.correction}",
                }
            )
    entries.extend(dict(p) for p in spec.provenance)
    return entries
