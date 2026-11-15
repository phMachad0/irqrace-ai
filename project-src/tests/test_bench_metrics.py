"""The Racebench scorer (``irqrace.bench_metrics``, ``scripts/bench-triage-report.py``)."""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

from benchfake import make_case, make_root, specs_001
from irqrace import bench_metrics as bm
from irqrace.groundtruth import CaseGroundTruth
from irqrace.run_evaluation import case_ground_truth, evaluate_run
from irqrace.runstore import RunStore

REPO = Path(__file__).resolve().parents[1]
V0 = Path(__file__).parent / "data" / "bench_triage_report_v0.py"
SCRIPT = REPO / "scripts" / "bench-triage-report.py"

pytestmark = pytest.mark.skipif(case_ground_truth("svp_simple_001_001") is None,
                                reason="Racebench is not on this machine")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _v0(root: Path, monkeypatch) -> tuple[bytes, bytes]:
    mod = _load(V0, "bench_triage_report_v0")
    monkeypatch.setattr(sys, "argv", ["bench-triage-report.py", str(root)])
    assert mod.main() == 0
    out = (root / "report.json").read_bytes(), (root / "report.md").read_bytes()
    (root / "report.json").unlink()
    (root / "report.md").unlink()
    return out


def _new(argv: list[str]) -> int:
    return _load(SCRIPT, "bench_triage_report").main(argv)


# ---------------------------------------------------------------------------
# Regression equivalence with the script as it was before the extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("triaged", [True, False])
def test_legacy_mode_is_byte_identical_to_the_previous_script(tmp_path, monkeypatch, capsys, triaged):
    root = make_root(tmp_path / "root", triaged=triaged)
    (root / "timings.tsv").write_text("svp_simple_001_001\t100.0\t160.5\t0\nsvp_simple_017_001\t160.5\t200.0\t0\n")
    (root / "start.txt").write_text("100.0")
    (root / "end.txt").write_text("200.0")
    before_json, before_md = _v0(root, monkeypatch)
    assert _new([str(root)]) == 0
    assert (root / "report.json").read_bytes() == before_json
    assert (root / "report.md").read_bytes() == before_md


def test_extended_numbers_equal_the_legacy_ones(tmp_path):
    rd = bm.load_root(make_root(tmp_path / "root"))
    doc, _ = bm.legacy_report(rd)
    s = doc["summary"]
    by_view = {m.view: m for m in bm.run_metrics(rd)}
    for view, legacy in s["scores"].items():
        m = by_view[view]
        assert (m.bug_points_detected, m.traps_reported, m.score, m.unannotated_reported) == (
            legacy["bugs_detected"], legacy["false_positives"], legacy["score"], legacy["unannotated_reported"])
        assert m.bug_points_total == s["ground_truth"]["bug_points"]
        assert m.traps_total == s["ground_truth"]["traps"]
        assert m.score_max == s["max_score"]
    assert by_view["static only"].inspection_ratio_mean == s["inspection_ratio_mean"]["static"]
    assert by_view["likely_real"].inspection_ratio_mean == s["inspection_ratio_mean"]["triage"]
    assert by_view["likely_real"].llm_calls == s["time"]["llm_calls"]


def test_stage_evals_reproduces_evaluate_run(tmp_path):
    root = make_root(tmp_path / "root")
    for run in sorted(p for p in root.iterdir() if p.is_dir()):
        store = RunStore(run)
        subject = store.read_manifest()["subject"]["name"]
        ours = bm.stage_evals(store, case_ground_truth(subject))
        assert ours == {e.stage: e for e in evaluate_run(store)}


# ---------------------------------------------------------------------------
# Numbers on a known tree
# ---------------------------------------------------------------------------


