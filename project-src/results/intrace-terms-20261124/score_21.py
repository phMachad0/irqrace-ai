"""Score static runs on Racebench 2.1 (the copy IntRace analysed) against the
48/38 annotations, moved from 2.1_remarks line numbers to 2.1 line numbers.

    python score_21.py RUN_ROOT REMARKS_DIR SRC_DIR

An annotated line is moved when difflib puts it in an "equal" block between the
two files (stripped text); otherwise it is reported as having no counterpart and
the annotation cannot match.
"""

import dataclasses
import difflib
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]  # project-src/
sys.path.insert(0, str(PROJECT / "src"))
from irqrace.bench_metrics import label_set  # noqa: E402
from irqrace.evaluation import match_subject  # noqa: E402

RUN_ROOT, REMARKS, SRC = map(Path, sys.argv[1:4])
LABELS = sys.argv[4] if len(sys.argv) > 4 else "48/38"

# IntRace, Table 3, rows mapped to cases by size (2.1 line count), #ISR and #Race.
INTRACE = {  # case: (No, race, num, tp, fp)
    "svp_simple_014_001": (1, 1, 1, 1, 0), "svp_simple_003_001": (2, 1, 1, 1, 0),
    "svp_simple_007_001": (3, 1, 2, 1, 1), "svp_simple_018_001": (4, 3, 3, 3, 0),
    "svp_simple_026_001": (5, 1, 1, 1, 0), "svp_simple_021_001": (6, 3, 3, 3, 0),
    "svp_simple_024_001": (7, 1, 1, 1, 0), "svp_simple_004_001": (8, 1, 1, 1, 0),
    "svp_simple_008_001": (9, 1, 2, 1, 1), "svp_simple_028_001": (10, 1, 1, 1, 0),
    "svp_simple_002_001": (11, 1, 2, 1, 1), "svp_simple_016_001": (12, 3, 3, 3, 0),
    "svp_simple_019_001": (13, 1, 1, 1, 0), "svp_simple_013_001": (14, 1, 2, 1, 1),
    "svp_simple_022_001": (15, 4, 4, 4, 0), "svp_simple_005_001": (16, 1, 1, 1, 0),
    "svp_simple_012_001": (17, 1, 1, 1, 0), "svp_simple_017_001": (18, 5, 5, 5, 0),
    "svp_simple_006_001": (19, 1, 1, 1, 0), "svp_simple_030_001": (20, 1, 1, 1, 0),
    "svp_simple_031_001": (21, 3, 3, 3, 0), "svp_simple_025_001": (22, 1, 1, 1, 0),
    "svp_simple_011_001": (23, 1, 1, 1, 0), "svp_simple_010_001": (24, 1, 1, 1, 0),
    "svp_simple_015_001": (25, 1, 1, 1, 0), "svp_simple_009_001": (26, 2, 2, 2, 0),
    "svp_simple_023_001": (27, 2, 2, 2, 0), "svp_simple_020_001": (28, 2, 2, 2, 0),
    "svp_simple_027_001": (29, 2, 2, 2, 0), "svp_simple_029_001": (30, 1, 1, 1, 0),
}


