"""Triage by variable (``llm triage --by-variable``): one checklist per shared variable.

The rule is the same as for intervals: the report holds the same candidates
however triage was run. On top of it, what the code enforces when the model
answers a checklist: an item left out is asked again on its own, a malformed
answer sends the whole group to one conversation per candidate, and the
transcript keeps every call that was made.
"""

from __future__ import annotations

import copy
import json
import re
import threading

import pytest

from irqrace import cli, contracts
from irqrace.candidate import stamp_identity
from irqrace.config import Config
from irqrace.llm.backends import Backend, Capabilities, ChatRequest, ChatResponse, StructuredMode, Usage
from irqrace.llm.backends.claude_cli_backend import DEFAULT_TIMEOUT_S, TIMEOUT_ENV, ClaudeCLIBackend
from irqrace.llm.checklist import group_variables, render_checklist
from irqrace.llm.client import TriageClient
from irqrace.llm.fixtures import load_all
from irqrace.llm.pipeline import triage_records, triage_store
from irqrace.llm.prompts import FULL, checklist_hash, checklist_prompt
from irqrace.llm.resolver import RecordBackedResolver
from irqrace.llm.verdict import Triage
from irqrace.runstore import RunStore

BASE = next(f for f in load_all() if f.subject == "svp_simple_001_001").record
ITEM_ID = re.compile(r'<item id="([^"]+)">')


def triple(a1=8, b=5, a2=11, variable=None) -> dict:
    rec = copy.deepcopy(BASE)
    if variable:
        rec["variable"]["name"] = variable
    for access, line in zip(sorted(rec["accesses"], key=lambda x: "A1 B A2".split().index(x["role"])), (a1, b, a2)):
        access["source"]["line"] = line
    return stamp_identity(rec)


class Checklists(Backend):
    """Answers single candidates and checklists. ``omit`` ids are left out of a
    checklist's feasibility answer; ``mangle`` is ``"twice"`` or ``"stranger"``."""

    provider = "fake"

    def __init__(self, omit=(), mangle=None):
        super().__init__("v1")
        self.omit, self.mangle = set(omit), mangle
        self.lock = threading.Lock()
        self.requests: list[ChatRequest] = []

    @property
    def capabilities(self):
        return Capabilities(structured=StructuredMode.native_schema, prompt_caching=True)

    def chat(self, request: ChatRequest) -> ChatResponse:
        with self.lock:
            self.requests.append(request)
        text = request.messages[0]["content"]
        harm = text.startswith("The interleaving") or request.schema_name == "HarmfulnessChecklist"
        one = ({"reasoning": "r", "criterion_matched": "feeds a branch", "verdict": "harmful", "confidence": 0.9}
               if harm else {"reasoning": "r", "blocking_element": None, "verdict": "feasible", "confidence": 0.9})
        if request.schema_name in ("FeasibilityChecklist", "HarmfulnessChecklist"):
            ids = ITEM_ID.findall(text)
            if not harm:
                ids = [i for i in ids if i not in self.omit]
                if self.mangle == "twice":
                    ids.append(ids[0])
                elif self.mangle == "stranger":
                    ids.append("c-nobody")
            payload = {"shared_findings": [{"id": "F1", "statement": "s"}],
                       "items": [{"candidate_id": i, "uses_findings": [], **one} for i in ids]}
        else:
            payload = one
        return ChatResponse(text=json.dumps(payload), parsed=payload, structured_mode=StructuredMode.native_schema,
                            usage=Usage(input_tokens=800, output_tokens=200))


def run(records, backend, run_dir=None, **kwargs):
    client = TriageClient(FULL, backend=backend)
    return triage_records(client, records, make_resolver=RecordBackedResolver, run_dir=run_dir,
                          by_variable=True, **kwargs)


def turns(run_dir, cid) -> list[dict]:
    path = run_dir / "llm" / cid / "turns.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# -- grouping and rendering -----------------------------------------------------


def test_candidates_are_grouped_by_variable_and_chunked_without_splitting_an_interval() -> None:
    x = [triple(b=b) for b in (5, 6, 7)] + [triple(a2=20, b=b) for b in (12, 13)]
    y = [triple(variable="other")]
    groups = group_variables(x + y, max_items=4)
    assert [[r["id"] for r in g] for g in groups] == [[r["id"] for r in x[:3]], [r["id"] for r in x[3:]],
                                                      [y[0]["id"]]]


def test_an_interval_larger_than_the_limit_is_split() -> None:
    x = [triple(b=b) for b in range(1, 6)]
    assert [len(g) for g in group_variables(x, max_items=2)] == [2, 2, 1]


def test_each_item_plus_the_shared_context_is_the_whole_record() -> None:
    a, b = triple(b=5), triple(b=6)
    text = render_checklist([a, b])
    shared = json.loads(text.split("<shared_context>\n", 1)[1].split("\n</shared_context>", 1)[0])
    for record in (a, b):
        item = text.split(f'<item id="{record["id"]}">\n', 1)[1].split("\n</item>", 1)[0]
        whole = {**shared, **json.loads(item)}
        assert whole == {k: v for k, v in record.items() if k != "enclosing_source"}
    for entry in a["enclosing_source"]:
        assert text.count(f'location="{entry["file"]}:{entry["line_start"]}-{entry["line_end"]}"') == 1


