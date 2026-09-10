"""Locating clang, llvm-link, SVF and the irqrace analysis binaries.

Everything is resolved once and reported together, because a half-present
toolchain produces failures that look like analysis bugs. ``irqrace doctor``
prints this.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Default SVF checkout, alongside the other tool artifacts rather than inside
#: the vault (see CLAUDE.md: artifacts live one directory up and are not copied).
DEFAULT_SVF_DIR = REPO_ROOT.parents[1] / "toolchain" / "SVF"

PROBE_PATH = REPO_ROOT / "analysis" / "build" / "bin" / "irqrace-probe"


@dataclass
class Tool:
    name: str
    path: Path | None
    version: str = ""
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.path is not None and Path(self.path).exists()


@dataclass
class Toolchain:
    cc: Tool
    linker: Tool
    svf: Tool
    probe: Tool
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _which(candidates: list[str]) -> Path | None:
    for c in candidates:
        p = shutil.which(c)
        if p:
            return Path(p)
    return None


def _version(path: Path | None, args: list[str]) -> str:
    if not path:
        return ""
    try:
        out = subprocess.run(
            [str(path), *args], capture_output=True, text=True, timeout=20
        )
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:  # noqa: BLE001 - a missing/odd tool must not crash `doctor`
        return ""


def detect(cc: str = "clang-14", linker: str = "llvm-link-14") -> Toolchain:
    cc_path = _which([cc, "clang-14", "clang"])
    ln_path = _which([linker, "llvm-link-14", "llvm-link"])

    svf_dir = Path(os.environ.get("SVF_DIR") or DEFAULT_SVF_DIR)
    svf_bin = svf_dir / "Release-build" / "bin" / "wpa"

    tc = Toolchain(
        cc=Tool(cc, cc_path, _version(cc_path, ["--version"])),
        linker=Tool(linker, ln_path, _version(ln_path, ["--version"])),
        svf=Tool("SVF", svf_bin if svf_bin.exists() else None, note=str(svf_dir)),
        probe=Tool("irqrace-probe", PROBE_PATH if PROBE_PATH.exists() else None),
    )

    if not tc.cc.ok:
        tc.problems.append(f"C compiler {cc!r} not found; apt install clang-14")
    if not tc.linker.ok:
        tc.problems.append(f"bitcode linker {linker!r} not found; apt install llvm-14")
    if not tc.svf.ok:
        tc.problems.append(
            f"SVF not built at {svf_dir}; run scripts/setup-svf.sh"
        )
    if not tc.probe.ok:
        tc.problems.append(
            f"irqrace-probe not built at {PROBE_PATH}; run scripts/build-analysis.sh"
        )
    return tc
