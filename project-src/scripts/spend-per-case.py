#!/usr/bin/env python3
"""Token spend per case, from the ``spend:`` lines the batch runner's case logs keep.

    python scripts/spend-per-case.py RUN_ROOT [RUN_ROOT ...] > tokens-per-case.csv

A run root is a pair directory (``OUT/<row>/<k>/``) with ``logs/<case>.log`` and
``batch.json``. One row per (run, case), with the raw fields of the spend line:
``tokens_in`` is the uncached input only; on a caching backend most of the input
is in ``cache_read`` and ``cache_write``, and the scorer's ``tokens_in`` column
in ``runs.csv`` is the sum of the three.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from irqrace.bench_metrics import parse_spend  # noqa: E402

FIELDS = ["requests", "tokens_in", "tokens_out", "cache_read", "cache_write", "latency_s"]


def main(roots: list[str]) -> int:
    out = csv.writer(sys.stdout)
    out.writerow(["run_id", "backend", "case", *FIELDS, "input_total"])
    for root in map(Path, roots):
        batch = json.loads((root / "batch.json").read_text(encoding="utf-8"))
        for log in sorted((root / "logs").glob("*.log")):
            spend = parse_spend(log.read_text(encoding="utf-8", errors="replace")) or {}
            vals = [spend.get(f, "") for f in FIELDS]
            total = sum(spend.get(f, 0) for f in ("tokens_in", "cache_read", "cache_write")) if spend else ""
            out.writerow([batch["run_id"], batch["backend"], log.stem,
                          *[int(v) if isinstance(v, float) and v.is_integer() else v for v in vals],
                          int(total) if total != "" else ""])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
