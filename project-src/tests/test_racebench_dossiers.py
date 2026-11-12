"""scripts/racebench-dossiers.py: selection, grouping, and blindness of the dossiers."""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys

import pytest

from conftest import EXAMPLES, REPO, SUITE

pytestmark = pytest.mark.skipif(not SUITE.is_dir(), reason="Racebench suite not available")

_spec = importlib.util.spec_from_file_location("racebench_dossiers", REPO / "scripts" / "racebench-dossiers.py")
dossiers = importlib.util.module_from_spec(_spec)
sys.modules["racebench_dossiers"] = dossiers  # dataclasses look their module up there
_spec.loader.exec_module(dossiers)

FIXTURE = EXAMPLES / "run-fixture"
#: Every string a triage file carries that would unblind a dossier.
BUCKETS = ("likely_real", "likely_infeasible", "likely_benign")
VERDICT_WORDS = ("feasible", "infeasible", "harmful", "benign")


def _relined(record: dict, lines: tuple[int, int, int], cid: str) -> dict:
    rec = json.loads(json.dumps(record))
    order = {"A1": 0, "B": 1, "A2": 2}
    for a in rec["accesses"]:
        a["source"]["line"] = lines[order[a["role"]]]
    rec["id"] = cid
    return rec


def _triage(cid: str, bucket: str) -> dict:
    return {
        "candidate_id": cid,
        "fingerprint": "f" * 64,
        "feasibility": {"reasoning": f"MARKER-FEAS-REASONING-{cid} the interleaving is real",
                        "blocking_element": f"MARKER-BLOCKING-{cid}",
                        "verdict": "infeasible" if bucket == "likely_infeasible" else "feasible",
                        "confidence": 0.8731},
        "harmfulness": {"reasoning": f"MARKER-HARM-REASONING-{cid}",
                        "criterion_matched": f"MARKER-CRITERION-{cid}",
                        "verdict": "harmful", "confidence": 0.6427},
        "produced_by": {"backend": "MARKER-BACKEND", "structured_mode": "native_schema"},
        "not_triaged": None, "interval_of": None, "bucket": bucket,
    }


@pytest.fixture()
def run(tmp_path):
    """A triaged run of svp_simple_001_001: one annotated record, four unannotated ones."""
    root = tmp_path / "runs" / "svp_simple_001_001-fixture"
    (root / "context").mkdir(parents=True)
    shutil.copy(FIXTURE / "manifest.json", root / "manifest.json")
    recs = {json.loads(p.read_text(encoding="utf-8"))["variable"]["name"]: json.loads(p.read_text(encoding="utf-8"))
            for p in (FIXTURE / "context").glob("*.json")}
    var, arr = recs["svp_simple_001_001_global_var"], recs["svp_simple_001_001_global_array"]
    records = [
        _relined(var, (43, 64, 44), "c000000000000annot"),   # 2.1 bug 2: annotated
        _relined(arr, (32, 55, 32), "c0000000000000real"),
        _relined(arr, (32, 58, 32), "c00000000000inf001"),
        _relined(arr, (32, 60, 32), "c00000000000inf002"),
        _relined(var, (43, 64, 43), "c00000000000inf003"),
    ]
    for r in records:
        (root / "context" / f"{r['id']}.json").write_text(json.dumps(r), encoding="utf-8")
    buckets = {"c000000000000annot": "likely_real", "c0000000000000real": "likely_real",
               "c00000000000inf001": "likely_infeasible", "c00000000000inf002": "likely_benign",
               "c00000000000inf003": "likely_infeasible"}
    (root / "llm").mkdir()
    triage = [_triage(cid, b) for cid, b in buckets.items()]
    (root / "llm" / "triage.jsonl").write_text("\n".join(json.dumps(t) for t in triage) + "\n", encoding="utf-8")
    for t in triage:
        (root / "llm" / t["candidate_id"]).mkdir()
        (root / "llm" / t["candidate_id"] / "verdict.json").write_text(json.dumps(t), encoding="utf-8")
    return root


def _strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, (str, float)) and not isinstance(obj, bool):
        yield str(obj)


def _blind_files(out):
    files = sorted((out / "dossiers").glob("*.md")) + [out / "README.md", out / "groups.csv"]
    assert files[:-2], "no dossier was written"
    return {p: p.read_text(encoding="utf-8") for p in files}


def _assert_blind(out, run):
    forbidden = set(BUCKETS)
    for line in (run / "llm" / "triage.jsonl").read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        for part in ("feasibility", "harmfulness"):
            forbidden |= {s for s in _strings(rec[part]) if len(s) >= 4}
        forbidden |= {rec["bucket"], rec["produced_by"]["backend"]}
    for path, text in _blind_files(out).items():
        for s in forbidden:
            assert s not in text, f"{path.name} contains triage content {s!r}"
        for word in VERDICT_WORDS + ("confidence", "reasoning", "bucket"):
            assert word not in text.lower(), f"{path.name} contains {word!r}"


