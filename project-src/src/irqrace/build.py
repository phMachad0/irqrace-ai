"""Building a subject to whole-program LLVM bitcode.

Two modes, both of which link **bitcode**, never C source. Merging at the source
level destroys the source ranges the whole pipeline depends on, collides
``static`` symbols, and throws away per-translation-unit preprocessor state
(``wiki/Pipeline Design.md``, *Get there by linking bitcode, not by concatenating
source*).

``-g`` is mandatory: ``DILocation`` is what lets an IR-level result be expressed
as C, and "every candidate maps back to a source range" is a hard requirement
from day one. ``-O0`` alone marks functions ``optnone`` and the pass manager
skips them, hence ``-Xclang -disable-O0-optnone`` in the default flags.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config


class BuildError(RuntimeError):
    """The subject did not compile. This is not an analysis failure and must not
    be reported as one (Dashboard Design R2)."""


@dataclass
class BuildResult:
    bitcode: Path
    translation_units: int
    objects: list[Path] = field(default_factory=list)
    log: str = ""

    @property
    def bitcode_sha256(self) -> str:
        return hashlib.sha256(self.bitcode.read_bytes()).hexdigest()


def _run(cmd: list[str], log: list[str]) -> None:
    log.append("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        log.append(proc.stdout.rstrip())
    if proc.stderr:
        log.append(proc.stderr.rstrip())
    if proc.returncode != 0:
        raise BuildError(
            "build command failed:\n  "
            + " ".join(cmd)
            + "\n"
            + (proc.stderr or proc.stdout or "").rstrip()
        )


def build(cfg: Config, out_dir: Path) -> BuildResult:
    """Compile every translation unit to bitcode and link them into one module."""
    build_cfg = cfg.build
    mode = build_cfg["mode"]
    if mode == "intercept":
        raise BuildError(
            "build mode 'intercept' (wllvm/gllvm) is not implemented yet; it is "
            "needed only for whole-repository input, which the benchmarks never "
            "exercise (de-scoping ladder rung 1)"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    log: list[str] = []

    cc = shutil.which(build_cfg["cc"]) or build_cfg["cc"]
    linker = shutil.which(build_cfg["linker"]) or build_cfg["linker"]

    flags = list(build_cfg["flags"])
    if "-g" not in flags:
        raise BuildError(
            "build.flags does not contain -g. Debug metadata is what makes the "
            "source mapping possible; without it every candidate loses its "
            "source range and the context record cannot be built."
        )
    for d in build_cfg.get("include_dirs", []):
        flags += ["-I", d]
    for d in build_cfg.get("defines", []):
        flags += [f"-D{d}"]

    sources = cfg.source_files()
    if not sources:
        raise BuildError(f"subject.sources matched no .c files: {cfg.subject['sources']}")
    missing = [str(s) for s in sources if not s.exists()]
    if missing:
        raise BuildError("source files do not exist: " + ", ".join(missing))

    objects: list[Path] = []
    for src in sources:
        obj = out_dir / (src.stem + ".bc")
        _run([cc, *flags, "-emit-llvm", "-c", str(src), "-o", str(obj)], log)
        objects.append(obj)

    for extra in build_cfg.get("extra_bitcode", []):
        p = Path(extra)
        if not p.is_absolute():
            p = Path(cfg.subject.get("source_root") or ".") / p
        if p.suffix == ".c":
            obj = out_dir / (p.stem + ".bc")
            _run([cc, *flags, "-emit-llvm", "-c", str(p), "-o", str(obj)], log)
            objects.append(obj)
        elif p.exists():
            objects.append(p)
        else:
            raise BuildError(f"extra_bitcode entry does not exist: {p}")

    whole = out_dir / "whole.bc"
    if len(objects) == 1:
        shutil.copyfile(objects[0], whole)
        log.append(f"$ cp {objects[0]} {whole}")
    else:
        _run([linker, *[str(o) for o in objects], "-o", str(whole)], log)

    (out_dir / "build.log").write_text("\n".join(log) + "\n")
    return BuildResult(
        bitcode=whole,
        translation_units=len(objects),
        objects=objects,
        log="\n".join(log),
    )
