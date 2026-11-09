"""The "Histórico LLM" tab: the conversation, with every code read made visible.

What the model read is an evaluation question, not a debugging aid: a verdict
can only be as good as the code it was reached on. The model sees code by two
routes, and this module separates them:

* **given** -- the ``<source>`` blocks of the C2 record, put in the first prompt
  by :func:`irqrace.llm.client.render_record` without the model asking;
* **requested** -- C4 context requests (``function_definition``, ``isr_body``,
  ...) the model issues in a fenced ``request`` block when progressive
  prompting is on, each answered by the resolver in the next user turn.

Requests and replies are read from the structured ``requests`` / ``replies``
fields :class:`~irqrace.llm.client.TriageClient` records on each turn; runs
older than those fields are read back from the turn text, with the same
parser the client uses. Pure Python: :func:`build_history` returns
``(text, tag)`` segments and the desktop only paints them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from irqrace.llm.client import _parse_requests

_SOURCE_BLOCK = re.compile(r'<source (?P<attrs>[^>]*)>\n(?P<code>.*?)\n</source>', re.S)
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_REQUEST_FENCE = re.compile(r"```request\s*.+?```", re.S)
_REPLY_HEAD = re.compile(r"^Reply to (?P<id>\S+) — status: (?P<status>\w+)", re.M)

STAGE_LABEL = {
    "combined": "triagem", "feasibility": "triagem/viabilidade",
    "harmfulness": "triagem/nocividade", "repair": "reparo",
}

#: Tag names the desktop configures colours for.
TAGS = ("title", "summary", "hdr", "given", "request", "read_ok", "read_miss", "text", "muted")


@dataclass
class Read:
    """One piece of code (or a refusal to give it) that reached the model."""

    route: str  # "given" | "requested"
    conversation: str  # "triagem" | "reparo"
    stage: str
    turn: int | None
    what: str  # e.g. 'function_definition(function="init")' or a function name
    status: str = "ok"
    location: str = ""
    lines: int = 0
    code: str = ""
    rule: str | None = None


@dataclass
class History:
    segments: list[tuple[str, str]] = field(default_factory=list)
    reads: list[Read] = field(default_factory=list)

    def add(self, text: str, tag: str = "text") -> None:
        self.segments.append((text, tag))


def load_turns(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _describe_request(req: dict[str, Any]) -> str:
    args = ", ".join(f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"
                     for k, v in (req.get("args") or {}).items())
    return f"{req.get('kind', '?')}({args})"


def _given_sources(text: str) -> list[tuple[dict[str, str], str]]:
    return [(dict(_ATTR.findall(m.group("attrs"))), m.group("code")) for m in _SOURCE_BLOCK.finditer(text)]


def _replies_from_text(text: str) -> list[dict[str, Any]]:
    """Old runs: rebuild reply dicts from :func:`render_reply`'s output."""
    out = []
    for chunk in text.split("\n\n---\n\n"):
        head = _REPLY_HEAD.search(chunk)
        if not head:
            continue
        payload: dict[str, Any] = {}
        src = _SOURCE_BLOCK.search(chunk)
        if src:
            loc = dict(_ATTR.findall(src.group("attrs"))).get("location", "")
            file, _, line = loc.rpartition(":")
            payload = {"code": src.group("code"), "file": file or loc,
                       "line_start": int(line) if line.isdigit() else None}
        rule = re.search(r"\*\*Apply this rule:\*\* (.+)", chunk)
        out.append({"request_id": head.group("id"), "status": head.group("status"),
                    "payload": payload, "recall_rule": rule.group(1) if rule else None})
    return out


def _location(payload: dict[str, Any]) -> tuple[str, int]:
    code = payload.get("code") or ""
    n = code.count("\n") + 1 if code else 0
    start = payload.get("line_start")
    end = payload.get("line_end") or (start + n - 1 if start and n else None)
    if not payload.get("file"):
        return "", n
    return f"{payload['file']}:{start}" + (f"-{end}" if end and end != start else ""), n


