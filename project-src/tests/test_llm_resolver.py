"""C4 — and the rule that a missing answer is never an empty one."""

import pytest
import json

from irqrace import contracts
from irqrace.llm.fixtures import load_all
from irqrace.llm.resolver import (
    RECALL_RULES,
    SUPPORTED_KINDS,
    RecordBackedResolver,
    render_distribution,
    render_reply,
    request_distribution,
)

RECORD = load_all()[0].record


def _req(kind, **args):
    return {
        "schema_version": "c4/1.0.0",
        "request_id": "r-1",
        "candidate_id": RECORD["id"],
        "kind": kind,
        "args": args,
    }


def test_every_reply_conforms_to_c4():
    r = RecordBackedResolver(RECORD)
    for kind, args in [
        ("function_definition", {"function": RECORD["accesses"][0]["function"]}),
        ("function_definition", {"function": "nonexistent_function"}),
        ("isr_body", {"flow": "isr_2"}),
        ("all_accesses_to", {"variable": RECORD["variable"]["name"]}),
        ("global_declaration", {"variable": RECORD["variable"]["name"]}),
        ("masking_state_at", {"file": "x.c", "line": 999}),
        ("macro_expansion", {"macro": "ANYTHING"}),
    ]:
        reply = r.resolve(_req(kind, **args))
        contracts.validate("c4-reply", reply, what=kind)


def test_a_known_function_comes_back_with_its_body():
    r = RecordBackedResolver(RECORD)
    fn = RECORD["enclosing_source"][0]["function"]
    reply = r.resolve(_req("function_definition", function=fn))
    assert reply["status"] == "ok"
    assert reply["payload"]["code"]


def test_not_found_carries_its_recall_rule():
    """The whole point of C4's status field."""
    r = RecordBackedResolver(RECORD)
    reply = r.resolve(_req("function_definition", function="vendor_blob"))
    assert reply["status"] == "not_found"
    assert reply["recall_rule"] == RECALL_RULES["not_found"]
    assert "may access the shared variable" in reply["recall_rule"]


def test_no_status_ever_produces_a_bare_empty_result():
    """An empty payload with no rule reads as 'this function is clean'."""
    r = RecordBackedResolver(RECORD)
    for kind, args in [
        ("function_definition", {"function": "missing"}),
        ("macro_expansion", {"macro": "MISSING"}),
        ("type_definition", {"type_name": "missing_t"}),
        ("masking_state_at", {"file": "x.c", "line": 1}),
    ]:
        reply = r.resolve(_req(kind, **args))
        assert reply["status"] != "ok"
        assert reply["recall_rule"], f"{kind} returned an unexplained empty payload"


def test_partial_accesses_are_marked_truncated_not_ok():
    """The record knows this candidate's accesses, not the variable's."""
    r = RecordBackedResolver(RECORD)
    reply = r.resolve(_req("all_accesses_to", variable=RECORD["variable"]["name"]))
    assert reply["status"] == "truncated"


def test_the_rule_appears_before_the_payload_when_rendered():
    r = RecordBackedResolver(RECORD)
    text = render_reply(r.resolve(_req("function_definition", function="missing")))
    assert "Apply this rule" in text
    assert text.index("Apply this rule") < len(text)


def test_requests_are_logged_for_the_d2_measurement():
    """What was asked, how often, how deep -- the cheapest experiment here."""
    r = RecordBackedResolver(RECORD)
    r.resolve({**_req("isr_body", flow="isr_2"), "turn": 1})
    r.resolve({**_req("function_definition", function="missing"), "turn": 2})
    assert [e["kind"] for e in r.log] == ["isr_body", "function_definition"]
    assert [e["turn"] for e in r.log] == [1, 2]
    assert [e["status"] for e in r.log] == ["ok", "not_found"]


def test_extra_context_widens_the_mock_without_touching_the_class():
    r = RecordBackedResolver(
        RECORD, extra={("macro_expansion", "CRITICAL"): {"expansion": "disable_isr(2)"}}
    )
    reply = r.resolve(_req("macro_expansion", macro="CRITICAL"))
    assert reply["status"] == "ok"
    assert "disable_isr" in json.dumps(reply["payload"])


# -- the D#2 measurement ---------------------------------------------------


def test_the_distribution_reports_kind_depth_and_status():
    r = RecordBackedResolver(RECORD)
    fn = RECORD["enclosing_source"][0]["function"]
    r.resolve({**_req("function_definition", function=fn), "turn": 1})
    r.resolve({**_req("function_definition", function="missing"), "turn": 2})
    r.resolve({**_req("isr_body", flow="isr_2"), "turn": 1})

    d = request_distribution([{**e, "candidate_id": RECORD["id"]} for e in r.log])
    assert d["requests"] == 3
    assert d["by_kind"]["function_definition"] == 2
    assert d["by_depth"] == {1: 2, 2: 1}
    assert d["not_found_rate"] == pytest.approx(1 / 3)


def test_kinds_nobody_asked_for_are_named():
    """A kind never requested is a candidate for removal at the next C4 bump."""
    r = RecordBackedResolver(RECORD)
    r.resolve({**_req("isr_body", flow="isr_2"), "turn": 1})
    d = request_distribution([{**e, "candidate_id": "c1"} for e in r.log])
    assert "macro_expansion" in d["never_requested"]
    assert "isr_body" not in d["never_requested"]


def test_the_supported_kinds_match_the_c4_contract():
    """Drift here would measure 'never requested' against a stale list."""
    schema = contracts.load_schema("c4-request")
    assert SUPPORTED_KINDS == set(schema["properties"]["kind"]["enum"])


def test_an_empty_log_reports_nothing_rather_than_dividing_by_zero():
    assert request_distribution([]) == {"requests": 0}
    assert "no context requests" in render_distribution({"requests": 0})
