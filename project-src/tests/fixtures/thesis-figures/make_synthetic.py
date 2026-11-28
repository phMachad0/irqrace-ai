#!/usr/bin/env python3
"""Regenerate the SYNTHETIC dataset in this directory.

    python tests/fixtures/thesis-figures/make_synthetic.py

Every value written here is invented by a seeded random generator, to exercise
``scripts/thesis-figures.py``. None of it is a measurement, and none of it may
reach the monograph. Case names say ``synthetic``, run ids start with
``SYNTHETIC-``, published tools are ``ToolA-sintetico`` etc., and the counts
(16 bug points, 10 traps, 8 cases) are not Racebench's.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
rnd = random.Random(20261112)

CASES = [f"synthetic_case_{k:03d}_001" for k in range(1, 9)]
PATTERNS = ["RWR", "WWR", "WRW", "RWW"]
PROMPTS = ["+racebench", "+racebench+c4", "+racebench+witness", "+racebench+location"]
SAMPLES = 3
BUCKETS = ["likely_real", "uncertain", "likely_benign", "likely_infeasible"]
VIEWS = {"likely_real": {"likely_real"},
         "not_infeasible": {"likely_real", "uncertain", "likely_benign"},
         "static_only": set(BUCKETS)}

# --- the frozen "static run": the same fates in every run --------------------
static = []  # (case, kind, item_id, pattern, fate)
for ci, case in enumerate(CASES):
    for b in (1, 2):
        static.append((case, "bug", f"bug {b}", PATTERNS[(ci + b) % 4], "llm"))
    for t in range(1, 2 + (ci % 2)):
        if len([s for s in static if s[1] == "trap"]) >= 10:
            break
        fate = ["stage1_absent", "stage2", "solver", "llm", "llm", "solver", "stage2", "llm", "solver", "llm"][
            len([s for s in static if s[1] == "trap"])]
        static.append((case, "trap", f"trap {t}", PATTERNS[(ci + t + 1) % 4], fate))
    for u in range(1, 5):
        fate = rnd.choice(["stage2", "solver", "llm", "llm", "llm"])
        static.append((case, "unannotated", f"cand {u:02d}", rnd.choice(PATTERNS), fate))

# Two bug points that "were traps before a relabel", for the 48/38 reading.
OLD_TRAPS = {("synthetic_case_001_001", "bug 2"), ("synthetic_case_005_001", "bug 1")}


def bucket_for(kind: str, prompt: str, sample: int, key: tuple) -> tuple[str, float]:
    if kind == "bug":
        if prompt == "+racebench+location" and sample == 2 and key == ("synthetic_case_003_001", "bug 1"):
            return "likely_infeasible", 0.6  # the synthetic recall loss F6/F7 must show
        if rnd.random() < 0.08:
            return "uncertain", 0.5
        return "likely_real", round(rnd.uniform(0.7, 0.95), 2)
    if kind == "trap":
        p_real = {"+racebench": 0.3, "+racebench+c4": 0.2, "+racebench+witness": 0.1,
                  "+racebench+location": 0.25}[prompt]
        r = rnd.random()
        if r < p_real:
            return "likely_real", round(rnd.uniform(0.55, 0.85), 2)
        return ("uncertain", 0.5) if r < p_real + 0.15 else ("likely_infeasible", round(rnd.uniform(0.7, 0.9), 2))
    return rnd.choice(["likely_real", "likely_real", "uncertain", "likely_infeasible"]), round(rnd.uniform(0.4, 0.95), 2)


items, runs, patterns = [], [], []
for pi, prompt in enumerate(PROMPTS):
    for sample in range(1, SAMPLES + 1):
        run_id = f"SYNTHETIC-{pi + 1}{sample}"
        its = []
        for case, kind, item_id, pat, fate in static:
            bucket, conf = bucket_for(kind, prompt, sample, (case, item_id)) if fate == "llm" else ("", "")
            its.append({"run_id": run_id, "prompt_row": prompt, "sample": sample, "case": case,
                        "item_kind": kind, "item_id": item_id,
                        "triple": f"<R#{10 + len(its)}><W#{50 + len(its)}><R#{11 + len(its)}>",
                        "pattern": pat, "fate": fate,
                        "feasibility": "" if fate != "llm" else ("infeasible" if bucket == "likely_infeasible" else "feasible"),
                        "bucket": bucket, "confidence": conf})
        items += its
        calls = 40 + 25 * (prompt.endswith("c4")) + rnd.randint(-4, 4)
        tin = calls * (9000 + 3000 * (prompt.endswith("witness"))) + rnd.randint(-5000, 5000)
        for labels in ("53/33", "48/38", "2.2"):
            def kind_of(it):
                if labels == "48/38" and (it["case"], it["item_id"]) in OLD_TRAPS:
                    return "trap"
                return it["item_kind"]
            extra_bugs = 5 if labels == "2.2" else 0
            for view, reported in VIEWS.items():
                system = "S1" if view == "static_only" else "S2"
                def rep(it):
                    return it["fate"] == "llm" and it["bucket"] in reported
                bt = sum(1 for it in its if kind_of(it) == "bug") + extra_bugs
                bd = sum(1 for it in its if kind_of(it) == "bug" and rep(it)) + (min(extra_bugs, 4) if labels == "2.2" else 0)
                tt = sum(1 for it in its if kind_of(it) == "trap")
                tr = sum(1 for it in its if kind_of(it) == "trap" and rep(it))
                ur = sum(1 for it in its if kind_of(it) == "unannotated" and rep(it))
                score = 2 * bd - 3 * tr
                runs.append({"run_id": run_id, "system": system, "prompt_row": prompt, "sample": sample,
                             "labels": labels, "case_subset": "all", "view": view,
                             "bug_points_total": bt, "bug_points_detected": bd, "traps_total": tt,
                             "traps_reported": tr, "unannotated_reported": ur,
                             "uncertain": sum(1 for it in its if it["bucket"] == "uncertain"),
                             "score": score, "score_max": 2 * bt, "recall": round(bd / bt, 4),
                             "precision": round(bd / (bd + tr), 4) if bd + tr else "",
                             "inspection_ratio_mean": round(rnd.uniform(0.75, 0.9) if system == "S1"
                                                            else rnd.uniform(0.4, 0.65), 3),
                             "llm_calls": calls if system == "S2" else 0,
                             "tokens_in": tin if system == "S2" else 0,
                             "tokens_out": calls * 700 if system == "S2" else 0,
                             "backend_failures": 0, "wall_s": 900 + rnd.randint(-60, 60),
                             "static_s": 30, "llm_s": 870})
                if labels != "2.2":
                    for pat in PATTERNS:
                        tot = sum(1 for it in its if kind_of(it) == "bug" and it["pattern"] == pat)
                        det = sum(1 for it in its if kind_of(it) == "bug" and it["pattern"] == pat and rep(it))
                        patterns.append({"run_id": run_id, "labels": labels, "case_subset": "all", "view": view,
                                         "pattern": pat, "bug_points_total": tot, "bug_points_detected": det})

agreement = []
for pi, prompt in enumerate(PROMPTS):
    for a, b in ((1, 2), (1, 3), (2, 3)):
        for field in ("feasibility", "bucket"):
            agreement.append({"prompt_row": prompt, "run_a": f"SYNTHETIC-{pi + 1}{a}",
                              "run_b": f"SYNTHETIC-{pi + 1}{b}", "field": field, "n_shared": 40,
                              "agreement": round(rnd.uniform(0.85, 0.97), 3),
                              "kappa": round(rnd.uniform(0.7, 0.92), 3)})

P = []
for tool, by, cases, gt, rec, fp, copied in (
        ("ToolA-sintetico", "ToolA-sintetico", 25, "38", 1.0, 0, "rerun"),
        ("ToolB-sintetico", "ToolA-sintetico", 25, "38", 0.6, 4, "copied"),
        ("ToolC-sintetico", "ToolC-sintetico", 30, "50", 0.9, 2, "rerun")):
    for metric, value in (("recall", rec), ("traps_reported", fp)):
        P.append({"tool": tool, "reported_by": by, "cases": cases, "ground_truth": gt,
                  "defect_class": "synthetic", "metric": metric, "value": value,
                  "rerun_or_copied": copied, "hardware": "SYNTHETIC", "source": "SYNTHETIC"})
for pat, v in (("RWR", 1.0), ("WWR", 1.0), ("WRW", 1.0), ("RWW", 0.0)):
    P.append({"tool": "ToolA-sintetico", "reported_by": "ToolA-sintetico", "cases": 25, "ground_truth": "38",
              "defect_class": "synthetic", "metric": f"recall_{pat}", "value": v,
              "rerun_or_copied": "rerun", "hardware": "SYNTHETIC", "source": "SYNTHETIC"})

cand = [(c, i) for c, k, i, _, f in static if k == "unannotated" and f == "llm"]
labels22 = []
verdicts = ["bug", "bug", "bug", "bug", "bug", "bug", "trap", "not_defect", "undecided", "bug"]
for (case, item_id), verdict in zip(cand, verdicts):
    group = f"{case}:G{1 if verdict == 'bug' and len(labels22) < 2 else len(labels22)}" if verdict == "bug" else ""
    labels22.append({"case": case, "item_id": item_id, "verdict": verdict, "group": group})


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


write("runs.csv", runs)
write("patterns.csv", patterns)
write("items.csv", items)
write("agreement.csv", agreement)
write("published.csv", P)
write("labels22.csv", labels22)
(HERE / "manifest.json").write_text(json.dumps(
    {"SYNTHETIC": "invented values for testing thesis-figures.py; not a measurement",
     "commit": "SYNTHETIC", "model": "none", "date": "1970-01-01"}, indent=2) + "\n", encoding="utf-8")
print(f"{len(runs)} runs rows, {len(items)} items, {len(labels22)} 2.2 labels")