def _conversation(h: History, turns: list[dict[str, Any]], name: str) -> None:
    h.add(f"\n\n══════ CONVERSA DE {name.upper()} ══════\n", "title")
    pending: dict[str, Read] = {}
    for idx, t in enumerate(turns, start=1):
        role, stage = t.get("role", "?"), t.get("stage", "?")
        content = t.get("content", "")
        turn_no = t.get("turn")
        label = STAGE_LABEL.get(stage, stage)
        is_reply = t.get("kind") == "c4_replies"
        who = {"user": "PROGRAMA → LLM", "assistant": "LLM", "system": "SISTEMA"}.get(role, role.upper())
        if is_reply:
            who = "RESOLVER C4 → LLM (código solicitado)"
        h.add(f"\n── Turno {idx} · {who} · {label}" + (f" · rodada {turn_no}" if turn_no else "") + " ──\n", "hdr")

        if isinstance(content, dict):
            h.add(json.dumps(content, indent=2, ensure_ascii=False) + "\n")
            continue
        text = str(content)

        if role == "user" and not is_reply:
            # The first prompt: task + C2 record + the source it carries.
            pos = 0
            for m in _SOURCE_BLOCK.finditer(text):
                h.add(text[pos:m.start()], "muted")
                attrs = dict(_ATTR.findall(m.group("attrs")))
                code = m.group("code")
                h.add(f"📥 CÓDIGO ENTREGUE NO PROMPT · {attrs.get('function', '?')} · "
                      f"{attrs.get('location', '?')}\n", "given")
                h.add(code + "\n", "given")
                h.reads.append(Read("given", name, label, turn_no, attrs.get("function", "?"),
                                    location=attrs.get("location", ""), lines=code.count("\n") + 1,
                                    code=code))
                pos = m.end()
            h.add(text[pos:] + "\n", "muted")
        elif role == "assistant":
            requests = t.get("requests")
            if requests is None:
                requests = _parse_requests(text, turn_no or 0)
            pos = 0
            for m in _REQUEST_FENCE.finditer(text):
                h.add(text[pos:m.start()])
                h.add(m.group(0) + "\n", "request")
                pos = m.end()
            h.add(text[pos:] + "\n")
            for req in requests:
                r = Read("requested", name, label, turn_no, _describe_request(req), status="pendente")
                h.add(f"🔎 A LLM SOLICITOU CÓDIGO: {r.what}  [{req.get('request_id', '?')}]\n", "request")
                pending[req.get("request_id", "")] = r
                h.reads.append(r)
        elif is_reply:
            replies = t.get("replies") or _replies_from_text(text)
            for rep in replies:
                rid = rep.get("request_id", "")
                payload = rep.get("payload") or {}
                status = rep.get("status", "?")
                loc, n = _location(payload)
                r = pending.pop(rid, None) or Read("requested", name, label, turn_no, rid)
                r.status, r.location, r.lines = status, loc, n
                r.code, r.rule = payload.get("code") or "", rep.get("recall_rule")
                ok = status == "ok"
                h.add(f"{'📄 CÓDIGO FORNECIDO' if ok else '✖ NÃO FORNECIDO'} para {r.what}  "
                      f"[{rid}] · status={status}" + (f" · {loc} ({n} linhas)" if loc else "") + "\n",
                      "read_ok" if ok else "read_miss")
                if r.rule:
                    h.add(f"   regra aplicada: {r.rule}\n", "read_miss")
                if r.code:
                    h.add(r.code + "\n", "read_ok")
                for key in ("masking", "accesses", "call_paths", "matches", "expansion"):
                    if key in payload:
                        h.add(f"{key}: {json.dumps(payload[key], ensure_ascii=False)}\n", "read_ok")
        else:
            h.add(text + "\n")


def build_history(
    triage_turns: list[dict[str, Any]],
    repair_turns: list[dict[str, Any]],
    *,
    prompt_name: str | None = None,
    progressive: bool | None = None,
) -> History:
    body = History()
    if triage_turns:
        _conversation(body, triage_turns, "triagem")
    if repair_turns:
        _conversation(body, repair_turns, "reparo")

    h = History(reads=body.reads)
    if not triage_turns and not repair_turns:
        h.add("Nenhuma conversa da LLM registrada para este candidato. Runs antigos podem ter um "
              "veredicto sem transcrição: ele veio do cache de respostas, que já foi removido.", "muted")
        return h

    h.add("══════ O QUE A LLM LEU ══════\n", "title")
    given = [r for r in body.reads if r.route == "given"]
    asked = [r for r in body.reads if r.route == "requested"]
    h.add(f"\nCódigo entregue no prompt, sem pedido da LLM (registro C2): {len(given)} trecho(s)\n", "summary")
    for r in given:
        h.add(f"  📥 [{r.conversation}] {r.what} · {r.location} ({r.lines} linhas)\n", "given")
    h.add(f"\nCódigo solicitado pela LLM (protocolo C4): {len(asked)} pedido(s)\n", "summary")
    for r in asked:
        tag = "read_ok" if r.status == "ok" else "read_miss"
        where = f" → {r.location} ({r.lines} linhas)" if r.location else ""
        rnd = f", rodada {r.turn}" if r.turn else ""
        h.add(f"  🔎 [{r.conversation}{rnd}] {r.what} → {r.status}{where}\n", tag)
    if not asked:
        if progressive is False:
            h.add(f"  Nenhum. A configuração de prompt deste run ({prompt_name}) não permite pedidos de "
                  "código (progressive=False): a LLM leu somente o código entregue acima.\n", "read_miss")
        else:
            h.add("  Nenhum: a LLM respondeu sem pedir código além do entregue acima.\n", "muted")
    h.segments.extend(body.segments)
    return h
