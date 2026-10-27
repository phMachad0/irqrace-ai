"""What a context record shows the model: the code that decides the case, and
nothing past it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from irqrace import cli
from irqrace.llm.client import render_record
from irqrace.run_evaluation import case_ground_truth
from irqrace.source_context import find_definition, function_extent

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_a_function_ends_at_its_closing_brace_not_the_line_after():
    lines = [
        "void f(void) {",
        '  /* } */ char *s = "}";',
        "  if (x) { y(); }",
        "}",
        "//bug: ground truth would be here",
    ]
    assert function_extent(lines, 1) == 4


def test_a_call_or_a_prototype_is_not_a_definition():
    lines = ["void enable_isr(int);", "void init() { enable_isr(-1); }"]
    assert find_definition(lines, "enable_isr") is None
    assert find_definition(lines, "init") == 2


@pytest.fixture(scope="module")
def run_001(tmp_path_factory):
    if case_ground_truth("svp_simple_001_001") is None:
        pytest.skip("Racebench is not on this machine")
    root = tmp_path_factory.mktemp("runs")
    cfg = REPO_ROOT / "bench" / "configs" / "svp_simple_001_001.yaml"
    assert cli.main(["pipeline", str(cfg), "--through", "context", "--run-root", str(root)]) == 0
    (run,) = [p for p in root.iterdir() if p.is_dir()]
    return run


def _contexts(run: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in (run / "context").glob("*.json")}


def test_no_record_carries_the_benchmark_annotations(run_001):
    for rec in _contexts(run_001).values():
        text = render_record(rec)
        assert "bug点" not in text and "误报点" not in text


def test_a_flow_the_masking_facts_name_is_in_the_record_with_its_code(run_001):
    rec = _contexts(run_001)["cf213e34277d338cc"]
    named = rec["masking"]["interval"]["reenabled_within_interval_by"]
    assert named == ["isr_1"]
    flows = {f["id"]: f for f in rec["flows"]}
    assert "isr_1" in flows
    shipped = {e["function"] for e in rec["enclosing_source"]}
    assert flows["isr_1"]["entry"] in shipped


def test_the_writers_of_a_guard_variable_are_stated_with_completeness(run_001):
    rec = _contexts(run_001)["cf213e34277d338cc"]
    facts = {e["fact"]: e for e in rec["provenance"]["entries"]}
    flag = facts["writers.svp_simple_001_001_global_flag"]
    assert flag["status"] == "proven" and ":41 " in flag["note"]
    assert facts["masking_primitives.disable_isr"]["status"] == "assumed_from_config"
    assert rec["provenance"]["completeness"]["opaque_external_calls"] == []
    assert "TRIGGER = 9999" in facts["macros"]["note"]


def test_source_is_rendered_with_its_file_line_numbers(run_001):
    rec = _contexts(run_001)["cf213e34277d338cc"]
    text = render_record(rec)
    assert "55      reader1 = svp_simple_001_001_global_array[TRIGGER];" in text \
        or "55    reader1" in text