def test_scores_per_view_and_per_pattern(tmp_path):
    rd = bm.load_root(make_root(tmp_path / "root"))
    m = {x.view: x for x in bm.run_metrics(rd)}
    assert (m["likely_real"].bug_points_detected, m["not infeasible"].bug_points_detected,
            m["static only"].bug_points_detected) == (4, 5, 5)
    assert m["static only"].bug_points_total == 6  # 017 bug 2 is never generated
    assert (m["likely_real"].traps_reported, m["static only"].traps_reported) == (0, 1)
    assert (m["likely_real"].score, m["not infeasible"].score, m["static only"].score) == (8, 10, 7)
    assert m["static only"].precision == pytest.approx(5 / 6)
    assert m["likely_real"].uncertain == 1 and m["static only"].uncertain is None
    assert m["static only"].system == "S1" and m["likely_real"].system == "S2"
    assert m["likely_real"].patterns == {"RWR": (2, 1), "WWR": (1, 1), "WRW": (2, 2), "RWW": (1, 0)}
    assert m["not infeasible"].patterns["RWW"] == (1, 1)
    assert m["likely_real"].llm_calls == 8 * 2
    assert m["likely_real"].static_s == pytest.approx(2 * (100 + 200 + 30 + 400 + 20) / 1000)
    assert m["likely_real"].llm_s == pytest.approx(10.0)


def test_items_carry_every_annotation_and_every_unannotated_candidate(tmp_path):
    rd = bm.load_root(make_root(tmp_path / "root"))
    items = {(i.case[11:14], i.item_id): i for i in bm.root_items(rd)}
    assert items[("017", "bug#2")].fate == "stage1_absent"
    assert items[("017", "trap#1")].fate == "solver"
    assert items[("001", "c001u2")].fate == "stage2" and items[("001", "c001u2")].kind == "unannotated"
    assert items[("001", "bug#2")].triple == "W43 R64 W44"
    assert items[("017", "trap#1")].pattern == "WWW"
    assert items[("001", "trap#1")].bucket == "likely_infeasible"


def test_case_and_pattern_filters_reach_the_denominators(tmp_path):
    rd = bm.load_root(make_root(tmp_path / "root"))
    only_001 = {m.view: m for m in bm.run_metrics(rd, bm.Subset(cases=frozenset({"svp_simple_001_001"})))}
    assert (only_001["static only"].bug_points_total, only_001["static only"].traps_total) == (2, 1)
    assert only_001["static only"].score_max == 4
    no_rww = {m.view: m for m in bm.run_metrics(rd, bm.Subset(exclude_patterns=frozenset({"RWW"})))}
    m = no_rww["not infeasible"]
    assert (m.bug_points_total, m.bug_points_detected) == (5, 4)
    assert "RWW" not in m.patterns
    assert no_rww["static only"].unannotated_reported == 1  # 017's RWW candidate is out too
    assert no_rww["likely_real"].llm_calls == 6 * 2  # its two calls and b3's leave with it
    assert m.case_subset == "exclude=RWW"


def test_pattern_exclusion_recomputes_the_inspection_ratio(tmp_path):
    rd = bm.load_root(make_root(tmp_path / "root"))
    store = next(c.store for c in rd.cases if c.subject == "svp_simple_017_001")
    full = bm.stage_evals(store, case_ground_truth("svp_simple_017_001"))
    cut = bm.stage_evals(store, case_ground_truth("svp_simple_017_001"), frozenset({"RWW"}))
    assert full["context"].candidates == 4 and cut["context"].candidates == 2
    assert (full["context"].bug_points, cut["context"].bug_points) == (4, 3)  # RWW bug 3 is out
    # Bug 2 is never generated, so the ratio stays undefined either way.
    assert full["context"].inspection_ratio is None and cut["context"].inspection_ratio is None
    one = bm.stage_evals(store, case_ground_truth("svp_simple_017_001"), frozenset({"RWW", "RWR"}))
    assert one["context"].candidates == 1 and one["context"].inspection_ratio == 1.0


def test_parse_cases_accepts_short_names_lists_and_files(tmp_path):
    f = tmp_path / "subset.txt"
    f.write_text("# comment\nsvp_simple_003_001  # trailing\n4, svp_simple_005\n")
    assert bm.parse_cases(["1,002", str(f)]) == frozenset(
        f"svp_simple_{i:03d}_001" for i in range(1, 6))
    with pytest.raises(ValueError):
        bm.parse_cases(["svp_real_001"])


def test_the_bmc4av_subset_is_the_31_cases_minus_the_rww_only_six():
    cases = bm.parse_cases([str(REPO / "bench" / "case-subsets" / "bmc4av-25.txt")])
    assert len(cases) == 25
    rww_only = {f"svp_simple_{i:03d}_001" for i in range(1, 32)
                if {a.pattern for a in case_ground_truth(f"svp_simple_{i:03d}_001").bugs} == {"RWW"}}
    assert rww_only == {f"svp_simple_{i:03d}_001" for i in range(25, 31)}
    assert not cases & rww_only


