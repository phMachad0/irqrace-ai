"""Loading and validating instance documents against the frozen contracts C1-C4.

The schemas in ``contracts/`` are the single source of truth. Nothing in this
package restates a constraint that a schema already expresses; where code has to
know a default it is written once, here or in :mod:`irqrace.config`, and the
tests check the two agree.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"

SCHEMAS = {
    "c1": "c1-config.schema.json",
    "c2": "c2-context-record.schema.json",
    "c3-manifest": "c3-manifest.schema.json",
    "c3-log-event": "c3-log-event.schema.json",
    "c4-request": "c4-context-request.schema.json",
    "c4-reply": "c4-context-reply.schema.json",
    "common": "common.defs.schema.json",
}


class ContractError(ValueError):
    """An instance document does not conform to its contract."""


@lru_cache(maxsize=None)
def _registry() -> Registry:
    """Resolve the relative ``$ref``s between the schema files from disk."""
    registry = Registry()
    for path in CONTRACTS_DIR.glob("*.schema.json"):
        schema = json.loads(path.read_text())
        resource = Resource.from_contents(schema)
        # Register under both the declared $id and the bare filename, because
        # the schemas refer to each other by filename (e.g.
        # "common.defs.schema.json#/$defs/Flow").
        registry = resource @ registry
        registry = registry.with_resource(path.name, resource)
    return registry


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict[str, Any]:
    if name not in SCHEMAS:
        raise KeyError(f"unknown contract {name!r}; known: {sorted(SCHEMAS)}")
    return json.loads((CONTRACTS_DIR / SCHEMAS[name]).read_text())


@lru_cache(maxsize=None)
def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(load_schema(name), registry=_registry())


def validate(name: str, instance: Any, *, what: str = "document") -> None:
    """Raise :class:`ContractError` listing every violation, not just the first.

    All errors at once matters during development: a half-built emitter usually
    breaks several fields, and fixing them one round-trip at a time is slow.
    """
    errors = sorted(validator(name).iter_errors(instance), key=lambda e: list(e.path))
    if not errors:
        return
    lines = [f"{what} does not conform to contract {name}:"]
    for e in errors:
        where = "/".join(str(p) for p in e.absolute_path) or "<root>"
        lines.append(f"  {where}: {e.message}")
    raise ContractError("\n".join(lines))


def is_valid(name: str, instance: Any) -> bool:
    return validator(name).is_valid(instance)


def canonical_json(obj: Any) -> str:
    """Stable serialisation used for every hash in the project.

    Sorted keys, no insignificant whitespace, no non-ASCII escaping surprises.
    Two documents that differ only in key order must hash the same, or run
    comparison and Track B's result cache both break.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
