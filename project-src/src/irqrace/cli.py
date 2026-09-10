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
        "c1-": "c1", "c2-": "c2", "c3-manifest": "c3-manifest",
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


# -- parser ---------------------------------------------------------------


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

    r = sub.add_parser("runstore", help="the C3 run store")
    rs = r.add_subparsers(dest="sub", required=True)
    rc = rs.add_parser("check", help="verify runs against contract C3")
    rc.add_argument("run", nargs="*")
    rc.add_argument("--run-root", default="runs")
    rc.set_defaults(func=cmd_runstore_check)

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

    return p


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
