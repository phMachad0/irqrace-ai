"""Candidate identity — the fingerprint every stage joins on.

Track B caches triage results by ``(fingerprint, prompt config, model)``, so the
fingerprint must depend only on *what the candidate is* and never on *when it
was computed*. Concretely it covers the subject, the class, the variable name
and the ordered access locations; it does not cover the run id, any timing, the
solver verdict, the masking analysis, or anything else a later stage fills in.

That is also what makes the run store joinable: the same id names the candidate
in ``stage1/``, ``stage2/``, ``solver/``, ``context/``, ``llm/`` and ``repair/``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from . import contracts

ROLE_ORDER = {"A1": 0, "B": 1, "A2": 2}


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
