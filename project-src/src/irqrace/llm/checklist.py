"""Triage by variable, with a checklist (``llm triage --by-variable``).

Every candidate on one shared variable goes into one conversation: the facts the
candidates share are rendered once, each candidate adds only what differs, and
the model answers one verdict per candidate id. Feasibility and harmfulness stay
separate calls (D#3), so the grouping changes one thing: how many conversations
produce the ordering. Measured on 2026-11-21 against one conversation per triple
(``results/speed-20261121``, ``results/realworld-cmp2-20261121``); the prompt
asset is ``prompts/checklist.md``.

Recall is untouched for the same reason as :mod:`irqrace.llm.intervals`: triage
drops nothing (Soundness Assumptions H3). What the code, not the model, enforces:

* a candidate the answer leaves out is asked again on its own, once
  (:func:`triage_variable`); only if that fails too is it ``uncertain``;
* an answer naming an id twice, or an id it was not asked about, is rejected and
  the group falls back to one conversation per candidate;
* ``infeasible`` without a blocking element is checked per candidate exactly as
  :class:`~irqrace.llm.verdict.Triage` checks it for a single conversation.

A retried candidate's conversation is appended to the same ``turns.jsonl`` as
the checklist when it is the group's lead (turns tagged ``"after"``), so the
transcript keeps every call that was made.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from irqrace.llm.backends import BackendError, RefusalError
from irqrace.llm.verdict import (
    Feasibility,
    FeasibilityAnswer,
    Harmfulness,
    HarmfulnessAnswer,
    Provenance,
    Triage,
)

#: Items per conversation. Larger variables are split by interval.
MAX_ITEMS = 20


# -- grouping ----------------------------------------------------------------


def _access(record: dict[str, Any], role: str) -> dict[str, Any]:
    return next(a for a in record["accesses"] if a["role"] == role)


def variable_key(record: dict[str, Any]) -> tuple[Any, ...]:
    """(subject, variable, declaration): the candidates that share one variable."""
    var = record["variable"]
    decl = var.get("decl") or {}
    return (json.dumps(record.get("subject"), sort_keys=True), var.get("name"),
            decl.get("file"), decl.get("line"))


def _interval_key(record: dict[str, Any]) -> tuple[Any, ...]:
    a1, a2 = _access(record, "A1")["source"], _access(record, "A2")["source"]
    return (a1.get("file"), a1.get("line"), a2.get("file"), a2.get("line"), record["pattern"])


def group_variables(records: list[dict[str, Any]], max_items: int = MAX_ITEMS) -> list[list[dict[str, Any]]]:
    """Records by variable, in order of first appearance, chunked to ``max_items``.

    A chunk never splits an interval unless the interval alone exceeds the limit,
    so the Bs of one A1..A2 stretch are judged side by side.
    """
    by_var: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for record in records:
        by_var.setdefault(variable_key(record), []).append(record)
    groups: list[list[dict[str, Any]]] = []
    for members in by_var.values():
        intervals: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for record in members:
            intervals.setdefault(_interval_key(record), []).append(record)
        chunk: list[dict[str, Any]] = []
        for interval in intervals.values():
            while len(interval) > max_items:
                if chunk:
                    groups.append(chunk)
                    chunk = []
                groups.append(interval[:max_items])
                interval = interval[max_items:]
            if len(chunk) + len(interval) > max_items:
                groups.append(chunk)
                chunk = []
            chunk.extend(interval)
        if chunk:
            groups.append(chunk)
    return groups


# -- rendering ----------------------------------------------------------------


def _numbered(entry: dict[str, Any]) -> str:
    first = entry["line_start"]
    width = len(str(first + entry["code"].count("\n")))
    numbered = "\n".join(f"{first + k:>{width}}  {text}" for k, text in enumerate(entry["code"].split("\n")))
    return (f'<source function="{entry["function"]}" '
            f'location="{entry["file"]}:{entry["line_start"]}-{entry["line_end"]}"'
            + (' truncated="true"' if entry.get("truncated") else "")
            + f'>\n{numbered}\n</source>')


def render_checklist(group: list[dict[str, Any]]) -> str:
    """Shared fields once, per-candidate fields per item, every source body once.

    A field is shared when its value is identical in every record of the group;
    nothing is summarised or dropped, so each item plus the shared part is the
    whole C2 record the per-candidate prompt would have shown.
    """
    keys = [k for k in group[0] if k != "enclosing_source"]
    shared = {k: group[0][k] for k in keys if all(r.get(k) == group[0][k] for r in group)}
    parts = ["<shared_context>",
             json.dumps(shared, indent=2, ensure_ascii=False),
             "</shared_context>"]
    seen: set[tuple[Any, ...]] = set()
    for record in group:
        for entry in record.get("enclosing_source", []):
            key = (entry["file"], entry["function"], entry["line_start"], entry["line_end"])
            if key not in seen:
                seen.add(key)
                parts.append(_numbered(entry))
    parts.append(f'\n<checklist count="{len(group)}">')
    for record in group:
        own = {k: v for k, v in record.items() if k != "enclosing_source" and k not in shared}
        own["id"] = record["id"]
        parts += [f'<item id="{record["id"]}">',
                  json.dumps(own, indent=2, ensure_ascii=False),
                  "</item>"]
    parts.append("</checklist>")
    return "\n".join(parts)


# -- answer schemas -------------------------------------------------------------


class SharedFinding(BaseModel):
    id: str = Field(description="F1, F2, ...")
    statement: str = Field(description="A fact about the variable as a whole, with line numbers.")


class FeasibilityItem(BaseModel):
    candidate_id: str
    reasoning: str = Field(description=(
        "This item's interleaving, on its own lines: which flow preempts where, the masking "
        "state there, and which shared findings apply and why they cover this item's accesses."))
    uses_findings: list[str] = Field(default_factory=list)
    blocking_element: str | None = Field(default=None, description=(
        "If and only if the verdict is 'infeasible': the single element that makes it "
        "impossible, cited with this item's own line numbers. Null otherwise."))
    verdict: Feasibility
    confidence: float = Field(ge=0.0, le=1.0)


class FeasibilityChecklist(BaseModel):
    shared_findings: list[SharedFinding]
    items: list[FeasibilityItem]


class HarmfulnessItem(BaseModel):
    candidate_id: str
    reasoning: str = Field(description="Apply the stated harmfulness criterion to this item.")
    criterion_matched: str | None = Field(default=None, description=(
        "Which clause of the stated criterion fired, or the named reason for benignity. "
        "A benign verdict with no criterion named is not acceptable."))
    verdict: Harmfulness
    confidence: float = Field(ge=0.0, le=1.0)


class HarmfulnessChecklist(BaseModel):
    shared_findings: list[SharedFinding]
    items: list[HarmfulnessItem]


FEASIBILITY_TASK = (
    "For every item in the checklist, decide whether its interleaving can actually occur in "
    "this program. First establish the shared findings, then answer each item by its id, "
    "exactly once."
)

HARMFULNESS_TASK = (
    "The interleavings of these items are possible. For every item, decide whether it is "
    "harmful, applying the stated criterion. Do not revisit feasibility. Answer each item by "
    "its id, exactly once."
)


class ChecklistRejected(ValueError):
    """The answer named an id twice or one it was not asked about."""


def _index(items: list[Any], asked: set[str], stage: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        if item.candidate_id not in asked:
            raise ChecklistRejected(f"{stage}: answered an id that was not asked: {item.candidate_id}")
        if item.candidate_id in out:
            raise ChecklistRejected(f"{stage}: answered {item.candidate_id} twice")
        out[item.candidate_id] = item
    return out


def triage_checklist(client: Any, group: list[dict[str, Any]], *, run_dir: Any = None) -> dict[str, Triage | str]:
    """One outcome per candidate of ``group``: a :class:`Triage`, or why there is none.

    ``client`` is a :class:`~irqrace.llm.client.TriageClient`; its turn loop,
    spend accounting and backend are reused unchanged.
    """
    from irqrace import contracts
    from irqrace.llm.client import Conversation
    from irqrace.llm.resolver import RecordBackedResolver

    for record in group:
        contracts.validate("c2", record, what=f"candidate {record.get('id')}")
    lead = group[0]
    with client._totals:
        client.spend.candidates += len(group)
    convo = Conversation(
        candidate_id=lead["id"],
        live_path=run_dir / "llm" / lead["id"] / "turns.jsonl" if run_dir is not None else None,
        tag={"checklist": [r["id"] for r in group]},
    )
    rendered = render_checklist(group)
    resolver = RecordBackedResolver(lead)  # unused: the checklist rows send no C4 requests
    asked = {r["id"] for r in group}

    feas_answer, prov = client._ask(FeasibilityChecklist, FEASIBILITY_TASK, rendered, resolver,
                                    convo, "feasibility", checklist=True)
    feas = _index(feas_answer.items, asked, "feasibility")

    harm: dict[str, Any] = {}
    possible = [r for r in group if r["id"] in feas and feas[r["id"]].verdict is not Feasibility.infeasible]
    if possible:
        harm_rendered = rendered if len(possible) == len(group) else render_checklist(possible)
        harm_answer, prov = client._ask(HarmfulnessChecklist, HARMFULNESS_TASK, harm_rendered, resolver,
                                        convo, "harmfulness", checklist=True)
        harm = _index(harm_answer.items, {r["id"] for r in possible}, "harmfulness")

    outcomes: dict[str, Triage | str] = {}
    for record in group:
        cid = record["id"]
        f = feas.get(cid)
        if f is None:
            outcomes[cid] = "checklist: the feasibility answer left this candidate out"
            continue
        h = harm.get(cid)
        if f.verdict is not Feasibility.infeasible and h is None:
            outcomes[cid] = "checklist: the harmfulness answer left this candidate out"
            continue
        outcomes[cid] = Triage(
            candidate_id=cid,
            fingerprint=record["fingerprint"],
            feasibility=FeasibilityAnswer(reasoning=f.reasoning, blocking_element=f.blocking_element,
                                          verdict=f.verdict, confidence=f.confidence),
            harmfulness=(HarmfulnessAnswer(reasoning=h.reasoning, criterion_matched=h.criterion_matched,
                                           verdict=h.verdict, confidence=h.confidence) if h else None),
            produced_by=Provenance(backend=prov.backend, structured_mode=prov.structured_mode),
            interval_of=lead["id"] if cid != lead["id"] else None,
        )
    return outcomes


def triage_variable(client: Any, group: list[dict[str, Any]], *, make_resolver: Any,
                    run_dir: Any = None) -> dict[str, Triage | str]:
    """The checklist, then one conversation per candidate it did not settle.

    An item the answer left out is asked on its own, once: an omission says
    nothing about the candidate, and one conversation per candidate is what the
    baseline does. A rejected answer says nothing about any of them, so the
    whole group is asked that way. Refusals and backend errors of the checklist
    call itself propagate to the caller, which reports them for every member.
    """
    def alone(member: dict[str, Any], after: str) -> Triage | str:
        try:
            return client.triage(member, resolver=make_resolver(member), run_dir=run_dir,
                                 after="checklist")
        except RefusalError as err:
            return f"the model refused: {err} (after {after})"
        except (BackendError, RuntimeError, ValueError) as err:
            return f"backend error: {err} (after {after})"

    try:
        out = triage_checklist(client, group, run_dir=run_dir)
    except ChecklistRejected as e:
        return {m["id"]: alone(m, f"checklist rejected: {e}") for m in group}
    for member in group:
        reason = out.get(member["id"])
        if isinstance(reason, str) and reason.startswith("checklist:"):
            out[member["id"]] = alone(member, reason)
    return out
