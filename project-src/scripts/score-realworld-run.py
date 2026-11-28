#!/usr/bin/env python3
"""Score an irqrace run on the 18 real-world programs, per violation.info entry.

    python scripts/score-realworld-run.py ROOT [ROOT ...]

``ROOT`` is a run root (``irqrace realworld run --run-root``) or a triaged pair
(``OUT/<row>/<k>``) whose case runs are ``<program>-*``; the ``__bmc4av-prio`` side
configurations are skipped. Matching is :func:`irqrace.realworld.match` with the
line errata applied, the unit of the recall gate: an entry is found when a
candidate has its variable and pattern (and its lines, for an instance entry).
With ``llm/triage.jsonl`` present, an entry counts as found in ``likely_real``
when one of its matching candidates is there, and as called infeasible when every
matching candidate is ``likely_infeasible``. Prints one JSON summary per root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irqrace.realworld import load_errata, match, parse_violation_info  # noqa: E402

SUITE = ROOT / "bench" / "realworld"


def score(root: Path) -> dict:
    errata = load_errata()
    out = {"root": str(root), "bugs": 0, "bugs_static": 0, "bugs_likely_real": 0, "bugs_infeasible": 0,
           "traps": 0, "traps_static": 0, "traps_likely_real": 0, "candidates": 0, "likely_real": 0,
           "unannotated_likely_real": 0, "not_triaged": 0, "triaged": False,
           "bugs_not_likely_real": [], "traps_reported": [], "missed_static": []}
    for run in sorted(p for p in root.iterdir() if p.is_dir() and "-" in p.name and "__" not in p.name):
        prog = run.name.rsplit("-", 2)[0]
        if not (SUITE / prog / "violation.info").exists():
            continue
        entries, _ = parse_violation_info(SUITE / prog / "violation.info", prog, errata)
        records = [json.loads(f.read_text()) for f in sorted((run / "context").glob("*.json"))]
        buckets: dict[str, dict] = {}
        tj = run / "llm" / "triage.jsonl"
        if tj.exists():
            out["triaged"] = True
            for line in tj.read_text().splitlines():
                if line.strip():
                    v = json.loads(line)
                    buckets[v["candidate_id"]] = v
        out["candidates"] += len(records)
        real = [r for r in records if buckets.get(r["id"], {}).get("bucket") == "likely_real"]
        out["likely_real"] += len(real)
        out["not_triaged"] += sum(bool(v.get("not_triaged")) for v in buckets.values())
        static = match(entries, records)
        top = {m.entry.index: m for m in match(entries, real)}
        used = set()
        for m in static:
            key = "bugs" if m.entry.label == "bug" else "traps"
            out[key] += 1
            tag = f"{prog} #{m.entry.index} {m.entry.raw}"
            if not m.found:
                if key == "bugs":
                    out["missed_static"].append(tag)
                continue
            out[f"{key}_static"] += 1
            if top[m.entry.index].found:
                out[f"{key}_likely_real"] += 1
                used |= set(top[m.entry.index].candidates)
                if key == "traps":
                    out["traps_reported"].append(tag)
            elif key == "bugs" and buckets:
                bs = sorted({buckets.get(c, {}).get("bucket") for c in m.candidates} - {None})
                out["bugs_not_likely_real"].append(f"{tag}: {', '.join(bs)}")
                if bs == ["likely_infeasible"]:
                    out["bugs_infeasible"] += 1
        matched_any = {c for m in match(entries, real) for c in m.candidates}
        out["unannotated_likely_real"] += sum(1 for r in real if r["id"] not in matched_any)
    return out


def main() -> int:
    for r in sys.argv[1:]:
        print(json.dumps(score(Path(r)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
