"""Command line interface.

Everything the dashboard will eventually do, the CLI does first. The UI is a
launcher and a viewer, never the executor (``wiki/Dashboard Design.md``), and
batch evaluation -- 31 subjects, five prompt configurations -- is script work. If
a capability lives only in the UI, the evaluation cannot be scripted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import TOOL_VERSION, contracts
from .build import BuildError, build
from .config import Config, ConfigError
from .probe import ProbeError, probe
from .runstore import RunStore, find_runs
from .toolchain import detect

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = Path("/home/pedro/Documentos/tcc/racebench/2.1_remarks")
BENCH_CONFIGS = REPO_ROOT / "bench" / "configs"
ERRATA = REPO_ROOT / "bench" / "racebench-errata.yaml"

#: The five adversarial cases hand-counted to certify the parser
#: (docs/groundtruth-handcount.md). Kept here so `irqrace groundtruth certify`
#: checks the parser against the written count rather than against itself.
HAND_COUNT = {
    "svp_simple_001_001": (1, 2),
    "svp_simple_016_001": (3, 0),
    "svp_simple_019_001": (1, 4),
    "svp_simple_022_001": (4, 3),
    "svp_simple_031_001": (3, 0),
}


def _err(msg: str) -> int:
    print(msg, file=sys.stderr)
    return 1


# -- doctor ---------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> int:
    tc = detect()
    for tool in (tc.cc, tc.linker, tc.svf, tc.probe):
        mark = "ok  " if tool.ok else "MISS"
        detail = tool.version or tool.note or ""
        print(f"[{mark}] {tool.name:<16} {tool.path or '-'}  {detail}")
    for p in tc.problems:
        print(f"  ! {p}")
    return 0 if tc.ok else 1


# -- contracts ------------------------------------------------------------


def cmd_contracts_validate(args: argparse.Namespace) -> int:
    examples = REPO_ROOT / "contracts" / "examples"
    mapping = {
        "c1-": "c1", "c2-": "c2", "c3-manifest": "c3-manifest", "c3-drop": "c3-drop",
        "c4-context-request": "c4-request", "c4-context-reply": "c4-reply",
    }
    failures = 0
    checked = 0
    for path in sorted(examples.rglob("*")):
        if path.suffix not in (".json", ".yaml") or not path.is_file():
            continue
        name = next((v for k, v in mapping.items() if path.name.startswith(k)), None)
        if name is None:
            continue
        import yaml
        doc = (yaml.safe_load(path.read_text()) if path.suffix == ".yaml"
               else json.loads(path.read_text()))
        checked += 1
        try:
            contracts.validate(name, doc, what=str(path.relative_to(REPO_ROOT)))
            print(f"[ok  ] {path.relative_to(REPO_ROOT)}  ({name})")
        except contracts.ContractError as e:
            failures += 1
            print(f"[FAIL] {e}")
    print(f"{checked - failures}/{checked} examples conform")
    return 1 if failures else 0


# -- config ---------------------------------------------------------------


def cmd_config_validate(args: argparse.Namespace) -> int:
    ok = 0
    bad = 0
    for p in args.config:
        try:
            cfg = Config.load(p)
        except ConfigError as e:
            bad += 1
            print(f"[FAIL] {e}")
            continue
        ok += 1
        flows = ", ".join(
            f"{f.id}(p{f.priority}{'' if f.irq is None else f', irq{f.irq}'})"
            for f in cfg.flows
        )
        print(f"[ok  ] {p}  {cfg.name}  hash={cfg.hash()[:12]}  flows: {flows}")
        for note in cfg.notes:
            print(f"       note: {note}")
    if len(args.config) > 1:
        print(f"{ok}/{ok + bad} configurations valid")
    return 1 if bad else 0


def cmd_config_show(args: argparse.Namespace) -> int:
    cfg = Config.load(args.config)
    print(json.dumps(cfg.resolved(), indent=2, ensure_ascii=False))
    return 0


# -- build / probe --------------------------------------------------------


def _prepare(args: argparse.Namespace) -> tuple[Config, RunStore]:
    cfg = Config.load(args.config)
    store = RunStore.create(cfg, run_root=args.run_root or cfg.data["output"]["run_root"])
    return cfg, store


def _do_build(cfg: Config, store: RunStore):
    store.set_stage("build", "running")
    try:
        result = build(cfg, store.root / "build")
    except BuildError as e:
        store.set_stage("build", "failed", error=str(e))
        store.log("error", "build", "build-failed", str(e))
        raise
    m = store.read_manifest()
    m["build"] = {
        "cc": cfg.build["cc"],
        "linker": cfg.build["linker"],
        "flags": list(cfg.build["flags"]),
        "translation_units": result.translation_units,
        "bitcode": str(result.bitcode.relative_to(store.root)),
        "bitcode_sha256": result.bitcode_sha256,
    }
    store.write_manifest(m)
    store.set_stage("build", "ok")
    return result


def cmd_build(args: argparse.Namespace) -> int:
    cfg, store = _prepare(args)
    try:
        result = _do_build(cfg, store)
    except BuildError as e:
        return _err(f"build failed: {e}")
    print(f"{store.root}\n  bitcode: {result.bitcode} "
          f"({result.translation_units} translation unit(s))")
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    cfg, store = _prepare(args)
    try:
        result = _do_build(cfg, store)
        report = probe(result.bitcode, cfg)
    except (BuildError, ProbeError) as e:
        return _err(str(e))

    m = store.read_manifest()
    m["build"].update(
        functions_with_bodies=report["functions_with_bodies"],
        functions_declared_only=report["functions_declared_only"],
    )
    store.write_manifest(m)
    (store.root / "build" / "probe.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )

    for w in report["warnings"]:
        store.log(w.get("severity", "warn"), "build", w["code"], w["message"])

    serious = [w for w in report["warnings"] if w.get("severity", "warn") != "info"]
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if serious else 0

    print(f"{cfg.name}: {report['globals_count']} global(s), "
          f"{report['functions_with_bodies']} function(s) with bodies, "
          f"{len(report['functions_declared_only'])} declared only "
          f"({', '.join(report['functions_declared_only']) or 'none'})")
    print(f"  debug info: {report['mappable_with_debug_loc']}/"
          f"{report['mappable_instructions']} loads, stores and calls mapped")
    for g in report["globals"]:
        # declared_type already spells out the qualifier; the flag is for
        # consumers, not for this line.
        print(f"  {g['declared_type'] or '?':<18} {g['name']:<40} "
              f"{Path(g['decl']['file']).name}:{g['decl']['line']}  "
              f"pag={g['svf_node']}")
    for w in report["warnings"]:
        print(f"  ! [{w.get('severity', 'warn')}] {w['code']}: {w['message']}")
    return 1 if serious else 0


# -- stage 1 --------------------------------------------------------------


def cmd_stage1(args: argparse.Namespace) -> int:
    from .stage1_driver import Stage1Error, stage1

    cfg, store = _prepare(args)
    try:
        _do_build(cfg, store)
        summary = stage1(cfg, store, store.root / "build" / "whole.bc")
    except (BuildError, Stage1Error) as e:
        return _err(str(e))

    print(f"{cfg.name}: {summary['candidates']} candidates from "
          f"{summary['accesses']} accesses to {summary['objects']} shared object(s)")
    for w in summary["warnings"]:
        print(f"  ! [{w.get('severity', 'warn')}] {w['code']}: {w['message']}")
    print(f"  {store.root}")
    return 0


def cmd_stage2(args: argparse.Namespace) -> int:
    from .stage1_driver import Stage1Error, stage1
    from .stage2 import Stage2Error, stage2

    cfg, store = _prepare(args)
    try:
        _do_build(cfg, store)
        s1 = stage1(cfg, store, store.root / "build" / "whole.bc")
        s2 = stage2(cfg, store)
    except (BuildError, Stage1Error, Stage2Error) as e:
        return _err(str(e))

    print(f"{cfg.name}: stage 1 {s1['candidates']} candidates -> stage 2 {s2['kept']} "
          f"kept, {s2['dropped']} dropped with proof "
          f"({', '.join(f'{k} {v}' for k, v in sorted(s2['reasons'].items())) or 'none'})")
    print(f"  masking fixpoint in {s2['rounds']} round(s), {s2['wall_ms']} ms")
    for d in store.read_drops() if args.verbose else []:
        print(f"  - {d['candidate_id']} {d['pattern']} {d['lines']} "
              f"[{d['reason']}] {d['proof']}")
    print(f"  {store.root}")
    return 0


def cmd_stage3(args: argparse.Namespace) -> int:
    from .stage1_driver import Stage1Error, stage1
    from .stage2 import Stage2Error, stage2
    from .stage3 import Stage3Error, stage3

    cfg, store = _prepare(args)
    try:
        result = _do_build(cfg, store)
        s1 = stage1(cfg, store, result.bitcode)
        s2 = stage2(cfg, store)
        s3 = stage3(cfg, store, result.bitcode)
    except (BuildError, Stage1Error, Stage2Error, Stage3Error) as e:
        return _err(str(e))
    v = s3["verdicts"]
    print(f"{cfg.name}: {s1['candidates']} -> stage 2 {s2['kept']} -> solver: "
          f"{v.get('sat', 0)} sat, {v.get('inconclusive', 0)} inconclusive, "
          f"{v.get('unsat', 0)} unsat -> {s3['kept']} reach the LLM  [{s3['wall_ms']} ms]")
    if args.verbose:
        by_id = {c["id"]: c for c in store.read_candidates("stage2")}
        for line in (store.root / "solver" / "results.jsonl").read_text().splitlines():
            r = json.loads(line)
            c = by_id[r["candidate_id"]]
            lines = [a["source"]["line"] for a in c["accesses"]]
            print(f"  - {r['candidate_id']} {c.get('pattern', ''):<3} "
                  f"{lines} {r['verdict']}{' (' + r['reason'] + ')' if r.get('reason') else ''}"
                  f"  {r['wall_ms']} ms")
    print(f"  {store.root}")
    return 0


def _bench_run(args: argparse.Namespace, through: str) -> int:
    """Run every Racebench case through ``through``, then the recall gate.

    The gate is evaluated on the output of the LAST stage run: a filter that
    drops an annotated bug point fails it, whichever stage the filter is in.
    """
    from .evaluation import inspection_ratio, match_subject, report_json
    from .groundtruth import load_suite
    from .stage1_driver import Stage1Error, stage1
    from .stage2 import Stage2Error, stage2
    from .stage3 import Stage3Error, stage3

    configs = sorted(Path(args.configs).glob("*.yaml"))
    if not configs:
        return _err(f"no configurations in {args.configs}")
    gt = load_suite(Path(args.suite), Path(args.errata))
    s3tot = {"in": 0, "kept": 0, "ms": 0}
    verdicts: dict[str, int] = {}
    traps_s3 = 0
    slowest: list[tuple[int, str]] = []

    rows, failures, problems = [], [], []
    tot = {"s1": 0, "s2": 0}
    reasons: dict[str, int] = {}
    bugs_found = bugs_total = traps_total = traps_s1 = traps_s2 = 0
    per_subject_attrition = []
    t_s1 = t_s2 = 0

    for path in configs:
        try:
            cfg = Config.load(path)
            store = RunStore.create(cfg, run_root=args.run_root)
            _do_build(cfg, store)
            s1 = stage1(cfg, store, store.root / "build" / "whole.bc")
            s2 = stage2(cfg, store) if through in ("stage2", "stage3") else None
            s3 = (stage3(cfg, store, store.root / "build" / "whole.bc")
                  if through == "stage3" else None)
        except (ConfigError, BuildError, Stage1Error, Stage2Error, Stage3Error) as e:
            failures.append((path.stem, str(e).splitlines()[0]))
            print(f"[FAIL] {path.stem}: {str(e).splitlines()[0]}")
            continue

        case = gt.by_case(cfg.name)
        rep1 = match_subject(case.all, store.read_candidates("stage1"), subject=cfg.name)
        rep = rep1
        if s2 is not None:
            rep = match_subject(case.all, store.read_candidates("stage2"), subject=cfg.name)
        rep2 = rep
        if s3 is not None:
            # The gate is taken on what reaches the LLM: the context records.
            rep = match_subject(case.all, store.read_contexts(), subject=cfg.name)
            traps_s3 += rep.traps_reported
            for k, v in s3["verdicts"].items():
                verdicts[k] = verdicts.get(k, 0) + v
            s3tot["in"] += s3["in"]
            s3tot["kept"] += s3["kept"]
            s3tot["ms"] += s3["wall_ms"]
            slowest.append((s3["wall_ms"], cfg.name))
        (store.root / "eval" / "report.json").write_text(
            json.dumps(report_json(rep, stage=through), indent=2, ensure_ascii=False) + "\n")
        problems += [f"{store.root.name}: {p}" for p in store.check()]

        bugs_found += rep.bugs_detected
        bugs_total += len(rep.bug_matches)
        traps_total += len(rep.trap_matches)
        traps_s1 += rep1.traps_reported
        traps_s2 += rep2.traps_reported
        tot["s1"] += s1["candidates"]
        stage_ms = {st["name"]: st.get("wall_ms") or 0
                    for st in store.read_manifest()["stages"]}
        t_s1 += stage_ms.get("stage1", 0)
        if s2 is not None:
            t_s2 += s2["wall_ms"]
            tot["s2"] += s2["kept"]
            for k, v in s2["reasons"].items():
                reasons[k] = reasons.get(k, 0) + v
            if s2["in"]:
                per_subject_attrition.append(s2["dropped"] / s2["in"])

        gate = "ok " if rep.bugs_detected == len(rep.bug_matches) else "MISS"
        rows.append(rep)
        if s3 is not None:
            v = s3["verdicts"]
            print(f"[{gate}] {cfg.name:<20} {s1['candidates']:>4} -> {s2['kept']:>3} -> "
                  f"{s3['kept']:>3}  (sat {v.get('sat', 0):>3}, inc {v.get('inconclusive', 0):>2}, "
                  f"unsat {v.get('unsat', 0):>3})  bugs {rep.bugs_detected}/{len(rep.bug_matches)}  "
                  f"traps {rep1.traps_reported}->{rep2.traps_reported}->{rep.traps_reported}"
                  f"/{len(rep.trap_matches)}  [{s3['wall_ms']} ms]")
        elif s2 is None:
            print(f"[{gate}] {cfg.name:<20} {s1['candidates']:>5} cand  "
                  f"bugs {rep.bugs_detected}/{len(rep.bug_matches)}  "
                  f"traps {rep.traps_reported}/{len(rep.trap_matches)}")
        else:
            print(f"[{gate}] {cfg.name:<20} {s1['candidates']:>4} -> {s2['kept']:>3} cand  "
                  f"bugs {rep.bugs_detected}/{len(rep.bug_matches)}  "
                  f"traps {rep1.traps_reported}->{rep.traps_reported}/{len(rep.trap_matches)}")
        for m in rep.bug_matches:
            if not m.detected:
                a = m.annotation
                print(f"        MISSED {a.kind}{a.index} {a.variable} {a.pattern}{a.lines}")

    n = len(rows)
    print()
    print(f"{n}/{len(configs)} subjects analysed")
    if n and through == "stage1":
        print(f"candidates: {tot['s1']} total, {tot['s1'] / n:.1f} per subject")
    elif n:
        print(f"stage 1: {tot['s1']} candidates, {tot['s1'] / n:.1f} per subject  "
              f"[{t_s1} ms total]")
    if through in ("stage2", "stage3") and n:
        dropped = tot["s1"] - tot["s2"]
        print(f"stage 2: {tot['s2']} kept, {dropped} dropped with proof "
              f"({', '.join(f'{k} {v}' for k, v in sorted(reasons.items())) or 'none'})"
              f"  [{t_s2} ms total]")

        def pct(a, b):
            return f"{100 * a / b:.1f}%" if b else "n/a"
        lo = min(per_subject_attrition, default=0)
        hi = max(per_subject_attrition, default=0)
        concurrency = reasons.get("priority", 0) + reasons.get("masking", 0)
        print(f"attrition: {pct(dropped, tot['s1'])} overall; "
              f"{100 * lo:.0f}-{100 * hi:.0f}% per subject")
        print(f"  of which concurrency (priority + masking): "
              f"{pct(concurrency, tot['s1'])}; no-path is stage 1's cross-function "
              f"may-precede refined, not a concurrency result")
        print("  for scale: IntRace reports 54.2% (33-63% per project) for its stage 2, "
              "on another candidate class, in real-world subjects")
    if through == "stage3" and n:
        def pct3(a, b):
            return f"{100 * a / b:.1f}%" if b else "n/a"
        print(f"solver: {s3tot['in']} in -> {verdicts.get('sat', 0)} sat, "
              f"{verdicts.get('inconclusive', 0)} inconclusive, {verdicts.get('unsat', 0)} unsat "
              f"(dropped with proof)  [{s3tot['ms']} ms total]")
        print(f"reaching the LLM: {s3tot['kept']}, "
              f"{s3tot['kept'] / n:.1f} per subject; solver attrition "
              f"{pct3(verdicts.get('unsat', 0), s3tot['in'])}")
        print("  for scale: IntRace reports 86.2% (41-93%) for its feasibility stage, on "
              "another candidate class, in real-world subjects")
        print(f"funnel: {tot['s1']} -> {tot['s2']} -> {s3tot['kept']}  "
              f"[stage 1 {t_s1} ms, stage 2 {t_s2} ms, solver {s3tot['ms']} ms]")
        slow = sorted(slowest, reverse=True)[:3]
        print("slowest subjects in the solver: "
              + ", ".join(f"{name} {ms} ms" for ms, name in slow))
    print(f"RECALL GATE{'' if through == 'stage1' else ' (' + through + ')'}: "
          f"{bugs_found}/{bugs_total} annotated bug points present "
          f"-- {'PASS' if bugs_found == bugs_total and bugs_total else 'FAIL'}")
    if through == "stage3":
        print(f"traps reported: {traps_s1}/{traps_total} after stage 1, "
              f"{traps_s2}/{traps_total} after stage 2, {traps_s3}/{traps_total} reaching the "
              f"LLM ({traps_s2 - traps_s3} refuted by the solver)")
    elif through == "stage2":
        print(f"traps reported: {traps_s1}/{traps_total} after stage 1, "
              f"{traps_s2}/{traps_total} after stage 2 "
              f"({traps_s1 - traps_s2} rejected by stage 2)")
    else:
        print(f"traps reported: {traps_s1}/{traps_total} "
              "(expected to be high; stage 1 does not filter)")
    ratios = [x for x in (inspection_ratio(r) for r in rows) if x is not None]
    if ratios:
        print(f"inspection ratio: {sum(ratios) / len(ratios):.2f} mean over "
              f"{len(ratios)} subject(s) whose bug points were all found")
    if through == "stage1":
        print("for scale: IntRace reports ~208 candidates per program, on real-world "
              "subjects rather than these 37-97 line cases")
    print(f"runstore check: {n - len({p.split(':')[0] for p in problems})}/{n} runs "
          "conform to C3 (rule 6: nothing vanished without a proof)")
    for p in problems:
        print(f"  ! {p}")
    for name, msg in failures:
        print(f"  FAILED {name}: {msg}")
    ok = bugs_total and bugs_found == bugs_total and not failures and not problems
    return 0 if ok else 1


def cmd_stage1_all(args: argparse.Namespace) -> int:
    """Stage 1 over every Racebench case, then the recall gate (W3-W4 done-when)."""
    return _bench_run(args, "stage1")


def cmd_stage3_all(args: argparse.Namespace) -> int:
    """Stages 1-3 over every Racebench case: the full funnel to the LLM, with
    per-stage timings, and the recall gate on what reaches it (W6-W7 done-when)."""
    return _bench_run(args, "stage3")


def cmd_stage2_all(args: argparse.Namespace) -> int:
    """Stages 1 and 2 over every Racebench case, the recall gate on what stage 2
    keeps, and attrition against IntRace's 54.2% (W5 done-when)."""
    return _bench_run(args, "stage2")


