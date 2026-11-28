#!/usr/bin/env python3
"""Compare triage variants scored by bench-triage-report.py: quality, tokens, time.

    python scripts/compare-speed-variants.py --baseline NAME RESULTS_DIR/NAME ... > summary.md

Each argument is a ``--results`` directory of ``bench-triage-report.py`` for one
variant (its basename is the variant's name), whose pair directory is recorded
in its ``manifest.json``. Reads ``runs.csv`` (view ``likely_real``),
``items.csv``, and the pair's ``logs/*.log`` spend lines for the call latencies.
Agreement is per annotated item (bug point or trap), bucket against bucket; it
assumes one run per results directory (n = 1 per variant).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irqrace.bench_metrics import parse_spend  # noqa: E402


def load(results: Path) -> dict:
    run = next(r for r in csv.DictReader(open(results / "runs.csv")) if r["view"] == "likely_real")
    items = {(r["case"], r["item_id"]): r for r in csv.DictReader(open(results / "items.csv"))
             if r["item_kind"] in ("bug", "trap")}
    manifest = json.loads((results / "manifest.json").read_text())
    roots = [r["path"] for r in manifest.get("input_run_roots", [])]
    lat = 0.0
    for root in roots:
        for log in Path(root).glob("logs/*.log"):
            lat += (parse_spend(log.read_text(errors="replace")) or {}).get("latency_s", 0.0)
    return {"run": run, "items": items, "latency": lat}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True)
    ap.add_argument("results", nargs="+")
    args = ap.parse_args()
    data = {Path(p).name: load(Path(p)) for p in args.results}
    base = data[args.baseline]
    names = list(data)

    rows = [
        ("Bug points in `likely_real`", lambda d: f"{d['run']['bug_points_detected']}/{d['run']['bug_points_total']}"),
        ("Bug points called infeasible", lambda d: str(sum(1 for i in d["items"].values()
                                                           if i["item_kind"] == "bug" and i["bucket"] == "likely_infeasible"))),
        ("Traps in `likely_real`", lambda d: d["run"]["traps_reported"]),
        ("Uncertain (not triaged)", lambda d: d["run"]["backend_failures"] or "0"),
        ("NASAC score /106", lambda d: d["run"]["score"]),
        ("Inspection Ratio", lambda d: f"{float(d['run']['inspection_ratio_mean']):.2f}"),
        ("Calls", lambda d: d["run"]["llm_calls"]),
        ("Input tokens (incl. cache)", lambda d: f"{int(d['run']['tokens_in']):,}"),
        ("Output tokens", lambda d: f"{int(d['run']['tokens_out']):,}"),
        ("Sum of call latencies (s)", lambda d: f"{d['latency']:,.0f}"),
        ("Wall time, triage (s)", lambda d: f"{float(d['run']['wall_s']):,.0f}"),
        ("Mean concurrency", lambda d: f"{d['latency'] / float(d['run']['wall_s']):.2f}"),
        ("Items with the baseline's bucket", lambda d: f"{sum(1 for k, i in d['items'].items() if base['items'].get(k, {}).get('bucket') == i['bucket'])}/{len(d['items'])}"),
    ]
    print("| | " + " | ".join(f"`{n}`" for n in names) + " |")
    print("| --- |" + " --- |" * len(names))
    for label, f in rows:
        print(f"| {label} | " + " | ".join(f(data[n]) for n in names) + " |")
    print()
    for n in names:
        if n == args.baseline:
            continue
        diff = [(k, base["items"][k]["bucket"], i["bucket"]) for k, i in sorted(data[n]["items"].items())
                if k in base["items"] and base["items"][k]["bucket"] != i["bucket"]]
        print(f"**`{n}` vs `{args.baseline}`: {len(diff)} annotated item(s) changed bucket.**")
        for (case, item), b, v in diff:
            kind = data[n]["items"][(case, item)]["item_kind"]
            print(f"- {case} {item} ({kind}, {data[n]['items'][(case, item)]['triple']}): {b} -> {v}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
