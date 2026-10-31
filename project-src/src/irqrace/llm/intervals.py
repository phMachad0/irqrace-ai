"""Triage by interval and under a budget (issue #9).

Most of a program's triples are one question asked many times: can this
interval, A1 to A2 on one variable, be interrupted by a write to it? ``wdt_pci_3``
has 132 triples on ``expect_close`` alone. Here the triples that differ only in B
become one conversation, with every B listed.

Neither grouping nor a budget can cost recall, because triage drops nothing
(Soundness Assumptions H3): every triple keeps its row in the report, a group's
verdict is copied to each member for **ordering**, and what a budget leaves out
stays ``uncertain`` with the reason. What they change is how much of the ranking
a model looked at, so a run records both in its manifest.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from irqrace.llm.cost import Spend


def _access(record: dict[str, Any], role: str) -> dict[str, Any]:
    return next(a for a in record["accesses"] if a["role"] == role)


def interval_key(record: dict[str, Any]) -> tuple[Any, ...]:
    """(variable, A1, A2, pattern): what the triples of an interval share.

    The flow is part of A1 and A2: one line reached from two flows is two
    intervals, with different masking and priority.
    """
    variable = record["variable"]
    decl = variable.get("decl") or {}

    def where(role: str) -> tuple[Any, ...]:
        access = _access(record, role)
        return access["flow"], access["kind"], access["source"]["file"], access["source"]["line"]

    return (variable["name"], decl.get("file"), decl.get("line"), where("A1"), where("A2"), record.get("pattern"))


def group_intervals(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """The records by interval, in order of first appearance."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(interval_key(record), []).append(record)
    return list(groups.values())


def _priority_gap(record: dict[str, Any]) -> int:
    flows = {f["id"]: f for f in record.get("flows", [])}
    known = [flows[a["flow"]].get("priority") for a in record["accesses"] if a["flow"] in flows]
    known = [p for p in known if p is not None]
    return max(known) - min(known) if known else 0


def signal(group: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    """Sort key putting first the group most likely to matter.

    Static features only, so the order is known before anything is spent:
    a value that feeds a branch or indexes memory, a volatile, a wide priority
    gap.
    """
    def score(record: dict[str, Any]) -> tuple[int, int, int, int]:
        features = record.get("static_features") or {}
        return (
            -bool(features.get("feeds_branch")),
            -bool(features.get("used_as_index")),
            -bool((record.get("variable") or {}).get("volatile")),
            -_priority_gap(record),
        )

    return min(score(record) for record in group)


def render_interval(lead: dict[str, Any], others: list[dict[str, Any]]) -> str:
    """The prompt's statement that one answer stands for every B of the group."""
    lines = [
        "<same_interval>",
        f"This record stands for {len(others) + 1} triples on the same variable with the same "
        "A1 and A2. They differ only in B, the access that may fall between them. B in the "
        "record is one of:",
    ]
    for record in [lead, *others]:
        b = _access(record, "B")
        source = b["source"]
        lines.append(
            f"- {record['id']}: {b['kind']} in flow {b['flow']}, function {b.get('function', '?')}, "
            f"{source['file']}:{source['line']}"
            + (f": {source['snippet'].strip()}" if source.get("snippet") else "")
        )
    lines += [
        "Answer for the interval as a whole: the interleaving is feasible if ANY of these B can "
        "occur inside it, and harmful if ANY of them that can occur does harm. Do not answer "
        "infeasible unless the blocking element rules out every B listed.",
        "</same_interval>",
    ]
    return "\n".join(lines)


class OverBudget(str):
    """The reason a candidate was left out: not an error, and not about it."""


@dataclasses.dataclass(frozen=True)
class Budget:
    """Limits for one run. Whatever is not ``None`` applies.

    Checked before each conversation, so with several calls in flight the total
    can pass a limit by what those are spending. A dollar limit on a backend
    that does not report prices stops at the first unpriced request: unpriced
    is not free, and spending on would be ignoring the limit.
    """

    max_requests: int | None = None
    max_tokens: int | None = None
    max_usd: float | None = None

    def exceeded(self, spend: Spend) -> OverBudget | None:
        if self.max_requests is not None and spend.requests >= self.max_requests:
            return OverBudget(f"budget: {self.max_requests} request(s) used")
        tokens = spend.input_tokens + spend.output_tokens
        if self.max_tokens is not None and tokens >= self.max_tokens:
            return OverBudget(f"budget: {self.max_tokens} token(s) used")
        if self.max_usd is not None:
            if spend.unpriced_requests:
                return OverBudget("budget: this backend reports no prices, so a dollar limit cannot be kept")
            if spend.cost_usd >= self.max_usd:
                return OverBudget(f"budget: ${self.max_usd:g} used")
        return None

    def as_manifest(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
