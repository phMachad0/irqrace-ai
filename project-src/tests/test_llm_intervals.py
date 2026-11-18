"""Issues #9 and #16: triage by interval, under a budget, and in parallel.

The rule all of it answers to: the report holds the same candidates however
triage was run. Grouping, a budget and parallel calls change who a model looked
at, never what is listed.
"""

from __future__ import annotations

import copy
import json
import threading
import time

import pytest

from irqrace import cli, contracts
from irqrace.candidate import stamp_identity
from irqrace.config import Config
from irqrace.llm.backends import Backend, Capabilities, ChatRequest, ChatResponse, StructuredMode, Usage
from irqrace.llm.client import TriageClient
from irqrace.llm.cost import Spend
from irqrace.llm.fixtures import load_all
from irqrace.llm.intervals import Budget, OverBudget, group_intervals, render_interval, signal
from irqrace.llm.pipeline import triage_records, triage_store
from irqrace.llm.prompts import FULL
from irqrace.llm.resolver import RecordBackedResolver
from irqrace.runstore import RunStore

BASE = next(f for f in load_all() if f.subject == "svp_simple_001_001").record


def triple(a1=8, b=5, a2=11, flow="isr_1", variable=None, **features) -> dict:
    rec = copy.deepcopy(BASE)
    if variable:
        rec["variable"]["name"] = variable
    for access, line in zip(sorted(rec["accesses"], key=lambda x: "A1 B A2".split().index(x["role"])), (a1, b, a2)):
        access["source"]["line"] = line
        if access["role"] == "B":
            access["flow"] = flow
    rec["static_features"] = {**(rec.get("static_features") or {}), **features}
    return stamp_identity(rec)


class Answers(Backend):
    """Says feasible and harmful, whoever asks, in any order and at any time."""

    provider = "fake"

    def __init__(self, price=5.0, delay=0.0, fail_on=None):
        super().__init__("v1")
        self.price, self.delay, self.fail_on = price, delay, fail_on
        self.lock = threading.Lock()
        self.requests: list[ChatRequest] = []
        self.busy = self.most_busy = 0

    @property
    def capabilities(self):
        return Capabilities(structured=StructuredMode.native_schema, prompt_caching=True)

    def chat(self, request: ChatRequest) -> ChatResponse:
        with self.lock:
            self.requests.append(request)
            self.busy += 1
            self.most_busy = max(self.most_busy, self.busy)
        time.sleep(self.delay)
        with self.lock:
            self.busy -= 1
        if self.fail_on and self.fail_on in request.messages[0]["content"]:
            raise RuntimeError("boom")
        harmful = request.messages[0]["content"].startswith("The interleaving is possible")
        payload = (
            {"reasoning": "r", "criterion_matched": "feeds a branch", "verdict": "harmful", "confidence": 0.9}
            if harmful
            else {"reasoning": "r", "blocking_element": None, "verdict": "feasible", "confidence": 0.9}
        )
        return ChatResponse(
            text=json.dumps(payload),
            parsed=payload,
            structured_mode=StructuredMode.native_schema,
            usage=Usage(input_tokens=800, output_tokens=200, price_in=self.price, price_out=self.price),
        )


def run(records, backend, **kwargs):
    client = TriageClient(FULL, backend=backend)
    return client, triage_records(client, records, make_resolver=RecordBackedResolver, run_dir=None, **kwargs)


def test_triples_that_differ_only_in_b_are_one_interval() -> None:
    a, b, other = triple(b=5), triple(b=6), triple(a2=12)
    assert [len(g) for g in group_intervals([a, b, other])] == [2, 1]


def test_one_line_in_two_flows_is_two_intervals() -> None:
    a = triple()
    b = copy.deepcopy(a)
    next(x for x in b["accesses"] if x["role"] == "A1")["flow"] = "other"
    assert len(group_intervals([a, b])) == 2


def test_the_prompt_lists_every_b_and_asks_about_any_of_them() -> None:
    a, b = triple(b=5), triple(b=6)
    text = render_interval(a, [b])
    assert f"- {a['id']}:" in text and f"- {b['id']}:" in text
    assert ":5" in text and ":6" in text
    assert "feasible if ANY" in text and "rules out every B" in text


def test_one_conversation_answers_for_every_triple_of_the_interval() -> None:
    a, b, c = triple(b=5), triple(b=6), triple(a2=12)
    backend = Answers()
    _, outcomes = run([a, b, c], backend, by_interval=True)
    assert set(outcomes) == {a["id"], b["id"], c["id"]}
    assert outcomes[b["id"]].interval_of == a["id"]
    assert outcomes[b["id"]].candidate_id == b["id"] and outcomes[b["id"]].fingerprint == b["fingerprint"]
    assert outcomes[a["id"]].interval_of == a["id"]
    assert outcomes[c["id"]].interval_of is None
    first = [r.messages[0]["content"] for r in backend.requests]
    assert sum("<same_interval>" in text for text in first) == len(first) // 2, "only the group's conversation"


def test_a_failed_interval_leaves_every_member_with_the_reason() -> None:
    a, b = triple(b=5), triple(b=6)
    _, outcomes = run([a, b], Answers(fail_on="<same_interval>"), by_interval=True)
    assert outcomes[a["id"]] == outcomes[b["id"]] == "backend error: boom"


