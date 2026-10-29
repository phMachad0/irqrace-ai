#!/usr/bin/env python3
"""Score the repair stage against the 10 hand-written reference fixes (Roadmap W7).

    python3 scripts/run-repair.py --backend anthropic:claude-opus-5
    python3 scripts/run-repair.py --backend ollama:qwen2.5-coder:32b
    python3 scripts/run-repair.py --cache-only

Runs :class:`~irqrace.llm.repair.RepairClient` over the 10 bug points in the
labelled fixture set and reports:

1. **Coverage** (how many of the 10 bug points received a structured patch).
2. **Well-formed diff rate** (whether the unified diff parses structurally).
3. **Mechanical witness check** (:func:`~irqrace.llm.repair.witness_problems`
   — firing flow in record, matches preempting flow, remote access between local pair).
4. **Syntax Rate** (:func:`~irqrace.llm.repair.syntax_rate` via a local C
   compiler when available; ``None`` / unmeasured otherwise, never a vacuous 100%).
5. **Logic Rate** (:func:`~irqrace.llm.repair.logic_rate` on strategy, masked
   interrupts, and covered region against :mod:`~irqrace.llm.repair_references`).
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
from irqrace.llm.fixtures import load_all  # noqa: E402
from irqrace.llm.prompts import BY_NAME, DEFERRED, FULL  # noqa: E402
from irqrace.llm.repair import (  # noqa: E402
    Patch,
    RepairClient,
    score_repairs,
)
from irqrace.llm.repair_references import references_for  # noqa: E402


def run_repairs(config, bug_fixtures, backend, cache, sample, run_dir):
    client = RepairClient(config, backend=backend, cache=cache)
    patches: dict[str, Patch] = {}
    excluded: list[tuple[str, str]] = []
    for fixture in bug_fixtures:
        cid = fixture.candidate_id
        try:
            patches[cid] = client.repair(
                fixture.record, sample=sample, run_dir=run_dir
            )
        except RefusalError as e:
            excluded.append((cid, str(e)))
        except (BackendError, RuntimeError) as e:
            excluded.append((cid, f"backend error: {e}"))
    return patches, excluded, client


def render_markdown(result: dict) -> str:
    syn = (
        "— (unmeasured)"
        if result["syntax_rate"] is None
        else f"{result['syntax_rate']:.1%}"
    )
    lines = [
        "| backend | config | coverage | well-formed | witness valid | Syntax Rate | Logic Rate |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| `{result['backend']}` | `{result['row']}` | "
        f"{result['n_repaired']}/{result['n_expected']} | "
        f"{result['wellformed_rate']:.1%} | "
        f"{result['witness_rate']:.1%} | "
        f"{syn} | "
        f"{result['logic_rate']:.1%} |",
        "",
        "### Per-candidate patches",
        "",
        "| subject | candidate | strategy | masked IRQs | lines covered | witness | logic match |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in result.get("candidates", []):
        lines.append(
            f"| `{item['subject']}` | `{item['candidate_id']}` | "
            f"`{item['strategy']}` | `{item['masked_irqs']}` | "
            f"{item['covers_from_line']}–{item['covers_to_line']} | "
            f"{'ok' if item['witness_ok'] else 'FAIL'} | "
            f"{'ok' if item['logic_ok'] else 'MISS'} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", default="anthropic:claude-opus-5")
    ap.add_argument(
        "--row",
        default=FULL.name,
        help="prompt configuration name (default: +self-validation)",
    )
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument(
        "--cache-only",
        action="store_true",
        help="never call the backend; a cache miss is reported as excluded",
    )
    ap.add_argument("--run-dir", type=Path, help="write C3 repair artifacts here")
    ap.add_argument("--json", type=Path, help="write repair results as JSON")
    ap.add_argument("--out", type=Path, help="write markdown summary table here")
    args = ap.parse_args(argv)

    if loaded := load_env():
        print(f"loaded {', '.join(loaded)} from .env")

    all_configs = {**BY_NAME, **DEFERRED}
    if args.row not in all_configs:
        print(
            f"unknown row {args.row!r}; known: {', '.join(all_configs)}",
            file=sys.stderr,
        )
        return 2
    config = all_configs[args.row]

    try:
        backend = from_spec(args.backend)
    except BackendError as e:
        print(e, file=sys.stderr)
        return 2

    if args.cache_only:
        if args.no_cache:
            print("--cache-only and --no-cache contradict each other", file=sys.stderr)
            return 2

        def _no_request(request):
            raise BackendError("--cache-only: cache miss, no request sent")

        backend.chat = _no_request

    fixtures = load_all()
    bugs = [f for f in fixtures if f.is_real]
    refs = references_for(fixtures)
    records_by_id = {f.candidate_id: f.record for f in bugs}
    subjects_by_id = {f.candidate_id: f.subject for f in bugs}

    cache = Cache(enabled=not args.no_cache)
    print(f"backend: {backend.spec}")
    for caveat in backend.capabilities.caveats():
        print(f"  [!] {caveat}")
    print(f"bug points to repair: {len(bugs)}\n")

    patches, excluded, client = run_repairs(
        config, bugs, backend, cache, args.sample, args.run_dir
    )
    s = score_repairs(patches, records_by_id, refs, n_expected=len(bugs))

    print(f"--- repair ({config.name}) ---")
    print("    " + s.report().replace("\n", "\n    "))
    if excluded:
        print(f"    [!] {len(excluded)} excluded, not scored:")
        for cid, why in excluded:
            print(f"        {cid}: {why}")
    print("    " + client.spend.report().replace("\n", "\n    "))

    missed_ids = {m.split(":", 1)[0] for m in s.logic_missed}
    candidates_detail = [
        {
            "candidate_id": cid,
            "subject": subjects_by_id.get(cid, ""),
            "strategy": p.strategy.value,
            "masked_irqs": p.masked_irqs,
            "covers_from_line": p.covers_from_line,
            "covers_to_line": p.covers_to_line,
            "latency_note": p.latency_note,
            "witness": p.witness.model_dump(mode="json"),
            "witness_ok": cid not in s.witness_failures,
            "logic_ok": cid not in missed_ids,
        }
        for cid, p in patches.items()
    ]

    result = {
        "row": config.name,
        "backend": backend.spec,
        "n_repaired": s.n_repaired,
        "n_expected": s.n_expected,
        "coverage": s.coverage,
        "complete": s.complete,
        "wellformed_rate": s.wellformed_rate,
        "malformed_diffs": list(s.malformed_diffs),
        "witness_rate": s.witness_rate,
        "witness_failures": s.witness_failures,
        "syntax_rate": s.syntax_rate,
        "syntax_failures": list(s.syntax_failures),
        "logic_rate": s.logic_rate,
        "logic_missed": list(s.logic_missed),
        "candidates": candidates_detail,
        "excluded": [{"candidate": c, "reason": r} for c, r in excluded],
        "cost_usd": client.spend.cost_usd if client.spend.fully_priced else None,
        "caveats": backend.capabilities.caveats(),
    }

    if args.json:
        args.json.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")

    if args.out:
        md = render_markdown(result)
        args.out.write_text(md + "\n", encoding="utf-8")
        print(f"wrote {args.out}")

    return 0 if s.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