# ---------------------------------------------------------------------------
# Label sets
# ---------------------------------------------------------------------------


def test_planned_and_unknown_label_sets_are_refused():
    with pytest.raises(bm.LabelSetUnavailable, match="2.2"):
        bm.label_set("2.2")
    with pytest.raises(bm.LabelSetUnavailable, match="unknown"):
        bm.label_set("50/33")
    assert bm.label_set("53/33").native


def test_a_registered_label_set_relabels_by_the_same_match_rule(tmp_path, monkeypatch):
    def no_traps(subject: str) -> CaseGroundTruth | None:
        gt = case_ground_truth(subject)
        return None if gt is None else CaseGroundTruth(gt.case, gt.path, bugs=list(gt.bugs), traps=[])

    monkeypatch.setitem(bm.LABEL_SETS, "test-no-traps", bm.LabelSet("test-no-traps", "bugs only", no_traps))
    rd = bm.load_root(make_root(tmp_path / "root"), "test-no-traps")
    m = {x.view: x for x in bm.run_metrics(rd)}["static only"]
    assert (m.traps_total, m.traps_reported, m.bug_points_total) == (0, 0, 6)
    assert m.unannotated_reported == 3  # 001's trap is now an unannotated candidate
    assert m.labels == "test-no-traps"


# ---------------------------------------------------------------------------
# Several runs
# ---------------------------------------------------------------------------


def test_cohen_kappa():
    assert bm.cohen_kappa([]) is None
    assert bm.cohen_kappa([("a", "a"), ("a", "a")]) is None  # chance agreement is 1
    assert bm.cohen_kappa([("a", "a"), ("b", "b")]) == pytest.approx(1.0)
    assert bm.cohen_kappa([("a", "b"), ("b", "a")]) == pytest.approx(-1.0)
    # 20 items: 15 agree; rater A says yes 10 times, rater B 11 times.
    pairs = [("y", "y")] * 8 + [("n", "n")] * 7 + [("y", "n")] * 2 + [("n", "y")] * 3
    po, pe = 15 / 20, (10 * 11 + 10 * 9) / 400
    assert bm.cohen_kappa(pairs) == pytest.approx((po - pe) / (1 - pe))


def test_agreement_flips_and_spread_over_runs(tmp_path):
    a = bm.load_root(make_root(tmp_path / "a"))
    b = bm.load_root(make_root(tmp_path / "b", trap_bucket="likely_real"))
    c = bm.load_root(make_root(tmp_path / "c"))
    a.run_id, b.run_id, c.run_id = "+racebench/1", "+racebench/2", "+racebench/3"
    ag = {(x.run_a, x.run_b, x.field): x for x in bm.agreement([a, b, c])}
    ab = ag[("+racebench/1", "+racebench/2", "feasibility")]
    assert (ab.n_shared, ab.agreement) == (8, 7 / 8)
    assert ab.kappa == pytest.approx(23 / 31)  # counts 5/2/1 against 6/1/1
    assert ag[("+racebench/1", "+racebench/3", "bucket")].kappa == pytest.approx(1.0)
    fl = bm.flips([a, b, c])
    assert {(f.case, f.item_id, f.field) for f in fl} == {
        ("svp_simple_001_001", "trap#1", "bucket"), ("svp_simple_001_001", "trap#1", "feasibility")}
    assert dict(next(f for f in fl if f.field == "bucket").values)["+racebench/2"] == "likely_real"
    agg = bm.aggregate([m for rd in (a, b, c) for m in bm.run_metrics(rd)])
    s = agg[("+racebench", "likely_real")]["score"]
    assert (s.n, s.mean, s.min, s.max) == (3, pytest.approx((8 + 5 + 8) / 3), 5, 8)
    assert s.sd == pytest.approx(3 ** 0.5)
    assert agg[("+racebench", "static only")]["score"].sd == 0


