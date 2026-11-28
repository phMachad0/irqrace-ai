"""Score S2 (triage) runs on Racebench 2.1 against the 48/38 annotations moved to 2.1 lines.

    python score_s2.py PAIR_DIR [PAIR_DIR ...]

Uses the same line mapping as score_21.py. S2 reports the `likely_real` bucket;
`not_infeasible` (everything not called infeasible) is given beside it.
"""

import dataclasses
import json
import re
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]  # project-src/
sys.path.insert(0, str(PROJECT / "src"))
from irqrace.bench_metrics import label_set  # noqa: E402
from irqrace.evaluation import match_subject  # noqa: E402

HERE = Path(__file__).resolve().parent
REMARKS = PROJECT / "bench" / "racebench" / "2.1_remarks"
#: Pristine 2.1 (git archive 3d77421); see NOTES.md.
SRC = Path(os.environ.get("PRISTINE_RACEBENCH", HERE / "pristine/project-src/bench/racebench")) / "2.1"
ns: dict = {}
code = (HERE / "score_21.py").read_text()
exec(code[code.index("def line_map"):code.index("def run_dir")], {"difflib": __import__("difflib"), "Path": Path}, ns)
line_map, MANUAL = ns["line_map"], ns["MANUAL"]
SPEND = re.compile(r"^spend: (.*)$", re.M)
EXCLUDED = "svp_simple_001_001"  # IntRace's 30 cases: all but this one (inferred)


def moved_truth(case, ls):
    gt = ls.ground_truth(case)
    sub = case.rsplit("_", 1)[0]
    lm = line_map(REMARKS / sub / f"{case}.c", SRC / sub / f"{case}.c")
    lm.update(MANUAL.get(case, {}))
    out = []
    for ann in gt.bugs + gt.traps:
        acc = tuple(dataclasses.replace(a, line=lm[a.line]) for a in ann.accesses)
        out.append(dataclasses.replace(ann, accesses=acc))
    return out


def score(pair: Path, labels="48/38"):
    ls = label_set(labels)
    tot = {k: {"bugs": 0, "found": 0, "traps_rep": 0, "reported": 0, "bugs_infeasible": 0}
           for k in ("likely_real", "not_infeasible")}
    tot30 = json.loads(json.dumps(tot))
    spend = {}
    per_case = []
    for run in sorted(p for p in pair.iterdir() if (p / "manifest.json").exists()):
        case = json.loads((run / "manifest.json").read_text())["subject"]["name"]
        triage = {d["candidate_id"]: d for d in map(json.loads, filter(str.strip, (run / "llm" / "triage.jsonl").read_text().splitlines()))}
        contexts = [json.loads(p.read_text()) for p in sorted((run / "context").glob("*.json"))]
        anns = moved_truth(case, ls)
        row = {"case": case}
        for view, keep in (("likely_real", lambda b: b == "likely_real"), ("not_infeasible", lambda b: b != "likely_infeasible")):
            shown = [c for c in contexts if keep(triage[c["id"]]["bucket"])]
            rep = match_subject(anns, shown, subject=case)
            all_rep = match_subject(anns, contexts, subject=case)
            d = {"bugs": len(rep.bug_matches), "found": sum(m.candidate_id is not None for m in rep.bug_matches),
                 "traps_rep": sum(m.candidate_id is not None for m in rep.trap_matches), "reported": len(shown),
                 "bugs_infeasible": sum(m.candidate_id is not None and triage[m.candidate_id]["bucket"] == "likely_infeasible"
                                        for m in all_rep.bug_matches)}
            row[view] = d
            for t in ((tot, tot30) if case != EXCLUDED else (tot,)):
                for k, v in d.items():
                    t[view][k] += v
        row["missed"] = [(m.annotation.lines, triage[m.candidate_id]["bucket"] if m.candidate_id else "not reported")
                         for m in match_subject(anns, contexts, subject=case).bug_matches
                         if m.candidate_id is None or triage[m.candidate_id]["bucket"] != "likely_real"]
        row["traps_on_top"] = [m.annotation.lines for m in match_subject(anns, [c for c in contexts if triage[c["id"]]["bucket"] == "likely_real"], subject=case).trap_matches if m.candidate_id]
        per_case.append(row)
        log = pair / "logs" / f"{case}.log"
        for m in SPEND.finditer(log.read_text() if log.exists() else ""):
            for kv in m.group(1).split():
                k, _, v = kv.partition("=")
                try:
                    spend[k] = spend.get(k, 0) + float(v)
                except ValueError:
                    pass
    wall = float((pair / "end.txt").read_text()) - float((pair / "start.txt").read_text())
    return {"pair": str(pair), "labels": labels, "all31": tot, "intrace30": tot30, "spend": spend, "wall_s": round(wall, 1),
            "batch_status": json.loads((pair / "batch.json").read_text())["status"], "cases": per_case}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = score(Path(p))
        print(f"== {p}  status={r['batch_status']}  wall={r['wall_s']} s  spend={ {k: round(v) for k, v in r['spend'].items()} }")
        for scope in ("intrace30", "all31"):
            print(f"  {scope}: {r[scope]}")
        for c in r["cases"]:
            if c["missed"] or c["traps_on_top"]:
                print(f"    {c['case']}: missed={c['missed']} traps_on_top={c['traps_on_top']}")
        Path(p, "score-2.1-48-38.json").write_text(json.dumps(r, indent=1, default=str))
