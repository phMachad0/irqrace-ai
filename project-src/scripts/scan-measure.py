#!/usr/bin/env python3
"""Measure the "just ask the model to read the files" baseline on Racebench.

    python scripts/scan-measure.py per-file --out DIR [--backend claude-cli:sonnet@low] [--workers 4]
    python scripts/scan-measure.py one-prompt --out DIR [--backend ...]
    python scripts/scan-measure.py recall --out DIR [--backend ...]
    python scripts/scan-measure.py score DIR [--labels 53/33|48/38]

No static analysis is involved. The model gets, per case, the C source with line
numbers, the interrupt API header and the flows of the case's C1 config (entry
function, ISR or task, IRQ, priority) — the facts a reader could not get from
the C file alone — and a short instruction. It answers with a list of
atomicity violations as line triples. ``per-file`` asks once per case, four at a
time; ``one-prompt`` puts all 31 cases into one request.

Sources are ``2.1_remarks`` with the trailing ``//bug点`` annotation block cut
off: the lines the ground truth cites are the vendored file's, 006 patch
included, and the model never sees the annotations.

Scoring uses the project's own matcher (:func:`irqrace.evaluation.match_subject`)
against the 53/33 labels (or 48/38): a finding matches an annotation when its three lines
are the annotated ones, access kinds breaking ties, exactly as for a candidate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import yaml  # noqa: E402

from irqrace.llm.backends import ChatRequest, from_spec  # noqa: E402

SUITE = ROOT / "bench" / "racebench" / "2.1_remarks"
CONFIGS = ROOT / "bench" / "configs"

SYSTEM = """You review interrupt-driven embedded C code for atomicity violations.

Program model: one main task runs at the lowest priority. An ISR can preempt the main task, or an ISR of strictly lower priority, whenever its interrupt is enabled; larger priority numbers are higher. disable_isr(n) / enable_isr(n) mask and unmask interrupt n (-1 means all); the masking state is global.

An atomicity violation is a triple of accesses to the same memory location: A1 and A2 in one flow, B in another flow that can run between them, in one of four shapes (A1-B-A2): read-write-read, write-write-read, read-write-write, write-read-write.