def test_all_mode_lists_every_unannotated_triple_and_never_reads_llm(run, tmp_path, monkeypatch):
    monkeypatch.setattr(dossiers, "read_buckets", lambda *_: pytest.fail("--all opened llm/"))
    out = tmp_path / "out"
    summary = dossiers.build(dossiers.collect_runs([run]), out, mode="all", log=lambda *_: None)
    assert summary["records_reaching_llm"] == 5
    assert summary["unannotated_triples"] == 4 and summary["chosen_triples"] == 4
    # global_array triples group with 2.1 bug 1 / trap 1, global_var's with 2.1 bug 2.
    assert summary["dossiers"] == 2 and summary["groups_with_an_annotated_member"] == 2
    rows = list(csv.DictReader((out / "groups.csv").open(encoding="utf-8")))
    assert sorted(r["triple"] for r in rows) == [
        "svp_simple_001_001@32-55-32", "svp_simple_001_001@32-58-32",
        "svp_simple_001_001@32-60-32", "svp_simple_001_001@43-64-43"]
    assert "c000000000000annot" not in "".join(r["candidate_ids"] for r in rows)
    _assert_blind(out, run)


def test_dossier_content(run, tmp_path):
    out = tmp_path / "out"
    dossiers.build(dossiers.collect_runs([run]), out, mode="all", log=lambda *_: None)
    text = (out / "dossiers" / "svp_simple_001_001-D1.md").read_text(encoding="utf-8")
    # The fixture's source_root does not exist here: the source comes from the vendored suite.
    assert "32    for (int i = 0; i < 10000; i++) svp_simple_001_001_global_array[i] = 0;" in text
    assert "51  void svp_simple_001_001_isr_2() {" in text
    assert "20  volatile int svp_simple_001_001_global_array[10000];" in text
    # The annotation block after the last function is never quoted raw.
    assert "bug点" not in text and "误报点" not in text
    # The README's arrival model, original and translation.
    assert "打断的时刻不定" in text and "whenever it is enabled" in text
    # Grouping shown, with the suite's labels; one form per triple to adjudicate.
    assert "| (32, 55, 35) | 2.1 bug 1 |" in text and "| (32, 60, 35) | 2.1 trap 1 |" in text
    assert text.count("- id: R22-____") == 3
    assert "verdict:           # bug | trap | not-a-defect | undecided" in text


def test_sample_mode_selects_without_unblinding(run, tmp_path):
    out = tmp_path / "out"
    summary = dossiers.build(dossiers.collect_runs([run]), out, mode="likely-real-plus-sample",
                             k=1, seed=7, log=lambda *_: None)
    sel = {r["triple"]: r for r in csv.DictReader((out / "selection.csv").open(encoding="utf-8"))}
    assert len(sel) == 4
    assert sel["svp_simple_001_001@32-55-32"]["selected_by"] == "likely_real"
    sampled = [t for t, r in sel.items() if r["selected_by"].startswith("sample")]
    assert len(sampled) == 1 and summary["chosen_triples"] == 2
    # selection.csv is the one file that carries buckets ...
    assert "likely_infeasible" in (out / "selection.csv").read_text(encoding="utf-8")
    # ... and nothing the adjudicator opens does, nor lists the triples left out.
    _assert_blind(out, run)
    left_out = [t for t, r in sel.items() if r["selected"] == "no"]
    for text in _blind_files(out).values():
        for t in left_out:
            assert t not in text
    # Same seed, same sample.
    again = tmp_path / "again"
    dossiers.build(dossiers.collect_runs([run]), again, mode="likely-real-plus-sample",
                   k=1, seed=7, log=lambda *_: None)
    assert (again / "selection.csv").read_text(encoding="utf-8") == (out / "selection.csv").read_text(encoding="utf-8")


def test_two_runs_of_one_subject_need_latest(run, tmp_path):
    other = run.parent / "svp_simple_001_001-fixture2"
    shutil.copytree(run, other)
    with pytest.raises(SystemExit, match="--latest"):
        dossiers.collect_runs([run.parent])
    assert dossiers.collect_runs([run.parent], latest=True) == {"svp_simple_001_001": other}


def test_cli_requires_a_seed_for_sampling(run, tmp_path):
    with pytest.raises(SystemExit):
        dossiers.main([str(run), "--out", str(tmp_path / "o"), "--likely-real-plus-sample", "3"])
