import os, sys, itertools
from pathlib import Path
PROJECT = Path(__file__).resolve().parents[2]  # project-src/
sys.path.insert(0, str(PROJECT / "src"))
from irqrace.groundtruth import parse_suite, load_suite
import re
CUR = PROJECT / "bench"
#: The suite as imported (git archive 3d77421 project-src/bench/racebench), unpacked here.
PRIS = Path(os.environ.get("PRISTINE_RACEBENCH", "pristine/project-src/bench/racebench"))
# IntRace Table 3: No, size, isr, race, rchecker num/tp/fp, intrace num/tp/fp
T = """1 60 3 1 2 1 1 1 1 0
2 74 2 1 2 1 1 1 1 0
3 51 1 1 11 1 10 2 1 1
4 65 2 3 3 3 0 3 3 0
5 44 2 1 1 1 0 1 1 0
6 81 1 3 3 3 0 3 3 0
7 65 1 1 2 1 1 1 1 0
8 69 2 1 3 1 2 1 1 0
9 53 1 1 2 1 1 2 1 1
10 54 3 1 2 1 1 1 1 0
11 46 2 1 2 1 1 2 1 1
12 34 1 3 3 3 0 3 3 0
13 72 1 1 2 1 1 1 1 0
14 67 3 1 2 1 1 2 1 1
15 67 1 4 6 4 2 4 4 0
16 47 1 1 3 1 2 1 1 0
17 35 1 1 1 1 0 1 1 0
18 42 1 5 5 5 0 5 5 0
19 54 1 1 1 1 0 1 1 0
20 57 3 1 2 1 1 1 1 0
21 92 1 3 3 3 0 3 3 0
22 39 1 1 1 1 0 1 1 0
23 44 1 1 1 1 0 1 1 0
24 54 1 1 1 1 0 1 1 0
25 41 1 1 1 1 0 1 1 0
26 48 1 2 2 2 0 2 2 0
27 40 1 2 2 2 0 2 2 0
28 55 2 2 3 2 1 2 2 0
29 49 3 2 2 2 0 2 2 0
30 95 1 1 1 1 0 1 1 0"""
rows = [list(map(int, l.split())) for l in T.splitlines()]
print("sums race/rc_num/rc_fp/ir_num/ir_tp/ir_fp", [sum(r[i] for r in rows) for i in (3,4,6,7,8,9)])
def lines(p):
    s = p.read_bytes(); return s.count(b"\n") + (0 if s.endswith(b"\n") else 1)
def isrs(p):
    return len(set(re.findall(rb"\bvoid\s+\w*isr_(\d+)\s*\(\s*(?:void)?\s*\)\s*\{", p.read_bytes())))
g48 = {c.case: c for c in parse_suite(PRIS / "2.1_remarks").cases}
g53 = {c.case: c for c in parse_suite(CUR / "racebench" / "2.1_remarks").cases}
info = {}
for v in ("2.1", "2.1_remarks"):
    for f in sorted((CUR / "racebench" / v).glob("svp_simple_*/*_001.c")):
        info.setdefault(f.stem, {})[v] = (lines(f), isrs(f))
print(f"{'case':20} {'2.1':>9} {'remarks':>9} bugs48 traps48 bugs53")
for c, d in info.items():
    print(f"{c:20} {str(d['2.1']):>9} {str(d['2.1_remarks']):>9} {len(g48[c].bugs):>6} {len(g48[c].traps):>7} {len(g53[c].bugs):>6}")
print()
for r in rows:
    m = [c for c, d in info.items() if d["2.1"] == (r[1], r[2])]
    m2 = [c for c, d in info.items() if d["2.1"][1] == r[2] and abs(d["2.1"][0]-r[1]) <= 1 and c not in m]
    print(f"No.{r[0]:<3} size {r[1]:>3} isr {r[2]} race {r[3]} | exact {m} | ±1 {m2}")
