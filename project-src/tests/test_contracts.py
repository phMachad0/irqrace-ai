"""The contracts are only useful if the examples actually conform to them.

An example that has drifted from its schema is worse than no example: it teaches
the wrong shape to whoever copies it.
"""
import json

import pytest
import yaml
from conftest import EXAMPLES, REPO

from irqrace import contracts
from irqrace.config import DEFAULTS, FLOW_DEFAULTS, PRIMITIVE_DEFAULTS
from irqrace.runstore import RunStore

CASES = [
    ("c1", "c1-svp_simple_001_001.yaml"),
    ("c2", "c2-bugpoint.json"),
    ("c2", "c2-trap.json"),
    ("c3-manifest", "c3-manifest-example.json"),
    ("c4-request", "c4-context-request-example.json"),
    ("c4-reply", "c4-context-reply-example.json"),
    ("c4-reply", "c4-context-reply-notfound-example.json"),
]


def _load(name):
    p = EXAMPLES / name
    return yaml.safe_load(p.read_text()) if p.suffix == ".yaml" else json.loads(p.read_text())


@pytest.mark.parametrize("schema,name", CASES)
def test_example_conforms(schema, name):
    contracts.validate(schema, _load(name), what=name)


@pytest.mark.parametrize("schema,name", CASES)
def test_example_declares_matching_schema_version(schema, name):
    doc = _load(name)
    expected = {"c1": "c1/", "c2": "c2/", "c3-manifest": "c3/",
                "c4-request": "c4/", "c4-reply": "c4/"}[schema]
    assert doc["schema_version"].startswith(expected)


def test_every_schema_loads_and_is_a_valid_metaschema():
    for name in contracts.SCHEMAS:
        contracts.validator(name).check_schema(contracts.load_schema(name))


def _schema_defaults(node, prefix=""):
    """Collect every ``default`` annotation, keyed by dotted property path."""
    out = {}
    if isinstance(node, dict):
        props = node.get("properties", {})
        for key, sub in props.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(sub, dict) and "default" in sub:
                out[path] = sub["default"]
            out.update(_schema_defaults(sub, path))
    return out


def _code_defaults(node, prefix=""):
    out = {}
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(_code_defaults(value, path))
        else:
            out[path] = value
    return out


def test_code_defaults_match_the_schema():
    """``config.DEFAULTS`` restates the schema's defaults so that a loaded
    configuration is fully resolved. The two must not drift apart: a default that
    exists only in the schema is never applied, and one that exists only in the
    code is undocumented."""
    schema_defaults = _schema_defaults(contracts.load_schema("c1"))
    code = _code_defaults(DEFAULTS)
    code.update({f"flows.{k}": v for k, v in FLOW_DEFAULTS.items()})
    code.update({f"masking.primitives.{k}": v for k, v in PRIMITIVE_DEFAULTS.items()})

    mismatched = {}
    for path, want in schema_defaults.items():
        # Array-valued and nested-under-array defaults are compared by the two
        # explicit dicts above rather than by path.
        got = code.get(path, code.get(path.split(".")[-1], "<<missing>>"))
        if got != want:
            mismatched[path] = (want, got)
    assert not mismatched, f"defaults drifted from the schema: {mismatched}"


def test_run_fixture_conforms_to_c3():
    problems = RunStore(EXAMPLES / "run-fixture").check()
    assert problems == []


def test_run_fixture_candidates_conform_to_c2():
    store = RunStore(EXAMPLES / "run-fixture")
    for stage in ("stage1", "stage2"):
        records = store.read_candidates(stage)
        assert records, f"{stage} has no candidates"
        for rec in records:
            contracts.validate("c2", rec, what=f"{stage} {rec['id']}")


def test_a_dropped_candidate_without_a_proof_is_caught(tmp_path):
    """C3 rule 6 is the one that protects recall, so test it directly."""
    import shutil

    run = tmp_path / "run"
    shutil.copytree(EXAMPLES / "run-fixture", run)
    (run / "solver" / "results.jsonl").write_text("")  # remove the UNSAT proof
    problems = RunStore(run).check()
    assert any("dropped without a proof" in p for p in problems), problems
