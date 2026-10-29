"""C4 — and the rule that a missing answer is never an empty one."""

import json
import pytest

from irqrace import contracts
from irqrace.llm.fixtures import load_all
from irqrace.llm.resolver import (
    RECALL_RULES,
    SUPPORTED_KINDS,
    RecordBackedResolver,
    SourceBackedResolver,
    render_distribution,
    render_reply,
    request_distribution,
    resolver_for,
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


# -- SourceBackedResolver (W4/W8 C4 resolver) ------------------------------


SAMPLE_HEADER = """\
#ifndef COMMON_H
#define COMMON_H
#define CRITICAL_ENTER() \\
    disable_isr(1); \\
    disable_isr(2)
#define MAX_SLOTS 8

typedef struct {
    int count;
    int flags;
} ctrl_state_t;
#endif
"""

SAMPLE_C = """\
#include "common.h"

volatile int shared_counter = 0;

void helper_touch(void) {
    int snap = shared_counter;
    shared_counter = snap + 1;
}

void isr_2(void) {
    helper_touch();
    shared_counter = 0;
}
"""


def test_source_backed_resolver_serves_from_source_tree(tmp_path):
    (tmp_path / "common.h").write_text(SAMPLE_HEADER, encoding="utf-8")
    src_dir = tmp_path / "svp_simple_001"
    src_dir.mkdir()
    (src_dir / "svp_simple_001_001.c").write_text(SAMPLE_C, encoding="utf-8")

    r = SourceBackedResolver(RECORD, source_root=tmp_path)
    assert r.served_by == "resolver"
    assert r.has_sources

    # 1. function_definition not in record, found in source tree
    reply_fn = r.resolve(_req("function_definition", function="helper_touch"))
    contracts.validate("c4-reply", reply_fn)
    assert reply_fn["status"] == "ok"
    assert reply_fn["served_by"] == "resolver"
    assert "snap + 1" in reply_fn["payload"]["code"]

    # 2. macro_expansion including multiline continuation
    reply_macro = r.resolve(_req("macro_expansion", macro="CRITICAL_ENTER"))
    contracts.validate("c4-reply", reply_macro)
    assert reply_macro["status"] == "ok"
    assert "disable_isr(2)" in reply_macro["payload"]["expansion"]

    # 3. type_definition from header
    reply_type = r.resolve(_req("type_definition", type_name="ctrl_state_t"))
    contracts.validate("c4-reply", reply_type)
    assert reply_type["status"] == "ok"
    assert "int count;" in reply_type["payload"]["code"]

    # 4. global_declaration from C file
    reply_glob = r.resolve(_req("global_declaration", variable="shared_counter"))
    contracts.validate("c4-reply", reply_glob)
    assert reply_glob["status"] == "ok"
    assert "volatile int shared_counter" in reply_glob["payload"]["code"]

    # 5. all_accesses_to across the source tree returns status == "ok"
    reply_acc = r.resolve(_req("all_accesses_to", variable="shared_counter"))
    contracts.validate("c4-reply", reply_acc)
    assert reply_acc["status"] == "ok"
    kinds = {s["kind"] for s in reply_acc["payload"]["accesses"]}
    assert {"read", "write"} <= kinds

    # 6. all_call_paths finds call chain from flow entry to helper_touch
    reply_paths = r.resolve(_req("all_call_paths", function="helper_touch"))
    contracts.validate("c4-reply", reply_paths)
    assert reply_paths["status"] == "ok"
    assert reply_paths["payload"]["call_paths"]

    # 7. missing symbol still carries recall_rule
    reply_missing = r.resolve(_req("function_definition", function="rom_routine"))
    contracts.validate("c4-reply", reply_missing)
    assert reply_missing["status"] == "not_found"
    assert reply_missing["recall_rule"] == RECALL_RULES["not_found"]


def test_resolver_for_selects_mode_appropriately(tmp_path):
    src_dir = tmp_path / "svp_simple_001"
    src_dir.mkdir()
    (src_dir / "svp_simple_001_001.c").write_text(SAMPLE_C, encoding="utf-8")

    mock_r = resolver_for(RECORD, source_root=tmp_path, mode="mock")
    assert type(mock_r) is RecordBackedResolver
    src_r = resolver_for(RECORD, source_root=tmp_path, mode="source")
    assert isinstance(src_r, SourceBackedResolver)
    auto_r = resolver_for(RECORD, source_root=tmp_path, mode="auto")
    assert isinstance(auto_r, SourceBackedResolver)
    fallback_r = resolver_for(RECORD, source_root=tmp_path / "nonexistent", mode="auto")
    assert type(fallback_r) is RecordBackedResolver


def test_masking_on_a_stage1_record_is_unknown_not_a_crash():
    """Stage 1 does not compute masking; a record that has not been through
    stage 2 carries none. Asking for it must say "unsupported" -- treat as
    unknown -- rather than raise, and never answer enabled or disabled."""
    import copy

    rec = copy.deepcopy(RECORD)
    rec.pop("masking", None)
    for a in rec["accesses"]:
        a.pop("masking", None)
    line = rec["accesses"][0]["source"]["line"]
    reply = RecordBackedResolver(rec).resolve(_req("masking_state_at", line=line))
    assert reply["status"] == "unsupported"
    assert reply["recall_rule"] == RECALL_RULES["unsupported"]


def test_masking_falls_back_to_the_record_level_state_by_role():
    """Stage 2 also writes the state per role under masking.per_access."""
    import copy

    rec = copy.deepcopy(RECORD)
    for a in rec["accesses"]:
        a.pop("masking", None)
    a1 = rec["accesses"][0]
    state = {"disabled": [2], "enabled": [1], "unknown": []}
    rec["masking"]["per_access"] = [{"role": "A1", "state": state}]
    reply = RecordBackedResolver(rec).resolve(_req("masking_state_at", line=a1["source"]["line"]))
    assert reply["status"] == "ok"
    assert reply["payload"]["masking"] == state