# -- run store ------------------------------------------------------------


def cmd_runstore_check(args: argparse.Namespace) -> int:
    targets = [Path(p) for p in args.run] if args.run else find_runs(Path(args.run_root))
    if not targets:
        return _err("no runs found")
    failures = 0
    for t in targets:
        problems = RunStore(t).check()
        if problems:
            failures += 1
            print(f"[FAIL] {t}")
            for p in problems:
                print(f"       {p}")
        else:
            print(f"[ok  ] {t}")
    return 1 if failures else 0


# -- benchmark ------------------------------------------------------------


def cmd_bench_gen(args: argparse.Namespace) -> int:
    from .racebench import generate

    suite = Path(args.suite)
    if not (suite / "README.md").exists():
        return _err(f"{suite} does not look like racebench/2.1_remarks")
    written = generate(suite, Path(args.out))
    print(f"wrote {len(written)} configuration(s) to {args.out}")
    return 0


def cmd_bench_build_all(args: argparse.Namespace) -> int:
    configs = sorted(Path(args.configs).glob("*.yaml"))
    if not configs:
        return _err(f"no configurations in {args.configs}; run `irqrace bench gen-configs`")

    ok, failed, warned = [], [], []
    for path in configs:
        try:
            cfg = Config.load(path)
            store = RunStore.create(cfg, run_root=args.run_root)
            result = _do_build(cfg, store)
            report = probe(result.bitcode, cfg) if args.probe else None
        except (ConfigError, BuildError, ProbeError) as e:
            failed.append((path.stem, str(e).splitlines()[0]))
            print(f"[FAIL] {path.stem}: {str(e).splitlines()[0]}")
            continue

        if report is None:
            ok.append(path.stem)
            print(f"[ok  ] {path.stem}")
            continue

        (store.root / "build" / "probe.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        )
        ok.append(path.stem)
        flag = ""
        serious = [w for w in report["warnings"] if w.get("severity", "warn") != "info"]
        if serious:
            warned.append(path.stem)
        if report["warnings"]:
            flag = "  ! " + "; ".join(
                f"{w['code']}({w.get('severity', 'warn')})" for w in report["warnings"]
            )
        print(f"[ok  ] {path.stem}: {report['globals_count']} globals, "
              f"{report['functions_with_bodies']} functions{flag}")

    print(f"\n{len(ok)}/{len(configs)} subjects built"
          + (" to bitcode and probed" if args.probe else " to bitcode"))
    if warned:
        print(f"{len(warned)} with warnings above info level: {', '.join(warned)}")
    for name, msg in failed:
        print(f"  FAILED {name}: {msg}")
    return 1 if failed else 0


# -- ground truth ---------------------------------------------------------


def cmd_groundtruth_parse(args: argparse.Namespace) -> int:
    from .groundtruth import apply_errata, load_errata, parse_suite

    suite = parse_suite(Path(args.suite))
    before = suite.shape_distribution()
    applied: list[str] = []
    if not args.raw:
        applied = apply_errata(suite, load_errata(Path(args.errata)))
    after = suite.shape_distribution()

    if args.json:
        print(json.dumps({
            "bug_points": len(suite.bugs), "traps": len(suite.traps),
            "cases": len(suite.cases), "errata_applied": len(applied),
            "shapes": after,
            "anomalies": [vars(a) for a in suite.anomalies],
        }, indent=2, ensure_ascii=False))
        return 0

    label = "as written" if args.raw else "with errata applied"
    print(f"{len(suite.cases)} cases, {label}: "
          f"{len(suite.bugs)} bug points, {len(suite.traps)} traps")
    print()
    print("shape   bug trap")
    for k in sorted(set(before) | set(after)):
        a = after.get(k, {"bug": 0, "trap": 0})
        b = before.get(k, {"bug": 0, "trap": 0})
        shift = "" if a == b else f"   (as written: {b['bug']}/{b['trap']})"
        print(f"  {k:<5} {a['bug']:>3} {a['trap']:>4}{shift}")

    if applied and args.verbose:
        print()
        print(f"{len(applied)} correction(s) applied:")
        for line in applied:
            print(f"  {line}")

    counts: dict[str, int] = {}
    for x in suite.anomalies:
        counts[x.code] = counts.get(x.code, 0) + 1
    if counts:
        print()
        print("tolerated deviations:")
        for code, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>3}  {code}")
    if args.verbose:
        for x in suite.anomalies:
            print(f"  {x.case}:{x.line} [{x.code}] {x.detail}")
    return 0


