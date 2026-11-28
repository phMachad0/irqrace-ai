#!/usr/bin/env python3
"""Score Racebench run roots the way the benchmark scores tools.

    python3 scripts/bench-triage-report.py RUN_ROOT [--out report.md]
    python3 scripts/bench-triage-report.py ROOT [ROOT ...] --results DIR
        [--cases LIST|FILE ...] [--exclude-pattern RWW] [--labels 53/33]
        [--subset-name NAME] [--allow-failed] [--out report.md]

RUN_ROOT holds one run directory per simple case (as left by
`irqrace pipeline ... --run-root RUN_ROOT` or `scripts/freeze-and-triage.py`),
and optionally `timings.tsv` (case, start epoch, end epoch, exit code),
`start.txt` / `end.txt`, per-case logs in `logs/`, `batch.json`, `freeze.json`.

**Two modes.** With one root and none of the options below, the script writes
`report.json` and `report.md` into the root exactly as it always has (the
legacy report; a test holds it byte-identical to the version before the
extension). With several roots, a filter, or `--results`, it writes the
multi-run report -- per-run scores, recall per access pattern, mean ± sample
standard deviation over runs of one prompt row, Cohen's κ between runs, the
labelled items that flip -- to `--out` (default `DIR/report.md`) and the CSVs
and `manifest.json` to `--results DIR`. That mode never writes into a run root.

**Scoring.** The NASAC 2019 rule for the 31 simple cases: +2 per bug point
detected, -3 per planted false-positive marker ("trap") reported. Denominators
are the project's measured ground truth (2.1_remarks + errata: 53 bug points and
33 traps since the 2026-10-28 relabel, 48 and 38 before), not the competition's
50/33. A detection the suite annotates as neither bug nor trap is not a false
positive, and is listed separately.

**What counts as "reported".** The tool never drops a candidate without a proof,
so "reported" needs a definition; three are scored:

* ``likely_real`` -- the LLM's top bucket is the tool's claim;
* ``not infeasible`` -- everything the LLM did not call infeasible (the
  recall-first reading; `uncertain` stays reported);
* ``static only`` -- everything that reaches the LLM, i.e. stages 1-3 alone.

A bug point counts as detected when its triple is reported; a trap counts as a
false positive when its triple is reported. Matching is the evaluation
harness's own rule (same subject, same ordered access lines).

**Filters** (`--cases`, `--exclude-pattern`) restrict the denominators too:
that is how a run is compared with BMC4AV on its 25 cases without `(R,W,W)`
(`--cases bench/case-subsets/bmc4av-25.txt --exclude-pattern RWW`). The logic
lives in `irqrace.bench_metrics`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irqrace import bench_metrics as bm  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score Racebench run roots (NASAC 2019 rule).")
    ap.add_argument("run_root", nargs="+", help="one or more run roots")
    ap.add_argument("--out", default=None, help="the Markdown report")
    ap.add_argument("--results", default=None, help="directory for runs/patterns/items/agreement CSVs")
    ap.add_argument("--cases", action="append", default=None,
                    help="cases to keep: a comma-separated list or a file (repeatable)")
    ap.add_argument("--exclude-pattern", action="append", default=[], metavar="PATTERN",
                    help="drop every item of this access pattern, e.g. RWW (repeatable)")
    ap.add_argument("--subset-name", default=None, help="name recorded for the case subset")
    ap.add_argument("--labels", default=bm.DEFAULT_LABELS,
                    help=f"label set: {', '.join(bm.LABEL_SETS)} (planned: {', '.join(bm.PLANNED_LABEL_SETS)})")
    ap.add_argument("--published", default=str(bm.PUBLISHED_YAML),
                    help="S0 dataset written to published.csv ('' to skip)")
    ap.add_argument("--allow-failed", action="store_true",
                    help="score runs whose batch.json says failed (they are listed as such)")
    args = ap.parse_args(argv)

    try:
        labels = bm.label_set(args.labels)
    except bm.LabelSetUnavailable as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    patterns = frozenset(p.upper() for p in args.exclude_pattern)
    subset = bm.Subset(cases=bm.parse_cases(args.cases) if args.cases else None,
                       exclude_patterns=patterns, name=args.subset_name)
    roots = [Path(r) for r in args.run_root]

    legacy = (len(roots) == 1 and not subset.filtered and args.results is None
              and labels.name == bm.DEFAULT_LABELS)
    if legacy:
        root = roots[0]
        doc, text = bm.legacy_report(bm.load_root(root, labels))
        (root / "report.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False))
        (Path(args.out) if args.out else root / "report.md").write_text(text, encoding="utf-8")
        print(text)
        return 0

    data = [bm.load_root(r, labels) for r in roots]
    failed = [rd for rd in data if rd.status == "failed"]
    if failed and not args.allow_failed:
        print("error: failed runs are never mixed in silently: "
              + ", ".join(f"{rd.run_id} ({rd.root})" for rd in failed)
              + ". Re-run them, or pass --allow-failed.", file=sys.stderr)
        return 2
    ids = [rd.run_id for rd in data]
    for rd in data:  # run ids key every CSV: make them unique
        if ids.count(rd.run_id) > 1:
            rd.run_id = f"{rd.run_id}@{rd.root.name}"
    if subset.cases is not None:
        present = {c.subject for rd in data for c in rd.cases}
        if missing := sorted(subset.cases - present):
            print(f"warning: {len(missing)} selected case(s) in no run root: {', '.join(missing)}",
                  file=sys.stderr)

    text = bm.markdown_report(data, subset, labels.name)
    if args.results:
        res = Path(args.results)
        published = bm.load_published(args.published) if args.published else None
        bm.write_results(res, data, subset, labels.name, published=published)
        out = Path(args.out) if args.out else res / "report.md"
    else:
        out = Path(args.out) if args.out else None
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
