"""Candidate identity — the fingerprint every stage joins on.

Runs are compared candidate by candidate, so the fingerprint must depend only on
*what the candidate is* and never on *when it was computed*. Concretely it covers the subject, the class, the variable name
and the ordered access locations; it does not cover the run id, any timing, the
solver verdict, the masking analysis, or anything else a later stage fills in.

That is also what makes the run store joinable: the same id names the candidate
in ``stage1/``, ``stage2/``, ``solver/``, ``context/``, ``llm/`` and ``repair/``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from . import contracts

ROLE_ORDER = {"A1": 0, "B": 1, "A2": 2}


def access_locations(accesses: list[dict[str, Any]]) -> str:
    """A triple's locations, for people.

    ``(8,5,11)`` when all three are in one file. Across files the line alone
    says nothing, so each carries its file: ``task.c:8, isr.c:5, task.c:11``,
    with the full path only if two files share a name.
    """
    sources = [a.get("source") or {} for a in accesses]
    files = {s.get("file") for s in sources}
    if len(files) <= 1:
        return "(" + ",".join(str(s.get("line", "?")) for s in sources) + ")"
    unique_names = len({Path(f).name for f in files if f}) == len(files)
    return ", ".join(
        f"{Path(s['file']).name if unique_names else s['file']}:{s.get('line', '?')}"
        for s in sources
    )


def same_source(path: Path | str, rel: str) -> bool:
    """Whether the file at *path* is the one a record names *rel*.

    Records name files relative to the subject's root. The comparison is by
    whole trailing path, so ``a/util.c`` is not ``b/util.c``.
    """
    disk, named = Path(path).as_posix(), Path(rel).as_posix()
    return disk == named or disk.endswith("/" + named)


def fingerprint_material(record: dict[str, Any]) -> dict[str, Any]:
    """The exact subset of a C2 record the fingerprint is taken over."""
    accesses = sorted(
        record["accesses"], key=lambda a: ROLE_ORDER.get(a["role"], 99)
    )
    return {
        "subject": record["subject"]["name"],
        "class": record["class"],
        "variable": record["variable"]["name"],
        "accesses": [
            {
                "role": a["role"],
                "kind": a["kind"],
                "flow": a["flow"],
                "file": a["source"]["file"],
                "line": a["source"]["line"],
                "column": a["source"].get("column", 0),
            }
            for a in accesses
        ],
    }


def fingerprint(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        contracts.canonical_json(fingerprint_material(record)).encode("utf-8")
    ).hexdigest()


def candidate_id(fp: str) -> str:
    return "c" + fp[:16]


def stamp_identity(record: dict[str, Any]) -> dict[str, Any]:
    """Fill in ``fingerprint`` and ``id``. Every emitter goes through here."""
    fp = fingerprint(record)
    record["fingerprint"] = fp
    record["id"] = candidate_id(fp)
    return record


def pattern_of(record: dict[str, Any]) -> str:
    """'WRW', 'RWR', ... in role order. 'readwrite' counts as a write."""
    accesses = sorted(record["accesses"], key=lambda a: ROLE_ORDER.get(a["role"], 99))
    return "".join("R" if a["kind"] == "read" else "W" for a in accesses)