def cmd_groundtruth_certify(args: argparse.Namespace) -> int:
    """Check the parser against the written hand count, not against itself."""
    from .groundtruth import parse_suite

    suite = parse_suite(Path(args.suite))
    bad = 0
    for case, (bugs, traps) in sorted(HAND_COUNT.items()):
        got = suite.by_case(case)
        ok = (len(got.bugs), len(got.traps)) == (bugs, traps)
        bad += not ok
        mark = "ok  " if ok else "FAIL"
        print(f"[{mark}] {case}: hand {bugs} bug / {traps} trap, "
              f"parser {len(got.bugs)} / {len(got.traps)}")
    hb = sum(v[0] for v in HAND_COUNT.values())
    ht = sum(v[1] for v in HAND_COUNT.values())
    print(f"       hand-counted total: {hb} bug, {ht} trap")
    print(f"       whole suite: {len(suite.bugs)} bug, {len(suite.traps)} trap "
          f"(expected 48 / 38)")
    if (len(suite.bugs), len(suite.traps)) != (48, 38):
        print("       ! suite total does not match the certified figures")
        bad += 1
    return 1 if bad else 0


def cmd_groundtruth_errata(args: argparse.Namespace) -> int:
    from .groundtruth import apply_errata, load_errata, parse_suite

    corrections = load_errata(Path(args.errata))
    suite = parse_suite(Path(args.suite))
    report = apply_errata(suite, corrections)
    for corr, line in zip(corrections, report):
        print(f"[{corr.confidence:<7}] {line}")
        if args.verbose:
            print(f"            as written: {corr.as_written}")
            print(f"            {corr.evidence}")
    print(f"{len(corrections)} correction(s); "
          f"totals unchanged at {len(suite.bugs)} bug / {len(suite.traps)} trap")
    return 0