def test_a_budget_spends_on_the_strongest_signal_first() -> None:
    weak, strong = triple(b=5, feeds_branch=False), triple(b=6, a2=12, feeds_branch=True)
    backend = Answers()
    _, outcomes = run([weak, strong], backend, budget=Budget(max_tokens=1))
    assert isinstance(outcomes[weak["id"]], OverBudget)
    assert not isinstance(outcomes[strong["id"]], str)
    assert signal([strong]) < signal([weak])


def test_budget_limits() -> None:
    spend = Spend(spec="s", requests=5, input_tokens=70, output_tokens=30, cost_usd=1.0)
    assert Budget(max_requests=5).exceeded(spend) and not Budget(max_requests=6).exceeded(spend)
    assert Budget(max_tokens=100).exceeded(spend) and not Budget(max_tokens=101).exceeded(spend)
    assert Budget(max_usd=1.0).exceeded(spend) and not Budget(max_usd=2.0).exceeded(spend)


def test_a_dollar_limit_stops_on_a_backend_with_no_prices() -> None:
    """Unpriced is not free: spending on would be ignoring the limit."""
    spend = Spend(spec="s", requests=1, unpriced_requests=1)
    assert "no prices" in Budget(max_usd=100.0).exceeded(spend)


def test_calls_really_overlap_and_the_outcome_does_not_depend_on_how_many() -> None:
    records = [triple(a1=i, b=i + 1, a2=i + 2) for i in range(20, 32)]
    parallel = Answers(delay=0.02)
    _, many = run(records, parallel, workers=4)
    _, one = run(records, Answers())
    assert parallel.most_busy > 1
    assert {k: v.bucket for k, v in many.items()} == {k: v.bucket for k, v in one.items()}


def test_totals_add_up_under_parallel_calls() -> None:
    records = [triple(a1=i, b=i + 1, a2=i + 2) for i in range(20, 60)]
    client, _ = run(records, Answers(), workers=8)
    assert client.spend.candidates == 40
    assert client.spend.input_tokens == 800 * client.spend.requests


def test_stopping_leaves_no_outcome_for_what_was_not_reached() -> None:
    records = [triple(a1=i, b=i + 1, a2=i + 2) for i in range(20, 26)]
    done: list[str] = []
    _, outcomes = run(records, Answers(), should_stop=lambda: len(done) >= 2,
                      on_done=lambda group, _o: done.append(group[0]["id"]))
    assert len(outcomes) == 2


# -- through the run store ---------------------------------------------------


def _store(tmp_path, records, name) -> RunStore:
    cfg = Config.load(cli.REPO_ROOT / "bench" / "configs" / "svp_simple_001_001.yaml")
    store = RunStore.create(cfg, run_root=tmp_path, run_id=name)
    store.append_candidates("stage1", records)
    store.set_stage("stage1", "ok", candidates_in=len(records), candidates_out=len(records), dropped_with_proof=0)
    return store


@pytest.mark.parametrize(
    "options",
    [
        {"by_interval": True},
        {"budget": Budget(max_requests=2)},
        {"budget": Budget(max_requests=0)},
        {"workers": 3},
        {"by_interval": True, "budget": Budget(max_requests=1), "workers": 2},
    ],
    ids=str,
)
def test_the_report_lists_the_same_candidates_however_triage_ran(tmp_path, options) -> None:
    records = [triple(b=b) for b in (5, 6, 7)] + [triple(a2=20), triple(a1=30, b=31, a2=32)]
    plain = triage_store(_store(tmp_path, records, "plain"), config=FULL, backend=Answers())
    other_store = _store(tmp_path, records, "other")
    other = triage_store(other_store, config=FULL, backend=Answers(), **options)

    assert {t.candidate_id for t in other["triages"]} == {t.candidate_id for t in plain["triages"]} == {
        r["id"] for r in records}
    assert other["candidates_out"] == len(records)
    assert other_store.check() == []
    for t in other["triages"]:
        assert (other_store.root / "llm" / t.candidate_id / "verdict.json").is_file()


def test_what_a_budget_leaves_out_is_visible_and_the_stage_is_ok(tmp_path) -> None:
    records = [triple(a1=i, b=i + 1, a2=i + 2) for i in (20, 30, 40)]
    store = _store(tmp_path, records, "budget")
    summary = triage_store(store, config=FULL, backend=Answers(), budget=Budget(max_requests=0))
    assert summary["not_triaged"] == 3
    assert all(t.bucket.value == "uncertain" and t.not_triaged.startswith("budget:") for t in summary["triages"])
    assert {s["name"]: s["status"] for s in store.read_manifest()["stages"]}["triage"] == "ok"


def test_the_manifest_says_how_triage_ran(tmp_path) -> None:
    store = _store(tmp_path, [triple()], "manifest")
    triage_store(store, config=FULL, backend=Answers(), workers=2, by_interval=True, budget=Budget(max_usd=3.0))
    llm = store.read_manifest()["llm"]
    assert (llm["workers"], llm["by_interval"], llm["budget"]["max_usd"]) == (2, True, 3.0)
    contracts.validate("c3-manifest", store.read_manifest())
