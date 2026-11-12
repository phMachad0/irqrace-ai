#!/usr/bin/env python3
"""Score a full-pipeline Racebench run the way the benchmark scores tools.

    python3 scripts/bench-triage-report.py RUN_ROOT [--out report.md]

RUN_ROOT holds one run directory per simple case (as left by
`irqrace pipeline ... --run-root RUN_ROOT`), and optionally `timings.tsv`
(case, start epoch, end epoch, exit code) and `start.txt` / `end.txt`.

**Scoring.** The NASAC 2019 rule for the 31 simple cases: +2 per bug point
detected, -3 per planted false-positive marker ("trap") reported. Denominators
are the project's measured ground truth (2.1_remarks + errata: 53 bug points and
33 traps since the 2026-10-28 relabel, 48 and 38 before), not the competition's
50/33. A detection the suite annotates as
neither bug nor trap is not a false positive, and is listed separately.

**What counts as "reported".** The tool never drops a candidate without a proof,
so "reported" needs a definition; three are scored:

* ``likely_real`` -- the LLM's top bucket is the tool's claim;
* ``not infeasible`` -- everything the LLM did not call infeasible (the
  recall-first reading; `uncertain` stays reported);
* ``static only`` -- everything that reaches the LLM, i.e. stages 1-3 alone.

A bug point counts as detected when its triple is reported; a trap counts as a
false positive when its triple is reported. Matching is the evaluation
harness's own rule (same subject, same ordered access lines).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irqrace.evaluation import RACEBENCH_SIMPLE_BUG_POINTS, RACEBENCH_SIMPLE_TRAPS  # noqa: E402
from irqrace.run_evaluation import candidate_table, case_ground_truth, evaluate_run  # noqa: E402
from irqrace.runstore import RunStore, find_runs  # noqa: E402

BUG, TRAP = 2, -3
VIEWS = {
    "likely_real": lambda r: r["fate"] == "llm" and r["bucket"] == "likely_real",
    "not infeasible": lambda r: r["fate"] == "llm" and r["feasibility"] != "infeasible",
    "static only": lambda r: r["fate"] == "llm",
}
STAGES = ("build", "stage1", "stage2", "solver", "context", "triage")


def llm_calls(run: Path) -> int:
    n = 0
    for turns in (run / "llm").glob("*/turns.jsonl"):
        n += sum(1 for line in turns.read_text(encoding="utf-8").splitlines()
                 if line.strip() and json.loads(line).get("role") == "assistant")
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_root")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.run_root)

    timings: dict[str, tuple[float, float, int]] = {}
    tpath = root / "timings.tsv"
    if tpath.exists():
        for line in tpath.read_text().splitlines():
            c, t0, t1, rc = line.split("\t")
            timings[c] = (float(t0), float(t1), int(rc))

    runs: dict[str, Path] = {}
    for r in find_runs(root):
        m = json.loads((r / "manifest.json").read_text())
        runs[m["subject"]["name"]] = r  # find_runs is sorted: the latest wins

    cases, all_rows = [], []
    for subj, run in sorted(runs.items()):
        store = RunStore(run)
        m = store.read_manifest()
        st = {s["name"]: s for s in m["stages"]}
        rows = candidate_table(store)
        all_rows += rows
        ev = {e.stage: e for e in (evaluate_run(store) or [])}
        wall = timings.get(subj)
        cases.append({
            "subject": subj,
            "run": run.name,
            "llm": m.get("llm"),
            "stage1": st["stage1"].get("candidates_out"),
            "stage2": st["stage2"].get("candidates_out"),
            "context": st["context"].get("candidates_out"),
            "stage_ms": {k: st[k].get("wall_ms") for k in STAGES},
            "triage_status": st["triage"]["status"],
            "wall_s": (wall[1] - wall[0]) if wall else None,
            "exit": wall[2] if wall else None,
            "llm_calls": llm_calls(run),
            "bugs": sum(1 for r in rows if r["gt"] == "bug"),
            "traps": sum(1 for r in rows if r["gt"] == "trap"),
            "ir_static": ev["context"].inspection_ratio if "context" in ev else None,
            "ir_triage": ev["triage"].inspection_ratio if "triage" in ev else None,
            "untriaged": sum(1 for r in rows if r["not_triaged"]),
        })

    bugs = [r for r in all_rows if r["gt"] == "bug"]
    traps = [r for r in all_rows if r["gt"] == "trap"]
    other = [r for r in all_rows if r["gt"] is None and r["fate"] == "llm"]
    # Denominators from the ground truth of the subjects actually in this run.
    gts = [case_ground_truth(c["subject"]) for c in cases]
    n_bugs_gt = sum(len(g.bugs) for g in gts if g)
    n_traps_gt = sum(len(g.traps) for g in gts if g)
    traps_unmatched = n_traps_gt - len(traps)  # traps stage 1 never generated

    scores = {}
    for name, rep in VIEWS.items():
        det = sum(1 for r in bugs if rep(r))
        fp = sum(1 for r in traps if rep(r))
        scores[name] = {"bugs_detected": det, "false_positives": fp,
                        "score": BUG * det + TRAP * fp,
                        "unannotated_reported": sum(1 for r in other if rep(r))}

    t_start = float((root / "start.txt").read_text()) if (root / "start.txt").exists() else None
    t_end = float((root / "end.txt").read_text()) if (root / "end.txt").exists() else None
    walls = [c["wall_s"] for c in cases if c["wall_s"] is not None]
    stage_tot = {k: sum((c["stage_ms"][k] or 0) for c in cases) for k in STAGES}
    irs_s = [c["ir_static"] for c in cases if c["ir_static"] is not None]
    irs_t = [c["ir_triage"] for c in cases if c["ir_triage"] is not None]

    def bucket_counts(sel):
        out: dict[str, int] = {}
        for r in sel:
            k = r["fate"] if r["fate"] != "llm" else (r["bucket"] or "untriaged")
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))

    summary = {
        "run_root": str(root),
        "subjects": len(cases),
        "llm": cases[0]["llm"] if cases else None,
        "ground_truth": {"bug_points": n_bugs_gt, "bug_points_generated": len(bugs),
                         "traps": n_traps_gt, "traps_generated": len(traps),
                         "traps_never_generated": traps_unmatched,
                         "suite_totals": [RACEBENCH_SIMPLE_BUG_POINTS, RACEBENCH_SIMPLE_TRAPS]},
        "funnel": {"stage1": sum(c["stage1"] or 0 for c in cases),
                   "stage2": sum(c["stage2"] or 0 for c in cases),
                   "reach_llm": sum(c["context"] or 0 for c in cases)},
        "bugs_by_outcome": bucket_counts(bugs),
        "traps_by_outcome": bucket_counts(traps),
        "unannotated_by_bucket": bucket_counts(other),
        "scores": scores,
        "max_score": BUG * n_bugs_gt,
        "inspection_ratio_mean": {"static": statistics.mean(irs_s) if irs_s else None,
                                  "triage": statistics.mean(irs_t) if irs_t else None},
        "time": {"total_wall_s": (t_end - t_start) if (t_start and t_end) else None,
                 "sum_case_wall_s": sum(walls), "mean_case_wall_s": statistics.mean(walls) if walls else None,
                 "max_case_wall_s": max(walls) if walls else None,
                 "stage_total_ms": stage_tot,
                 "llm_calls": sum(c["llm_calls"] for c in cases)},
        "untriaged": sum(c["untriaged"] for c in cases),
        "cases": cases,
    }
    (root / "report.json").write_text(json.dumps({"summary": summary, "candidates": all_rows},
                                                 indent=2, ensure_ascii=False))

    f = lambda v, d=2: "-" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))
    out = [f"# Racebench run — {root.name}", "",
           f"Model: `{(summary['llm'] or {}).get('model')}`, prompt row: "
           f"`{(summary['llm'] or {}).get('prompt_config')}`. {len(cases)} subjects.", "",
           "## Score (NASAC 2019 rule: +2 per bug point, −3 per trap reported)", "",
           f"Ground truth of these subjects: {n_bugs_gt} bug points, {n_traps_gt} traps "
           f"({traps_unmatched} never generated by stage 1). Maximum {BUG * n_bugs_gt}. "
           "Detections annotated as neither are not false positives.", "",
           "| reported = | bugs detected | traps reported (FP) | score | unannotated reported |",
           "| --- | --- | --- | --- | --- |"]
    for name, s in scores.items():
        out.append(f"| {name} | {s['bugs_detected']}/{n_bugs_gt} | {s['false_positives']}/"
                   f"{n_traps_gt} | **{s['score']}** | {s['unannotated_reported']} |")
    out += ["", "## Funnel and outcomes", "",
            f"- Candidates: stage 1 {summary['funnel']['stage1']} → stage 2 {summary['funnel']['stage2']} "
            f"→ reach the LLM {summary['funnel']['reach_llm']}.",
            f"- Bug points: {summary['bugs_by_outcome']}",
            f"- Traps (generated): {summary['traps_by_outcome']}",
            f"- Unannotated reaching the LLM: {summary['unannotated_by_bucket']}",
            f"- Not triaged (backend failures, kept as uncertain): {summary['untriaged']}",
            f"- Mean Inspection Ratio: before triage {f(summary['inspection_ratio_mean']['static'])}, "
            f"after triage {f(summary['inspection_ratio_mean']['triage'])}.",
            "", "## Time", "",
            f"- Total wall clock (4 cases in parallel): {f(summary['time']['total_wall_s'], 0)} s; "
            f"sum of per-case wall times {f(summary['time']['sum_case_wall_s'], 0)} s; "
            f"mean per case {f(summary['time']['mean_case_wall_s'], 0)} s, slowest "
            f"{f(summary['time']['max_case_wall_s'], 0)} s.",
            f"- LLM calls: {summary['time']['llm_calls']}.",
            "- Stage totals (ms): " + ", ".join(f"{k} {v}" for k, v in stage_tot.items()) + ".",
            "", "## Per case", "",
            "| case | s1 → s2 → LLM | bugs | traps | calls | wall (s) | build | stage1 | stage2 | solver | triage (ms) | IR before → after |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in cases:
        sm = c["stage_ms"]
        out.append(f"| {c['subject'][11:14]} | {c['stage1']} → {c['stage2']} → {c['context']} | {c['bugs']} | "
                   f"{c['traps']} | {c['llm_calls']} | {f(c['wall_s'], 0)} | {sm['build']} | {sm['stage1']} | "
                   f"{sm['stage2']} | {sm['solver']} | {sm['triage']} | {f(c['ir_static'])} → {f(c['ir_triage'])} |")
    out += ["", "## Every bug point and trap", "",
            "| case | GT | lines | fate | feasibility (conf) | bucket |", "| --- | --- | --- | --- | --- | --- |"]
    for r in sorted(bugs + traps, key=lambda r: (r["subject"], r["gt"], r["gt_index"] or 0)):
        feas = "-" if r["feasibility"] is None else f"{r['feasibility']} ({f(r['feasibility_confidence'])})"
        out.append(f"| {r['subject'][11:14]} | {r['gt']} #{r['gt_index']} | {tuple(r['lines'])} | {r['fate']} | "
                   f"{feas} | {r['bucket'] or '-'} |")
    text = "\n".join(out) + "\n"
    (Path(args.out) if args.out else root / "report.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
