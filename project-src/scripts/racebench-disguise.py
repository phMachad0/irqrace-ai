#!/usr/bin/env python3
"""A disguised copy of the 31 Racebench cases, for the contamination test.

    python scripts/racebench-disguise.py --out DIR [--seed 2026]

A model that has seen Racebench can recall its planted bugs instead of finding
them. This copy keeps every program's behaviour and changes everything a memory
could key on:

* the header comment (suite name, company, dates, the Chinese notes) and every
  other comment are removed, and the trailing ``//bug点`` answer block with them;
* every ``svp_simple_NNN_NNN_<name>`` identifier becomes a neutral one, per case
  (``v_<word>`` for data, ``fn_``/``irq_``/``task_`` for functions), and the case
  itself becomes ``program_NN`` in a shuffled order;
* the top-level function definitions are reordered, so every line moves.

``DIR/<program>.c`` is the disguised source, ``DIR/<program>.json`` holds the
case it came from, its flows under the new names and ``line_map`` (new line ->
original line), so findings on the copy are scored against the original
annotations with the same matcher. ``DIR/common.h`` is the API header without
its comments. Deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "bench" / "racebench" / "2.1_remarks"
CONFIGS = ROOT / "bench" / "configs"

WORDS = ("amber basalt cobalt dune ember fjord garnet harbor iris jasper kestrel lagoon marble nectar "
         "onyx pebble quartz ridge saffron timber umber velvet willow yarrow zenith anchor beacon cedar "
         "delta falcon glacier hazel indigo juniper kelp lantern meadow nimbus orchid pylon quiver "
         "raptor summit tundra upland vessel walnut").split()

PREFIX = re.compile(r"\bsvp_simple_\d{3}_\d{3}_(\w+)")


def strip_comments(lines: list[str]) -> list[str]:
    """Remove // and /* */ comments, keeping one output line per input line."""
    out, in_block = [], False
    for line in lines:
        res, i = "", 0
        while i < len(line):
            if in_block:
                end = line.find("*/", i)
                if end < 0:
                    i = len(line)
                else:
                    in_block, i = False, end + 2
            elif line.startswith("/*", i):
                in_block, i = True, i + 2
            elif line.startswith("//", i):
                break
            else:
                res += line[i]
                i += 1
        out.append(res.rstrip())
    return out


def blocks(lines: list[tuple[int, str]]) -> tuple[list[tuple[int, str]], list[list[tuple[int, str]]]]:
    """Split into the prelude (includes, globals, type definitions) and function definitions."""
    prelude: list[tuple[int, str]] = []
    funcs: list[list[tuple[int, str]]] = []
    depth, cur, is_func = 0, None, False
    for orig, text in lines:
        if depth == 0 and cur is None:
            if not text.strip():
                continue
            opens = text.count("{")
            looks_like_function = "(" in text and not text.rstrip().endswith(";") and not text.lstrip().startswith("#")
            if looks_like_function or opens:
                cur, is_func = [], looks_like_function
            else:
                prelude.append((orig, text))
                continue
        cur.append((orig, text))
        depth += text.count("{") - text.count("}")
        if depth == 0 and "{" in "".join(t for _, t in cur):
            if is_func and not text.rstrip().endswith(";"):
                funcs.append(cur)
            else:
                prelude.extend(cur)
            cur = None
    if cur:
        prelude.extend(cur)
    return prelude, funcs


def prototype(block: list[tuple[int, str]]) -> str:
    """``void f(int a)`` from a definition, for the reordered file to compile."""
    head = []
    for _, text in block:
        head.append(text.split("{", 1)[0])
        if "{" in text:
            break
    return " ".join(h.strip() for h in head if h.strip()) + ";"


