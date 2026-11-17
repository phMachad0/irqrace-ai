#!/usr/bin/env python3
"""Compare prompt variants against a baseline row, item by item (T3).

    python scripts/prompt-variant-report.py RESULTS_DIR --base +racebench \\
        --runs-root runs/m1-20261115 --runs-root runs/m3-20261117 [--out RESULTS_DIR/variants.md]

RESULTS_DIR is what ``bench-triage-report.py ... --results RESULTS_DIR`` wrote over
the baseline runs and the variant runs together (``runs.csv``, ``items.csv``).
This script adds what that report cannot: each variant set against the
baseline, item by item, and the metrics that belong to one variant.

**Per variant** (``likely_real`` reading, 53/33, all cases):

- the scores of ``runs.csv`` with the difference to the baseline's mean, and
  whether the variant falls outside the baseline's observed [min, max];
- the **recall veto**: every bug point whose bucket is not ``likely_real``, by
  name (``likely_infeasible`` is a recall loss; ``uncertain`` and
  ``likely_benign`` leave the headline bucket);
- every labelled item (bug point or trap) whose bucket differs from the
  baseline's, and the count of unannotated candidates that moved, per
  transition;
- Cohen's kappa on the bucket between the variant and each baseline run, next
  to the baseline's own run-to-run kappa, so a variant is read against the
  baseline's noise;
- from each case's ``llm/triage.jsonl``: the distribution of feasibility
  confidences (distinct values, the share on 0.85/0.90), the share of answers
  carrying the variant's heading (``Rubric:``, ``Witness:``) and the reasoning
  length.

A single variant run is compared with every baseline run. With n = 1, a
difference inside the baseline's own spread is not read as an effect; the
report says which differences are outside it.

Writes ``variants.md``, ``variants.csv`` (one row per variant and metric) and
``item_changes.csv`` (one row per changed item).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

METRICS = [  # runs.csv column, label, higher is better (None: no direction)
    ("score", "NASAC score /106", True),
    ("bug_points_detected", "bug points (of 53)", True),
    ("traps_reported", "traps reported (of 33)", False),
    ("precision", "precision", True),
    ("inspection_ratio_mean", "Inspection Ratio", False),
    ("unannotated_reported", "unannotated in likely_real", None),
    ("uncertain", "uncertain", None),
    ("llm_calls", "LLM calls", False),
    ("tokens_in", "input tokens", False),
    ("tokens_out", "output tokens", False),
    ("llm_s", "LLM time (s)", False),
]
HEADINGS = {"rubric": "Rubric:", "witness": "Witness:", "location": "Location:"}


def num(x: str | None) -> float | None:
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def fmt(v: float | None, col: str) -> str:
    if v is None:
        return "–"
    if col in ("precision", "inspection_ratio_mean"):
        return f"{v:.3f}"
    if col in ("tokens_in", "tokens_out"):
        return f"{v / 1e6:.2f} M"
    if col == "llm_s":
        return f"{v:.0f}"
    return f"{v:.4g}"


def load_runs(results: Path) -> dict[str, dict]:
    out = {}
    for r in csv.DictReader(open(results / "runs.csv", encoding="utf-8")):
        if r["system"] == "S2" and r["view"] == "likely_real" and r["labels"] == "53/33" and r["case_subset"] == "all":
            out[r["run_id"]] = r
    return out


def load_items(results: Path) -> dict[str, dict[tuple, dict]]:
    out: dict[str, dict[tuple, dict]] = defaultdict(dict)
    for r in csv.DictReader(open(results / "items.csv", encoding="utf-8")):
        if r["fate"] == "llm":
            out[r["run_id"]][(r["case"], r["item_kind"], r["item_id"])] = r
    return out


def find_run_dir(roots: list[Path], run_id: str) -> Path | None:
    row, _, k = run_id.rpartition("/")
    for root in roots:
        d = root / row / k
        if d.is_dir():
            return d
    return None


def triage_stats(run_dir: Path | None, row: str) -> dict:
    if run_dir is None:
        return {}
    confs, lens, n, heads = [], [], 0, Counter()
    feasible, feasible_with_witness = 0, 0
    for f in run_dir.glob("*/llm/triage.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            fe, ha = rec.get("feasibility") or {}, rec.get("harmfulness") or {}
            if not fe:
                continue
            n += 1
            if fe.get("confidence") is not None:
                confs.append(round(float(fe["confidence"]), 2))
            text = (fe.get("reasoning") or "") + "\n" + (ha.get("reasoning") or "")
            lens.append(len(fe.get("reasoning") or ""))
            for name, h in HEADINGS.items():
                if h in text:
                    heads[name] += 1
            if fe.get("verdict") == "feasible":
                feasible += 1
                feasible_with_witness += "Witness:" in (fe.get("reasoning") or "")
    c = Counter(confs)
    return {
        "answers": n,
        "distinct_conf": len(c),
        "top_conf": ", ".join(f"{v:g}×{k}" for v, k in sorted(c.items(), key=lambda kv: -kv[1])[:5]),
        "share_085_090": (c[0.85] + c[0.9]) / len(confs) if confs else None,
        "mean_reasoning_chars": statistics.mean(lens) if lens else None,
        "rubric_share": heads["rubric"] / n if n else None,
        "witness_share_of_feasible": feasible_with_witness / feasible if feasible else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("results", type=Path)
    ap.add_argument("--base", default="+racebench")
    ap.add_argument("--runs-root", action="append", type=Path, default=[])
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    runs, items = load_runs(args.results), load_items(args.results)
    base_ids = sorted(r for r, d in runs.items() if d["prompt_row"] == args.base)
    var_ids = sorted(r for r, d in runs.items() if d["prompt_row"] != args.base
                     and d["prompt_row"].startswith(args.base))
    if not base_ids or not var_ids:
        raise SystemExit(f"need baseline ({args.base}) and variant runs in {args.results}/runs.csv")

    # the baseline's modal bucket per item, and whether its runs agree
    keys = set().union(*(items[r].keys() for r in base_ids))
    modal, stable = {}, {}
    for k in keys:
        bs = [items[r][k]["bucket"] for r in base_ids if k in items[r]]
        modal[k] = Counter(bs).most_common(1)[0][0]
        stable[k] = len(set(bs)) == 1 and len(bs) == len(base_ids)

    base_kappas = []
    for a, b in combinations(base_ids, 2):
        shared = sorted(set(items[a]) & set(items[b]))
        base_kappas.append(kappa([items[a][k]["bucket"] for k in shared], [items[b][k]["bucket"] for k in shared]))

    csv_rows, change_rows, md = [], [], []
    md.append(f"# Prompt variants against `{args.base}` (T3)\n")
    md.append(f"Baseline: `{args.base}`, runs {', '.join(base_ids)}. Variants: n = 1 each. "
              "Reading: `likely_real`, labels 53/33, all 31 cases. A difference is called *outside the "
              "baseline's noise* only when the variant falls outside the [min, max] its baseline runs span.\n")

    # --- headline table
    md.append("## Metrics\n")
    head = "| metric | " + f"`{args.base}` mean [min–max]" + " | " + " | ".join(f"`{v}`" for v in var_ids) + " |"
    md.append(head)
    md.append("| --- | --- | " + " | ".join("---" for _ in var_ids) + " |")
    for col, label, better in METRICS:
        bv = [num(runs[r][col]) for r in base_ids if num(runs[r][col]) is not None]
        if not bv:
            continue
        bmean, bmin, bmax = statistics.mean(bv), min(bv), max(bv)
        cells = []
        for v in var_ids:
            x = num(runs[v][col])
            if x is None:
                cells.append("–")
                continue
            d = x - bmean
            outside = x < bmin or x > bmax
            mark = ""
            if outside and better is not None and d != 0:
                mark = " ▲" if (d > 0) == better else " ▼"
            dtxt = (f"{d:+.3f}" if col in ("precision", "inspection_ratio_mean")
                    else f"{d / 1e6:+.2f} M" if col.startswith("tokens") else f"{d:+.0f}")
            cells.append(f"{fmt(x, col)} ({dtxt}){mark}{' *' if outside else ''}")
            csv_rows.append({"variant": runs[v]["prompt_row"], "metric": col, "value": x,
                             "base_mean": bmean, "base_min": bmin, "base_max": bmax,
                             "delta": d, "outside_base_range": outside})
        md.append(f"| {label} | {fmt(bmean, col)} [{fmt(bmin, col)}–{fmt(bmax, col)}] | " + " | ".join(cells) + " |")
    md.append("\n`*` outside the baseline's [min–max]; ▲ better, ▼ worse, only when outside it.\n")

    # --- agreement
    md.append("## Agreement with the baseline (Cohen's κ on the bucket)\n")
    md.append(f"Baseline run-to-run κ: {', '.join(f'{k:.3f}' for k in base_kappas if k is not None)}.\n")
    md.append("| variant | κ vs each baseline run | mean | items compared |")
    md.append("| --- | --- | --- | --- |")
    for v in var_ids:
        ks, n = [], 0
        for b in base_ids:
            shared = sorted(set(items[v]) & set(items[b]))
            n = len(shared)
            ks.append(kappa([items[v][k]["bucket"] for k in shared], [items[b][k]["bucket"] for k in shared]))
        md.append(f"| `{v}` | {', '.join(f'{k:.3f}' for k in ks)} | "
                  f"{statistics.mean(ks):.3f} | {n} |")
        csv_rows.append({"variant": runs[v]["prompt_row"], "metric": "kappa_vs_base_mean",
                         "value": statistics.mean(ks), "base_mean": statistics.mean([k for k in base_kappas if k is not None]),
                         "base_min": min(base_kappas), "base_max": max(base_kappas), "delta": None,
                         "outside_base_range": statistics.mean(ks) < min(base_kappas)})
    md.append("")

    # --- recall veto and labelled changes
    md.append("## Recall veto and labelled items that moved\n")
    for v in var_ids:
        row = runs[v]["prompt_row"]
        vit = items[v]
        bugs_out = sorted(k for k, r in vit.items() if k[1] == "bug" and r["bucket"] != "likely_real")
        veto = [k for k in bugs_out if vit[k]["bucket"] == "likely_infeasible"]
        md.append(f"### `{row}`\n")
        md.append(f"- **Recall veto:** {'**FIRED**: ' + ', '.join(f'{c[11:14]} {i} {vit[(c, kd, i)]['triple']}' for c, kd, i in veto) if veto else 'not fired'} "
                  f"(bug points in `likely_infeasible`: {len(veto)}).")
        if bugs_out:
            md.append(f"- Bug points outside `likely_real`: " + "; ".join(
                f"{c[11:14]} {i} `{vit[(c, kd, i)]['triple']}` → {vit[(c, kd, i)]['bucket']}" for c, kd, i in bugs_out) + ".")
        moved = Counter()
        lab_lines = []
        for k, r in sorted(vit.items()):
            if k not in modal or r["bucket"] == modal[k]:
                continue
            moved[(k[1], modal[k], r["bucket"])] += 1
            change_rows.append({"variant": row, "case": k[0], "item_kind": k[1], "item_id": k[2],
                                "triple": r["triple"], "pattern": r["pattern"], "base_bucket": modal[k],
                                "base_stable": stable[k], "variant_bucket": r["bucket"],
                                "variant_confidence": r["confidence"]})
            if k[1] in ("bug", "trap"):
                lab_lines.append(f"  - {k[1]} {k[0][11:14]} {k[2]} `{r['triple']}`: {modal[k]} → **{r['bucket']}**"
                                 + ("" if stable[k] else " (baseline itself unstable)"))
        md.append("- Labelled items whose bucket differs from the baseline's:" + ("" if lab_lines else " none."))
        md.extend(lab_lines)
        if moved:
            md.append("- All moves, by kind: " + "; ".join(f"{kd} {a} → {b}: {n}" for (kd, a, b), n in sorted(moved.items())) + ".")
        md.append("")

    # --- variant-specific
    md.append("## Answer-level metrics (from each case's `llm/triage.jsonl`)\n")
    md.append("| row | answers | distinct feasibility confidences | most frequent | share on 0.85/0.90 | "
              "`Rubric:` present | `Witness:` in feasible answers | mean feasibility reasoning (chars) |")
    md.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for rid in base_ids + var_ids:
        st = triage_stats(find_run_dir(args.runs_root, rid), runs[rid]["prompt_row"])
        if not st:
            continue
        pct = lambda x: "–" if x is None else f"{100 * x:.0f}%"
        md.append(f"| {rid} | {st['answers']} | {st['distinct_conf']} | {st['top_conf']} | {pct(st['share_085_090'])} | "
                  f"{pct(st['rubric_share'])} | {pct(st['witness_share_of_feasible'])} | "
                  f"{st['mean_reasoning_chars']:.0f} |")
        for m in ("distinct_conf", "share_085_090", "rubric_share", "witness_share_of_feasible", "mean_reasoning_chars"):
            csv_rows.append({"variant": runs[rid]["prompt_row"], "metric": f"{m}@{rid}", "value": st[m],
                             "base_mean": None, "base_min": None, "base_max": None, "delta": None,
                             "outside_base_range": None})
    md.append("")

    out = args.out or args.results / "variants.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    with open(args.results / "variants.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["variant", "metric", "value", "base_mean", "base_min", "base_max", "delta",
                               "outside_base_range"])
        w.writeheader()
        w.writerows(csv_rows)
    with open(args.results / "item_changes.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["variant", "case", "item_kind", "item_id", "triple", "pattern", "base_bucket",
                               "base_stable", "variant_bucket", "variant_confidence"])
        w.writeheader()
        w.writerows(change_rows)
    print(f"wrote {out}, variants.csv, item_changes.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