Report every atomicity violation you find, each as the three source line numbers in the order A1, B, A2 and their access kinds. Report only violations you believe can actually happen."""

SYSTEM_REALWORLD = SYSTEM.replace(
    "An ISR can preempt the main task, or an ISR of strictly lower priority, whenever its interrupt is enabled; larger priority numbers are higher.",
    "An ISR can preempt the main task, or an ISR of lower priority, whenever its interrupt is enabled; larger priority numbers are higher. Whether ISRs of equal priority can preempt each other is stated with each program's flows. The initial masking state is unknown.")
assert SYSTEM_REALWORLD != SYSTEM

FINDING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["variable", "a1_line", "a1_kind", "b_line", "b_kind", "a2_line", "a2_kind", "why"],
    "properties": {
        "variable": {"type": "string"},
        "a1_line": {"type": "integer"}, "a1_kind": {"type": "string", "enum": ["read", "write"]},
        "b_line": {"type": "integer"}, "b_kind": {"type": "string", "enum": ["read", "write"]},
        "a2_line": {"type": "integer"}, "a2_kind": {"type": "string", "enum": ["read", "write"]},
        "why": {"type": "string", "description": "one or two sentences"},
    },
}
PER_FILE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["violations"],
                   "properties": {"violations": {"type": "array", "items": FINDING}}}
ONE_PROMPT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["cases"],
    "properties": {"cases": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["case", "violations"],
        "properties": {"case": {"type": "string"}, "violations": {"type": "array", "items": FINDING}}}}}}


#: Set by --suite: a disguised copy made by racebench-disguise.py, or None for the original.
DISGUISED: Path | None = None
#: Set by --max-tokens. Providers that count the requested output against a
#: per-minute token limit (Groq's free tier: 8,000) need it lower than the default.
MAX_TOKENS = 16000
#: Set by --realworld: the 18 programs of bench/realworld (official configs) instead of Racebench.
REALWORLD = False
RW_CONFIGS = ROOT / "bench" / "configs-realworld"
RW_SUITE = ROOT / "bench" / "realworld"

#: The real-world configs allow equal-priority ISRs to preempt each other (the conservative
#: semantics the shipped ground truth needs), so the scan states the same model.



def cases() -> list[str]:
    """The names the model sees: case names, or ``program_NN`` in a disguised copy."""
    if REALWORLD:
        return sorted(p.stem for p in RW_CONFIGS.glob("*.yaml") if "__" not in p.stem)
    if DISGUISED is not None:
        return sorted(json.loads((DISGUISED / "index.json").read_text())["programs"])
    return sorted(p.stem for p in CONFIGS.glob("svp_simple_*.yaml"))


def _meta(name: str) -> dict:
    return json.loads((DISGUISED / f"{name}.json").read_text())


def original(name: str, line: int) -> tuple[str, int]:
    """The original case and line a name and line of the prompt stand for."""
    if DISGUISED is None:
        return name, line
    m = _meta(name)
    return m["case"], m["line_map"].get(str(line), -line)


def source_of(case: str) -> str:
    """The case's C file, numbered, without the trailing annotation block."""
    if REALWORLD:
        lines = (RW_SUITE / case / "main.c").read_text(encoding="utf-8", errors="replace").splitlines()
        # blink1-3 end with their answers ("//violations", "//true violations", "//false positive").
        cut = next((i for i, l in enumerate(lines)
                    if re.match(r"^//\s*(true\s+)?violations|^//\s*false positive", l)), len(lines))
        lines = lines[:cut]
        width = len(str(len(lines)))
        return "\n".join(f"{i:>{width}}  {l}" for i, l in enumerate(lines, 1))
    if DISGUISED is not None:
        lines = (DISGUISED / f"{case}.c").read_text(encoding="utf-8").splitlines()
        width = len(str(len(lines)))
        return "\n".join(f"{i:>{width}}  {l}" for i, l in enumerate(lines, 1))
    path = SUITE / case.rsplit("_", 1)[0] / f"{case}.c"
    lines = path.read_text(encoding="utf-8").splitlines()
    cut = next((i for i, l in enumerate(lines) if l.strip().startswith("//bug")), len(lines))
    lines = lines[:cut]
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}}  {l}" for i, l in enumerate(lines, 1))


def flows_of(case: str) -> str:
    if REALWORLD:
        cfg = yaml.safe_load((RW_CONFIGS / f"{case}.yaml").read_text())
        flows = cfg["flows"]
        equal = cfg["semantics"]["equal_priority_preemption"]
    else:
        flows = _meta(case)["flows"] if DISGUISED is not None else yaml.safe_load((CONFIGS / f"{case}.yaml").read_text())["flows"]
    rows = []
    for f in flows:
        kind = "ISR" if f["kind"] == "isr" else "task"
        irq = f", interrupt {f['irq']}" if f.get("irq") is not None else ""
        rows.append(f"- {f['entry']}: {kind}, priority {f['priority']}{irq}")
    if REALWORLD:
        rows.append("ISRs of equal priority " + ("may" if equal else "never") + " preempt each other.")
    return "\n".join(rows)


def header() -> str:
    if REALWORLD:
        return ("void disable_isr(int n);  /* mask interrupt n; -1 masks all */\n"
                "void enable_isr(int n);   /* unmask interrupt n; -1 unmasks all */")
    return ((DISGUISED or SUITE) / "common.h").read_text(encoding="utf-8")


def case_block(case: str) -> str:
    fname = "main.c" if REALWORLD else f"{case}.c"
    return (f'<case name="{case}">\nFlows:\n{flows_of(case)}\n\n'
            f'<source file="{fname}">\n{source_of(case)}\n</source>\n</case>')


