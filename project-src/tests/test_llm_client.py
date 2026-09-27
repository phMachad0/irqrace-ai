"""The harness, driven by a fake backend so the loop is testable offline.

The fake implements the same :class:`Backend` interface the real providers do,
which is the point of having the seam: the conversation logic is exercised
without a network, a key, or a provider-specific stub.
"""

import json

import pytest

from irqrace.llm.backends import (
    Backend,
    Capabilities,
    ChatRequest,
    ChatResponse,
    RefusalError,
    StructuredMode,
    Usage,
)
from irqrace.llm.cache import Cache
from irqrace.llm.client import TriageClient, _parse_requests, render_record
from irqrace.llm.fixtures import load_all
from irqrace.llm.prompts import BY_NAME, PromptConfig
from irqrace.llm.verdict import Bucket, Feasibility, Harmfulness

RECORD = load_all()[0].record


class FakeBackend(Backend):
    """Replays a script and records every request it received."""

    provider = "fake"

    def __init__(self, texts=(), answers=(), *, caching=True, refuse=False,
                 mode=StructuredMode.native_schema):
        super().__init__("v1")
        self._texts = list(texts)
        self._answers = list(answers)
        self._caching = caching
        self._refuse = refuse
        self._mode = mode
        self.requests: list[ChatRequest] = []

    @property
    def capabilities(self):
        return Capabilities(structured=self._mode, prompt_caching=self._caching)

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        if self._refuse:
            raise RefusalError("declined (category=cyber)")
        usage = Usage(input_tokens=1000, output_tokens=200, cache_read_tokens=900,
                      price_in=5.0, price_out=25.0)
        if request.schema is None:
            text = self._texts.pop(0) if self._texts else "I am ready to answer."
            return ChatResponse(text=text, usage=usage)
        answer = self._answers.pop(0)
        return ChatResponse(
            text=json.dumps(answer), parsed=answer, structured_mode=self._mode,
            usage=usage,
        )


def _feas(verdict=Feasibility.feasible, conf=0.8):
    return {"reasoning": "isr_2 preempts the interval",
            "blocking_element": None, "verdict": verdict.value, "confidence": conf}


def _harm(verdict=Harmfulness.harmful):
    return {"reasoning": "indexes an array", "criterion_matched": "indexes an array",
            "verdict": verdict.value, "confidence": 0.8}


def _combined(verdict=Feasibility.feasible, harm=Harmfulness.harmful):
    return {"reasoning": "isr_2 preempts and it indexes an array",
            "blocking_element": None, "verdict": verdict.value, "confidence": 0.8,
            "harm_verdict": harm.value, "harm_confidence": 0.8}


def _client(config, backend):
    return TriageClient(config, backend=backend, cache=Cache(enabled=False))


# -- rendering -----------------------------------------------------------


def test_source_is_rendered_inside_delimiters():
    text = render_record(RECORD)
    assert "<context_record>" in text and "</context_record>" in text
    assert "<source function=" in text


def test_the_bodies_are_lifted_out_of_the_json_blob():
    """Code in a JSON string is unreadable and loses the delimiter boundary."""
    blob = render_record(RECORD).split("</context_record>")[0]
    assert "enclosing_source" not in blob


# -- the conversation ----------------------------------------------------


def test_decomposition_runs_two_conversations():
    fake = FakeBackend(answers=[_feas(), _harm()])
    t = _client(BY_NAME["+decomposition"], fake).triage(RECORD)
    assert t.bucket is Bucket.likely_real
    assert sum(1 for r in fake.requests if r.schema is not None) == 2


def test_harmfulness_is_not_asked_when_infeasible():
    fake = FakeBackend(answers=[_feas(Feasibility.infeasible)])
    t = _client(BY_NAME["+decomposition"], fake).triage(RECORD)
    assert t.bucket is Bucket.likely_infeasible
    assert t.harmfulness is None


def test_a_row_without_decomposition_asks_both_questions_at_once():
    fake = FakeBackend(answers=[_combined()])
    t = _client(BY_NAME["+domain"], fake).triage(RECORD)
    assert len(fake.requests) == 1
    assert t.bucket is Bucket.likely_real
    # The cost of the merge, made visible: both answers cite one reasoning pass.
    assert t.feasibility.reasoning == t.harmfulness.reasoning


def test_the_merged_arm_still_suppresses_harm_when_infeasible():
    fake = FakeBackend(answers=[_combined(verdict=Feasibility.infeasible)])
    t = _client(BY_NAME["+domain"], fake).triage(RECORD)
    assert t.harmfulness is None


def test_the_system_prefix_is_identical_across_candidates():
    fake = FakeBackend(answers=[_feas(), _harm(), _feas(), _harm()])
    client = _client(BY_NAME["+decomposition"], fake)
    client.triage(RECORD)
    client.triage(load_all()[1].record)
    assert len({r.system for r in fake.requests}) == 1


def test_nothing_candidate_specific_leaks_into_the_prefix():
    fake = FakeBackend(answers=[_feas(), _harm()])
    _client(BY_NAME["+decomposition"], fake).triage(RECORD)
    prefix = fake.requests[0].system
    assert RECORD["id"] not in prefix
    assert RECORD["subject"]["name"] not in prefix


# -- provenance ----------------------------------------------------------


