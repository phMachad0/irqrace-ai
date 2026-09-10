"""C1 — the analysis configuration, a.k.a. the interrupt model.

Loading a C1 file is deliberately more than parsing YAML. It:

* applies the defaults the schema documents, so that everything downstream sees
  a fully resolved configuration and no stage has to guess;
* validates against ``contracts/c1-config.schema.json``;
* runs the semantic checks a JSON Schema cannot express -- duplicate flow ids,
  duplicate interrupt numbers, an ISR without an ``irq``, a task with one;
* hashes the resolved document, because two runs with different configuration
  hashes are not comparable and the manifest has to say so.

The decision to hand-write this file rather than infer it is recorded in
``wiki/concepts/Specification Inference.md``. Its recall-critical half is
``flows``: a handler missing from that list contributes no accesses, and every
defect reachable only from it becomes invisible with no error anywhere.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from . import contracts

SCHEMA_VERSION = "c1/1.0.0"

#: Defaults applied on load. Kept in one place and checked against the schema's
#: own ``default`` annotations by ``tests/test_contracts.py``, so the two cannot
#: drift apart silently.
DEFAULTS: dict[str, Any] = {
    "priority_convention": "larger-is-higher",
    "subject": {
        "build": {
            "mode": "single-tu",
            "cc": "clang-14",
            "linker": "llvm-link-14",
            "flags": ["-g", "-O0", "-Xclang", "-disable-O0-optnone"],
            "include_dirs": [],
            "defines": [],
            "extra_bitcode": [],
        },
    },
    "masking": {
        "initial_state": "all-enabled",
        "isr_entry_masks_self": False,
    },
    "semantics": {
        "equal_priority_preemption": True,
        "isr_arrival": "unbounded",
        "isr_reentrant": False,
        "nesting": True,
        "timing_model": "unconstrained",
    },
    "externals": {
        "default": "may-read-write-reachable",
        "models": [],
    },
    "analysis": {
        "alias": "may",
        "indirect_calls": "signature-matched-address-taken",
        "candidate_classes": ["race-pair", "atomicity-triple"],
        "allow_same_statement_a1_a2": True,
        "solver": {"enabled": True, "timeout_ms": 10000, "on_timeout": "inconclusive"},
    },
    "output": {"run_root": "runs", "run_id": None},
}

PRIMITIVE_DEFAULTS: dict[str, Any] = {
    "irq_arg": 0,
    "all_value": -1,
    "non_constant_arg": "unknown",
}

FLOW_DEFAULTS: dict[str, Any] = {"identified_by": "config"}


class ConfigError(ValueError):
    """The configuration file is invalid, or self-inconsistent."""


@dataclass(frozen=True)
class Flow:
    id: str
    kind: str
    entry: str
    priority: int
    irq: int | None = None
    identified_by: str = "config"

    @property
    def is_isr(self) -> bool:
        return self.kind == "isr"


@dataclass(frozen=True)
class MaskingPrimitive:
    function: str
    effect: str
    irq_arg: int | None = 0
    all_value: int | None = -1
    non_constant_arg: str = "unknown"


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Merge ``over`` onto a copy of ``base``; ``over`` wins on every leaf."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Config:
    """A loaded, defaulted, validated C1 document."""

    def __init__(self, data: dict[str, Any], *, path: Path | None = None):
        self.data = data
        self.path = path

    # -- construction ----------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        path = Path(path)
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: not valid YAML: {e}") from e
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: expected a mapping at the top level")
        cfg = cls.from_dict(raw, path=path)
        return cfg

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, path: Path | None = None) -> "Config":
        raw = copy.deepcopy(raw)
        raw.setdefault("schema_version", SCHEMA_VERSION)
        data = _deep_merge(DEFAULTS, raw)

        for flow in data.get("flows", []):
            for k, v in FLOW_DEFAULTS.items():
                flow.setdefault(k, v)
            flow.setdefault("irq", None)
        for prim in data.get("masking", {}).get("primitives", []):
            for k, v in PRIMITIVE_DEFAULTS.items():
                prim.setdefault(k, v)

        where = str(path) if path else "configuration"
        contracts.validate("c1", data, what=where)
        cfg = cls(data, path=path)
        cfg._check_semantics(where)
        return cfg

    # -- semantic checks a schema cannot express -------------------------

    def _check_semantics(self, where: str) -> None:
        problems: list[str] = []
        flows = self.flows

        if self.data["schema_version"] != SCHEMA_VERSION:
            problems.append(
                f"schema_version is {self.data['schema_version']!r}, "
                f"this build implements {SCHEMA_VERSION!r}"
            )

        seen_ids: set[str] = set()
        seen_entries: set[str] = set()
        for f in flows:
            if f.id in seen_ids:
                problems.append(f"duplicate flow id {f.id!r}")
            seen_ids.add(f.id)
            if f.entry in seen_entries:
                problems.append(f"two flows share entry function {f.entry!r}")
            seen_entries.add(f.entry)
            if f.is_isr and f.irq is None:
                problems.append(
                    f"flow {f.id!r} is an ISR but has no irq number; "
                    "disable_isr/enable_isr arguments could never be matched to it"
                )
            if not f.is_isr and f.irq is not None:
                problems.append(f"flow {f.id!r} is a task but declares irq {f.irq}")

        irqs: dict[int, str] = {}
        for f in flows:
            if f.irq is None:
                continue
            if f.irq in irqs:
                problems.append(
                    f"flows {irqs[f.irq]!r} and {f.id!r} share interrupt number {f.irq}"
                )
            irqs[f.irq] = f.id

        if not any(f.kind == "task" for f in flows):
            problems.append("no flow of kind 'task'; at least one is required")

        # Equal priorities are legal and interesting -- svp_real_002 has two ISRs
        # sharing priority 1 and no tool in the corpus models it -- but the run
        # must record which way the semantics setting was set, so say so loudly.
        by_prio: dict[int, list[str]] = {}
        for f in flows:
            by_prio.setdefault(f.priority, []).append(f.id)
        for prio, ids in sorted(by_prio.items()):
            if len(ids) > 1:
                self.notes.append(
                    f"flows {', '.join(sorted(ids))} share priority {prio}; "
                    f"equal_priority_preemption="
                    f"{self.semantics['equal_priority_preemption']} decides whether "
                    "they may preempt each other"
                )

        prim_names = [p.function for p in self.masking_primitives]
        if len(prim_names) != len(set(prim_names)):
            problems.append("a masking primitive is listed twice")
        if not prim_names:
            self.notes.append(
                "no masking primitives configured; nothing will ever be proven "
                "masked, which is sound but maximally imprecise"
            )

        if self.data["externals"]["default"] == "none":
            self.notes.append(
                "externals.default is 'none', which is UNSOUND: unmodelled "
                "external functions are assumed to touch nothing. Results from "
                "this run are not comparable with the recall gate."
            )

        if problems:
            raise ConfigError(
                f"{where}: inconsistent configuration:\n"
                + "\n".join(f"  {p}" for p in problems)
            )

    # -- accessors -------------------------------------------------------

    @property
    def notes(self) -> list[str]:
        """Non-fatal observations worth surfacing to the user and the manifest."""
        return self.data.setdefault("_notes", [])

    @property
    def name(self) -> str:
        return self.data["subject"]["name"]

    @property
    def subject(self) -> dict[str, Any]:
        return self.data["subject"]

    @property
    def build(self) -> dict[str, Any]:
        return self.data["subject"]["build"]

    @property
    def semantics(self) -> dict[str, Any]:
        return self.data["semantics"]

    @property
    def analysis(self) -> dict[str, Any]:
        return self.data["analysis"]

    @property
    def flows(self) -> list[Flow]:
        return [
            Flow(
                id=f["id"],
                kind=f["kind"],
                entry=f["entry"],
                priority=f["priority"],
                irq=f.get("irq"),
                identified_by=f.get("identified_by", "config"),
            )
            for f in self.data["flows"]
        ]

    @property
    def masking_primitives(self) -> list[MaskingPrimitive]:
        return [
            MaskingPrimitive(
                function=p["function"],
                effect=p["effect"],
                irq_arg=p.get("irq_arg", 0),
                all_value=p.get("all_value", -1),
                non_constant_arg=p.get("non_constant_arg", "unknown"),
            )
            for p in self.data["masking"]["primitives"]
        ]

    @property
    def all_irqs(self) -> list[int]:
        """Concrete interrupt set that ``all_value`` (-1) expands to.

        Expanding ``disable_isr(-1)`` to exactly the configured interrupts is
        sound only because the configuration is also what defines which
        interrupts exist. If a handler is missing from ``flows`` it is missing
        here too, and both losses are the same loss.
        """
        return sorted({f.irq for f in self.flows if f.irq is not None})

    def flow_by_entry(self, entry: str) -> Flow | None:
        for f in self.flows:
            if f.entry == entry:
                return f
        return None

    def can_preempt(self, high: Flow, low: Flow) -> bool:
        """May ``high`` preempt ``low``, on priority grounds alone?

        LARGER NUMBER = HIGHER PRIORITY. Settled from the Racebench and NIChecker
        READMEs against the papers' prose (Contradictions #3). Getting this
        backwards drops exactly the real preemptions and reports exactly the
        impossible ones, so it lives in one function that everything calls.

        Masking is *not* considered here; it is a separate, path-sensitive
        question answered in stage 2.
        """
        if high.id == low.id:
            return bool(self.semantics["isr_reentrant"])
        if not high.is_isr:
            return False  # a task never preempts anything
        if high.priority > low.priority:
            return True
        if high.priority == low.priority:
            return bool(self.semantics["equal_priority_preemption"])
        return False

    # -- identity --------------------------------------------------------

    def resolved(self) -> dict[str, Any]:
        """The fully defaulted document, minus run-varying and advisory fields."""
        d = copy.deepcopy(self.data)
        d.pop("_notes", None)
        d.get("output", {}).pop("run_id", None)
        return d

    def hash(self) -> str:
        """sha256 of the resolved configuration. Goes in the manifest verbatim."""
        return hashlib.sha256(
            contracts.canonical_json(self.resolved()).encode("utf-8")
        ).hexdigest()

    def dump(self) -> str:
        return yaml.safe_dump(self.resolved(), sort_keys=False, allow_unicode=True)

    def source_files(self, *, exts: Iterable[str] = (".c",)) -> list[Path]:
        """Every translation unit named by ``subject.sources``, files or dirs."""
        root = Path(self.subject.get("source_root") or ".")
        out: list[Path] = []
        for s in self.subject["sources"]:
            p = Path(s)
            if not p.is_absolute():
                p = root / p
            if p.is_dir():
                out.extend(sorted(q for e in exts for q in p.rglob(f"*{e}")))
            else:
                out.append(p)
        return out