def ask(backend, prompt: str, schema: dict, name: str, system: str | None = None) -> dict:
    if system is None:
        system = SYSTEM_REALWORLD if REALWORLD else SYSTEM
    t0 = time.time()
    resp = backend.chat(ChatRequest(system=system, messages=[{"role": "user", "content": prompt}],
                                    schema=schema, schema_name=name, max_tokens=MAX_TOKENS))
    u = resp.usage
    return {"parsed": resp.parsed, "text": resp.text, "wall_s": time.time() - t0,
            "usage": {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                      "cache_read": u.cache_read_tokens, "cache_write": u.cache_write_tokens,
                      "latency_s": u.latency_s},
            "model": getattr(backend, "resolved_model", None), "backend": backend.spec}


def cmd_per_file(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    backend = from_spec(args.backend)
    common = f'<header file="common.h">\n{header()}\n</header>'

    def one(case: str) -> None:
        prompt = f"{common}\n\n{case_block(case)}\n\nList the atomicity violations in this case."
        try:
            res = ask(backend, prompt, PER_FILE_SCHEMA, "violations")
        except Exception as e:  # recorded, not retried: a refusal is an outcome
            res = {"error": str(e)}
        (out / f"{case}.json").write_text(json.dumps({"case": case, **res}, indent=2, ensure_ascii=False))
        print(f"{case}: {'error' if 'error' in res else len(res['parsed']['violations'])}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, cases()))
    (out / "run.json").write_text(json.dumps({"mode": "per-file", "backend": args.backend, "workers": args.workers,
                                              "suite": "realworld" if REALWORLD else (str(DISGUISED) if DISGUISED else "original"), "max_tokens": MAX_TOKENS,
                                              "wall_s": time.time() - t0}, indent=2))
    return 0


def cmd_one_prompt(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    backend = from_spec(args.backend)
    blocks = "\n\n".join(case_block(c) for c in cases())
    prompt = (f'<header file="common.h">\n{header()}\n</header>\n\n{blocks}\n\n'
              "Each <case> is an independent program. List the atomicity violations of every case, "
              "under its name; a case with none gets an empty list.")
    t0 = time.time()
    try:
        res = ask(backend, prompt, ONE_PROMPT_SCHEMA, "cases")
    except Exception as e:
        res = {"error": str(e)}
    (out / "all.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    (out / "run.json").write_text(json.dumps({"mode": "one-prompt", "backend": args.backend,
                                              "suite": "realworld" if REALWORLD else (str(DISGUISED) if DISGUISED else "original"), "max_tokens": MAX_TOKENS,
                                              "wall_s": time.time() - t0}, indent=2))
    print("error" if "error" in res else f"{sum(len(c['violations']) for c in res['parsed']['cases'])} findings")
    return 0


RECALL_SYSTEM = (
    "You answer questions about published software benchmarks from memory. If you do not remember "
    "something, return an empty list rather than guessing."
)


def cmd_recall(args) -> int:
    """No source at all: ask for a case's annotated bug points by its name alone."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    backend = from_spec(args.backend)

    def one(case: str) -> None:
        prompt = (f"Racebench (github.com/chenruibuaa/racebench) is an interrupt-race benchmark. Its "
                  f"2.1_remarks version annotates each program with its bug points (bug点) and false "
                  f"positives (误报点) as line triples. Without the source in front of you: what are the "
                  f"annotated bug points of {case}.c? Give each as the three line numbers A1, B, A2 with "
                  f"access kinds and the variable. Empty list if you do not remember this case.")
        try:
            res = ask(backend, prompt, PER_FILE_SCHEMA, "violations", system=RECALL_SYSTEM)
        except Exception as e:
            res = {"error": str(e)}
        (out / f"{case}.json").write_text(json.dumps({"case": case, **res}, indent=2, ensure_ascii=False))
        print(f"{case}: {'error' if 'error' in res else len(res['parsed']['violations'])}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, cases()))
    (out / "run.json").write_text(json.dumps({"mode": "per-file", "probe": "recall", "backend": args.backend,
                                              "suite": "original", "wall_s": time.time() - t0}, indent=2))
    return 0


def findings_by_case(out: Path) -> tuple[dict[str, list[dict]], list[dict], dict]:
    run = json.loads((out / "run.json").read_text())
    calls: list[dict] = []
    by_case: dict[str, list[dict]] = {}
    if run["mode"] == "per-file":
        for f in sorted(p for p in out.glob("*.json") if p.stem not in ("run", "score", "all") and not p.stem.startswith("score")):
            d = json.loads(f.read_text())
            calls.append(d)
            by_case[d["case"]] = [] if "error" in d else d["parsed"]["violations"]
    else:
        d = json.loads((out / "all.json").read_text())
        calls.append(d)
        if "error" not in d:
            for c in d["parsed"]["cases"]:
                by_case.setdefault(c["case"].removesuffix(".c"), []).extend(c["violations"])
    return by_case, calls, run


def score_realworld(out: Path, by_name: dict, calls: list, run: dict) -> int:
    """Entries of violation.info (line errata applied) against the scan's findings, with
    irqrace.realworld.match: same variable and pattern, and the lines for instance entries."""
    import csv

    from irqrace.evaluation import normalise_variable
    from irqrace.realworld import load_errata, match, parse_violation_info

    errata = load_errata()
    rows = []
    tot = {"bugs": 0, "bugs_found": 0, "traps": 0, "traps_found": 0, "findings": 0, "unmatched": 0}
    for prog in cases():
        entries, _ = parse_violation_info(RW_SUITE / prog / "violation.info", prog, errata)
        cands = []
        for i, v in enumerate(by_name.get(prog, [])):
            kinds = (v["a1_kind"], v["b_kind"], v["a2_kind"])
            cands.append({"id": f"{prog}#{i}", "variable": {"name": normalise_variable(v["variable"])},
                          "pattern": "".join(k[0].upper() for k in kinds),
                          "accesses": [{"source": {"line": v[f"{r}_line"]}, "kind": k}
                                       for r, k in zip(("a1", "b", "a2"), kinds)]})
        ms = match(entries, cands)
        used = {c for m in ms for c in m.candidates}
        bugs = [m for m in ms if m.entry.label == "bug"]
        traps = [m for m in ms if m.entry.label == "trap"]
        row = {"program": prog, "bugs": len(bugs), "bugs_found": sum(m.found for m in bugs),
               "traps": len(traps), "traps_found": sum(m.found for m in traps),
               "findings": len(cands), "unmatched": len(cands) - len(used),
               "missed": "; ".join(f"#{m.entry.index} {m.entry.raw}" for m in bugs if not m.found),
               "traps_reported": "; ".join(f"#{m.entry.index} {m.entry.raw}" for m in traps if m.found)}
        rows.append(row)
        for k in tot:
            tot[k] += row[k]
    usage = {k: sum((c.get("usage") or {}).get(k, 0) or 0 for c in calls)
             for k in ("input_tokens", "output_tokens", "cache_read", "cache_write", "latency_s")}
    summary = {"suite": "realworld", "mode": run["mode"], "backend": run["backend"], "wall_s": run["wall_s"],
               "calls": len(calls), "errors": [c.get("case", "all") for c in calls if "error" in c], **tot,
               "input_total": usage["input_tokens"] + usage["cache_read"] + usage["cache_write"],
               "output_tokens": usage["output_tokens"], "latency_sum_s": usage["latency_s"],
               "models": sorted({c.get("model") for c in calls if c.get("model")})}
    (out / "score.json").write_text(json.dumps({"summary": summary, "programs": rows}, indent=2, ensure_ascii=False))
    with (out / "cases.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(summary, indent=2))
    return 0


def cmd_score(args) -> int:
    from irqrace.bench_metrics import label_set
    from irqrace.evaluation import match_subject

    global DISGUISED, REALWORLD
    out = Path(args.dir)
    by_name, calls, run = findings_by_case(out)
    if run.get("suite") == "realworld":
        REALWORLD = True
        return score_realworld(out, by_name, calls, run)
    DISGUISED = Path(run["suite"]) if run.get("suite", "original") != "original" else None
    by_case: dict[str, list[dict]] = {}
    for name, found in by_name.items():
        if DISGUISED is not None and not (DISGUISED / f"{name}.json").exists():
            continue  # a name the model invented
        for v in found:
            case, _ = original(name, 0)
            w = dict(v)
            for k in ("a1_line", "b_line", "a2_line"):
                w[k] = original(name, v[k])[1]
            by_case.setdefault(case, []).append(w)
    labels = label_set(args.labels)
    names = sorted(p.stem for p in CONFIGS.glob("svp_simple_*.yaml"))
    gt = {case: labels.ground_truth(case) for case in names}
    rows = []
    tot = {"bugs": 0, "bugs_found": 0, "traps": 0, "traps_found": 0, "findings": 0, "unmatched": 0}
    for case in names:
        g = gt[case]
        cands = []
        for i, v in enumerate(by_case.get(case, [])):
            cands.append({"id": f"{case}#{i}", "variable": {"name": v["variable"], "aliases": []},
                          "accesses": [
                              {"role": "A1", "kind": v["a1_kind"], "source": {"file": f"{case}.c", "line": v["a1_line"]}},
                              {"role": "B", "kind": v["b_kind"], "source": {"file": f"{case}.c", "line": v["b_line"]}},
                              {"role": "A2", "kind": v["a2_kind"], "source": {"file": f"{case}.c", "line": v["a2_line"]}}]})
        rep = match_subject([*g.bugs, *g.traps], cands, subject=case)
        missed = [f"bug#{m.annotation.index} {m.annotation.pattern}{m.annotation.lines}" for m in rep.bug_matches if not m.detected]
        traps = [f"trap#{m.annotation.index} {m.annotation.pattern}{m.annotation.lines}" for m in rep.trap_matches if m.detected]
        rows.append({"case": case, "bugs": len(rep.bug_matches), "bugs_found": rep.bugs_detected,
                     "traps": len(rep.trap_matches), "traps_found": rep.traps_reported,
                     "findings": len(cands), "unmatched": rep.unmatched_candidates,
                     "missed": "; ".join(missed), "traps_reported": "; ".join(traps)})
        for k in tot:
            tot[k] += rows[-1][k]
    usage = {k: sum((c.get("usage") or {}).get(k, 0) or 0 for c in calls)
             for k in ("input_tokens", "output_tokens", "cache_read", "cache_write", "latency_s")}
    errors = [c.get("case", "all") for c in calls if "error" in c]
    summary = {"mode": run["mode"], "backend": run["backend"], "wall_s": run["wall_s"], "calls": len(calls),
               "errors": errors, **tot,
               "input_total": usage["input_tokens"] + usage["cache_read"] + usage["cache_write"],
               "output_tokens": usage["output_tokens"], "latency_sum_s": usage["latency_s"],
               "score_nasac": 2 * tot["bugs_found"] - 3 * tot["traps_found"],
               "models": sorted({c.get("model") for c in calls if c.get("model")})}
    summary["labels"] = args.labels
    suffix = "" if args.labels == "53/33" else "-" + args.labels.replace("/", "-")
    (out / f"score{suffix}.json").write_text(json.dumps({"summary": summary, "cases": rows}, indent=2, ensure_ascii=False))
    import csv
    with (out / f"cases{suffix}.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("per-file", "one-prompt", "recall"):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.add_argument("--backend", default="claude-cli:sonnet@low")
        p.add_argument("--workers", type=int, default=4)
    for name in ("per-file", "one-prompt"):
        sub.choices[name].add_argument("--suite", help="a disguised copy (racebench-disguise.py)")
        sub.choices[name].add_argument("--max-tokens", type=int, default=16000)
        sub.choices[name].add_argument("--realworld", action="store_true",
                                       help="the 18 real-world programs instead of Racebench")
    s = sub.add_parser("score")
    s.add_argument("dir")
    s.add_argument("--labels", default="53/33", help="53/33 (default) or 48/38")
    args = ap.parse_args()
    global DISGUISED, MAX_TOKENS
    MAX_TOKENS = getattr(args, "max_tokens", MAX_TOKENS)
    global REALWORLD
    REALWORLD = getattr(args, "realworld", False)
    if getattr(args, "suite", None):
        DISGUISED = Path(args.suite).resolve()
    return {"recall": cmd_recall, "per-file": cmd_per_file, "one-prompt": cmd_one_prompt, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