def disguise_case(case: str, rng: random.Random, prototypes: bool = False) -> tuple[list[str], dict[int, int], dict[str, str]]:
    path = SUITE / case.rsplit("_", 1)[0] / f"{case}.c"
    raw = path.read_text(encoding="utf-8").splitlines()
    cut = next((i for i, l in enumerate(raw) if l.strip().startswith("//bug")), len(raw))
    clean = strip_comments(raw[:cut])

    tails = sorted({m.group(1) for l in clean for m in PREFIX.finditer(l)}, key=lambda t: (-len(t), t))
    words = rng.sample(WORDS, len(tails))
    names: dict[str, str] = {}
    for tail, word in zip(tails, words):
        if tail == "main":
            names[tail] = f"task_{word}"
        elif tail.startswith("isr_") and not tail.endswith("flag"):
            names[tail] = f"irq_{word}"
        elif tail.startswith("func") or tail == "init":
            names[tail] = f"fn_{word}"
        else:
            names[tail] = f"v_{word}"
    renamed = [PREFIX.sub(lambda m: names[m.group(1)], l) for l in clean]
    leftovers = [l for l in renamed if "svp_simple" in l or "racebench" in l.lower()]
    if leftovers:
        raise SystemExit(f"{case}: identifiers left after renaming: {leftovers[:3]}")

    prelude, funcs = blocks(list(enumerate(renamed, 1)))
    order = list(range(len(funcs)))
    if len(order) > 1:
        while order == sorted(order):
            rng.shuffle(order)
    out: list[str] = []
    line_map: dict[int, int] = {}

    def emit(orig: int | None, text: str) -> None:
        out.append(text)
        if orig is not None:
            line_map[len(out)] = orig

    for orig, text in prelude:
        emit(orig, text)
    if prototypes:
        for block in funcs:
            emit(None, prototype(block))
    for k in order:
        emit(None, "")
        for orig, text in funcs[k]:
            emit(orig, text)
    return out, line_map, names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--compilable", action="store_true",
                    help="add prototypes, a <program>/ copy and C1 configs for the pipeline (same names and order)")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    cases = sorted(p.stem for p in CONFIGS.glob("svp_simple_*.yaml"))
    programs = list(range(1, len(cases) + 1))
    rng.shuffle(programs)
    header = strip_comments((SUITE / "common.h").read_text(encoding="utf-8").splitlines())
    (out / "common.h").write_text("\n".join(l for l in header if l.strip()) + "\n")
    if args.compilable:
        body = strip_comments((SUITE / "common.c").read_text(encoding="utf-8").splitlines())
        (out / "common.c").write_text("\n".join(l for l in body if l.strip()) + "\n")
        (out / "configs").mkdir()
    index = {}
    for case, num in zip(cases, programs):
        program = f"program_{num:02d}"
        src, line_map, names = disguise_case(case, rng, prototypes=args.compilable)
        cfg = yaml.safe_load((CONFIGS / f"{case}.yaml").read_text())
        flows = []
        for f in cfg["flows"]:
            tail = PREFIX.match(f["entry"]).group(1)
            flows.append({"entry": names[tail], "kind": f["kind"], "priority": f["priority"], "irq": f.get("irq")})
        (out / f"{program}.c").write_text("\n".join(src) + "\n")
        if args.compilable:
            (out / program).mkdir()
            (out / program / f"{program}.c").write_text("\n".join(src) + "\n")
            c1 = dict(cfg)
            c1["subject"] = {**cfg["subject"], "name": program, "source_root": str(out.resolve()),
                             "sources": [f"{program}/{program}.c"]}
            c1["flows"] = [{**f, "id": f["id"], "entry": names[PREFIX.match(f["entry"]).group(1)]}
                           for f in cfg["flows"]]
            c1.pop("ground_truth", None)
            (out / "configs" / f"{program}.yaml").write_text(yaml.safe_dump(c1, sort_keys=False, allow_unicode=True))
        (out / f"{program}.json").write_text(json.dumps(
            {"program": program, "case": case, "flows": flows, "names": names,
             "line_map": {str(k): v for k, v in line_map.items()}}, indent=2))
        index[program] = case
    (out / "index.json").write_text(json.dumps({"seed": args.seed, "programs": index}, indent=2))
    print(f"{len(cases)} cases disguised into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