# -- parser ---------------------------------------------------------------


# -- LLM stage (Track B) --------------------------------------------------


def cmd_llm_fixtures(args: argparse.Namespace) -> int:
    """Report the labelled set. Non-zero while it is short of W1's 10 + 10.

    Exiting non-zero on an incomplete set is deliberate: the fixtures are the
    input to every measured row, and a row scored against a partial set is a
    number that will be quoted later without the caveat.
    """
    from .llm.fixtures import FixtureError, coverage, load_all

    try:
        fixtures = load_all()
    except FixtureError as e:
        return _err(str(e))

    cov = coverage(fixtures)
    print(cov.report())
    for f in fixtures:
        print(f"  [{f.label:10}] {f.candidate_id}  {f.subject}  {f.annotation}")
    if not cov.complete:
        print(
            f"\nshort of Roadmap W1: need {10 - cov.bug_points} more bug point(s) "
            f"and {10 - cov.traps} more trap(s)"
        )
    return 0 if cov.complete else 1


def cmd_llm_prompts(args: argparse.Namespace) -> int:
    from .llm.prompts import ABLATION, BY_NAME, DEFERRED

    if args.row is None:
        for c in ABLATION:
            on = [
                n
                for n, v in (
                    ("domain", c.domain_rules),
                    ("progressive", c.progressive),
                    ("decomposition", c.decomposition),
                    ("self-validation", c.self_validation),
                )
                if v
            ]
            print(f"{c.name:18} {c.hash()}  {', '.join(on) or 'baseline'}")
        return 0

    if args.row in DEFERRED:
        return _err(f"row {args.row!r} is deferred until the static pipeline exists")
    if args.row not in BY_NAME:
        return _err(f"unknown row {args.row!r}; known: {', '.join(BY_NAME)}")
    print(BY_NAME[args.row].system_prompt())
    return 0


