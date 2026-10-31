"""What the candidate list shows, without the widgets.

The desktop's table orders rows, groups them by variable and marks each lower
tab with a state. All of that is decided here, from plain data, so it can be
tested on a machine with no display. :mod:`irqrace.ui.desktop` only draws it.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any

from irqrace.llm.verdict import INSPECTION_ORDER

DISCARDED = "descartado c/ prova"
PENDING = "pendente"

#: Semantic order of the bucket column: what a reviewer reads first.
BUCKET_ORDER = tuple(b.value for b in INSPECTION_ORDER) + (PENDING, DISCARDED)

SYMBOLS = {"done": "✓", "idle": "○", "failed": "✗", "running": "…"}
#: A tab can only carry its colour in an image; the symbol says the same thing
#: to whoever cannot tell the colours apart.
COLOURS = {"done": "#1a7f37", "idle": "#8c959f", "failed": "#cf222e", "running": "#bf8700"}


@dataclasses.dataclass(frozen=True)
class Row:
    """One line of the table, with what sorting needs next to what it shows."""

    cid: str
    pattern: str
    variable: str
    locations: str
    feasibility: str
    bucket: str
    repair: str
    lines: tuple[int, ...] = ()
    confidence: float = -1.0
    group: str = ""

    @property
    def values(self) -> tuple[str, ...]:
        return (self.cid, self.pattern, self.variable, self.locations,
                self.feasibility, self.bucket, self.repair)

    @property
    def discarded(self) -> bool:
        return self.bucket == DISCARDED


def variable_key(variable: dict[str, Any]) -> str:
    """What makes two records the same variable, for grouping.

    The name alone merges two locals of the same name in different functions;
    the declaration tells them apart.
    """
    decl = variable.get("decl") or {}
    return f"{variable.get('name', '?')}@{decl.get('file', '')}:{decl.get('line', 0)}"


def variable_label(variable: dict[str, Any]) -> str:
    """The name a person reads: ``rate (local de taskControl, tasks.cpp:226)``."""
    name = variable.get("name", "?")
    decl = variable.get("decl") or {}
    where = f"{Path(decl['file']).name}:{decl['line']}" if decl.get("file") and decl.get("line") else ""
    storage = variable.get("storage")
    if storage == "stack" and variable.get("function"):
        return f"{name} (local de {variable['function']}" + (f", {where})" if where else ")")
    if storage == "heap" and where:
        return f"{name} ({where})"
    return name


def _text_key(value: str) -> list[Any]:
    """Text with its numbers compared as numbers: ``obj_9`` before ``obj_10``."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _bucket_rank(bucket: str) -> int:
    return BUCKET_ORDER.index(bucket) if bucket in BUCKET_ORDER else len(BUCKET_ORDER)


def sort_rows(rows: list[Row], column: str | None = None, reverse: bool = False) -> list[Row]:
    """The table's order.

    With no column: what reaches the LLM first, in the order given, then the
    candidates dropped with a proof. The sort is stable, so triage's ranking
    survives inside the first group.
    """
    if column is None:
        return sorted(rows, key=lambda r: r.discarded)
    keys = {
        "id": lambda r: _text_key(r.cid),
        "pattern": lambda r: r.pattern,
        "var": lambda r: _text_key(r.variable),
        "lines": lambda r: r.lines,
        "feas": lambda r: r.confidence,
        "bucket": lambda r: _bucket_rank(r.bucket),
        "repair": lambda r: _text_key(r.repair),
    }
    return sorted(rows, key=keys[column], reverse=reverse)


@dataclasses.dataclass(frozen=True)
class Group:
    """A variable in the grouped view: its candidates and what they add up to."""

    key: str
    label: str
    rows: tuple[Row, ...]

    @property
    def iid(self) -> str:
        return f"var:{self.key}"

    @property
    def discarded(self) -> int:
        return sum(r.discarded for r in self.rows)

    @property
    def reaching_llm(self) -> int:
        return len(self.rows) - self.discarded

    @property
    def patterns(self) -> str:
        names = sorted({r.pattern for r in self.rows})
        return " ".join(f"{n}:{sum(r.pattern == n for r in self.rows)}" for n in names)

    @property
    def best_bucket(self) -> str:
        return min((r.bucket for r in self.rows), key=_bucket_rank)

    @property
    def values(self) -> tuple[str, ...]:
        n = len(self.rows)
        return (f"{n} candidato{'s' if n != 1 else ''}", "", self.label, self.patterns,
                f"{self.reaching_llm} LLM, {self.discarded} desc.", self.best_bucket, "")


def group_rows(rows: list[Row], column: str | None = None, reverse: bool = False) -> list[Group]:
    """Rows gathered by variable, each group keeping the order of *rows*.

    Variables follow the chosen column when it means something for a group, and
    otherwise go most urgent first, so "which variables are at risk?" is
    answered by reading from the top.
    """
    gathered: dict[str, list[Row]] = {}
    for row in rows:
        gathered.setdefault(row.group or row.variable, []).append(row)
    groups = [Group(key, members[0].variable, tuple(members)) for key, members in gathered.items()]
    if column == "var":
        return sorted(groups, key=lambda g: _text_key(g.label), reverse=reverse)
    if column == "id":
        return sorted(groups, key=lambda g: len(g.rows), reverse=reverse)
    if column == "bucket":
        return sorted(groups, key=lambda g: _bucket_rank(g.best_bucket), reverse=reverse)
    return sorted(groups, key=lambda g: (_bucket_rank(g.best_bucket), -len(g.rows)))


def _stage_state(stages: dict[str, str], *names: str) -> str:
    states = [stages.get(n, "pending") for n in names]
    if "failed" in states:
        return "failed"
    if "running" in states:
        return "running"
    if states and all(s in ("ok", "skipped") for s in states):
        return "done"
    return "idle"


def tab_states(stages: dict[str, str], *, verdict: bool = False, patch: bool = False,
               turns: bool = False, selected: bool = False) -> dict[str, str]:
    """Each lower tab's state, from the manifest and the selected candidate.

    With a candidate selected, a tab says whether *that candidate* has what the
    tab shows, because that is what opening it would find; a stage that failed
    or is still running says so whatever the candidate has.
    """
    log = _stage_state(stages, *stages)
    if log == "idle" and any(s in ("ok", "skipped") for s in stages.values()):
        log = "done"  # stages still pending; what ran left its log

    def by_file(stage: str, present: bool) -> str:
        state = _stage_state(stages, stage)
        if not selected or state in ("failed", "running"):
            return state
        return "done" if present else "idle"

    return {
        "log": log,
        "triage": by_file("triage", verdict),
        "repair": by_file("repair", patch),
        "source": _stage_state(stages, "stage1"),
        "history": by_file("triage", turns),
    }
