"""The triage harness — one candidate in, one :class:`Triage` out.

``wiki/Roadmap.md`` W2. Everything measurable about a row of the ablation is
produced here: the conversation, the C4 request log, the token and cost
accounting, and the structured verdict.

The harness is **provider-neutral**. It talks to a
:class:`~irqrace.llm.backends.base.Backend` and never to an SDK, which is what
lets the same prompt configuration be measured against Claude, an
OpenAI-compatible endpoint or a local model. That is not only portability:
[[LLift (paper)]]'s central claim is that prompt architecture dominates model
choice, and holding the prompt fixed while swapping the model is the only way
to check it here.

Four design points, each a decision rather than a default.

**The system prefix is identical for every candidate in a row.** No subject
name, no candidate id, no timestamp. On a caching backend that is what makes a
31-subject sweep affordable; on every backend it is what makes two rows
comparable.

**Reasoning precedes the verdict, in separate turns.** With progressive
prompting on, the model reasons in prose and may request context; only the
final turn is schema-constrained. Asking for structured output first forces the
verdict out ahead of its justification, which is the failure
``wiki/concepts/Prompt Architecture.md`` records from [[IRIS (paper)]].

**A refusal is surfaced, never scored.** Analysed C is security-adjacent text
and a classifier may decline a candidate. Counting that as any verdict would
corrupt the row, so it propagates.

**How the answer was obtained travels with it.** :attr:`Triage.produced_by`
records the backend spec and the structured-output tier, because a row served
by prompted JSON is not the same experiment as one served by an enforced
schema.
"""

from __future__ import annotations

import dataclasses
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from irqrace import contracts
from irqrace.llm import cost as _cost
from irqrace.llm.backends import Backend, ChatRequest, from_spec
from irqrace.llm.intervals import render_interval
from irqrace.llm.prompts import FULL, PromptConfig
from irqrace.llm.resolver import RECALL_RULES, RecordBackedResolver, Resolver, render_reply
from irqrace.llm.verdict import (
    CombinedAnswer,
    Feasibility,
    FeasibilityAnswer,
    HarmfulnessAnswer,
    Provenance,
    Triage,
)

MAX_TOKENS = 16000

_REQUEST_BLOCK = re.compile(r"```request\s*(.+?)```", re.DOTALL)


class TriageError(RuntimeError):
    """The conversation could not be completed."""


@dataclasses.dataclass
class Conversation:
    """A transcript, written to ``llm/<cand_id>/turns.jsonl`` per contract C3."""

    candidate_id: str
    turns: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    #: Kept up to date turn by turn: a run being watched shows the conversation
    #: as it happens, and one that fails half way leaves what was said so far.
    live_path: Path | None = None

    def add(self, role: str, content: Any, **meta: Any) -> None:
        self.turns.append({"role": role, "content": content, **meta})
        if self.live_path is not None:
            self._dump(self.live_path)

    def _dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for turn in self.turns:
                fh.write(json.dumps(turn, ensure_ascii=False) + "\n")

    def write(self, run_dir: Path) -> Path:
        path = run_dir / "llm" / self.candidate_id / "turns.jsonl"
        self._dump(path)
        return path


def render_record(record: dict[str, Any]) -> str:
    """Render a C2 record for the model.

    The whole document goes in, inside a delimiter, with the source bodies
    lifted out into their own ``<source>`` blocks. Delimiters around code are
    from [[ChatGPT for Static Analysis (paper)]]; here they carry a second job,
    which is marking the boundary of the untrusted region named in ``base.md``.
    """
    body = {k: v for k, v in record.items() if k != "enclosing_source"}
    parts = [
        "<context_record>",
        json.dumps(body, indent=2, ensure_ascii=False),
        "</context_record>",
    ]
    for entry in record.get("enclosing_source", []):
        # Numbered, so a line the model cites is the line it read: unnumbered
        # bodies produced miscounted line numbers in blocking elements.
        first = entry["line_start"]
        width = len(str(first + entry["code"].count("\n")))
        numbered = "\n".join(
            f"{first + k:>{width}}  {text}" for k, text in enumerate(entry["code"].split("\n"))
        )
        parts.append(
            f'\n<source function="{entry["function"]}" '
            f'location="{entry["file"]}:{entry["line_start"]}-{entry["line_end"]}"'
            + (' truncated="true"' if entry.get("truncated") else "")
            + f'>\n{numbered}\n</source>'
        )
    return "\n".join(parts)


