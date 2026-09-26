#!/usr/bin/env python3
"""Score prompt configurations against the labelled fixtures.

    python3 scripts/run-ablation.py --backend anthropic:claude-opus-5
    python3 scripts/run-ablation.py --rows simple --samples 1     # the W1 probe
    python3 scripts/run-ablation.py --backend ollama:qwen2.5-coder:32b

With no ``--rows`` it runs all five rows of the LLift-shaped ablation and
prints the table (Roadmap W5, milestone M3). With ``--rows simple`` and one
sample it is the **W1 feasibility probe**: the go/no-go that
``wiki/Open Questions.md`` says must run before anything is built on top of the
LLM stage, and whose negative result reshapes the design rather than tuning it.

Nothing here decides anything. It prints recall, trap rejection, Inspection
Ratio and cost, and it prints the backend's caveats beside them, because a row
served by prompted JSON on an unpriced backend is not comparable to one served
by an enforced schema on a cached one.

**A candidate the backend refuses is excluded and reported, never scored.**
Scoring a refusal as any bucket would corrupt the row.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def load_env(path: Path = REPO / ".env") -> list[str]:
    """Read ``KEY=VALUE`` lines into the environment, if the file exists.

    Credentials belong in a gitignored file rather than in shell history or a
    command line, and a run should not depend on remembering to export
    anything. Existing environment variables win, so an explicit export still
    overrides the file.

    Deliberately not ``python-dotenv``: the whole point of the generic
    backends is that they need nothing beyond the standard library, and this
    is ten lines.
    """
    if not path.exists():
        return []
    loaded = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded

from irqrace.llm.backends import BackendError, RefusalError, from_spec  # noqa: E402
from irqrace.llm.cache import Cache  # noqa: E402
from irqrace.llm.client import TriageClient  # noqa: E402
from irqrace.llm.fixtures import load_all  # noqa: E402
from irqrace.llm.prompts import ABLATION, BY_NAME  # noqa: E402
from irqrace.llm.resolver import (  # noqa: E402
    render_distribution,
    request_distribution,
)
from irqrace.llm.scoring import (  # noqa: E402
    blocking_element_groups,
    consistency,
    score,
    vote,
)


def run_row(config, fixtures, backend, cache, samples, run_dir):
    """Returns (runs, excluded, client). One entry in ``runs`` per sample."""
    client = TriageClient(config, backend=backend, cache=cache)
    runs, excluded = [], []
    for sample in range(samples):
        triaged = []
        for fixture in fixtures:
            try:
                triaged.append(
                    client.triage(fixture.record, sample=sample, run_dir=run_dir)
                )
            except RefusalError as e:
                excluded.append((fixture.candidate_id, str(e)))
            except BackendError as e:
                excluded.append((fixture.candidate_id, f"backend error: {e}"))
        runs.append(triaged)
    return runs, excluded, client


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="anthropic:claude-opus-5")
    ap.add_argument("--rows", nargs="*", help="row names; default is all five")
    ap.add_argument("--samples", type=int, default=1, help=">1 measures consistency")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--run-dir", type=Path, help="write C3 transcripts here")
    ap.add_argument("--json", type=Path, help="also write the results as JSON")
    args = ap.parse_args()

    if loaded := load_env():
        print(f"loaded {', '.join(loaded)} from .env")

    try:
        backend = from_spec(args.backend)
    except BackendError as e:
        print(e, file=sys.stderr)
        return 2

    fixtures = load_all()
    configs = (
        [BY_NAME[r] for r in args.rows] if args.rows else list(ABLATION)
    )
    cache = Cache(enabled=not args.no_cache)

    print(f"backend: {backend.spec}")
    for caveat in backend.capabilities.caveats():
        print(f"  [!] {caveat}")
    print(
        f"fixtures: {sum(1 for f in fixtures if f.is_real)} bug points, "
        f"{sum(1 for f in fixtures if not f.is_real)} traps\n"
    )

    results = []
    for config in configs:
        runs, excluded, client = run_row(
            config, fixtures, backend, cache, args.samples, args.run_dir
        )
        scored = [f for f in fixtures if f.candidate_id not in {c for c, _ in excluded}]
        # With several samples the reported verdict is the vote, not run 0:
        # ties resolve toward the higher bucket, so voting cannot lose recall.
        final = vote(runs) if len(runs) > 1 else runs[0]
        s = score(scored, final)

        print(f"--- {config.name}  ({config.hash()})")
        print("    " + s.report().replace("\n", "\n    "))
        if args.samples > 1:
            agreement = consistency(runs)["__mean__"]
            print(f"    consistency:      {agreement:.1%} over {args.samples} runs")

        violations = {
            t.candidate_id: v
            for t in final
            if (v := t.protocol_violations())
        }
        if violations:
            print(f"    protocol violations ({len(violations)}):")
            for cid, vs in violations.items():
                for v in vs:
                    print(f"        {cid}: {v}")

        # Real bug points in a low bucket. The recall gate does not catch
        # likely_benign, so it is printed separately rather than inferred from
        # the Inspection Ratio.
        low = [
            f.candidate_id
            for f in scored
            if f.is_real
            and next(t for t in final if t.candidate_id == f.candidate_id)
            .bucket.value == "likely_benign"
        ]
        if low:
            print(
                f"    [!] {len(low)} bug point(s) bucketed likely_benign — passes "
                f"the recall gate, sinks the Inspection Ratio: {', '.join(low)}"
            )

        # IRIS-style grouping: shared blocking elements shorten review without
        # removing anything, which is the only pruning this design permits.
        groups = blocking_element_groups(final)
        if groups:
            print(f"    shared blocking elements ({len(groups)}):")
            for element, members in groups.items():
                print(f"        {len(members)} candidates: {element}")

        if config.progressive and client.request_log:
            print(
                "    "
                + render_distribution(
                    request_distribution(client.request_log)
                ).replace("\n", "\n    ")
            )
        if excluded:
            print(f"    [!] {len(excluded)} excluded, not scored:")
            for cid, why in excluded:
                print(f"        {cid}: {why}")
        print("    " + client.spend.report().replace("\n", "\n    "))
        print()

        results.append(
            {
                "row": config.name,
                "config_hash": config.hash(),
                "backend": backend.spec,
                "recall": s.recall,
                "gate_passed": s.gate_passed,
                "trap_rejection": s.trap_rejection,
                "inspection_ratio": s.inspection_ratio,
                "buckets": s.bucket_counts,
                "blocking_element_groups": blocking_element_groups(final),
                "request_distribution": (
                    request_distribution(client.request_log)
                    if client.request_log
                    else None
                ),
                "missed": list(s.missed),
                "protocol_violations": violations,
                "bug_points_bucketed_benign": low,
                "excluded": [{"candidate": c, "reason": r} for c, r in excluded],
                "cost_usd": client.spend.cost_usd if client.spend.fully_priced else None,
                "caveats": backend.capabilities.caveats(),
            }
        )

    if args.json:
        args.json.write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.json}")

    # The recall gate is the one result that is pass/fail rather than a number.
    # A row that scored nothing counts as failed: recall over an empty set is
    # 1.0, and reporting that as a pass would be the exact silent success the
    # decision policy is built to prevent.
    failed = [r["row"] for r in results if not r["gate_passed"]]
    if failed:
        print(f"RECALL GATE FAILED on: {', '.join(failed)}")
        print(
            "A bug point ranked likely_infeasible is a design failure, not a "
            "tuning issue, and is reportable as such (wiki/LLM Stage Design.md). "
            "A row that scored no candidates at all has measured nothing."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