# -- what the code enforces -------------------------------------------------------


def test_one_checklist_answers_for_every_candidate_on_the_variable() -> None:
    records = [triple(b=b) for b in (5, 6, 7)]
    backend = Checklists()
    outcomes = run(records, backend)
    assert set(outcomes) == {r["id"] for r in records}
    assert all(isinstance(t, Triage) for t in outcomes.values())
    assert [t.interval_of for t in (outcomes[r["id"]] for r in records)] == [None, records[0]["id"], records[0]["id"]]
    assert [r.schema_name for r in backend.requests] == ["FeasibilityChecklist", "HarmfulnessChecklist"]
    assert all(r.system.endswith(checklist_prompt()) for r in backend.requests)


def test_a_variable_with_one_candidate_is_asked_the_usual_way() -> None:
    backend = Checklists()
    outcomes = run([triple()], backend)
    assert isinstance(next(iter(outcomes.values())), Triage)
    assert [r.schema_name for r in backend.requests] == ["FeasibilityAnswer", "HarmfulnessAnswer"]


@pytest.mark.parametrize("omitted", [0, 1], ids=["lead", "member"])
def test_an_item_left_out_is_asked_again_alone_and_the_transcript_keeps_both(tmp_path, omitted) -> None:
    records = [triple(b=b) for b in (5, 6, 7)]
    left_out = records[omitted]["id"]
    backend = Checklists(omit={left_out})
    outcomes = run(records, backend, run_dir=tmp_path)
    assert all(isinstance(t, Triage) for t in outcomes.values())
    assert outcomes[left_out].interval_of is None, "answered by its own conversation"
    assert [r.schema_name for r in backend.requests].count("FeasibilityAnswer") == 1

    lead = turns(tmp_path, records[0]["id"])
    assert sum(t["role"] == "assistant" and "checklist" in t for t in lead) == 2, "checklist turns not overwritten"
    retry = turns(tmp_path, left_out)
    assert any(t.get("after") == "checklist" for t in retry)
    if omitted == 0:
        assert lead == retry and [t.get("after") for t in lead if t["role"] == "assistant"] == [
            None, None, "checklist", "checklist"]


@pytest.mark.parametrize("mangle", ["twice", "stranger"])
def test_a_malformed_answer_sends_every_member_to_its_own_conversation(tmp_path, mangle) -> None:
    records = [triple(b=b) for b in (5, 6)]
    backend = Checklists(mangle=mangle)
    outcomes = run(records, backend, run_dir=tmp_path)
    assert all(isinstance(t, Triage) and t.interval_of is None for t in outcomes.values())
    assert [r.schema_name for r in backend.requests].count("FeasibilityAnswer") == 2
    lead = turns(tmp_path, records[0]["id"])
    assert lead[0].get("checklist") and any(t.get("after") == "checklist" for t in lead)


def test_the_two_groupings_do_not_combine() -> None:
    with pytest.raises(ValueError, match="pick one"):
        run([triple()], Checklists(), by_interval=True)
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["llm", "triage", "x", "--by-interval", "--by-variable"])


def _store(tmp_path, records, name) -> RunStore:
    cfg = Config.load(cli.REPO_ROOT / "bench" / "configs" / "svp_simple_001_001.yaml")
    store = RunStore.create(cfg, run_root=tmp_path, run_id=name)
    store.append_candidates("stage1", records)
    store.set_stage("stage1", "ok", candidates_in=len(records), candidates_out=len(records), dropped_with_proof=0)
    return store


@pytest.mark.parametrize("omit", [False, True])
def test_the_report_lists_every_candidate_and_the_manifest_says_how(tmp_path, omit) -> None:
    records = [triple(b=b) for b in (5, 6, 7)] + [triple(a2=20), triple(variable="other")]
    store = _store(tmp_path, records, "var")
    backend = Checklists(omit={records[1]["id"]} if omit else ())
    summary = triage_store(store, config=FULL, backend=backend, workers=2, by_variable=True)
    assert {t.candidate_id for t in summary["triages"]} == {r["id"] for r in records}
    assert summary["not_triaged"] == 0
    assert store.check() == []
    llm = store.read_manifest()["llm"]
    assert (llm["by_variable"], llm["by_interval"], llm["checklist_sha256"]) == (True, False, checklist_hash())
    contracts.validate("c3-manifest", store.read_manifest())


def test_the_claude_cli_timeout_can_be_raised_from_the_environment(monkeypatch) -> None:
    monkeypatch.delenv(TIMEOUT_ENV, raising=False)
    assert ClaudeCLIBackend("sonnet").timeout_s == DEFAULT_TIMEOUT_S
    monkeypatch.setenv(TIMEOUT_ENV, "1200")
    assert ClaudeCLIBackend("sonnet").timeout_s == 1200.0
    assert ClaudeCLIBackend("sonnet", timeout_s=30).timeout_s == 30
