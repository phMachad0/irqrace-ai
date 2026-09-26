#!/usr/bin/env python3
"""Render ablation results as the table milestone M3 is.

    python3 scripts/ablation-table.py ablation-groq.json
    python3 scripts/ablation-table.py ablation-groq.json ablation-opus.json

Takes the JSON written by ``run-ablation.py`` and prints a markdown table in
[[LLift (paper)]]'s shape. Separate from the runner on purpose: re-rendering
must not re-run, and **several result files become several column groups**, so
the same prompt configurations measured on different models sit side by side.
That comparison is the point — LLift's claim is that prompt architecture
dominates model choice, and one model cannot test it.

## What the columns are, and why recall is not the headline here

LLift's ablation moves recall from 0.15 to 1.00 and recall is its story. On
this benchmark the simple-prompt baseline already scores 1.00, so a flat recall
column is expected and is itself the finding. **Inspection Ratio and trap
rejection are the dependent variables**; recall is a gate that must not break,
printed so a break is visible.

Every cell carries what produced it. A row served by prompted JSON is not
comparable with one served by an enforced schema, and a backend without prompt
caching is not comparable on cost — so both travel with the table rather than
in a footnote nobody reads.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROW_ORDER = ["simple", "+domain", "+progressive", "+decomposition", "+self-validation"]


def pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.1%}"


def _coverage(row: dict) -> tuple[int, int]:
    """(scored, expected) for a row, derived from older files if need be."""
    if "n_expected" in row:
        return row.get("n_scored", 0), row["n_expected"]
    # Results written before coverage was recorded still carry the exclusions.
    excluded = len(row.get("excluded", []))
    counted = sum(row.get("buckets", {}).values())
    return counted, counted + excluded


def load(paths: list[Path]) -> dict[str, dict[str, dict]]:
    """backend spec -> row name -> result."""
    out: dict[str, dict[str, dict]] = {}
    for path in paths:
        for row in json.loads(path.read_text(encoding="utf-8")):
            out.setdefault(row["backend"], {})[row["row"]] = row
    return out


def render(by_backend: dict[str, dict[str, dict]]) -> str:
    backends = list(by_backend)
    rows = [r for r in ROW_ORDER if any(r in b for b in by_backend.values())]

    lines: list[str] = []
    header = ["prompt configuration"]
    for spec in backends:
        header += [f"{spec} recall", "trap rej.", "insp. ratio"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")

    for name in rows:
        cells = [f"`{name}`"]
        for spec in backends:
            r = by_backend[spec].get(name)
            if r is None:
                cells += ["—", "—", "—"]
                continue
            # An incomplete row's figures describe whichever candidates
            # survived, which is not a sample of anything. Showing them as
            # ordinary cells is how "100% / 100% / 100%" over three of twenty
            # candidates ends up quoted, so they are struck out instead.
            scored, expected = _coverage(r)
            if expected and scored < expected:
                cells += [f"_{scored}/{expected} scored_", "—", "—"]
                continue
            gate = "" if r.get("gate_passed", r["recall"] == 1.0) else " ⚠"
            cells += [
                f"{pct(r['recall'])}{gate}",
                pct(r["trap_rejection"]),
                pct(r["inspection_ratio"]),
            ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    for spec in backends:
        results = by_backend[spec]
        any_row = next(iter(results.values()))
        lines.append(f"**{spec}**")
        for caveat in any_row.get("caveats", []):
            lines.append(f"- {caveat}")
        costs = [r["cost_usd"] for r in results.values() if r.get("cost_usd")]
        lines.append(
            f"- cost: ${sum(costs):.2f} across {len(results)} rows"
            if costs
            else "- cost: unpriced backend; tokens only"
        )
        misses = {
            name: r["missed"] for name, r in results.items() if r.get("missed")
        }
        if misses:
            lines.append(f"- **recall gate broken**: {misses}")
        benign = {
            name: r["bug_points_bucketed_benign"]
            for name, r in results.items()
            if r.get("bug_points_bucketed_benign")
        }
        if benign:
            lines.append(
                "- bug points bucketed `likely_benign` (passes the gate, sinks "
                f"the Inspection Ratio): {benign}"
            )
        excluded = {
            name: len(r["excluded"]) for name, r in results.items() if r.get("excluded")
        }
        if excluded:
            lines.append(f"- excluded, not scored: {excluded}")
        violations = {
            name: len(r["protocol_violations"])
            for name, r in results.items()
            if r.get("protocol_violations")
        }
        if violations:
            lines.append(f"- protocol violations: {violations}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, help="write the table here as well")
    args = ap.parse_args()

    missing = [p for p in args.results if not p.exists()]
    if missing:
        print(f"no such file: {', '.join(map(str, missing))}", file=sys.stderr)
        return 2

    table = render(load(args.results))
    print(table)
    if args.out:
        args.out.write_text(table + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