def test_the_verdict_records_which_backend_and_which_structured_tier():
    fake = FakeBackend(answers=[_combined()], mode=StructuredMode.prompted_json)
    t = _client(BY_NAME["+domain"], fake).triage(RECORD)
    assert t.produced_by.backend == "fake:v1"
    assert t.produced_by.structured_mode == "prompted_json"


def test_backend_caveats_are_available_next_to_the_numbers():
    fake = FakeBackend(answers=[_combined()], caching=False,
                       mode=StructuredMode.prompted_json)
    client = _client(BY_NAME["+domain"], fake)
    assert any("not an enforced schema" in c for c in client.caveats)
    assert any("no prompt caching" in c for c in client.caveats)


# -- progressive prompting ------------------------------------------------


def test_a_request_block_is_answered_before_the_verdict_is_asked_for():
    fake = FakeBackend(
        texts=['```request\n[{"kind": "isr_body", "args": {"flow": "isr_2"}}]\n```',
               "Now I can answer."],
        answers=[_feas(), _harm()],
    )
    config = PromptConfig(name="progressive", domain_rules=True, progressive=True,
                          decomposition=True, self_validation=True)
    client = _client(config, fake)
    client.triage(RECORD)
    assert any(e["kind"] == "isr_body" for e in client.request_log)
    assert any(
        "Reply to" in m["content"]
        for r in fake.requests for m in r.messages
    ), "the resolver's answer never reached the model"


def test_the_request_budget_terminates_the_loop():
    asking = '```request\n[{"kind": "isr_body", "args": {"flow": "isr_2"}}]\n```'
    fake = FakeBackend(texts=[asking] * 10, answers=[_feas(), _harm()])
    config = PromptConfig(name="capped", domain_rules=True, progressive=True,
                          decomposition=True, max_request_rounds=2)
    client = _client(config, fake)
    client.triage(RECORD)
    assert len(client.request_log) == 4  # two rounds x two conversations


def test_a_row_without_progressive_never_opens_a_free_form_turn():
    fake = FakeBackend(answers=[_combined()])
    _client(BY_NAME["+domain"], fake).triage(RECORD)
    assert all(r.schema is not None for r in fake.requests)


@pytest.mark.parametrize(
    "text,expected",
    [
        ('```request\n[{"kind": "isr_body", "args": {"flow": "a"}}]\n```', 1),
        ('```request\n{"kind": "isr_body", "args": {"flow": "a"}}\n```', 1),
        ("no request here", 0),
        ("```request\nnot json\n```", 0),
        ('```request\n[{"nokind": 1}]\n```', 0),
    ],
)
def test_request_parsing_is_tolerant_but_not_credulous(text, expected):
    assert len(_parse_requests(text, turn=1)) == expected


# -- refusals, cost and caching -------------------------------------------


def test_a_refusal_propagates_instead_of_becoming_a_verdict():
    with pytest.raises(RefusalError, match="cyber"):
        _client(BY_NAME["+domain"], FakeBackend(refuse=True)).triage(RECORD)


def test_cost_is_accounted_per_candidate():
    """`+decomposition` asks two structured questions and, with progressive
    prompting deferred, nothing else. Two requests is the row's price."""
    fake = FakeBackend(answers=[_feas(), _harm()])
    client = _client(BY_NAME["+decomposition"], fake)
    client.triage(RECORD)
    assert client.spend.candidates == 1
    assert client.spend.requests == 2
    assert client.spend.cost_per_candidate > 0
    assert "fake:v1" in client.spend.report()


def test_a_simple_row_costs_one_request_per_candidate():
    client = _client(BY_NAME["simple"], FakeBackend(answers=[_combined()]))
    client.triage(RECORD)
    assert client.spend.requests == 1


def test_the_cache_is_keyed_by_backend_so_two_models_do_not_collide(tmp_path):
    """The whole point of the seam: the same candidate and row, two models,
    two answers. A cache keyed only on the row would serve one for the other."""
    cache = Cache(tmp_path)
    a = FakeBackend(answers=[_combined(verdict=Feasibility.feasible)])
    b = FakeBackend(answers=[_combined(verdict=Feasibility.infeasible)])
    b.model = "v2"

    first = TriageClient(BY_NAME["+domain"], backend=a, cache=cache).triage(RECORD)
    second = TriageClient(BY_NAME["+domain"], backend=b, cache=cache).triage(RECORD)

    assert first.bucket is Bucket.likely_real
    assert second.bucket is Bucket.likely_infeasible


def test_the_cache_returns_an_equal_triage_without_a_second_call(tmp_path):
    cache = Cache(tmp_path)
    fake = FakeBackend(answers=[_feas(), _harm()])
    client = TriageClient(BY_NAME["+decomposition"], backend=fake, cache=cache)
    first = client.triage(RECORD)
    calls = len(fake.requests)
    second = client.triage(RECORD)
    assert len(fake.requests) == calls
    assert second.model_dump() == first.model_dump()


def test_the_transcript_is_written_where_c3_says(tmp_path):
    fake = FakeBackend(answers=[_feas(), _harm()])
    _client(BY_NAME["+decomposition"], fake).triage(RECORD, run_dir=tmp_path)
    path = tmp_path / "llm" / RECORD["id"] / "turns.jsonl"
    lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert {l["role"] for l in lines} <= {"user", "assistant", "system"}
    structured = [l for l in lines if l.get("structured")]
    assert structured and all(l["backend"] == "fake:v1" for l in structured)