FEASIBILITY_TASK = (
    "Decide whether the reported interleaving can actually occur in this "
    "program. Reason about the specific flows, priorities and masking state in "
    "the record; do not generalise from how the code looks."
)

HARMFULNESS_TASK = (
    "The interleaving is possible. Decide whether it is harmful, applying the "
    "stated criterion. Do not revisit feasibility."
)

COMBINED_TASK = (
    "Decide whether the reported interleaving can occur and, if it can, "
    "whether it is harmful."
)


class TriageClient:
    """Runs one ablation row, against one backend.

    :param config: the prompt configuration -- the row.
    :param backend: a :class:`Backend`, or a ``provider:model`` spec string.
        Defaults to ``anthropic:claude-opus-5``.
    """

    def __init__(
        self,
        config: PromptConfig = FULL,
        *,
        backend: Backend | str | None = None,
        temperature: float | None = None,
    ):
        self.config = config
        self.backend = (
            backend
            if isinstance(backend, Backend)
            else from_spec(backend) if isinstance(backend, str) else from_spec()
        )
        self.temperature = temperature
        self.spend = _cost.Spend(spec=self.backend.spec)
        self.request_log: list[dict[str, Any]] = []
        # One client serves every call of a parallel run; a conversation touches
        # nothing shared except these totals.
        self._totals = threading.Lock()

    @property
    def caveats(self) -> list[str]:
        """Backend limitations that belong next to this row's numbers."""
        return self.backend.capabilities.caveats()

    # -- public ----------------------------------------------------------

    def triage(
        self,
        record: dict[str, Any],
        *,
        resolver: Resolver | None = None,
        run_dir: Path | None = None,
        same_interval: list[dict[str, Any]] | None = None,
    ) -> Triage:
        """Triage one candidate. Never returns ``None`` and never drops.

        :param same_interval: the other triples this answer stands for; see
            :mod:`irqrace.llm.intervals`.
        """
        contracts.validate("c2", record, what=f"candidate {record.get('id')}")
        with self._totals:
            self.spend.candidates += 1
        resolver = resolver or RecordBackedResolver(record)
        convo = Conversation(
            candidate_id=record["id"],
            live_path=run_dir / "llm" / record["id"] / "turns.jsonl" if run_dir is not None else None,
        )
        rendered = render_record(record)
        if same_interval:
            rendered += "\n\n" + render_interval(record, same_interval)

        if self.config.decomposition:
            triage = self._decomposed(record, rendered, resolver, convo)
        else:
            triage = self._combined(record, rendered, resolver, convo)

        if isinstance(resolver, RecordBackedResolver):
            with self._totals:
                self.request_log.extend(
                    {**r, "candidate_id": record["id"]} for r in resolver.log
                )
        return triage

    # -- conversation shapes ---------------------------------------------

    def _decomposed(
        self,
        record: dict[str, Any],
        rendered: str,
        resolver: Resolver,
        convo: Conversation,
    ) -> Triage:
        """D#3: feasibility and harmfulness as separate conversations."""
        feas, prov = self._ask(
            FeasibilityAnswer, FEASIBILITY_TASK, rendered, resolver, convo, "feasibility"
        )
        harm = None
        if feas.verdict is not Feasibility.infeasible:
            harm, prov = self._ask(
                HarmfulnessAnswer,
                HARMFULNESS_TASK,
                rendered,
                resolver,
                convo,
                "harmfulness",
            )
        return Triage(
            candidate_id=record["id"],
            fingerprint=record["fingerprint"],
            feasibility=feas,
            harmfulness=harm,
            produced_by=prov,
        )

    def _combined(
        self,
        record: dict[str, Any],
        rendered: str,
        resolver: Resolver,
        convo: Conversation,
    ) -> Triage:
        """Rows 1-3: both questions in one conversation.

        See :class:`~irqrace.llm.verdict.CombinedAnswer` for why this arm is
        kept faithful rather than improved.
        """
        answer, prov = self._ask(
            CombinedAnswer, COMBINED_TASK, rendered, resolver, convo, "combined"
        )
        feasibility, harm = answer.split()
        return Triage(
            candidate_id=record["id"],
            fingerprint=record["fingerprint"],
            feasibility=feasibility,
            harmfulness=harm,
            produced_by=prov,
        )

    # -- the turn loop ----------------------------------------------------

    def _ask(
        self,
        schema: type,
        task: str,
        rendered: str,
        resolver: Resolver,
        convo: Conversation,
        stage: str,
    ) -> tuple[Any, Provenance]:
        system = self.config.system_prompt(stage if self.config.decomposition else None)
        messages: list[dict[str, str]] = [
            {"role": "user", "content": f"{task}\n\n{rendered}"}
        ]
        convo.add("user", messages[0]["content"], stage=stage, turn=0)

        if self.config.progressive:
            messages = self._request_rounds(system, messages, resolver, convo, stage)

        response = self._call(
            ChatRequest(
                system=system,
                messages=messages,
                schema=schema.model_json_schema(),
                schema_name=schema.__name__,
                max_tokens=MAX_TOKENS,
                temperature=self.temperature,
            )
        )
        if response.parsed is None:
            raise TriageError(f"{stage}: the backend returned no structured answer")

        answer = schema.model_validate(response.parsed)
        provenance = Provenance(
            backend=self.backend.spec,
            structured_mode=(
                response.structured_mode.value if response.structured_mode else None
            ),
        )
        convo.add(
            "assistant",
            answer.model_dump(mode="json"),
            stage=stage,
            structured=True,
            backend=self.backend.spec,
            structured_mode=provenance.structured_mode,
        )
        return answer, provenance

    def _request_rounds(
        self,
        system: str,
        messages: list[dict[str, str]],
        resolver: Resolver,
        convo: Conversation,
        stage: str,
    ) -> list[dict[str, str]]:
        """D#2: let the model pull context before it is asked to commit."""
        for turn in range(1, self.config.max_request_rounds + 1):
            response = self._call(
                ChatRequest(
                    system=system,
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                    temperature=self.temperature,
                )
            )
            text = response.text

            requests = _parse_requests(text, turn)
            if not requests:
                convo.add("assistant", text, stage=stage, turn=turn)
                # The model answered instead of asking. Keep its prose in the
                # history -- the structured turn that follows converts it,
                # which is the two-step IRIS recommends.
                messages.append({"role": "assistant", "content": text})
                messages.append(
                    {
                        "role": "user",
                        "content": "Now give your answer in the required format.",
                    }
                )
                return messages

            for req in requests:
                req.setdefault("schema_version", "c4/1.0.0")
                req.setdefault("candidate_id", convo.candidate_id)
                req["turn"] = turn
            # The parsed requests and the resolver's replies are kept as data
            # next to the text: what the model read is an evaluation question,
            # and answering it from prose would mean re-parsing the transcript.
            convo.add("assistant", text, stage=stage, turn=turn, requests=requests)
            replies = [_answer(req, resolver) for req in requests]

            messages.append({"role": "assistant", "content": text})
            reply_text = "\n\n---\n\n".join(render_reply(r) for r in replies)
            messages.append({"role": "user", "content": reply_text})
            convo.add("user", reply_text, stage=stage, turn=turn, kind="c4_replies", replies=replies)

        # Budget reached. Recorded, not swallowed: a candidate that keeps
        # asking is evidence about the context record, which is the point of
        # measuring this at all.
        convo.add(
            "system",
            f"context request budget ({self.config.max_request_rounds}) reached",
            stage=stage,
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    "No further context is available. Answer now in the required "
                    "format, applying the rule that an unobtainable definition "
                    "may access the shared variable."
                ),
            }
        )
        return messages

    def _call(self, request: ChatRequest):
        started = time.perf_counter()
        response = self.backend.chat(request)
        if not response.usage.latency_s:
            response.usage = dataclasses.replace(
                response.usage, latency_s=time.perf_counter() - started
            )
        with self._totals:
            self.spend.record(response.usage)
        return response


def _answer(request: dict[str, Any], resolver: Resolver) -> dict[str, Any]:
    """Resolve one C4 request. A request we cannot serve is an answer, not a crash.

    The request comes from the model and the reply from code that has rarely seen
    its questions: neither failing may cost the candidate its verdict. It goes
    back as ``unsupported``, which carries the rule for what it could not settle.
    """
    try:
        contracts.validate("c4-request", request, what=request["request_id"])
        return resolver.resolve(request)
    except contracts.ContractError:
        return {
            "request_id": request["request_id"],
            "status": "unsupported",
            "payload": {},
            "recall_rule": RECALL_RULES["unsupported"],
        }


def _parse_requests(text: str, turn: int) -> list[dict[str, Any]]:
    """Extract C4 requests from a ```request block, tolerantly."""
    match = _REQUEST_BLOCK.search(text)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return []
    items = parsed if isinstance(parsed, list) else [parsed]
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or "kind" not in item:
            continue
        item.setdefault("request_id", f"r-t{turn}-{i}")
        out.append(item)
    return out
