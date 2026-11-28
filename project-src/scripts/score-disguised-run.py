#!/usr/bin/env python3
"""Score an irqrace run on a disguised Racebench copy against the original annotations.

    python scripts/score-disguised-run.py --copy DISGUISED_DIR ROOT [ROOT ...] [--labels 53/33|48/38]

``ROOT`` is a frozen root or a triaged pair (``OUT/<row>/<k>``) whose case runs are
``program_NN-*``. Each context record's access lines are mapped back through the
copy's ``line_map`` and matched with :func:`irqrace.evaluation.match_subject`, the
matcher the native scorer uses. With ``llm/triage.jsonl`` present, the bucket of
each matched candidate is read too. Prints one JSON summary per root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irqrace.bench_metrics import label_set  # noqa: E402
from irqrace.evaluation import match_subject  # noqa: E402


def score(root: Path, copy: Path, labels: str) -> dict:
    ls = label_set(labels)
    out = {"root": str(root), "labels": labels, "bugs": 0, "bugs_static": 0, "bugs_likely_real": 0,
           "bugs_infeasible": 0, "traps": 0, "traps_static": 0, "traps_likely_real": 0,
           "candidates": 0, "unannotated_likely_real": 0, "not_triaged": 0, "triaged": False,
           "missed_static": [], "traps_reported": [], "bugs_not_likely_real": []}
    for run in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("program_")):
        program = run.name.split("-", 1)[0]
        meta = json.loads((copy / f"{program}.json").read_text())
        case, lmap = meta["case"], meta["line_map"]
        records = [json.loads(f.read_text()) for f in sorted((run / "context").glob("*.json"))]
        buckets: dict[str, dict] = {}
        tj = run / "llm" / "triage.jsonl"
        if tj.exists():
            out["triaged"] = True
            for line in tj.read_text().splitlines():
                if line.strip():
                    v = json.loads(line)
                    buckets[v["candidate_id"]] = v
        for r in records:
            for a in r["accesses"]:
                a["source"] = {**a["source"], "line": lmap.get(str(a["source"]["line"]), -a["source"]["line"]),
                               "file": f"{case}.c"}
        gt = ls.ground_truth(case)
        rep = match_subject([*gt.bugs, *gt.traps], records, subject=case)
        out["candidates"] += len(records)
        matched = set()
        for m in rep.bug_matches:
            out["bugs"] += 1
            tag = f"{case[11:14]} bug#{m.annotation.index} {m.annotation.pattern}{m.annotation.lines}"
            if not m.detected:
                out["missed_static"].append(tag)
                continue
            out["bugs_static"] += 1
            matched.add(m.candidate_id)
            b = buckets.get(m.candidate_id, {}).get("bucket")
            if b == "likely_real":
                out["bugs_likely_real"] += 1
            elif buckets:
                out["bugs_not_likely_real"].append(f"{tag}: {b}")
            if b == "likely_infeasible":
                out["bugs_infeasible"] += 1
        for m in rep.trap_matches:
            out["traps"] += 1
            if m.detected:
                out["traps_static"] += 1
                matched.add(m.candidate_id)
                if buckets.get(m.candidate_id, {}).get("bucket") == "likely_real":
                    out["traps_likely_real"] += 1
                    out["traps_reported"].append(f"{case[11:14]} trap#{m.annotation.index} {m.annotation.pattern}{m.annotation.lines}")
        for cid, v in buckets.items():
            out["not_triaged"] += bool(v.get("not_triaged"))
            if cid not in matched and v.get("bucket") == "likely_real":
                out["unannotated_likely_real"] += 1
    out["nasac_static"] = 2 * out["bugs_static"] - 3 * out["traps_static"]
    if out["triaged"]:
        out["nasac_likely_real"] = 2 * out["bugs_likely_real"] - 3 * out["traps_likely_real"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--copy", required=True)
    ap.add_argument("--labels", default="53/33")
    ap.add_argument("roots", nargs="+")
    args = ap.parse_args()
    for r in args.roots:
        print(json.dumps(score(Path(r), Path(args.copy), args.labels), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