def cmd_llm_backends(args: argparse.Namespace) -> int:
    """List the providers, or report one spec's capabilities and caveats.

    The caveats are the point. Structured-output tier and prompt caching differ
    per provider and both land in the ablation's cost and comparability, so
    they are printed next to the spec rather than discovered in a footnote.
    """
    from .llm.backends import REGISTRY, BackendError, from_spec

    if not args.spec:
        print("providers:")
        for name in sorted(REGISTRY):
            print(f"  {name}")
        print(
            "\nspec form: provider:model  (e.g. anthropic:claude-opus-5, "
            "openai:gpt-4o, ollama:qwen2.5-coder:32b)\n"
            "any OpenAI-compatible endpoint - Groq, Together, OpenRouter, "
            "LiteLLM, vLLM, LM Studio —\nis reachable as 'openai:<model>' with "
            "IRQRACE_OPENAI_BASE_URL set.\n"
            "'claude-cli:<model>' (e.g. claude-cli:sonnet) runs `claude -p` on "
            "your Claude Pro/Max login:\ndrawn from the plan's usage limits, "
            "not billed per token."
        )
        return 0

    try:
        backend = from_spec(args.spec)
    except BackendError as e:
        return _err(str(e))

    caps = backend.capabilities
    print(f"{backend.spec}")
    print(f"  structured output: {caps.structured.value}")
    print(f"  prompt caching:    {caps.prompt_caching}")
    print(f"  temperature:       {caps.temperature}")
    for caveat in caps.caveats():
        print(f"  [!] {caveat}")
    return 0


