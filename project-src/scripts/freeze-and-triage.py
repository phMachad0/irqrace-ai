#!/usr/bin/env python3
"""Freeze the static stages once; triage independent copies of them, in series.

    # 1. once, in WSL, from the checkout of the commit being frozen:
    python3 scripts/freeze-and-triage.py freeze --run-root runs/frozen-YYYYMMDD

    # 2. on Windows (where the `claude` CLI lives), from the same commit:
    python scripts/freeze-and-triage.py triage --frozen runs/frozen-YYYYMMDD \\
        --out runs/m1-YYYYMMDD --rows +racebench,+racebench+c4 --samples 3 \\
        --backend claude-cli:sonnet --workers 4 [--dry-run]

    # 3. score every pair (and S1, which every pair contains):
    python scripts/bench-triage-report.py runs/m1-YYYYMMDD/*/* --results results/m1

**freeze** runs ``irqrace pipeline <config> --through context --run-root ROOT``
for every ``bench/configs/*.yaml`` -- the same ``PipelineStepper`` the desktop
app's Racebench screen drives, so the run directories are the ones that screen
would leave -- one case at a time, with a per-case timeout and log, then writes
``timings.tsv``, ``start.txt`` / ``end.txt`` and ``freeze.json`` (commit, dirty
flag, platform) and checks that every case reached ``context`` and none was
triaged.

**triage** copies the frozen root once per (prompt row, sample k) into
``OUT/<row>/<k>/`` and runs ``irqrace llm triage <case_run_dir> --row ROW
--backend SPEC --samples 1 --workers W`` on every case of the copy. ``--samples``
of ``llm triage`` is majority voting inside one run, not independent runs;
independence comes from the copies. Pairs run strictly in series, interleaved by
sample. A pair is marked ``failed`` in its ``batch.json`` if any case fails,
times out, or reports not-triaged candidates; the scorer refuses failed pairs.
Each pair gets ``timings.tsv`` (case, start epoch, end epoch, exit code) as
``bench-triage-report.py`` reads it, and one log per case in ``logs/``, which
also carries the triage's token spend (the ``spend:`` line).

**Running the freeze in WSL.** The static toolchain (clang-14, SVF, the built
``analysis/build/bin`` binaries, Z3) is installed in WSL only, and
``C:/Users/luoma/Desktop/irqrace-wsl.cmd`` opens a login shell already cd'ed
into the *main* checkout's ``project-src`` (``/etc/profile.d/irqrace.sh`` puts
that checkout's ``src`` on ``PYTHONPATH`` and its ``analysis/build/bin`` on
``PATH``). So: check out the commit to freeze in the main checkout, rebuild
``analysis/`` if the C++ changed, then from Windows::

    C:\\Users\\luoma\\Desktop\\irqrace-wsl.cmd python3 scripts/freeze-and-triage.py freeze --run-root runs/frozen-YYYYMMDD

A git worktree elsewhere has no ``analysis/build`` and would mix its Python with
the main checkout's binaries; freeze from the checkout of the frozen commit, and
triage from the same commit (the prompts live in ``src/``). The child processes
get this checkout's ``src`` first on ``PYTHONPATH`` and **no
``IRQRACE_RACEBENCH``**: WSL's profile points it at the pristine ``../racebench``
checkout (no 006 patch, no 2026-10-28 relabel), which would silently change the
ground truth in ``eval/report.json`` and the sources the C4 resolver shows the
model. ``--keep-racebench-env`` keeps it, on purpose.

**No LLM result cache exists** (removed 2026-10-30): every triage is a fresh
call. A stale ``project-src/.llm-cache/`` directory may remain outside git;
nothing reads it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irqrace import bench_batch as bb  # noqa: E402


def _rows(values: list[str]) -> list[str]:
    return [r for v in values for r in v.split(",") if r]


def cmd_freeze(args: argparse.Namespace) -> int:
    configs = sorted(Path(args.configs).glob("*.yaml"))
    if args.cases:
        keep = set(_rows(args.cases))
        configs = [c for c in configs if c.stem in keep]
    if not configs:
        print(f"error: no configs in {args.configs}", file=sys.stderr)
        return 2
    env = bb.child_env(keep_racebench_env=args.keep_racebench_env)
    if args.dry_run:
        print(f"freeze {len(configs)} case(s) into {Path(args.run_root).resolve()}, "
              f"{args.case_timeout:.0f} s each, IRQRACE_RACEBENCH={env.get('IRQRACE_RACEBENCH')!r}:")
        for c in configs:
            print("  " + " ".join([args.python, "-m", "irqrace", "pipeline", str(c.resolve()),
                                   "--through", "context", "--run-root", str(Path(args.run_root).resolve())]))
        return 0
    try:
        doc = bb.freeze(configs, Path(args.run_root), python=args.python, case_timeout=args.case_timeout,
                        env=env, log=lambda m: print(m, flush=True))
    except bb.BatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"freeze {doc['status']}: {args.run_root} at {doc['git_commit']}"
          + (" (dirty tree)" if doc["git_dirty"] else ""))
    for f in doc["failures"]:
        print(f"  FAILED {f['case']}: {f['reason']}")
    return 0 if doc["status"] == "ok" else 1


def cmd_triage(args: argparse.Namespace) -> int:
    rows = _rows(args.rows)
    try:
        pairs = bb.plan(Path(args.out), rows, args.samples)
        cases = bb.frozen_cases(Path(args.frozen))
    except bb.BatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(bb.describe_plan(pairs, cases, backend=args.backend, workers=args.workers,
                           case_timeout=args.case_timeout, python=args.python), flush=True)
    if args.dry_run:
        return 0
    env = bb.child_env(keep_racebench_env=args.keep_racebench_env)
    try:
        docs = bb.run_plan(pairs, Path(args.frozen), backend=args.backend, workers=args.workers,
                           case_timeout=args.case_timeout, python=args.python, resume=args.resume,
                           keep_going=args.keep_going, env=env, log=lambda m: print(m, flush=True))
    except bb.BatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    bad = [d for d in docs if d["status"] != "ok"]
    print(f"{len(docs) - len(bad)} pair(s) ok, {len(bad)} failed" + (": " + ", ".join(d["run_id"] for d in bad) if bad else ""))
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Freeze the static stages; triage independent copies.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--python", default=sys.executable, help="interpreter for the irqrace children")
    common.add_argument("--case-timeout", type=float, default=None, help="hard limit per case, seconds")
    common.add_argument("--keep-racebench-env", action="store_true",
                        help="pass IRQRACE_RACEBENCH through to the children (dropped by default)")
    common.add_argument("--dry-run", action="store_true", help="print the plan and stop")

    fz = sub.add_parser("freeze", parents=[common], help="run stages 1-3 + context once per case")
    fz.add_argument("--run-root", required=True)
    fz.add_argument("--configs", default=str(bb.CONFIGS))
    fz.add_argument("--cases", action="append", help="only these config stems (comma-separated)")
    fz.set_defaults(func=cmd_freeze, default_timeout=900.0)

    tr = sub.add_parser("triage", parents=[common], help="triage copies of a frozen root")
    tr.add_argument("--frozen", required=True, help="the frozen static run root")
    tr.add_argument("--out", required=True, help="pairs go to OUT/<row>/<k>/")
    tr.add_argument("--rows", action="append", required=True, help="prompt rows, comma-separated")
    tr.add_argument("--samples", type=int, default=3, help="independent runs per row")
    tr.add_argument("--backend", required=True, help="provider:model, e.g. claude-cli:sonnet")
    tr.add_argument("--workers", type=int, default=4, help="conversations at a time inside one case")
    tr.add_argument("--resume", action="store_true", help="skip pairs whose batch.json says ok")
    tr.add_argument("--keep-going", action="store_true", help="continue after a failed pair")
    tr.set_defaults(func=cmd_triage, default_timeout=3600.0)

    args = ap.parse_args(argv)
    if args.case_timeout is None:
        args.case_timeout = args.default_timeout
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
