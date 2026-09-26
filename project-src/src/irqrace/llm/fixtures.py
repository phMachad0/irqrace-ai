"""The labelled fixture set — Track B's evaluation ground truth.

``wiki/Roadmap.md`` W1 asks for 20 hand-built C2 context records: 10 annotated
Racebench bug points and 10 planted false-positive traps. They are the input to
the entire LLM pipeline until week 8, when Track A's real emitter replaces them.

Building them by hand is not busywork. It is how schema gaps get found while
they are still cheap to fix, and the same 20 records are the feasibility probe
that ``wiki/Open Questions.md`` says must run before anything is built on top.

**Why the labels live in a separate manifest.** A C2 record deliberately carries
no ground-truth field -- a context record is what the analyzer knows, and
whether a candidate is a real defect is precisely what the analyzer does not
know. Putting the label inside the record would leak the answer into the prompt
the moment someone renders the whole document. The manifest keeps the two apart,
and :func:`load_all` is the only place they are joined.

Each label also records **which Racebench annotation it came from**, because
this suite's ground truth is contested and every recall number the project
reports has to state which count it divides by (``wiki/benchmarks/Racebench.md``).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any, Literal

from irqrace import contracts

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"
MANIFEST = FIXTURES_DIR / "labels.json"

Label = Literal["bug_point", "trap"]

#: What W1 asks for. Coverage is reported against this rather than against
#: however many files happen to exist, so an incomplete set is visible.
TARGET_PER_LABEL = 10


class FixtureError(ValueError):
    """The fixture set is malformed, not merely incomplete."""


@dataclasses.dataclass(frozen=True)
class Fixture:
    """One labelled context record.

    :param record: the C2 document, validated on load.
    :param label: ``bug_point`` for an annotated real defect, ``trap`` for a
        deliberately planted false positive.
    :param annotation: the Racebench ``2.1_remarks`` annotation this was built
        from, verbatim, so the label is traceable to the suite rather than to
        whoever typed it.
    :param notes: why this one was chosen -- usually the interrupt pattern it
        exercises, so the set can be checked for coverage of the D#1 table.
    """

    path: Path
    record: dict[str, Any]
    label: Label
    subject: str
    annotation: str
    notes: str = ""

    @property
    def candidate_id(self) -> str:
        return self.record["id"]

    @property
    def fingerprint(self) -> str:
        return self.record["fingerprint"]

    @property
    def is_real(self) -> bool:
        return self.label == "bug_point"


def load_all(*, strict: bool = True) -> list[Fixture]:
    """Load and validate every fixture named in the manifest.

    :param strict: when true, a record that does not conform to C2 raises. Keep
        it true -- a fixture that violates the contract would be measuring the
        prompt against an input Track A can never produce.
    """
    if not MANIFEST.exists():
        raise FixtureError(
            f"no fixture manifest at {MANIFEST}. "
            "Run `irqrace llm fixtures init` to create an empty one."
        )
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    out: list[Fixture] = []
    seen_ids: dict[str, Path] = {}

    for entry in manifest["fixtures"]:
        path = (FIXTURES_DIR / entry["path"]).resolve()
        if not path.exists():
            raise FixtureError(f"manifest names {entry['path']}, which does not exist")
        record = json.loads(path.read_text(encoding="utf-8"))
        if strict:
            contracts.validate("c2", record, what=str(path))

        cid = record["id"]
        if cid in seen_ids:
            raise FixtureError(
                f"candidate id {cid} appears in both {seen_ids[cid].name} and "
                f"{path.name}; ids are the join key for the whole run store"
            )
        seen_ids[cid] = path

        out.append(
            Fixture(
                path=path,
                record=record,
                label=entry["label"],
                subject=record["subject"]["name"],
                annotation=entry["annotation"],
                notes=entry.get("notes", ""),
            )
        )
    return out


@dataclasses.dataclass(frozen=True)
class Coverage:
    """How far the fixture set is from what W1 asks for."""

    bug_points: int
    traps: int
    subjects: int
    patterns_covered: set[str]

    @property
    def complete(self) -> bool:
        return (
            self.bug_points >= TARGET_PER_LABEL and self.traps >= TARGET_PER_LABEL
        )

    def report(self) -> str:
        ok = "complete" if self.complete else "INCOMPLETE"
        return (
            f"fixtures: {ok} - {self.bug_points}/{TARGET_PER_LABEL} bug points, "
            f"{self.traps}/{TARGET_PER_LABEL} traps, across {self.subjects} subjects; "
            f"patterns: {', '.join(sorted(self.patterns_covered)) or 'none'}"
        )


def coverage(fixtures: list[Fixture] | None = None) -> Coverage:
    """Report the shape of the set, not just its size.

    Pattern coverage matters as much as the count: 20 fixtures that are all
    ``WRW`` on one subject would score the prompt against a single interrupt
    pattern, and the D#1 table has seven rows.
    """
    fixtures = load_all() if fixtures is None else fixtures
    return Coverage(
        bug_points=sum(1 for f in fixtures if f.label == "bug_point"),
        traps=sum(1 for f in fixtures if f.label == "trap"),
        subjects=len({f.subject for f in fixtures}),
        patterns_covered={
            f.record["pattern"] for f in fixtures if f.record.get("pattern")
        },
    )
