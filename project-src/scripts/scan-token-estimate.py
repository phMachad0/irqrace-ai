#!/usr/bin/env python3
"""Input tokens: irqrace's triage prompts against "ask the model to read every file".

    python scripts/scan-token-estimate.py racebench --root FROZEN_ROOT --clean-sources bench/racebench/2.1
    python scripts/scan-token-estimate.py realworld --root RUN_ROOT

An **estimate**, not a measurement: no model is called. Characters are counted
exactly and converted with a characters-per-token ratio. The default ratio,
2.41, is calibrated on M1 (``results/m1``): the 304 prompts of ``+racebench/1``
(system prompt, JSON schema, task, rendered record) total 8,479,763 characters
and the CLI reported 3,519,824 input tokens for them. Plain C source usually
tokenizes at more characters per token than this JSON-heavy mix, so the scan
side is also given at ``--code-ratio`` (default 3.5, not calibrated here).

The tool side, per candidate, is the feasibility prompt plus, for the share of
candidates not called infeasible, the harmfulness prompt (``--harm-share``,
default 138/166 from M1). Three groupings are computed: one conversation per
triple (today), per interval (``--by-interval``) and per variable (checklist).

The scan side sends each subject's source files once with the same system
prompt the triage uses for feasibility (so the model gets the same domain
knowledge), or with no system prompt at all (lower bound). Output tokens are
not estimated: they depend on how much the model writes per finding.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irqrace.llm.client import FEASIBILITY_TASK, HARMFULNESS_TASK, render_record  # noqa: E402
from irqrace.llm.intervals import group_intervals, render_interval  # noqa: E402
from irqrace.llm.prompts import EXPERIMENTAL, FULL  # noqa: E402
from irqrace.llm.verdict import FeasibilityAnswer, HarmfulnessAnswer  # noqa: E402

try:  # the checklist lives only in the per-variable experiment
    from irqrace.llm.checklist import group_variables, render_checklist  # noqa: E402
except ImportError:  # pragma: no cover
    group_variables = render_checklist = None


def records_of(root: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted(glob.glob(str(root / "*" / "context" / "*.json"))):
        rec = json.loads(Path(f).read_text())
        out.setdefault(Path(f).parents[1].name, []).append(rec)
    return out


def sources_of(run: Path) -> list[tuple[Path, str]]:
    import yaml

    cfg = yaml.safe_load((run / "config.yaml").read_text())
    subj = cfg["subject"]
    base = (run / subj["source_root"]) if not Path(subj["source_root"]).is_absolute() else Path(subj["source_root"])
    if not base.exists():  # configs keep source_root relative to bench/configs*
        for cand in (ROOT / "bench" / "configs", ROOT / "bench" / "configs-realworld"):
            if (cand / subj["source_root"]).exists():
                base = cand / subj["source_root"]
                break
    return [(base, s) for s in subj["sources"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("suite", choices=["racebench", "realworld"])
    ap.add_argument("--root", required=True, help="frozen root / run root with context/ records")
    ap.add_argument("--row", default="+racebench")
    ap.add_argument("--ratio", type=float, default=2.41)
    ap.add_argument("--code-ratio", type=float, default=3.5)
    ap.add_argument("--harm-share", type=float, default=138 / 166)
    ap.add_argument("--clean-sources", help="for Racebench: read sources from this tree instead (2.1 without remarks)")
    args = ap.parse_args()

    cfg = EXPERIMENTAL.get(args.row) or FULL
    sys_f, sys_h = cfg.system_prompt("feasibility"), cfg.system_prompt("harmfulness")
    fixed_f = len(sys_f) + len(json.dumps(FeasibilityAnswer.model_json_schema())) + len(FEASIBILITY_TASK)
    fixed_h = len(sys_h) + len(json.dumps(HarmfulnessAnswer.model_json_schema())) + len(HARMFULNESS_TASK)

    per_case = records_of(Path(args.root))
    tool = {"triple": 0.0, "interval": 0.0, "variable": 0.0}
    calls = {"triple": 0, "interval": 0, "variable": 0}
    scan_chars = 0
    for case, recs in per_case.items():
        for r in recs:
            body = len(render_record(r))
            tool["triple"] += fixed_f + body + args.harm_share * (fixed_h + body)
            calls["triple"] += 1
        for g in group_intervals(recs):
            body = len(render_record(g[0])) + (len(render_interval(g[0], g[1:])) if len(g) > 1 else 0)
            tool["interval"] += fixed_f + body + args.harm_share * (fixed_h + body)
            calls["interval"] += 1
        if group_variables is not None:
            for g in group_variables(recs):
                body = len(render_checklist(g)) if len(g) > 1 else len(render_record(g[0]))
                tool["variable"] += fixed_f + body + args.harm_share * (fixed_h + body)
                calls["variable"] += 1
        run = Path(args.root) / case
        srcs = [(Path(args.clean_sources) if args.clean_sources else base) / rel
                for base, rel in sources_of(run)]
        scan_chars += sum(len(p.read_text(errors="replace")) for p in srcs)
    n_cases = len(per_case)
    scan_with_sys = scan_chars + n_cases * len(sys_f)

    def tok(c: float, ratio: float) -> str:
        return f"{c / ratio:,.0f}"

    print(f"subjects with candidates: {n_cases}; candidates: {calls['triple']}")
    print("| | conversations | input tokens (est.) |")
    print("| --- | --- | --- |")
    print(f"| irqrace, one per triple | {calls['triple']} | {tok(tool['triple'], args.ratio)} |")
    print(f"| irqrace, one per interval | {calls['interval']} | {tok(tool['interval'], args.ratio)} |")
    if group_variables is not None:
        print(f"| irqrace, one per variable (checklist) | {calls['variable']} | {tok(tool['variable'], args.ratio)} |")
    print(f"| scan: every source file once + the triage system prompt | {n_cases} | "
          f"{tok(scan_with_sys, args.ratio)} – {tok(scan_with_sys, args.code_ratio)} |")
    print(f"| scan: every source file once, no system prompt | {n_cases} | "
          f"{tok(scan_chars, args.ratio)} – {tok(scan_chars, args.code_ratio)} |")
    print(f"\nsource characters: {scan_chars:,}; ratios: {args.ratio} (calibrated) / {args.code_ratio} (code, assumed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
