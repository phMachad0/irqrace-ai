"""The LLM history tab: every piece of code the model read is visible and classified."""

from __future__ import annotations

import json
from pathlib import Path

from irqrace.llm.client import TriageClient
from irqrace.llm.prompts import PromptConfig
from irqrace.ui.llm_history import build_history, load_turns
from test_llm_client import RECORD, FakeBackend, _feas, _harm


def _triage_with_requests(tmp_path: Path) -> list[dict]:
    fake = FakeBackend(
        texts=['I need the handler.\n```request\n[{"kind": "isr_body", "args": {"flow": "isr_2"}},'
               ' {"kind": "function_definition", "args": {"function": "no_such_fn"}}]\n```',
               "Now I can answer."],
        answers=[_feas(), _harm()],
    )
    config = PromptConfig(name="progressive", domain_rules=True, progressive=True,
                          decomposition=True, self_validation=True)
    TriageClient(config, backend=fake).triage(RECORD, run_dir=tmp_path)
    return load_turns(tmp_path / "llm" / RECORD["id"] / "turns.jsonl")


def test_requests_and_replies_are_recorded_as_data(tmp_path: Path) -> None:
    turns = _triage_with_requests(tmp_path)
    asking = [t for t in turns if t.get("requests")]
    assert asking, "the parsed C4 requests are not on the assistant turn"
    kinds = [r["kind"] for t in asking for r in t["requests"]]
    assert "isr_body" in kinds and "function_definition" in kinds
    replies = [r for t in turns if t.get("kind") == "c4_replies" for r in t["replies"]]
    assert {r["status"] for r in replies} >= {"ok", "not_found"}


def test_history_lists_what_was_given_and_what_was_requested(tmp_path: Path) -> None:
    h = build_history(_triage_with_requests(tmp_path), [], prompt_name="progressive", progressive=True)
    text = "".join(s for s, _ in h.segments)
    asked = [r for r in h.reads if r.route == "requested"]
    given = [r for r in h.reads if r.route == "given"]

    assert given and all(r.location for r in given)  # the C2 record's <source> blocks
    isr = next(r for r in asked if r.what.startswith("isr_body"))
    assert isr.status == "ok" and isr.code and isr.location
    missing = next(r for r in asked if "no_such_fn" in r.what)
    assert missing.status == "not_found" and missing.rule  # the recall rule travels with it

    assert "O QUE A LLM LEU" in text and "🔎 A LLM SOLICITOU CÓDIGO: isr_body" in text
    tags = {tag for s, tag in h.segments if "isr_body" in s}
    assert "request" in tags and "read_ok" in tags
    assert any(tag == "read_miss" and "no_such_fn" in s for s, tag in h.segments)


def test_old_runs_without_structured_fields_are_read_from_the_text(tmp_path: Path) -> None:
    turns = _triage_with_requests(tmp_path)
    for t in turns:
        t.pop("requests", None)
        t.pop("replies", None)
    old = build_history(turns, [], progressive=True)
    asked = [r for r in old.reads if r.route == "requested"]
    assert {r.status for r in asked} >= {"ok", "not_found"}
    assert next(r for r in asked if r.what.startswith("isr_body")).code


def test_a_prompt_without_progressive_says_the_model_could_not_ask() -> None:
    turns = [
        {"role": "user", "stage": "combined", "turn": 0,
         "content": 'Task\n\n<context_record>\n{}\n</context_record>\n'
                    '\n<source function="main" location="a.c:3-4">\n3  x = 1;\n4  y = x;\n</source>'},
        {"role": "assistant", "stage": "combined", "structured": True, "content": {"verdict": "feasible"}},
    ]
    h = build_history(turns, [], prompt_name="+self-validation", progressive=False)
    text = "".join(s for s, _ in h.segments)
    assert [r.what for r in h.reads] == ["main"]
    assert "progressive=False" in text and "+self-validation" in text


def test_an_old_run_served_by_the_removed_cache_still_says_so() -> None:
    """Runs from before the cache was removed carry a marker turn: it stays readable."""
    turns = [{"role": "system", "kind": "cache_hit", "stage": "triage", "transcript_kept": False,
              "content": "Resposta servida do cache, sem chamada à API."}]
    text = "".join(s for s, _ in build_history(turns, []).segments)
    assert "SISTEMA" in text and "Resposta servida do cache" in text


def test_no_conversation() -> None:
    h = build_history([], [])
    assert h.reads == [] and "Nenhuma conversa" in h.segments[0][0]
    json.dumps([s for s, _ in h.segments])  # plain strings, paintable as-is
