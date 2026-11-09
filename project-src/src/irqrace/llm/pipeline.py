"""W8 Integration — running Track B (triage and repair) over a C3 RunStore.

Connects Track A's static output (``runs/<run_id>/``) to Track B's LLM stages
while enforcing Contract C3's invariants:

1. **No candidate disappears without an ``unsat`` proof** (C3 Rule 6). When
   stage 2 or stage 3 has not run (e.g. de-scoping ladder rung 3),
   :func:`prepare_context` promotes stage-1 candidates directly into
   ``context/<cand_id>.json`` so the run directory remains C3-valid.
2. **Triage orders and explains; it never drops.** ``candidates_in`` and
   ``candidates_out`` on the ``triage`` stage are equal by construction, and
   ``dropped_with_proof`` is always ``0``.
3. **Every run records its model, prompt configuration, date, and vote count**
   in ``manifest.json["llm"]`` (``wiki/concepts/Precision Metrics.md`` #8).
"""

from __future__ import annotations

import datetime
import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from irqrace import contracts
from irqrace.llm.backends import Backend, BackendError, RefusalError, from_spec
from irqrace.llm.client import TriageClient
from irqrace.llm.intervals import Budget, OverBudget, group_intervals, signal
from irqrace.llm.prompts import FULL, PromptConfig
from irqrace.llm.repair import Patch, RepairClient, witness_problems
from irqrace.llm.resolver import (
    request_distribution,
    resolver_for,
)
from irqrace.llm.scoring import (
    blocking_element_groups,
    consistency,
    vote,
)
from irqrace.llm.verdict import (
    INSPECTION_ORDER,
    Bucket,
    Triage,
)
from irqrace.runstore import RunStore


def prepare_context(store: RunStore) -> list[dict[str, Any]]:
    """Ensure ``context/<cand_id>.json`` exists for every surviving candidate.

    If ``context/`` is already populated (for instance after stage 3 wrote the
    post-solver residue), those records are loaded and returned. Otherwise,
    candidates from ``stage2`` (or ``stage1`` if stage 2 did not run) that were
    not proven ``unsat`` in ``solver/results.jsonl`` are promoted into
    ``context/``.
    """
    ctx_dir = store.root / "context"
    ctx_files = sorted(ctx_dir.glob("*.json"))
    if ctx_files:
        records = [
            json.loads(p.read_text(encoding="utf-8")) for p in ctx_files
        ]
        for rec in records:
            contracts.validate("c2", rec, what=f"context/{rec.get('id')}.json")
        return records

    source_candidates = store.read_candidates("stage2") or store.read_candidates(
        "stage1"
    )
    solver_path = store.root / "solver" / "results.jsonl"
    verdicts: dict[str, dict[str, Any]] = {}
    if solver_path.exists():
        for line in solver_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                verdicts[r["candidate_id"]] = r

    store.set_stage("context", "running")
    promoted: list[dict[str, Any]] = []
    for rec in source_candidates:
        cid = rec["id"]
        sv = verdicts.get(cid)
        if sv and sv.get("verdict") == "unsat":
            continue
        enriched = json.loads(json.dumps(rec))
        if sv:
            enriched["solver_result"] = {
                k: v for k, v in sv.items() if k != "candidate_id"
            }
        store.write_context(enriched)
        promoted.append(enriched)

    store.set_stage(
        "context",
        "ok",
        candidates_in=len(source_candidates),
        candidates_out=len(promoted),
        dropped_with_proof=0,
    )
    store.log(
        "info",
        "context",
        "context-prepared",
        f"{len(promoted)} candidate(s) ready in context/",
    )
    return promoted


def triage_records(
    client: TriageClient,
    records: list[dict[str, Any]],
    *,
    make_resolver: Callable[[dict[str, Any]], Any],
    run_dir: Path,
    workers: int = 1,
    by_interval: bool = False,
    budget: Budget | None = None,
    should_stop: Callable[[], bool] = lambda: False,
    on_start: Callable[[dict[str, Any]], None] | None = None,
    on_done: Callable[[list[dict[str, Any]], dict[str, Triage | str]], None] | None = None,
) -> dict[str, Triage | str]:
    """One outcome per candidate id: a :class:`Triage`, or why there is none.

    With *workers* above 1 the conversations run in parallel; they are I/O, and
    each writes only its own directory. The outcome does not depend on *workers*,
    except under a budget, where calls in flight decide exactly where it stops.
    A candidate an interrupted run never reached has no entry. *on_done* runs on
    the calling thread, one conversation at a time; *on_start* on the worker.
    """
    groups = group_intervals(records) if by_interval else [[r] for r in records]
    if budget is not None:
        groups = sorted(groups, key=signal)  # the sort is stable: ties keep their order
    stop = threading.Event()

    def converse(group: list[dict[str, Any]]) -> Triage | str | None:
        lead = group[0]
        if stop.is_set() or should_stop():
            return None
        if budget is not None and (reason := budget.exceeded(client.spend)):
            return reason
        if on_start is not None:
            on_start(lead)
        interval = {"same_interval": group[1:]} if len(group) > 1 else {}
        try:
            return client.triage(lead, resolver=make_resolver(lead), run_dir=run_dir, **interval)
        except InterruptedError:
            stop.set()
            return None
        except RefusalError as e:
            return f"the model refused: {e}"
        except (BackendError, RuntimeError, ValueError) as e:
            return f"backend error: {e}"

    outcomes: dict[str, Triage | str] = {}

    def settle(group: list[dict[str, Any]], result: Triage | str | None) -> None:
        if result is None:
            return
        settled: dict[str, Triage | str] = {}
        for member in group:
            if isinstance(result, Triage) and len(group) > 1:
                settled[member["id"]] = result.model_copy(
                    update={
                        "candidate_id": member["id"],
                        "fingerprint": member["fingerprint"],
                        "interval_of": group[0]["id"],
                    }
                )
            else:
                settled[member["id"]] = result
        outcomes.update(settled)
        if on_done is not None:
            on_done(group, settled)

    if workers <= 1:
        for group in groups:
            settle(group, converse(group))
        return outcomes
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="irqrace-triage") as pool:
        futures = {pool.submit(converse, group): group for group in groups}
        for future in as_completed(futures):
            settle(futures[future], future.result())
    return outcomes


