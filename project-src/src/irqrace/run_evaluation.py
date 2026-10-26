"""Ground-truth evaluation of one run, stage by stage.

The desktop app, its PDF report and the dashboard all show recall, traps and the
Inspection Ratio per stage. They compute them here, with the evaluation harness's
own match rule (:func:`irqrace.evaluation.match_subject`), from what each stage
actually emitted. Nothing is assumed: a subject with no ground truth on this
machine gets ``None``, and a stage that did not run gets no row -- a recall figure
for a stage that never ran is a claim, not a measurement.

The sets evaluated are the ones the bench harness gates on: stage 1's and stage
2's candidates, and the context records that reach the LLM. One more is
measured here that the bench does not: the same context records **in the order
triage ranked them**. Triage drops nothing, so its recall equals the context
set's; what it changes is the order, which is exactly what the Inspection Ratio
measures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .evaluation import inspection_ratio, match_subject, report_json
from .groundtruth import CaseGroundTruth, ErrataError, SuiteGroundTruth, load_suite
from .llm.annotations import locate_suite
from .runstore import RunStore

REPO_ROOT = Path(__file__).resolve().parents[2]
ERRATA = REPO_ROOT / "bench" / "racebench-errata.yaml"

#: Stage names as they appear in a report row, in pipeline order.
STAGES = ("stage1", "stage2", "context", "triage")


@dataclass(frozen=True)
class StageEval:
    stage: str
    candidates: int
    bug_points: int
    bugs_detected: int
    traps: int
    traps_reported: int
    #: ``None`` when a bug point was missed or the stage reported nothing.
    inspection_ratio: float | None

    @property
    def recall_gate(self) -> bool:
        return self.bugs_detected == self.bug_points


@lru_cache(maxsize=4)
def _suite(root: str, errata: str) -> SuiteGroundTruth:
    return load_suite(Path(root), Path(errata))


def case_ground_truth(subject: str, *, suite_root: Path | None = None) -> CaseGroundTruth | None:
    """The annotated triples for ``subject``, or ``None`` if it has none here."""
    root = suite_root or locate_suite()
    if root is None or not Path(root).is_dir():
        return None
    try:
        suite = _suite(str(root), str(ERRATA))
    except (OSError, ErrataError):
        return None
    return next((c for c in suite.cases if c.case == subject), None)


def _triage_order(store: RunStore, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {c["id"]: c for c in contexts}
    path = store.root / "llm" / "triage.jsonl"
    ranked = [
        json.loads(line)["candidate_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ordered = [by_id[cid] for cid in ranked if cid in by_id]
    # A context record triage did not list would be a pipeline defect; keep it
    # at the end rather than letting it fall out of the denominator.
    seen = set(ranked)
    return ordered + [c for c in contexts if c["id"] not in seen]


def _sets(store: RunStore) -> list[tuple[str, list[dict[str, Any]]]]:
    status = {s["name"]: s["status"] for s in store.read_manifest().get("stages", [])}
    out: list[tuple[str, list[dict[str, Any]]]] = []
    if status.get("stage1") == "ok":
        out.append(("stage1", store.read_candidates("stage1")))
    if status.get("stage2") == "ok":
        out.append(("stage2", store.read_candidates("stage2")))
    if status.get("context") == "ok":
        contexts = store.read_contexts()
        out.append(("context", contexts))
        if status.get("triage") == "ok" and (store.root / "llm" / "triage.jsonl").exists():
            out.append(("triage", _triage_order(store, contexts)))
    return out


def evaluate_run(store: RunStore, *, suite_root: Path | None = None) -> list[StageEval] | None:
    """One :class:`StageEval` per stage that ran, or ``None`` without ground truth."""
    subject = store.read_manifest()["subject"]["name"]
    case = case_ground_truth(subject, suite_root=suite_root)
    if case is None:
        return None
    rows = []
    for stage, candidates in _sets(store):
        rep = match_subject(case.all, candidates, subject=subject)
        rows.append(
            StageEval(
                stage=stage,
                candidates=rep.candidates_reported,
                bug_points=len(rep.bug_matches),
                bugs_detected=rep.bugs_detected,
                traps=len(rep.trap_matches),
                traps_reported=rep.traps_reported,
                inspection_ratio=inspection_ratio(rep),
            )
        )
    return rows


def write_report(store: RunStore, *, suite_root: Path | None = None) -> dict[str, Any] | None:
    """Write ``eval/report.json`` the way ``irqrace stage3-all`` does.

    Taken on the last static set that exists -- the context records when stage 3
    ran, otherwise stage 2's or stage 1's candidates -- and named by the stage
    that produced it, so a report from a partial run says how far it got.
    Returns the report, or ``None`` when the subject has no ground truth here.
    """
    manifest = store.read_manifest()
    subject = manifest["subject"]["name"]
    case = case_ground_truth(subject, suite_root=suite_root)
    if case is None:
        return None
    static = [(s, c) for s, c in _sets(store) if s != "triage"]
    if not static:
        return None
    stage, candidates = static[-1]
    rep = match_subject(case.all, candidates, subject=subject)
    doc = report_json(rep, stage={"context": "stage3"}.get(stage, stage))
    (store.root / "eval").mkdir(parents=True, exist_ok=True)
    (store.root / "eval" / "report.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return doc