def cmd_llm_triage(args: argparse.Namespace) -> int:
    """Triage a C3 run directory or a single C2 context record."""
    from .llm.backends import BackendError, RefusalError, from_spec
    from .llm.cache import Cache
    from .llm.client import TriageClient
    from .llm.pipeline import triage_store
    from .llm.prompts import BY_NAME, DEFERRED
    from .llm.resolver import resolver_for

    all_rows = {**BY_NAME, **DEFERRED}
    if args.row not in all_rows:
        return _err(f"unknown row {args.row!r}; known: {', '.join(all_rows)}")
    config = all_rows[args.row]

    try:
        backend = from_spec(args.backend)
    except BackendError as e:
        return _err(str(e))

    cache = Cache(enabled=not args.no_cache)
    target = Path(args.target)

    if target.is_dir():
        store = RunStore(target)
        try:
            summary = triage_store(
                store,
                config=config,
                backend=backend,
                cache=cache,
                samples=args.samples,
                resolver_mode=args.resolver,
            )
        except (BackendError, RefusalError) as e:
            return _err(str(e))
        if args.json:
            doc = {
                k: v
                for k, v in summary.items()
                if k not in ("triages", "spend")
            }
            doc["triages"] = [
                {**t.model_dump(mode="json"), "bucket": t.bucket.value}
                for t in summary["triages"]
            ]
            print(json.dumps(doc, indent=2, ensure_ascii=False))
            return 0
        n_untriaged = summary["not_triaged"]
        print(
            f"{summary['run_id']}: {summary['candidates_out'] - n_untriaged}/"
            f"{summary['candidates_in']} triaged ({summary['backend']}, {summary['config']})"
            + (f"; {n_untriaged} NOT TRIAGED, kept as uncertain" if n_untriaged else "")
        )
        for t in summary["triages"]:
            if t.not_triaged:
                print(f"  [{t.bucket.value:<17}] {t.candidate_id}  NOT TRIAGED: {t.not_triaged}")
            else:
                print(f"  [{t.bucket.value:<17}] {t.candidate_id}  conf={t.feasibility.confidence:.2f}")
        return 0

    if not target.is_file():
        return _err(f"{target} does not exist")

    record = json.loads(target.read_text(encoding="utf-8"))
    client = TriageClient(config, backend=backend, cache=cache)
    resolver = resolver_for(record, mode=args.resolver)
    try:
        verdict = client.triage(record, resolver=resolver)
    except (BackendError, RefusalError) as e:
        return _err(str(e))

    doc = {**verdict.model_dump(mode="json"), "bucket": verdict.bucket.value}
    if args.json:
        print(json.dumps(doc, indent=2, ensure_ascii=False))
    else:
        print(f"[{verdict.bucket.value}] {verdict.candidate_id}")
        print(f"  feasibility: {verdict.feasibility.verdict.value} ({verdict.feasibility.confidence:.2f})")
        if verdict.harmfulness is not None:
            print(f"  harmfulness: {verdict.harmfulness.verdict.value} ({verdict.harmfulness.confidence:.2f})")
        print(f"  reasoning:   {verdict.feasibility.reasoning}")
    return 0