def triage_settings(workers: int, by_interval: bool, budget: Budget | None) -> dict[str, Any]:
    """What a run did beyond the prompt, for ``manifest.json["llm"]``.

    These change how much of the ranking a model looked at, so they travel with
    the numbers.
    """
    return {
        "workers": workers,
        "by_interval": by_interval,
        "budget": budget.as_manifest() if budget is not None else None,
    }


def triage_store(
    store: RunStore,
    *,
    config: PromptConfig = FULL,
    backend: Backend | str | None = None,
    samples: int = 1,
    resolver_mode: Literal["mock", "source", "auto"] = "auto",
    source_root: Path | str | None = None,
    workers: int = 1,
    by_interval: bool = False,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Run Track B triage over all candidates in ``store`` and write C3 outputs.

    :param workers: conversations at a time.
    :param by_interval: one conversation per interval; see
        :mod:`irqrace.llm.intervals`.
    :param budget: what the run may spend. What it leaves out stays in the
        report as ``uncertain``, with the reason.

    Writes:
    * ``llm/<cand_id>/turns.jsonl`` — full conversation transcript
    * ``llm/<cand_id>/verdict.json`` — structured :class:`Triage` verdict
    * ``llm/triage.jsonl`` — all verdicts ordered by :data:`INSPECTION_ORDER`
    * ``manifest.json`` — ``llm`` metadata and ``triage`` stage funnel metrics
    """
    started = time.perf_counter()
    records = prepare_context(store)
    resolved_backend = (
        backend
        if isinstance(backend, Backend)
        else from_spec(backend) if isinstance(backend, str) else from_spec()
    )
    client = TriageClient(config, backend=resolved_backend)

    manifest = store.read_manifest()
    manifest["llm"] = {
        "model": resolved_backend.spec,
        "prompt_config": config.name,
        "date": datetime.now_utc_date()
        if hasattr(datetime, "now_utc_date")
        else datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "votes": samples,
        "seed": None,
        **triage_settings(workers, by_interval, budget),
    }
    store.write_manifest(manifest)
    store.set_stage("triage", "running", candidates_in=len(records))

    runs: list[list[Triage]] = []
    excluded: list[tuple[str, str]] = []
    over_budget: dict[str, str] = {}

    for _ in range(samples):
        gone = {c for c, _ in excluded}
        pending = [rec for rec in records if rec["id"] not in gone]
        outcomes = triage_records(
            client,
            pending,
            make_resolver=lambda rec: resolver_for(rec, source_root=source_root, mode=resolver_mode),
            run_dir=store.root,
            workers=workers,
            by_interval=by_interval,
            budget=budget,
        )
        sample_triages = []
        for rec in pending:
            outcome = outcomes[rec["id"]]
            if isinstance(outcome, Triage):
                sample_triages.append(outcome)
            elif isinstance(outcome, OverBudget):
                over_budget[rec["id"]] = outcome
            else:
                excluded.append((rec["id"], outcome))
        runs.append(sample_triages)

    if excluded and not any(runs):
        wall_ms = int((time.perf_counter() - started) * 1000)
        msg = f"all {len(excluded)} candidate(s) excluded: {excluded[0][1]}"
        store.set_stage("triage", "failed", wall_ms=wall_ms, error=msg)
        store.log("error", "triage", "triage-failed", msg)
        raise BackendError(msg)

    non_empty_runs = [r for r in runs if r]
    final = (
        vote(non_empty_runs)
        if len(non_empty_runs) > 1
        else (non_empty_runs[0] if non_empty_runs else [])
    )
    # A candidate no sample could triage stays in the report as uncertain, with
    # the reason: a backend error is not evidence about the candidate.
    answered = {t.candidate_id for t in final}
    reasons = {**over_budget, **dict(excluded)}
    for rec in records:
        if rec["id"] not in answered:
            reason = reasons.get(rec["id"], "no verdict was produced")
            final.append(Triage.untriaged(rec, reason))
            store.log("warn", "triage", "candidate-not-triaged",
                      f"{rec['id']}: {reason}", candidate_id=rec["id"])
    ordered = sorted(final, key=lambda t: (t.rank_key, t.candidate_id))

    llm_dir = store.root / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)
    with (llm_dir / "triage.jsonl").open("w", encoding="utf-8") as fh:
        for t in ordered:
            cand_dir = llm_dir / t.candidate_id
            cand_dir.mkdir(parents=True, exist_ok=True)
            verdict_doc = {
                **t.model_dump(mode="json"),
                "bucket": t.bucket.value,
            }
            (cand_dir / "verdict.json").write_text(
                json.dumps(verdict_doc, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            fh.write(json.dumps(verdict_doc, ensure_ascii=False) + "\n")

    wall_ms = int((time.perf_counter() - started) * 1000)
    store.set_stage(
        "triage",
        "ok",
        wall_ms=wall_ms,
        candidates_in=len(records),
        candidates_out=len(ordered),
        dropped_with_proof=0,
    )

    bucket_counts = {
        b.value: sum(1 for t in ordered if t.bucket is b)
        for b in INSPECTION_ORDER
    }
    n_untriaged = sum(1 for t in ordered if t.not_triaged)
    store.log(
        "info",
        "triage",
        "triage-complete",
        f"triaged {len(ordered) - n_untriaged}/{len(records)} candidate(s) with "
        f"{resolved_backend.spec} ({config.name}); {n_untriaged} kept as uncertain "
        "without a verdict",
        buckets=bucket_counts,
        not_triaged=n_untriaged,
    )

    return {
        "run_id": store.read_manifest()["run_id"],
        "backend": resolved_backend.spec,
        "config": config.name,
        "candidates_in": len(records),
        "candidates_out": len(ordered),
        "buckets": bucket_counts,
        "not_triaged": n_untriaged,
        "triages": ordered,
        "consistency": (
            consistency(non_empty_runs)["__mean__"]
            if len(non_empty_runs) > 1
            else None
        ),
        "blocking_element_groups": blocking_element_groups(ordered),
        "request_distribution": (
            request_distribution(client.request_log)
            if client.request_log
            else None
        ),
        "excluded": [{"candidate": c, "reason": r} for c, r in excluded],
        "spend": client.spend,
        "wall_ms": wall_ms,
    }


def read_triages(store: RunStore) -> list[Triage]:
    """Read ``llm/triage.jsonl`` from a run store."""
    path = store.root / "llm" / "triage.jsonl"
    if not path.exists():
        return []
    out: list[Triage] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        doc.pop("bucket", None)
        out.append(Triage.model_validate(doc))
    return out


def repair_store(
    store: RunStore,
    *,
    config: PromptConfig = FULL,
    backend: Backend | str | None = None,
    buckets: tuple[Bucket, ...] = (Bucket.likely_real,),
) -> dict[str, Any]:
    """Run Track B repair on candidates in ``store`` matching ``buckets``.

    Writes ``repair/<cand_id>/patch.diff`` and ``repair/<cand_id>/patch.json``
    and updates the ``repair`` stage in ``manifest.json``.
    """
    started = time.perf_counter()
    records = {r["id"]: r for r in prepare_context(store)}
    triages = read_triages(store)

    if triages:
        target_ids = [t.candidate_id for t in triages if t.bucket in buckets]
    else:
        target_ids = sorted(records)

    resolved_backend = (
        backend
        if isinstance(backend, Backend)
        else from_spec(backend) if isinstance(backend, str) else from_spec()
    )
    client = RepairClient(config, backend=resolved_backend)
    store.set_stage("repair", "running", candidates_in=len(target_ids))

    patches: dict[str, Patch] = {}
    witness_issues: dict[str, list[str]] = {}
    excluded: list[tuple[str, str]] = []

    for cid in target_ids:
        rec = records.get(cid)
        if rec is None:
            continue
        try:
            patch = client.repair(rec, run_dir=store.root)
            patches[cid] = patch
            if probs := witness_problems(patch, rec):
                witness_issues[cid] = probs
        except RefusalError as e:
            excluded.append((cid, str(e)))
        except (BackendError, RuntimeError) as e:
            excluded.append((cid, f"backend error: {e}"))

    wall_ms = int((time.perf_counter() - started) * 1000)
    store.set_stage(
        "repair",
        "ok",
        wall_ms=wall_ms,
        candidates_in=len(target_ids),
        candidates_out=len(patches),
        dropped_with_proof=0,
    )
    store.log(
        "info",
        "repair",
        "repair-complete",
        f"generated {len(patches)}/{len(target_ids)} patch(es) with {resolved_backend.spec}",
        witness_issues=len(witness_issues),
        excluded=len(excluded),
    )

    return {
        "run_id": store.read_manifest()["run_id"],
        "backend": resolved_backend.spec,
        "config": config.name,
        "candidates_in": len(target_ids),
        "candidates_out": len(patches),
        "patches": patches,
        "witness_issues": witness_issues,
        "excluded": [{"candidate": c, "reason": r} for c, r in excluded],
        "spend": client.spend,
        "wall_ms": wall_ms,
    }
