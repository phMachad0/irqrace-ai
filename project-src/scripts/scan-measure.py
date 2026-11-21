#!/usr/bin/env python3
"""Measure the "just ask the model to read the files" baseline on Racebench.

    python scripts/scan-measure.py per-file --out DIR [--backend claude-cli:sonnet@low] [--workers 4]
    python scripts/scan-measure.py one-prompt --out DIR [--backend ...]
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


def cases() -> list[str]:
    return sorted(p.stem for p in CONFIGS.glob("svp_simple_*.yaml"))


def source_of(case: str) -> str:
    """The case's C file, numbered, without the trailing annotation block."""
    path = SUITE / case.rsplit("_", 1)[0] / f"{case}.c"
    lines = path.read_text(encoding="utf-8").splitlines()
    cut = next((i for i, l in enumerate(lines) if l.strip().startswith("//bug")), len(lines))
    lines = lines[:cut]
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}}  {l}" for i, l in enumerate(lines, 1))


def flows_of(case: str) -> str:
    cfg = yaml.safe_load((CONFIGS / f"{case}.yaml").read_text())
    rows = []
    for f in cfg["flows"]:
        kind = "ISR" if f["kind"] == "isr" else "task"
        irq = f", interrupt {f['irq']}" if f.get("irq") is not None else ""
        rows.append(f"- {f['entry']}: {kind}, priority {f['priority']}{irq}")
    return "\n".join(rows)


def header() -> str:
    return (SUITE / "common.h").read_text(encoding="utf-8")


def case_block(case: str) -> str:
    return (f'<case name="{case}">\nFlows:\n{flows_of(case)}\n\n'
            f'<source file="{case}.c">\n{source_of(case)}\n</source>\n</case>')


def ask(backend, prompt: str, schema: dict, name: str) -> dict:
    t0 = time.time()
    resp = backend.chat(ChatRequest(system=SYSTEM, messages=[{"role": "user", "content": prompt}],
                                    schema=schema, schema_name=name))
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
                                              "wall_s": time.time() - t0}, indent=2))
    print("error" if "error" in res else f"{sum(len(c['violations']) for c in res['parsed']['cases'])} findings")
    return 0


def findings_by_case(out: Path) -> tuple[dict[str, list[dict]], list[dict], dict]:
    run = json.loads((out / "run.json").read_text())
    calls: list[dict] = []
    by_case: dict[str, list[dict]] = {}
    if run["mode"] == "per-file":
        for f in sorted(out.glob("svp_simple_*.json")):
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


def cmd_score(args) -> int:
    from irqrace.bench_metrics import label_set
    from irqrace.evaluation import match_subject

    out = Path(args.dir)
    by_case, calls, run = findings_by_case(out)
    labels = label_set(args.labels)
    gt = {case: labels.ground_truth(case) for case in cases()}
    rows = []
    tot = {"bugs": 0, "bugs_found": 0, "traps": 0, "traps_found": 0, "findings": 0, "unmatched": 0}
    for case in cases():
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
    for name in ("per-file", "one-prompt"):
        p = sub.add_parser(name)
        p.add_argument("--out", required=True)
        p.add_argument("--backend", default="claude-cli:sonnet@low")
        p.add_argument("--workers", type=int, default=4)
    s = sub.add_parser("score")
    s.add_argument("dir")
    s.add_argument("--labels", default="53/33", help="53/33 (default) or 48/38")
    args = ap.parse_args()
    return {"per-file": cmd_per_file, "one-prompt": cmd_one_prompt, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