def cmd_llm_repair(args: argparse.Namespace) -> int:
    """Propose an interrupt-specific fix for a C3 run directory or a C2 record."""
    from .llm.backends import BackendError, RefusalError, from_spec
    from .llm.cache import Cache
    from .llm.pipeline import repair_store
    from .llm.prompts import BY_NAME, DEFERRED
    from .llm.repair import RepairClient, witness_problems

    all_rows = {**BY_NAME, **DEFERRED}
    if args.row not in all_rows:
        return _err(f"unknown row {args.row!r}; known: {', '.join(all_rows)}")
    config = all_rows[args.row]

    try:
        backend = from_spec(args.backend)
    except BackendError as e:
        return _err(str(e))

    cache = Cache(enabled=not args.no_cache)
    target = Path(args.target)

    if target.is_dir():
        store = RunStore(target)
        try:
            summary = repair_store(
                store, config=config, backend=backend, cache=cache
            )
        except (BackendError, RefusalError, RuntimeError) as e:
            return _err(str(e))
        if args.json:
            doc = {
                k: v
                for k, v in summary.items()
                if k not in ("patches", "spend")
            }
            doc["patches"] = {
                cid: p.model_dump(mode="json")
                for cid, p in summary["patches"].items()
            }
            print(json.dumps(doc, indent=2, ensure_ascii=False))
            return 0
        print(
            f"{summary['run_id']}: {summary['candidates_out']}/{summary['candidates_in']} "
            f"repaired ({summary['backend']}, {summary['config']})"
        )
        for cid, p in summary["patches"].items():
            print(
                f"  [{p.strategy.value:<15}] {cid}  irqs={p.masked_irqs}  "
                f"lines={p.covers_from_line}..{p.covers_to_line}"
            )
        return 0

    if not target.is_file():
        return _err(f"{target} does not exist")

    record = json.loads(target.read_text(encoding="utf-8"))
    client = RepairClient(config, backend=backend, cache=cache)
    try:
        patch = client.repair(record)
    except (BackendError, RefusalError, RuntimeError) as e:
        return _err(str(e))

    problems = witness_problems(patch, record)
    if args.json:
        print(
            json.dumps(
                {**patch.model_dump(mode="json"), "witness_problems": problems},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"[{patch.strategy.value}] {record['id']}  irqs={patch.masked_irqs}  "
            f"lines={patch.covers_from_line}..{patch.covers_to_line}"
        )
        print(f"  witness: {patch.witness.firing_flow} @ {patch.witness.preemption_point}")
        print(f"  latency: {patch.latency_note}")
        if problems:
            for prob in problems:
                print(f"  ! witness problem: {prob}")
        print(patch.diff)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="irqrace", description=__doc__)
    p.add_argument("--version", action="version", version=f"irqrace {TOOL_VERSION}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="report the state of the toolchain").set_defaults(
        func=cmd_doctor
    )

    c = sub.add_parser("contracts", help="the frozen contracts C1-C4")
    cs = c.add_subparsers(dest="sub", required=True)
    cs.add_parser("validate", help="validate every example against its schema").set_defaults(
        func=cmd_contracts_validate
    )

    g = sub.add_parser("config", help="C1 configuration files")
    gs = g.add_subparsers(dest="sub", required=True)
    gv = gs.add_parser("validate", help="load, default and check a configuration")
    gv.add_argument("config", nargs="+")
    gv.set_defaults(func=cmd_config_validate)
    gsh = gs.add_parser("show", help="print the fully resolved configuration")
    gsh.add_argument("config")
    gsh.set_defaults(func=cmd_config_show)

    b = sub.add_parser("build", help="build a subject to whole-program bitcode")
    b.add_argument("config")
    b.add_argument("--run-root", default=None)
    b.set_defaults(func=cmd_build)

    pr = sub.add_parser("probe", help="build, then report what SVF sees in the module")
    pr.add_argument("config")
    pr.add_argument("--run-root", default=None)
    pr.add_argument("--json", action="store_true")
    pr.set_defaults(func=cmd_probe)

    s1 = sub.add_parser("stage1", help="run stage 1 on one subject")
    s1.add_argument("config")
    s1.add_argument("--run-root", default=None)
    s1.set_defaults(func=cmd_stage1)

    s2 = sub.add_parser("stage2", help="run stages 1 and 2 on one subject")
    s2.add_argument("config")
    s2.add_argument("--run-root", default=None)
    s2.add_argument("--verbose", "-v", action="store_true", help="print every drop and its proof")
    s2.set_defaults(func=cmd_stage2)

    s3 = sub.add_parser("stage3", help="run stages 1-3 on one subject")
    s3.add_argument("config")
    s3.add_argument("--run-root", default=None)
    s3.add_argument("--verbose", "-v", action="store_true", help="print every verdict")
    s3.set_defaults(func=cmd_stage3)

    for name, fn, helptext in (
        ("stage1-all", cmd_stage1_all, "stage 1 over every Racebench case, then the recall gate"),
        ("stage2-all", cmd_stage2_all,
         "stages 1 and 2 over every Racebench case, the recall gate, and attrition"),
        ("stage3-all", cmd_stage3_all,
         "stages 1-3 over every Racebench case: the funnel to the LLM and the recall gate"),
    ):
        sa = sub.add_parser(name, help=helptext)
        sa.add_argument("--configs", default=str(BENCH_CONFIGS))
        sa.add_argument("--suite", default=str(DEFAULT_SUITE))
        sa.add_argument("--errata", default=str(ERRATA))
        sa.add_argument("--run-root", default="runs")
        sa.set_defaults(func=fn)

    r = sub.add_parser("runstore", help="the C3 run store")
    rs = r.add_subparsers(dest="sub", required=True)
    rc = rs.add_parser("check", help="verify runs against contract C3")
    rc.add_argument("run", nargs="*")
    rc.add_argument("--run-root", default="runs")
    rc.set_defaults(func=cmd_runstore_check)

    gtp = sub.add_parser("groundtruth", help="Racebench's annotated ground truth")
    gts = gtp.add_subparsers(dest="sub", required=True)
    for name, fn, helptext in (
        ("parse", cmd_groundtruth_parse, "parse the annotations and report what was tolerated"),
        ("certify", cmd_groundtruth_certify, "check the parser against the hand count"),
        ("errata", cmd_groundtruth_errata, "list the curated corrections and their evidence"),
    ):
        sp = gts.add_parser(name, help=helptext)
        sp.add_argument("--suite", default=str(DEFAULT_SUITE))
        sp.add_argument("--errata", default=str(ERRATA))
        sp.add_argument("--raw", action="store_true",
                        help="do not apply the errata; report the annotations as shipped")
        sp.add_argument("--verbose", "-v", action="store_true")
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)

    bn = sub.add_parser("bench", help="Racebench")
    bs = bn.add_subparsers(dest="sub", required=True)
    bg = bs.add_parser("gen-configs", help="generate one C1 file per simple case")
    bg.add_argument("--suite", default=str(DEFAULT_SUITE))
    bg.add_argument("--out", default=str(BENCH_CONFIGS))
    bg.set_defaults(func=cmd_bench_gen)
    ba = bs.add_parser("build-all", help="build every case, and optionally probe it")
    ba.add_argument("--configs", default=str(BENCH_CONFIGS))
    ba.add_argument("--run-root", default="runs")
    ba.add_argument("--probe", action="store_true")
    ba.set_defaults(func=cmd_bench_build_all)

    m = sub.add_parser("llm", help="Track B — the triage and repair stage")
    ms = m.add_subparsers(dest="sub", required=True)
    mf = ms.add_parser("fixtures", help="report the labelled fixture set")
    mf.set_defaults(func=cmd_llm_fixtures)
    mp = ms.add_parser("prompts", help="list the ablation rows, or print one")
    mp.add_argument("row", nargs="?", help="row name, e.g. '+self-validation'")
    mp.set_defaults(func=cmd_llm_prompts)
    mb = ms.add_parser("backends", help="list providers, or inspect one spec")
    mb.add_argument("spec", nargs="?", help="provider:model, e.g. ollama:llama3")
    mb.set_defaults(func=cmd_llm_backends)

    mt = ms.add_parser("triage", help="triage a C3 run directory or C2 context record")
    mt.add_argument("target", help="path to a C3 run directory or C2 .json file")
    mt.add_argument("--backend", default="anthropic:claude-opus-5")
    mt.add_argument("--row", default="+self-validation")
    mt.add_argument("--samples", type=int, default=1)
    mt.add_argument("--resolver", choices=("mock", "source", "auto"), default="auto")
    mt.add_argument("--no-cache", action="store_true")
    mt.add_argument("--json", action="store_true")
    mt.set_defaults(func=cmd_llm_triage)

    mr = ms.add_parser("repair", help="propose a fix for a C3 run directory or C2 record")
    mr.add_argument("target", help="path to a C3 run directory or C2 .json file")
    mr.add_argument("--backend", default="anthropic:claude-opus-5")
    mr.add_argument("--row", default="+self-validation")
    mr.add_argument("--no-cache", action="store_true")
    mr.add_argument("--json", action="store_true")
    mr.set_defaults(func=cmd_llm_repair)

    ui = sub.add_parser("ui", help="launch the Streamlit pipeline visualizer and dashboard")
    ui.add_argument("--port", type=int, default=8501)
    ui.add_argument("--headless", action="store_true")
    ui.set_defaults(func=cmd_ui)

    gui = sub.add_parser("gui", help="launch the native Windows (Win32/Tkinter) MVP GUI")
    gui.set_defaults(func=cmd_gui)

    return p


def cmd_gui(args: argparse.Namespace) -> int:
    """Launch the native Windows (Win32/Tkinter) MVP application."""
    from .ui.desktop import main as desktop_main

    desktop_main()
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    """Launch the Streamlit dashboard over the C3 run store."""
    import subprocess

    app_path = Path(__file__).resolve().parent / "ui" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(args.port),
    ]
    if args.headless:
        cmd.extend(["--server.headless", "true"])
    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except contracts.ContractError as e:
        return _err(str(e))
    except ConfigError as e:
        return _err(str(e))


if __name__ == "__main__":
    raise SystemExit(main())
