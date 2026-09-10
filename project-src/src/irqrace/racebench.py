"""Generating C1 configurations for the 31 Racebench simple cases.

The interrupt model is not guessed: ``racebench/2.1_remarks/README.md`` ships a
table giving, for every case, the main entry point and each handler as
``name/irq/priority``. That table is the primary source for the convention
**larger number = higher priority** (Contradictions #3), so parsing it rather
than reconstructing it from filenames keeps the configurations traceable.

Racebench-specific facts encoded here:

* ``disable_isr(n)`` / ``enable_isr(n)`` are lock/unlock primitives and ``n = -1``
  means all interrupts;
* ``init()`` calls ``enable_isr(-1)``, so the initial masking state is
  all-enabled;
* interrupts are **non-periodic** -- an ISR may fire at any enabled point, any
  number of times, at unspecified moments -- so ``isr_arrival`` is ``unbounded``
  and the timing model stays unconstrained. Assuming otherwise is an unsound
  filter (``wiki/Pipeline Design.md``, stage 2, *Timing*);
* ``common.c`` must be linked in, and ``idlerun``/``rand`` do not touch shared
  state, so they are modelled rather than left opaque.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CASE_RE = re.compile(r"^svp_simple_(\d{3})_001\.c$")
HANDLER_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*/\s*(-?\d+)\s*/\s*(-?\d+)")

#: Externals with bodies in common.c or in libc that provably do not touch the
#: subject's shared globals. Everything not listed keeps the sound default of
#: "may read and write any global".
EXTERNAL_MODELS = [
    {"function": "idlerun", "effect": "none", "note": "common.c: an empty spin loop"},
    {"function": "init", "effect": "none", "note": "common.c: calls enable_isr(-1) only"},
    {"function": "rand", "effect": "none", "note": "libc, no shared state in these subjects"},
]


#: The README's case table names the main entry point of two cases wrongly: it
#: says ``svp_simple_028_001_main`` and ``svp_simple_030_001_main`` while both
#: files actually define ``..._001__main`` with a DOUBLE underscore. Discovered
#: 2026-08-31 by the probe's R7 check on the first build of the suite.
#:
#: This is recall-critical rather than cosmetic. A tool that trusts the table
#: analyses the main task of those two cases as unreachable, contributing no
#: accesses, and every defect involving the main task disappears -- with no error
#: anywhere. It is a concrete instance of the first soundness assumption in
#: ``wiki/Pipeline Design.md``: a flow whose entry point is not recognised is
#: invisible, and the loss does not show up in the output.
ENTRY_OVERRIDES: dict[str, str] = {
    "svp_simple_028_001": "svp_simple_028_001__main",
    "svp_simple_030_001": "svp_simple_030_001__main",
}


class RacebenchError(RuntimeError):
    pass


def parse_readme(readme: Path) -> list[dict[str, Any]]:
    """Parse the case table out of ``2.1_remarks/README.md``.

    Returns one dict per case with ``case``, ``file``, ``main`` and ``isrs``,
    each ISR a ``(entry, irq, priority)`` triple.
    """
    rows: list[dict[str, Any]] = []
    for line in readme.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        m = CASE_RE.match(cells[1])
        if not m:
            continue
        main = cells[2]
        isrs = [
            {"entry": e, "irq": int(i), "priority": int(p)}
            for e, i, p in HANDLER_RE.findall(cells[3])
        ]
        if not isrs:
            raise RacebenchError(f"no handlers parsed for {cells[1]}: {cells[3]!r}")
        rows.append(
            {"case": f"svp_simple_{m.group(1)}", "file": cells[1],
             "name": cells[1][:-2], "main": main, "isrs": isrs}
        )
    if not rows:
        raise RacebenchError(f"no case rows found in {readme}")
    return rows


def config_for(row: dict[str, Any], suite_root: Path) -> dict[str, Any]:
    """Build the C1 document for one case."""
    main_entry = ENTRY_OVERRIDES.get(row["name"], row["main"])
    flows: list[dict[str, Any]] = [
        {
            "id": "main",
            "kind": "task",
            "entry": main_entry,
            "irq": None,
            "priority": 0,
            "identified_by": "config",
        }
    ]
    for isr in sorted(row["isrs"], key=lambda h: h["irq"]):
        flows.append(
            {
                "id": f"isr_{isr['irq']}",
                "kind": "isr",
                "entry": isr["entry"],
                "irq": isr["irq"],
                "priority": isr["priority"],
                "identified_by": "config",
            }
        )

    return {
        "schema_version": "c1/1.0.0",
        "subject": {
            "name": row["name"],
            "source_root": str(suite_root),
            "sources": [f"{row['case']}/{row['file']}"],
            "build": {
                "mode": "single-tu",
                "cc": "clang-14",
                "linker": "llvm-link-14",
                "flags": ["-g", "-O0", "-Xclang", "-disable-O0-optnone"],
                "extra_bitcode": ["common.c"],
            },
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
            # init() calls enable_isr(-1) before anything else in every case.
            "initial_state": "all-enabled",
            "isr_entry_masks_self": False,
        },
        "semantics": {
            # Recall-safe defaults; both are open questions and both are echoed
            # into the run manifest so no number is reported without them.
            "equal_priority_preemption": True,
            "isr_arrival": "unbounded",
            "isr_reentrant": False,
            "nesting": True,
            "timing_model": "unconstrained",
        },
        "externals": {
            "default": "may-read-write-reachable",
            "models": list(EXTERNAL_MODELS),
        },
        "ground_truth": {
            "kind": "racebench-remarks",
            "path": f"{row['case']}/{row['file']}",
        },
    }


def generate(suite_root: Path, out_dir: Path) -> list[Path]:
    """Write one C1 file per case. Validates each before writing."""
    import yaml

    from .config import Config

    rows = parse_readme(suite_root / "README.md")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for row in rows:
        doc = config_for(row, suite_root)
        Config.from_dict(doc)  # fails loudly rather than writing a broken file
        path = out_dir / f"{row['name']}.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
        written.append(path)
    return written
