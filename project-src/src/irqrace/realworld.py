"""The 18 real-world programs: C1 generation, ground truth and the recall gate.

The suite is vendored at ``bench/realworld`` (zhvngyuan/NIChecker at 40267c0; see
``bench/realworld/VENDORED.md``). Each program is one ``main.c`` with a
``priority.info`` and a ``violation.info``. What differs from Racebench, and is
encoded here:

* ``priority.info`` names a flow ``task_measure`` while its function is
  ``task_measure_isr``, and never names ``main``. The entry is ``<name>_isr`` and
  ``main`` is a task at priority 0, as BMC4AV's copy of the same files states
  (``main:0``). A wrong entry name is not cosmetic: the flow would contribute no
  accesses, silently -- the same failure as Racebench's 028/030 README entries,
  and ``irqrace probe``'s R7 check is what catches it.
* Masking is ``disable_isr(-1)`` / ``enable_isr(-1)`` only (all 15 call pairs use
  ``-1``), so the IRQ numbers assigned below -- 1..n in file order -- never decide
  anything. ``main`` masks around its initialisation; nothing calls an ``init()``
  first, so the state at flow entry is ``unknown`` rather than Racebench's
  ``all-enabled`` (Soundness Assumptions F5).
* The ground truth is mostly **per variable and pattern**
  (``true violation int numberOfRecords rww``), coarser than Racebench's
  per-instance lines. ``blink1-3`` are the exception and annotate instances
  (``timerCount(95W,121W,96R)``). Both are matched, each at its own grain.
* Six programs do not compile as shipped; ``bench/realworld-errata.yaml`` lists
  the preprocessor definitions and flags that fix them without touching the source.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .config import SCHEMA_VERSION

VENDORED_SUITE = Path(__file__).resolve().parents[2] / "bench" / "realworld"
ERRATA = Path(__file__).resolve().parents[2] / "bench" / "realworld-errata.yaml"
CONFIGS = Path(__file__).resolve().parents[2] / "bench" / "configs-realworld"

PROGRAMS = [
    "logger1", "logger2", "logger3",
    "blink1", "blink2", "blink3",
    "brake1", "brake2", "brake3",
    "i2c_pca_isa_1", "i2c_pca_isa_2", "i2c_pca_isa_3",
    "i8xx_tco_1", "i8xx_tco_2", "i8xx_tco_3",
    "wdt_pci_1", "wdt_pci_2", "wdt_pci_3",
]

#: The variant name of a configuration generated from BMC4AV's priorities.
ALT_SUFFIX = "__bmc4av-prio"


class RealWorldError(RuntimeError):
    pass


def locate_suite() -> Path | None:
    """``bench/realworld``, or ``IRQRACE_REALWORLD`` if set (never a silent fallback)."""
    if env := os.environ.get("IRQRACE_REALWORLD"):
        path = Path(env)
        return path if path.is_dir() else None
    return VENDORED_SUITE if VENDORED_SUITE.is_dir() else None


def load_errata(path: Path = ERRATA) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


# -- priority.info ----------------------------------------------------------

def parse_priority(path: Path) -> list[tuple[str, int]]:
    """``name:priority`` per line, in file order; ``_isr`` stripped if present."""
    out: list[tuple[str, int]] = []
    for tok in path.read_text(encoding="utf-8").split():
        name, _, prio = tok.partition(":")
        if not prio:
            raise RealWorldError(f"{path}: cannot read {tok!r}")
        out.append((name.removesuffix("_isr"), int(prio)))
    return out


# -- violation.info ---------------------------------------------------------

@dataclass(frozen=True)
class Access:
    lines: tuple[int, ...]   # alternatives: "123/136W" -> (123, 136)
    kind: str                # "read" | "write"


@dataclass(frozen=True)
class Entry:
    """One ground-truth line. ``accesses`` is set for instance entries only."""

    program: str
    index: int
    label: str               # "bug" (true violation) | "trap" (false violation)
    variable: str            # base object: test_global_array[9000] -> test_global_array
    pattern: str             # RWR | RWW | WWR | WRW
    accesses: tuple[Access, ...] | None = None
    raw: str = ""

    @property
    def is_instance(self) -> bool:
        return self.accesses is not None


LABEL_RE = re.compile(r"^\s*(true|false)\s+violation\s*:?\s*(.*)$")
VAR_RE = re.compile(r"^(?:int\s+)?([A-Za-z_]\w*)(?:\[[^\]]*\])?\s+([rwRW]{3})\s*$")
INST_RE = re.compile(r"^([A-Za-z_]\w*)\(([^)]*)\)\s*$")
ACC_RE = re.compile(r"^([\d/]+)\s*([RW])$")


def _instance(var: str, body: str) -> tuple[tuple[Access, ...], str]:
    parts = [p.strip() for p in body.split(",")]
    if len(parts) != 3:
        raise RealWorldError(f"{var}({body}): expected three accesses")
    accs = []
    for p in parts:
        # "93W/132W" and "123/136W" both mean: one of these lines, kind W.
        kinds = set(re.findall(r"[RW]", p))
        lines = tuple(int(n) for n in re.findall(r"\d+", p))
        if len(kinds) != 1 or not lines:
            raise RealWorldError(f"{var}({body}): cannot read access {p!r}")
        accs.append(Access(lines, "read" if kinds == {"R"} else "write"))
    return tuple(accs), "".join(a.kind[0].upper() for a in accs)


def parse_violation_info(path: Path, program: str, errata: dict[str, Any] | None = None,
                         *, corrected: bool = True) -> tuple[list[Entry], list[str]]:
    """The entries of one ``violation.info``, and a note for every line not read.

    Tolerates a colon after the label and an ``[index]`` on the variable. A line
    with no ``true``/``false`` label is not an entry: it is reported, never
    guessed at.
    """
    gt = ((errata or {}).get("groundtruth") or {}).get(program) or {}
    if gt.get("action") == "no-entries":
        return [], [f"{program}: errata says no-entries ({gt.get('evidence', '').strip()[:80]}...)"]
    fixes = {c["index"]: c for c in (errata or {}).get("corrections") or []
             if c["program"] == program} if corrected else {}
    entries: list[Entry] = []
    notes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        m = LABEL_RE.match(line)
        if not m:
            notes.append(f"{program}: unlabelled line skipped: {line.strip()!r}")
            continue
        label = "bug" if m.group(1) == "true" else "trap"
        rest = m.group(2).strip()
        if fix := fixes.get(len(entries) + 1):
            if fix["as_written"] != line.strip():
                raise RealWorldError(f"{program} entry {fix['index']}: erratum quotes "
                                     f"{fix['as_written']!r}, file says {line.strip()!r}")
            rest = fix["corrected"]
            notes.append(f"{program}: entry {fix['index']} corrected ({fix['confidence']})")
        if im := INST_RE.match(rest):
            accs, pattern = _instance(im.group(1), im.group(2))
            entries.append(Entry(program, len(entries) + 1, label, im.group(1), pattern,
                                 accs, line.strip()))
        elif vm := VAR_RE.match(rest):
            entries.append(Entry(program, len(entries) + 1, label, vm.group(1),
                                 vm.group(2).upper(), None, line.strip()))
        else:
            raise RealWorldError(f"{path}: cannot read {line!r}")
    return entries, notes


# -- C1 ---------------------------------------------------------------------

def config_for(program: str, suite_root: Path, *, errata: dict[str, Any],
               priorities: list[tuple[str, int]] | None = None,
               name: str | None = None) -> dict[str, Any]:
    prios = priorities or parse_priority(suite_root / program / "priority.info")
    flows: list[dict[str, Any]] = [
        {"id": "main", "kind": "task", "entry": "main", "irq": None, "priority": 0,
         "identified_by": "config"},
    ]
    for irq, (flow, prio) in enumerate(prios, start=1):
        flows.append({"id": flow, "kind": "isr", "entry": f"{flow}_isr", "irq": irq,
                      "priority": prio, "identified_by": "config"})
    flags = ["-g", "-O0", "-Xclang", "-disable-O0-optnone",
             *((errata.get("build_flags") or {}).get(program) or [])]
    defines = list((errata.get("build_defines") or {}).get(program) or [])
    return {
        "schema_version": SCHEMA_VERSION,
        "subject": {
            "name": name or program,
            "source_root": str(suite_root),
            "sources": [f"{program}/main.c"],
            "build": {"mode": "single-tu", "cc": "clang-14", "linker": "llvm-link-14",
                      "flags": flags, "defines": defines},
        },
        "priority_convention": "larger-is-higher",
        "flows": flows,
        "masking": {
            "primitives": [
                {"function": "disable_isr", "effect": "disable", "irq_arg": 0,
                 "all_value": -1, "non_constant_arg": "unknown"},
                {"function": "enable_isr", "effect": "enable", "irq_arg": 0,
                 "all_value": -1, "non_constant_arg": "unknown"},
            ],
            "initial_state": "unknown",
            "isr_entry_masks_self": False,
        },
        "semantics": {
            "equal_priority_preemption": True,
            "isr_arrival": "unbounded",
            "isr_reentrant": False,
            "nesting": True,
            "timing_model": "unconstrained",
        },
        "externals": {"default": "may-read-write-reachable", "models": []},
        "ground_truth": {"kind": "violation-info", "path": f"{program}/violation.info"},
    }


def priorities_for(program: str, suite_root: Path, errata: dict[str, Any] | None,
                   *, corrected: bool = True) -> list[tuple[str, int]]:
    """The program's priorities: ``priority.info``, or its erratum when *corrected*.

    A correction replaces the shipped levels only where they make the program's
    own ground truth unreachable (``priority_corrections`` in the errata); it must
    name exactly the flows the file names.
    """
    shipped = parse_priority(suite_root / program / "priority.info")
    fix = ((errata or {}).get("priority_corrections") or {}).get(program) if corrected else None
    if not fix:
        return shipped
    levels = fix["priorities"]
    if set(levels) != {n for n, _ in shipped}:
        raise RealWorldError(f"{program}: priority correction names other flows")
    return [(n, levels[n]) for n, _ in shipped]


def generate(suite_root: Path, out_dir: Path, errata_path: Path = ERRATA,
             *, corrected: bool = True) -> list[Path]:
    """One C1 per program, plus one per BMC4AV priority alternative.

    *corrected* applies ``priority_corrections``; without it the shipped
    ``priority.info`` is used everywhere, which is how the 40/45 run was made.
    """
    import yaml

    from .config import Config
    from .racebench import source_root_for

    errata = load_errata(errata_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    root = source_root_for(suite_root, out_dir)
    written: list[Path] = []

    def write(doc: dict[str, Any]) -> None:
        Config.from_dict(doc, path=out_dir / "x.yaml")  # validate before writing
        p = out_dir / f"{doc['subject']['name']}.yaml"
        p.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
        written.append(p)

    for program in PROGRAMS:
        shipped = priorities_for(program, suite_root, errata, corrected=corrected)
        write(config_for(program, root, errata=errata, priorities=shipped))
        alt = (errata.get("priority_alternatives") or {}).get(program)
        if alt:
            if set(alt) != {n for n, _ in shipped}:
                raise RealWorldError(f"{program}: alternative priorities name other flows")
            write(config_for(program, root, errata=errata,
                             priorities=[(n, alt[n]) for n, _ in shipped],
                             name=program + ALT_SUFFIX))
    return written


# -- matching ---------------------------------------------------------------

@dataclass
class Match:
    entry: Entry
    candidates: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.candidates)


def _matches(entry: Entry, c: dict[str, Any]) -> bool:
    if c.get("variable", {}).get("name") != entry.variable or c.get("pattern") != entry.pattern:
        return False
    if not entry.is_instance:
        return True
    for want, got in zip(entry.accesses, c["accesses"]):
        if got["source"]["line"] not in want.lines or got["kind"] != want.kind:
            return False
    return True


def match(entries: Iterable[Entry], candidates: list[dict[str, Any]]) -> list[Match]:
    """Each entry against a candidate set: same variable, same pattern -- and, for
    an instance entry, the same ordered lines and kinds (any listed alternative)."""
    return [Match(e, [c["id"] for c in candidates if _matches(e, c)]) for e in entries]


# -- the run ----------------------------------------------------------------

def program_of(name: str) -> str:
    return name.removesuffix(ALT_SUFFIX)


def _run_one(path: Path, run_root: str, through: str, suite_root: Path,
             errata_path: Path, corrected: bool) -> dict[str, Any]:
    """One configuration through stages 1..*through*, matched. Module-level so a
    process pool can run it; returns its printed lines instead of printing them."""
    import json

    from .build import BuildError
    from .cli import _do_build
    from .config import Config, ConfigError
    from .runstore import RunStore
    from .stage1_driver import Stage1Error, stage1
    from .stage2 import Stage2Error, stage2
    from .stage3 import Stage3Error, stage3

    errata = load_errata(errata_path)
    try:
        cfg = Config.load(path)
        store = RunStore.create(cfg, run_root=run_root)
        result = _do_build(cfg, store)
        s1 = stage1(cfg, store, result.bitcode)
        s2 = stage2(cfg, store) if through in ("stage2", "stage3") else None
        s3 = stage3(cfg, store, result.bitcode) if through == "stage3" else None
    except (ConfigError, BuildError, Stage1Error, Stage2Error, Stage3Error) as e:
        msg = str(e).splitlines()[0]
        return {"failure": (path.stem, msg), "lines": [f"[FAIL] {path.stem}: {msg}"]}

    program = program_of(cfg.name)
    entries, notes = parse_violation_info(suite_root / program / "violation.info",
                                          program, errata, corrected=corrected)
    sets = {"stage1": store.read_candidates("stage1")}
    if s2 is not None:
        sets["stage2"] = store.read_candidates("stage2")
    if s3 is not None:
        sets["context"] = store.read_contexts()
    last = list(sets)[-1]
    by_stage = {k: match(entries, v) for k, v in sets.items()}
    final = by_stage[last]
    bugs = [m for m in final if m.entry.label == "bug"]
    traps = {k: sum(m.found for m in v if m.entry.label == "trap") for k, v in by_stage.items()}
    n_traps = sum(e.label == "trap" for e in entries)
    row = {
        "name": cfg.name, "program": program, "alt": cfg.name != program,
        "run": store.root.name,
        "counts": {k: len(v) for k, v in sets.items()},
        "s2": s2, "s3": s3,
        "bugs_found": sum(m.found for m in bugs), "bugs": len(bugs),
        "traps_found": traps, "traps": n_traps,
        "missed": [m.entry.raw for m in bugs if not m.found],
        "notes": notes,
    }
    (store.root / "eval" / "report.json").write_text(json.dumps({
        "suite": "realworld", "stage": last, "errata_applied": corrected,
        "unit": "per-entry (variable+pattern, or instance)",
        "entries": [{"index": m.entry.index, "label": m.entry.label, "raw": m.entry.raw,
                     "found": m.found, "candidates": m.candidates} for m in final],
    }, indent=2) + "\n")

    gate = "ok " if row["bugs_found"] == row["bugs"] else "MISS"
    funnel = " -> ".join(f"{v:>4}" for v in row["counts"].values())
    extra = ""
    if s3 is not None:
        v = s3["verdicts"]
        extra = (f" (sat {v.get('sat', 0)}, inc {v.get('inconclusive', 0)}, "
                 f"unsat {v.get('unsat', 0)}) [{s3['wall_ms'] // 1000} s]")
    tr = "->".join(str(t) for t in traps.values())
    lines = [f"[{gate}] {cfg.name:<26} {funnel}{extra}  bugs {row['bugs_found']}/{row['bugs']}"
             f"  traps {tr}/{n_traps}"]
    lines += [f"        MISSED {raw}" for raw in row["missed"]]
    return {"row": row, "lines": lines,
            "problems": [f"{store.root.name}: {p}" for p in store.check()]}


def run(configs: list[Path], *, run_root: str, through: str = "stage3",
        suite_root: Path | None = None, errata_path: Path = ERRATA,
        corrected: bool = True, jobs: int = 1, out=print) -> dict[str, Any]:
    """Stages 1..*through* on every configuration, matched against violation.info.

    The gate is taken on the output of the last stage run, as for Racebench: a
    filter that drops a ground-truth entry fails it, whichever stage it is in.
    Configurations with BMC4AV's priorities are reported beside, not counted in.
    With *jobs* > 1 the configurations run in parallel processes -- each is
    independent, and Z3 is single-threaded -- and are reported in input order.
    """
    suite_root = suite_root or locate_suite()
    if suite_root is None:
        raise RealWorldError("bench/realworld not found (or IRQRACE_REALWORLD is wrong)")
    summary: dict[str, Any] = {"subjects": [], "failures": [], "problems": []}
    argv = [(p, run_root, through, suite_root, errata_path, corrected) for p in configs]

    def take(res: dict[str, Any]) -> None:
        for line in res["lines"]:
            out(line)
        if "failure" in res:
            summary["failures"].append(res["failure"])
        else:
            summary["subjects"].append(res["row"])
            summary["problems"] += res["problems"]

    if jobs <= 1:
        for a in argv:
            take(_run_one(*a))
    else:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=jobs) as pool:
            for res in pool.map(_run_one, *zip(*argv)):
                take(res)

    prim = [r for r in summary["subjects"] if not r["alt"]]
    found = sum(r["bugs_found"] for r in prim)
    total = sum(r["bugs"] for r in prim)
    summary.update(found=found, total=total)
    if prim:
        stages = list(prim[0]["counts"])
        tot = {k: sum(r["counts"][k] for r in prim) for k in stages}
        out("")
        out(f"{len(prim)}/{len([c for c in configs if ALT_SUFFIX not in c.stem])} programs analysed"
            f" (+{len(summary['subjects']) - len(prim)} with BMC4AV's priorities)")
        out("funnel: " + " -> ".join(f"{k} {v}" for k, v in tot.items()))
        if through in ("stage2", "stage3"):
            reasons: dict[str, int] = {}
            for r in prim:
                for k, v in r["s2"]["reasons"].items():
                    reasons[k] = reasons.get(k, 0) + v
            out("stage 2 drops: " + (", ".join(f"{k} {v}" for k, v in sorted(reasons.items()))
                                     or "none"))
        ntr = sum(r["traps"] for r in prim)
        out("traps reported: " + " -> ".join(
            f"{k} {sum(r['traps_found'][k] for r in prim)}/{ntr}" for k in stages))
        out(f"RECALL GATE ({stages[-1]}): {found}/{total} ground-truth violations present "
            f"-- {'PASS' if found == total and total else 'FAIL'}"
            f"  [unit: per violation.info entry; line errata {'applied' if corrected else 'NOT applied'}]")
    for p in summary["problems"]:
        out(f"  ! {p}")
    return summary
