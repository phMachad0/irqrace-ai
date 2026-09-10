"""Thin wrapper around the SVF-based ``irqrace-probe`` binary.

The probe answers two questions the pipeline needs before it can trust anything:
what the build actually produced (Dashboard Design R4) and whether the C1
interrupt model matches the built bitcode in both directions (R7). Its output
populates the ``build`` block of the C3 manifest.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .config import Config
from .toolchain import PROBE_PATH


class ProbeError(RuntimeError):
    pass


def probe(bitcode: Path, cfg: Config | None = None, *, binary: Path | None = None,
          timeout: int = 600) -> dict[str, Any]:
    exe = Path(binary or PROBE_PATH)
    if not exe.exists():
        raise ProbeError(
            f"irqrace-probe not built at {exe}; run scripts/build-analysis.sh"
        )

    cmd = [str(exe)]
    if cfg is not None:
        for f in cfg.flows:
            cmd += ["--entry", f.entry]
        for p in cfg.masking_primitives:
            cmd += ["--primitive", p.function]
    cmd.append(str(bitcode))

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise ProbeError(
            f"irqrace-probe failed ({proc.returncode}):\n{proc.stderr.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ProbeError(
            "irqrace-probe did not produce JSON. SVF writes its statistics to "
            f"stdout; -stat=false should suppress them.\n{proc.stdout[:2000]}"
        ) from e