def line_map(a: Path, b: Path) -> dict[int, int]:
    la = [x.strip() for x in a.read_text(encoding="utf-8", errors="replace").splitlines()]
    lb = [x.strip() for x in b.read_text(encoding="utf-8", errors="replace").splitlines()]
    out = {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, la, lb, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            # A same-size replaced block is the same statement with another
            # expression (`x++` -> `x = 12`); checked by hand in 017, 026-028, 030.
            out.update({i1 + k + 1: j1 + k + 1 for k in range(i2 - i1)})
    return out


#: 019 is rewritten between the copies (reads moved in and out of the masked
#: region); these three lines were matched by hand to the same statement.
MANUAL = {"svp_simple_019_001": {51: 49, 56: 53, 59: 54}}


def run_dir(case: str) -> Path:
    runs = sorted(RUN_ROOT.glob(f"{case}-*"))
    assert len(runs) == 1, (case, runs)
    return runs[0]


rows, unmapped = [], []
ls = label_set(LABELS)
for case in sorted(p.name.rsplit("-", 2)[0] for p in RUN_ROOT.glob("svp_simple_*")):
    gt = ls.ground_truth(case)
    sub = case.rsplit("_", 1)[0]
    lm = line_map(REMARKS / sub / f"{case}.c", SRC / sub / f"{case}.c")
    lm.update(MANUAL.get(case, {}))
    moved = []
    for ann in gt.bugs + gt.traps:
        new = [dataclasses.replace(acc, line=lm.get(acc.line, -acc.line)) for acc in ann.accesses]
        if any(acc.line < 0 for acc in new):
            unmapped.append((case, ann.kind, ann.index, ann.lines))
        moved.append(dataclasses.replace(ann, accesses=tuple(new)))
    rd = run_dir(case)
    manifest = json.loads((rd / "manifest.json").read_text())
    stages = {s["name"]: s for s in manifest["stages"]}
    contexts = [json.loads(p.read_text()) for p in sorted((rd / "context").glob("*.json"))]
    rep = match_subject(moved, contexts, subject=case)
    bugs_found = sum(m.candidate_id is not None for m in rep.bug_matches)
    traps_rep = sum(m.candidate_id is not None for m in rep.trap_matches)
    missed = [m.annotation.lines for m in rep.bug_matches if m.candidate_id is None]
    pairs = {tuple(sorted((a["source"]["line"], a["role"] == "B") for a in c["accesses"] if a["role"] in r))
             for c in contexts for r in (("A1", "B"), ("B", "A2"))}
    rows.append(dict(case=case, intrace=INTRACE.get(case), bugs=len(gt.bugs), traps=len(gt.traps),
                     found=bugs_found, traps_reported=traps_rep, reported=len(contexts),
                     pairs=len(pairs), missed=missed,
                     s1=stages.get("stage1", {}).get("candidates_out"),
                     s2=stages.get("stage2", {}).get("candidates_out"),
                     s3=stages.get("solver", {}).get("candidates_out"),
                     source_root=manifest["subject"]["source_root"]))

print(f"labels {LABELS}; source roots: {sorted({r['source_root'] for r in rows})}")
print("annotations with no counterpart in 2.1:", unmapped or "none")
print(f"{'case':20} {'No':>3} {'IRrace':>6} {'IRnum':>5} {'IRfp':>4} | {'bugs':>4} {'found':>5} {'traps':>5} {'trRep':>5} {'rep':>4} {'pairs':>5} | s1  s2  s3  missed")
for r in rows:
    ir = r["intrace"] or ("-",) * 5
    print(f"{r['case']:20} {ir[0]:>3} {ir[1]:>6} {ir[2]:>5} {ir[4]:>4} | {r['bugs']:>4} {r['found']:>5} {r['traps']:>5} "
          f"{r['traps_reported']:>5} {r['reported']:>4} {r['pairs']:>5} | {r['s1']} {r['s2']} {r['s3']} {r['missed'] or ''}")
for excl in ("svp_simple_001_001", "svp_simple_019_001"):
    sub = [r for r in rows if r["case"] != excl]
    tot = {k: sum(r[k] for r in sub) for k in ("bugs", "found", "traps", "traps_reported", "reported", "pairs", "s1", "s2", "s3")}
    print(f"30 cases without {excl}: {tot}")
tot = {k: sum(r[k] for r in rows) for k in ("bugs", "found", "traps", "traps_reported", "reported", "pairs", "s1", "s2", "s3")}
print(f"31 cases: {tot}")
json.dump(rows, open(RUN_ROOT.parent / f"score-{RUN_ROOT.name}-{LABELS.replace('/', '-')}.json", "w"), indent=1, default=str)