def test_agreement_skips_candidates_kept_uncertain_after_a_backend_failure(tmp_path):
    a = bm.load_root(make_root(tmp_path / "a"))
    root_b = tmp_path / "b"
    specs = specs_001()
    specs[0]["not_triaged"] = "backend error"
    make_case(root_b, "svp_simple_001_001", specs)
    b = bm.load_root(root_b)
    a.run_id, b.run_id = "r/1", "r/2"
    ab = next(x for x in bm.agreement([a, b]) if x.field == "bucket")
    assert ab.n_shared == 3  # 001 only, minus the untriaged one
    assert {m.view: m for m in bm.run_metrics(b)}["likely_real"].backend_failures == 1


# ---------------------------------------------------------------------------
# Output files and the command
# ---------------------------------------------------------------------------


def _header(path: Path) -> tuple[str, ...]:
    with path.open(encoding="utf-8", newline="") as fh:
        return tuple(next(csv.reader(fh)))


def test_results_directory_has_exactly_the_agreed_schema(tmp_path):
    roots = []
    for k in (1, 2):
        r = make_root(tmp_path / "+racebench" / str(k))
        (r / "batch.json").write_text(json.dumps({"run_id": f"+racebench/{k}", "row": "+racebench",
                                                  "sample": k, "status": "ok"}))
        (r / "freeze.json").write_text(json.dumps({"git_commit": "abc123"}))
        roots.append(bm.load_root(r))
    res = tmp_path / "results"
    bm.write_results(res, roots, bm.Subset(), "53/33", published=bm.load_published())
    assert _header(res / "runs.csv") == bm.RUNS_FIELDS == (
        "run_id", "system", "prompt_row", "sample", "labels", "case_subset", "view", "bug_points_total",
        "bug_points_detected", "traps_total", "traps_reported", "unannotated_reported", "uncertain", "score",
        "score_max", "recall", "precision", "inspection_ratio_mean", "llm_calls", "tokens_in", "tokens_out",
        "backend_failures", "wall_s", "static_s", "llm_s")
    assert _header(res / "patterns.csv") == ("run_id", "labels", "case_subset", "view", "pattern",
                                             "bug_points_total", "bug_points_detected")
    assert _header(res / "items.csv") == ("run_id", "prompt_row", "sample", "case", "item_kind", "item_id",
                                          "triple", "pattern", "fate", "feasibility", "bucket", "confidence")
    assert _header(res / "agreement.csv") == ("prompt_row", "run_a", "run_b", "field", "n_shared",
                                              "agreement", "kappa")
    assert _header(res / "published.csv") == bm.PUBLISHED_FIELDS
    assert _header(res / "cases.csv") == ("run_id", "case", "ir_static", "ir_triage")
    with (res / "cases.csv").open(encoding="utf-8", newline="") as fh:
        cases = {(r["run_id"], r["case"]): r for r in csv.DictReader(fh)}
    assert len(cases) == 4
    one = cases[("+racebench/1", "svp_simple_001_001")]
    ev = {e.stage: e for e in evaluate_run(roots[0].cases[0].store)}
    assert float(one["ir_static"]) == pytest.approx(ev["context"].inspection_ratio)
    assert float(one["ir_triage"]) == pytest.approx(ev["triage"].inspection_ratio)
    assert cases[("+racebench/1", "svp_simple_017_001")]["ir_static"] == ""  # bug 2 missed: undefined
    man = json.loads((res / "manifest.json").read_text(encoding="utf-8"))
    assert {"tool_git_commit", "date", "backend", "prompt_rows", "label_set", "case_subset",
            "input_run_roots", "scorer_version"} <= set(man)
    assert man["tool_git_commit"] == "abc123" and man["prompt_rows"] == ["+racebench"]
    with (res / "runs.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 6
    assert {r["view"] for r in rows} == {"likely_real", "not_infeasible", "static_only"}
    assert {(r["view"], r["system"]) for r in rows} == {
        ("likely_real", "S2"), ("not_infeasible", "S2"), ("static_only", "S1")}
    assert {r["labels"] for r in rows} == {"53/33"}
    s1 = next(r for r in rows if r["view"] == "static_only")
    assert s1["llm_calls"] == "" and s1["sample"] == "1"
    with (res / "patterns.csv").open(encoding="utf-8", newline="") as fh:
        assert {r["view"] for r in csv.DictReader(fh)} == {"likely_real", "not_infeasible", "static_only"}
    with (res / "items.csv").open(encoding="utf-8", newline="") as fh:
        assert {r["fate"] for r in csv.DictReader(fh)} == {"stage1_absent", "stage2", "solver", "llm"}


def test_tokens_come_from_the_spend_line_of_the_case_logs(tmp_path):
    from irqrace.llm.cost import Spend
    from irqrace.llm.backends import Usage

    sp = Spend(spec="fake:m")
    sp.record(Usage(input_tokens=10, output_tokens=5, cache_read_tokens=100, cache_write_tokens=20))
    sp.record(Usage(input_tokens=1, output_tokens=2))
    line = sp.machine_line()
    assert bm.parse_spend("noise\n" + line + "\n") == {
        "requests": 2, "tokens_in": 11, "tokens_out": 7, "cache_read": 100, "cache_write": 20,
        "latency_s": 0.0}
    root = make_root(tmp_path / "root")
    (root / "logs").mkdir()
    (root / "logs" / "svp_simple_001_001.log").write_text(sp.report() + "\n" + line + "\n")
    m = {x.view: x for x in bm.run_metrics(bm.load_root(root))}["likely_real"]
    assert (m.tokens_in, m.tokens_out) == (131, 7)


def test_the_command_refuses_failed_runs_and_never_writes_into_roots(tmp_path, capsys):
    ok = make_root(tmp_path / "ok")
    bad = make_root(tmp_path / "bad")
    (bad / "batch.json").write_text(json.dumps({"run_id": "r/2", "row": "+racebench", "sample": 2,
                                                "status": "failed"}))
    assert _new([str(ok), str(bad), "--results", str(tmp_path / "res")]) == 2
    assert "never mixed in silently" in capsys.readouterr().err
    assert _new([str(ok), str(bad), "--results", str(tmp_path / "res"), "--allow-failed",
                 "--cases", "001", "--exclude-pattern", "rww"]) == 0
    assert not (ok / "report.json").exists() and not (ok / "report.md").exists()
    text = (tmp_path / "res" / "report.md").read_text(encoding="utf-8")
    assert "cases=1;exclude=RWW" in text and "| r/2 | failed |" in text
    assert _new([str(ok), "--labels", "2.2"]) == 2


def test_a_static_root_scores_s1_only(tmp_path):
    rd = bm.load_root(make_root(tmp_path / "root", triaged=False))
    assert all(r["ir_triage"] is None for r in bm.cases_rows(rd, bm.Subset()))
    ms = bm.run_metrics(rd)
    assert [m.view for m in ms] == ["static only"]
    assert bm.agreement([rd, rd]) == [] and bm.flips([rd, rd]) == []
    assert "Trap disposition" in bm.markdown_report([rd], bm.Subset(), "53/33")


# ---------------------------------------------------------------------------
# S0: the published results
# ---------------------------------------------------------------------------


def test_published_results_load_and_every_row_has_a_source():
    rows = bm.load_published()
    assert rows and all(r["source"].strip() for r in rows)
    assert {r["tool"] for r in rows} >= {"NIChecker", "BMC4AV", "IntRace"}
    # The figure script's names, where they apply.
    assert {"recall", "precision", "false_positives", "warnings", "time_s"} <= {r["metric"] for r in rows}
    assert not [r for r in rows if r["metric"].startswith("time") and r["metric"] != "time_s"]
    per_pattern = {r["metric"]: r["value"] for r in rows if r["metric"].startswith("recall_")}
    assert per_pattern == {"recall_RWR": 1.0, "recall_WWR": 1.0, "recall_WRW": 1.0}
    rebased = [r for r in rows if r["rerun_or_copied"] == "rebased"]
    assert any(r["tool"] == "BMC4AV" and r["ground_truth"] == 48 and r["value"] == pytest.approx(38 / 48, abs=1e-3)
               for r in rebased)


def test_published_loader_rejects_a_row_without_a_source(tmp_path):
    bad = tmp_path / "p.yaml"
    shutil.copy(bm.PUBLISHED_YAML, bad)
    text = bad.read_text(encoding="utf-8")
    bad.write_text(text + "\n  - {tool: X, reported_by: Y, cases: 1, ground_truth: 1, defect_class: z,"
                   " metric: m, value: 1, rerun_or_copied: run, hardware: h, source: ''}\n", encoding="utf-8")
    with pytest.raises(bm.PublishedError, match="missing source"):
        bm.load_published(bad)
