"""Racebench scoring over one or several run roots: the measurement layer of T1/T3.

``scripts/bench-triage-report.py`` is the command; this module is what it runs.
A **run root** is a directory holding one C3 run directory per simple case, as
``irqrace pipeline ... --run-root ROOT`` or ``scripts/freeze-and-triage.py``
leave it, optionally with ``timings.tsv`` (case, start epoch, end epoch, exit
code), ``start.txt`` / ``end.txt``, per-case logs in ``logs/``, and the batch
runner's ``batch.json`` and ``freeze.json``.

Nothing here re-implements the evaluation harness. Every label comes from
:func:`irqrace.run_evaluation.candidate_table` (the harness's match rule), every
per-stage figure from :func:`irqrace.run_evaluation.evaluate_run`, and the
legacy single-root report (:func:`legacy_report`) is the earlier script's code,
moved here unchanged so that its output stays byte-identical.

**What "reported" means.** The tool never drops a candidate without a proof, so
three readings are scored (:data:`VIEWS`): ``likely_real`` (the LLM's top
bucket), ``not infeasible`` (everything the LLM did not call infeasible) and
``static only`` (everything that reaches the LLM: stages 1-3 alone). The first
two are system S2, the third is system S1.

**Filters reach the denominators.** ``Subset`` restricts the cases and removes
whole access patterns (``RWW`` for BMC4AV's terms). A removed pattern removes
the bug points, the traps and the unannotated candidates of that shape, and the
Inspection Ratio is recomputed on what is left: the comparison is then on the
other paper's terms, not ours with a footnote.

**Label sets.** ``53/33`` (the suite as vendored, since the 2026-10-28 relabel)
is the only one implemented. :func:`register_label_set` is the extension point
for the Racebench 2.2 labels (T2), which another loader provides.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import math
import re
import statistics
import subprocess
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .evaluation import (
    RACEBENCH_SIMPLE_BUG_POINTS,
    RACEBENCH_SIMPLE_TRAPS,
    candidate_pattern,
    inspection_ratio,
    match_subject,
)
from .groundtruth import CaseGroundTruth
from .run_evaluation import REPO_ROOT, StageEval, _sets, candidate_table, case_ground_truth, evaluate_run
from .runstore import RunStore, find_runs

#: Bumped whenever a number this module produces could change for the same input.
SCORER_VERSION = "bench_metrics/1.0.0"

BUG, TRAP = 2, -3
VIEWS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "likely_real": lambda r: r["fate"] == "llm" and r["bucket"] == "likely_real",
    "not infeasible": lambda r: r["fate"] == "llm" and r["feasibility"] != "infeasible",
    "static only": lambda r: r["fate"] == "llm",
}
#: S1 is the static stages alone; S2 adds the LLM's reading.
SYSTEM = {"likely_real": "S2", "not infeasible": "S2", "static only": "S1"}
#: The ordering a view is read in, for the Inspection Ratio.
VIEW_STAGE = {"likely_real": "triage", "not infeasible": "triage", "static only": "context"}
#: The four atomicity-violation shapes the suite annotates bug points with.
PATTERNS = ("RWR", "WWR", "WRW", "RWW")
STAGES = ("build", "stage1", "stage2", "solver", "context", "triage")
STATIC_STAGES = ("build", "stage1", "stage2", "solver", "context")

PUBLISHED_YAML = REPO_ROOT / "bench" / "published-results.yaml"
PUBLISHED_FIELDS = ("tool", "reported_by", "cases", "ground_truth", "defect_class", "metric",
                    "value", "rerun_or_copied", "hardware", "source")
RERUN_OR_COPIED = ("run", "copied", "rebased", "unknown")

RUNS_FIELDS = ("run_id", "system", "prompt_row", "sample", "labels", "case_subset", "view",
               "bug_points_total", "bug_points_detected", "traps_total", "traps_reported",
               "unannotated_reported", "uncertain", "score", "score_max", "recall", "precision",
               "inspection_ratio_mean", "llm_calls", "tokens_in", "tokens_out", "backend_failures",
               "wall_s", "static_s", "llm_s")
PATTERNS_FIELDS = ("run_id", "labels", "case_subset", "view", "pattern", "bug_points_total",
                   "bug_points_detected")
ITEMS_FIELDS = ("run_id", "prompt_row", "sample", "case", "item_kind", "item_id", "triple",
                "pattern", "fate", "feasibility", "bucket", "confidence")
AGREEMENT_FIELDS = ("prompt_row", "run_a", "run_b", "field", "n_shared", "agreement", "kappa")
CASES_FIELDS = ("run_id", "case", "ir_static", "ir_triage")
#: How a view is spelled in the CSVs (the figure script's vocabulary); the
#: Markdown and the legacy report keep the readable names.
VIEW_ID = {"likely_real": "likely_real", "not infeasible": "not_infeasible", "static only": "static_only"}

#: Metrics aggregated over the independent runs of one prompt row.
AGGREGATED = ("bug_points_detected", "traps_reported", "score", "recall", "precision",
              "inspection_ratio_mean", "unannotated_reported", "uncertain", "llm_calls",
              "tokens_in", "tokens_out", "backend_failures", "wall_s", "static_s", "llm_s")


# ---------------------------------------------------------------------------
# Label sets
# ---------------------------------------------------------------------------


class LabelSetUnavailable(LookupError):
    """A label set that is named but cannot be loaded here."""


@dataclass(frozen=True)
class LabelSet:
    """A ground truth the scorer can label candidates with.

    ``ground_truth(subject)`` returns the case's annotations, or ``None`` when
    the subject has none. ``native`` marks the set that
    :func:`~irqrace.run_evaluation.candidate_table` and
    :func:`~irqrace.run_evaluation.evaluate_run` already label with; any other
    set is applied by re-matching stage 1's candidates with the same match rule.
    """

    name: str
    description: str
    ground_truth: Callable[[str], CaseGroundTruth | None]
    native: bool = False


LABEL_SETS: dict[str, LabelSet] = {}
DEFAULT_LABELS = "53/33"

#: Named, not implemented here. The message says what building them needs.
PLANNED_LABEL_SETS = {
    "2.2": "Racebench 2.2 (T2: the 2.1 labels plus adjudicated unannotated candidates) is built by "
           "its own loader; it plugs in with bench_metrics.register_label_set(LabelSet('2.2', ...)).",
    "48/38": "the labels before the 2026-10-28 relabel need the pristine annotations (vendored commit "
             "3d77421) and the errata as they stood before that date; not built.",
}


def register_label_set(labels: LabelSet) -> None:
    """The extension point: make ``labels`` selectable by name (``--labels``)."""
    LABEL_SETS[labels.name] = labels


register_label_set(LabelSet(
    DEFAULT_LABELS,
    "racebench 2.1_remarks as vendored (relabel 2026-10-28) + curated errata: "
    f"{RACEBENCH_SIMPLE_BUG_POINTS} bug points, {RACEBENCH_SIMPLE_TRAPS} traps",
    case_ground_truth,
    native=True,
))


def label_set(name: str) -> LabelSet:
    if name in LABEL_SETS:
        return LABEL_SETS[name]
    if name in PLANNED_LABEL_SETS:
        raise LabelSetUnavailable(f"label set {name!r} is not available: {PLANNED_LABEL_SETS[name]}")
    raise LabelSetUnavailable(f"unknown label set {name!r}; known: {', '.join(LABEL_SETS)}")


# ---------------------------------------------------------------------------
# Case subsets
# ---------------------------------------------------------------------------

_CASE_RE = re.compile(r"^(?:svp_simple_)?0*(\d{1,3})(?:_001)?$")


def normalise_case(token: str) -> str:
    """``7``, ``007``, ``svp_simple_007`` and ``svp_simple_007_001`` all name one case."""
    m = _CASE_RE.match(token.strip())
    if not m:
        raise ValueError(f"not a simple Racebench case: {token!r}")
    return f"svp_simple_{int(m.group(1)):03d}_001"


def parse_cases(values: Iterable[str]) -> frozenset[str]:
    """Case names from ``--cases``: each value a comma-separated list or a file.

    A file holds names separated by commas, spaces or newlines; ``#`` starts a
    comment.
    """
    out: set[str] = set()
    for value in values:
        path = Path(value)
        if path.is_file():
            text = "\n".join(line.split("#", 1)[0] for line in path.read_text(encoding="utf-8").splitlines())
        else:
            text = value
        out |= {normalise_case(t) for t in re.split(r"[\s,]+", text) if t}
    return frozenset(out)


@dataclass(frozen=True)
class Subset:
    """Which cases and which access patterns count -- numerators and denominators."""

    cases: frozenset[str] | None = None
    exclude_patterns: frozenset[str] = frozenset()
    name: str | None = None

    def has_case(self, subject: str) -> bool:
        return self.cases is None or subject in self.cases

    def has_pattern(self, pattern: str | None) -> bool:
        return pattern not in self.exclude_patterns

    @property
    def filtered(self) -> bool:
        return self.cases is not None or bool(self.exclude_patterns)

    @property
    def label(self) -> str:
        if self.name:
            return self.name
        parts = []
        if self.cases is not None:
            parts.append(f"cases={len(self.cases)}")
        if self.exclude_patterns:
            parts.append("exclude=" + "+".join(sorted(self.exclude_patterns)))
        return ";".join(parts) or "all"

    def describe(self) -> dict[str, Any]:
        return {"name": self.label,
                "cases": sorted(self.cases) if self.cases is not None else None,
                "exclude_patterns": sorted(self.exclude_patterns)}


# ---------------------------------------------------------------------------
# Loading a run root
# ---------------------------------------------------------------------------

#: The line ``irqrace llm triage`` prints with its token spend.
SPEND_RE = re.compile(r"^spend: (?P<fields>(?:\w+=\S+ ?)+)$", re.M)


def llm_calls_by_candidate(run: Path) -> dict[str, int]:
    """Assistant turns per candidate directory under ``llm/`` -- the earlier script's count."""
    out: dict[str, int] = {}
    for turns in (run / "llm").glob("*/turns.jsonl"):
        out[turns.parent.name] = sum(
            1 for line in turns.read_text(encoding="utf-8").splitlines()
            if line.strip() and json.loads(line).get("role") == "assistant")
    return out


def parse_spend(log_text: str) -> dict[str, float] | None:
    """The machine-readable spend line(s) of a case log, summed; ``None`` without one."""
    total: dict[str, float] = {}
    for m in SPEND_RE.finditer(log_text):
        for kv in m.group("fields").split():
            k, _, v = kv.partition("=")
            try:
                total[k] = total.get(k, 0) + float(v)
            except ValueError:
                continue
    return total or None


@dataclass
class CaseData:
    subject: str
    run: Path
    store: RunStore
    manifest: dict[str, Any]
    rows: list[dict[str, Any]]
    evals: dict[str, StageEval]
    gt: CaseGroundTruth | None
    timing: tuple[float, float, int] | None
    calls: dict[str, int]
    spend: dict[str, float] | None

    @property
    def stages(self) -> dict[str, dict[str, Any]]:
        return {s["name"]: s for s in self.manifest.get("stages", [])}

    @property
    def triaged(self) -> bool:
        return self.stages.get("triage", {}).get("status") == "ok"


@dataclass
class RootData:
    root: Path
    labels: LabelSet
    cases: list[CaseData]
    t_start: float | None
    t_end: float | None
    batch: dict[str, Any] | None
    freeze: dict[str, Any] | None
    run_id: str = ""

    @property
    def has_triage(self) -> bool:
        return any(c.triaged for c in self.cases)

    @property
    def prompt_row(self) -> str:
        if self.batch and self.batch.get("row"):
            return str(self.batch["row"])
        rows = sorted({(c.manifest.get("llm") or {}).get("prompt_config") for c in self.cases} - {None})
        return "|".join(rows)

    @property
    def backends(self) -> list[str]:
        return sorted({(c.manifest.get("llm") or {}).get("model") for c in self.cases} - {None})

    @property
    def sample(self) -> str:
        if self.batch and self.batch.get("sample") is not None:
            return str(self.batch["sample"])
        return self.root.name if self.root.name.isdigit() else ""

    @property
    def status(self) -> str:
        return str((self.batch or {}).get("status", "unknown"))


def _read_timings(root: Path) -> dict[str, tuple[float, float, int]]:
    timings: dict[str, tuple[float, float, int]] = {}
    tpath = root / "timings.tsv"
    if tpath.exists():
        for line in tpath.read_text().splitlines():
            if not line.strip():
                continue
            c, t0, t1, rc = line.split("\t")
            timings[c] = (float(t0), float(t1), int(rc))
    return timings


def _read_json(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _relabel(store: RunStore, rows: list[dict[str, Any]], case: CaseGroundTruth | None) -> list[dict[str, Any]]:
    """``rows`` labelled with another label set's annotations, by the same match rule."""
    labels: dict[str, tuple[str, int]] = {}
    if case is not None:
        rep = match_subject(case.all, store.read_candidates("stage1"), subject=case.case)
        for m in rep.bug_matches + rep.trap_matches:
            if m.candidate_id is not None:
                labels[m.candidate_id] = (m.annotation.kind, m.annotation.index)
    out = []
    for r in rows:
        lab = labels.get(r["id"])
        out.append({**r, "gt": lab[0] if lab else None, "gt_index": lab[1] if lab else None})
    return out


def stage_evals(store: RunStore, case: CaseGroundTruth | None,
                exclude: frozenset[str] = frozenset()) -> dict[str, StageEval]:
    """:func:`evaluate_run` for any annotations, optionally without some patterns.

    With nothing excluded and the native labels this computes exactly what
    :func:`evaluate_run` does (a test holds it to that); excluding a pattern
    removes its annotations and the candidates of that shape before matching,
    so the Inspection Ratio is the one a reviewer on those terms would face.
    """
    if case is None:
        return {}
    anns = [a for a in case.all if a.pattern not in exclude]
    out: dict[str, StageEval] = {}
    for stage, candidates in _sets(store):
        cands = [c for c in candidates if candidate_pattern(c) not in exclude]
        rep = match_subject(anns, cands, subject=case.case)
        out[stage] = StageEval(
            stage=stage, candidates=rep.candidates_reported, bug_points=len(rep.bug_matches),
            bugs_detected=rep.bugs_detected, traps=len(rep.trap_matches),
            traps_reported=rep.traps_reported, inspection_ratio=inspection_ratio(rep))
    return out


def load_root(root: Path | str, labels: LabelSet | str = DEFAULT_LABELS) -> RootData:
    """Everything the scorer needs from one run root, read once."""
    root = Path(root)
    ls = label_set(labels) if isinstance(labels, str) else labels
    timings = _read_timings(root)
    runs: dict[str, Path] = {}
    for r in find_runs(root):
        m = json.loads((r / "manifest.json").read_text())
        runs[m["subject"]["name"]] = r  # find_runs is sorted: the latest wins
    cases = []
    for subj, run in sorted(runs.items()):
        store = RunStore(run)
        manifest = store.read_manifest()
        rows = candidate_table(store)
        gt = ls.ground_truth(subj)
        if ls.native:
            evals = {e.stage: e for e in (evaluate_run(store) or [])}
        else:
            rows = _relabel(store, rows, gt)
            evals = stage_evals(store, gt)
        log = root / "logs" / f"{subj}.log"
        spend = parse_spend(log.read_text(encoding="utf-8", errors="replace")) if log.exists() else None
        cases.append(CaseData(subj, run, store, manifest, rows, evals, gt, timings.get(subj),
                              llm_calls_by_candidate(run), spend))
    t_start = float((root / "start.txt").read_text()) if (root / "start.txt").exists() else None
    t_end = float((root / "end.txt").read_text()) if (root / "end.txt").exists() else None
    rd = RootData(root, ls, cases, t_start, t_end, _read_json(root / "batch.json"),
                  _read_json(root / "freeze.json"))
    rd.run_id = str((rd.batch or {}).get("run_id") or "")
    if not rd.run_id:
        rd.run_id = f"{rd.prompt_row}/{rd.sample}" if (rd.prompt_row and rd.sample) else root.name
    return rd


# ---------------------------------------------------------------------------
# Items: every labelled annotation and every unannotated candidate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    case: str
    kind: str  # bug | trap | unannotated
    item_id: str  # "bug#2" / "trap#1" for annotations, the candidate id otherwise
    triple: str  # "W43 R64 W44": access kind and line, A1 B A2
    pattern: str
    fate: str  # stage1_absent | stage2 | solver | llm | pending
    row: dict[str, Any] | None

    @property
    def candidate_id(self) -> str | None:
        return self.row["id"] if self.row else None

    @property
    def feasibility(self) -> str | None:
        return self.row["feasibility"] if self.row else None

    @property
    def bucket(self) -> str | None:
        return self.row["bucket"] if self.row else None

    @property
    def confidence(self) -> float | None:
        return self.row["feasibility_confidence"] if self.row else None

    @property
    def reaches_llm(self) -> bool:
        return self.fate == "llm"

    @property
    def has_verdict(self) -> bool:
        return self.reaches_llm and self.bucket is not None and not self.row.get("not_triaged")

    def reported(self, view: str) -> bool:
        return self.row is not None and VIEWS[view](self.row)


def _fate(row: dict[str, Any] | None) -> str:
    if row is None:
        return "stage1_absent"
    return row["fate"].split(":", 1)[0]


def _row_triple(row: dict[str, Any]) -> tuple[str, str]:
    pattern = row.get("pattern") or ""
    lines = row.get("lines") or []
    if len(pattern) == len(lines):
        return pattern, " ".join(f"{k}{n}" for k, n in zip(pattern, lines))
    return pattern, " ".join(str(n) for n in lines)


def case_items(cd: CaseData, subset: Subset = Subset()) -> list[Item]:
    """The case's annotations (with or without a candidate) and its unannotated candidates."""
    if not subset.has_case(cd.subject):
        return []
    by_label = {(r["gt"], r["gt_index"]): r for r in cd.rows if r["gt"]}
    items: list[Item] = []
    for ann in (cd.gt.all if cd.gt else []):
        if not subset.has_pattern(ann.pattern):
            continue
        row = by_label.get((ann.kind, ann.index))
        triple = " ".join(f"{a.letter}{a.line}" for a in ann.accesses)
        items.append(Item(cd.subject, ann.kind, f"{ann.kind}#{ann.index}", triple, ann.pattern,
                          _fate(row), row))
    for row in cd.rows:
        if row["gt"]:
            continue
        pattern, triple = _row_triple(row)
        if not subset.has_pattern(pattern):
            continue
        items.append(Item(cd.subject, "unannotated", row["id"], triple, pattern, _fate(row), row))
    return items


def root_items(rd: RootData, subset: Subset = Subset()) -> list[Item]:
    return [it for cd in rd.cases for it in case_items(cd, subset)]


# ---------------------------------------------------------------------------
# Metrics per (run root, view)
# ---------------------------------------------------------------------------


@dataclass
class RunMetrics:
    run_id: str
    system: str
    prompt_row: str
    sample: str
    labels: str
    case_subset: str
    view: str
    bug_points_total: int
    bug_points_detected: int
    traps_total: int
    traps_reported: int
    unannotated_reported: int
    uncertain: int | None
    score: int
    score_max: int
    recall: float | None
    precision: float | None
    inspection_ratio_mean: float | None
    llm_calls: int | None
    tokens_in: int | None
    tokens_out: int | None
    backend_failures: int | None
    wall_s: float | None
    static_s: float | None
    llm_s: float | None
    patterns: dict[str, tuple[int, int]] = field(default_factory=dict)

    def csv_row(self) -> dict[str, Any]:
        return {**{k: getattr(self, k) for k in RUNS_FIELDS}, "view": VIEW_ID[self.view]}


def _sum_or_none(values: Iterable[float | int | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def _mean_or_none(values: Iterable[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.mean(vals) if vals else None


def views_for(rd: RootData) -> list[str]:
    """S1 always; S2's readings only for a root whose cases were triaged."""
    return list(VIEWS) if rd.has_triage else ["static only"]


def run_metrics(rd: RootData, subset: Subset = Subset()) -> list[RunMetrics]:
    items = root_items(rd, subset)
    cases = [cd for cd in rd.cases if subset.has_case(cd.subject)]
    bugs = [i for i in items if i.kind == "bug"]
    traps = [i for i in items if i.kind == "trap"]
    other = [i for i in items if i.kind == "unannotated"]
    in_llm = [i for i in items if i.reaches_llm]
    kept_ids = {(i.case, i.candidate_id) for i in items if i.candidate_id}

    # Costs. LLM calls are counted per candidate directory, so a removed pattern
    # removes its calls too; with no pattern removed this is the earlier count.
    if subset.exclude_patterns:
        calls = sum(n for cd in cases for cid, n in cd.calls.items() if (cd.subject, cid) in kept_ids)
    else:
        calls = sum(sum(cd.calls.values()) for cd in cases)
    spends = [cd.spend for cd in cases if cd.spend]
    tokens_in = tokens_out = None
    if spends and not subset.exclude_patterns:
        tokens_in = int(sum(s.get("tokens_in", 0) + s.get("cache_read", 0) + s.get("cache_write", 0)
                            for s in spends))
        tokens_out = int(sum(s.get("tokens_out", 0) for s in spends))
    failures = sum(1 for i in in_llm if i.bucket is None or i.row.get("not_triaged"))

    def stage_s(names: Sequence[str]) -> float | None:
        ms = [cd.stages.get(k, {}).get("wall_ms") for cd in cases for k in names]
        total = _sum_or_none(ms)
        return None if total is None else total / 1000
    static_s, llm_s = stage_s(STATIC_STAGES), stage_s(("triage",))
    walls = [cd.timing[1] - cd.timing[0] for cd in cases if cd.timing]
    if not subset.cases and rd.t_start and rd.t_end:
        wall_s: float | None = rd.t_end - rd.t_start
    else:
        wall_s = sum(walls) if walls else None

    out = []
    for view in views_for(rd):
        det = sum(1 for i in bugs if i.reported(view))
        fp = sum(1 for i in traps if i.reported(view))
        ir_stage = VIEW_STAGE[view]
        if subset.exclude_patterns or not rd.labels.native:
            irs = [stage_evals(cd.store, cd.gt, subset.exclude_patterns).get(ir_stage) for cd in cases]
        else:
            irs = [cd.evals.get(ir_stage) for cd in cases]
        s2 = SYSTEM[view] == "S2"
        patterns = {}
        for p in [p for p in PATTERNS if subset.has_pattern(p)] + sorted(
                {i.pattern for i in bugs} - set(PATTERNS)):
            sel = [i for i in bugs if i.pattern == p]
            patterns[p] = (len(sel), sum(1 for i in sel if i.reported(view)))
        out.append(RunMetrics(
            run_id=rd.run_id, system=SYSTEM[view], prompt_row=rd.prompt_row, sample=rd.sample,
            labels=rd.labels.name, case_subset=subset.label, view=view,
            bug_points_total=len(bugs), bug_points_detected=det,
            traps_total=len(traps), traps_reported=fp,
            unannotated_reported=sum(1 for i in other if i.reported(view)),
            uncertain=sum(1 for i in in_llm if i.bucket == "uncertain") if s2 else None,
            score=BUG * det + TRAP * fp, score_max=BUG * len(bugs),
            recall=det / len(bugs) if bugs else None,
            precision=det / (det + fp) if (det + fp) else None,
            inspection_ratio_mean=_mean_or_none(e.inspection_ratio if e else None for e in irs),
            llm_calls=calls if s2 else None,
            tokens_in=tokens_in if s2 else None, tokens_out=tokens_out if s2 else None,
            backend_failures=failures if s2 else None,
            wall_s=wall_s if s2 else None, static_s=static_s, llm_s=llm_s if s2 else None,
            patterns=patterns))
    return out


# ---------------------------------------------------------------------------
# Several runs: spread, agreement, flips
# ---------------------------------------------------------------------------


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Cohen's kappa of two raters over ``pairs``; ``None`` when undefined.

    Undefined for no pairs, and when chance agreement is 1 -- both runs gave a
    single, identical category to everything, so there is no disagreement a
    chance model could explain.
    """
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    cats = {a for a, _ in pairs} | {b for _, b in pairs}
    pe = sum((sum(1 for a, _ in pairs if a == c) / n) * (sum(1 for _, b in pairs if b == c) / n) for c in cats)
    if math.isclose(pe, 1.0):
        return None
    return (po - pe) / (1 - pe)


@dataclass(frozen=True)
class Agreement:
    prompt_row: str
    run_a: str
    run_b: str
    field: str
    n_shared: int
    agreement: float | None
    kappa: float | None

    def csv_row(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in AGREEMENT_FIELDS}


def _verdicts(items: Iterable[Item], what: str) -> dict[tuple[str, str], str]:
    """``(case, candidate id) -> verdict`` for the candidates the model answered."""
    return {(i.case, i.candidate_id): getattr(i, what) for i in items if i.has_verdict and getattr(i, what)}


def group_by_row(roots: Sequence[RootData]) -> dict[str, list[RootData]]:
    groups: dict[str, list[RootData]] = {}
    for rd in roots:
        groups.setdefault(rd.prompt_row or "(static)", []).append(rd)
    return groups


def agreement(roots: Sequence[RootData], subset: Subset = Subset()) -> list[Agreement]:
    """Pairwise agreement and kappa, on feasibility and bucket, per prompt row.

    Over the candidates both runs reached the LLM with and answered (a
    candidate kept as uncertain after a backend failure is not an answer).
    """
    out = []
    for row, group in group_by_row([r for r in roots if r.has_triage]).items():
        items = {rd.run_id: root_items(rd, subset) for rd in group}
        for a, b in combinations(group, 2):
            for fld in ("feasibility", "bucket"):
                va, vb = _verdicts(items[a.run_id], fld), _verdicts(items[b.run_id], fld)
                shared = sorted(set(va) & set(vb))
                pairs = [(va[k], vb[k]) for k in shared]
                out.append(Agreement(row, a.run_id, b.run_id, fld, len(pairs),
                                     (sum(1 for x, y in pairs if x == y) / len(pairs)) if pairs else None,
                                     cohen_kappa(pairs)))
    return out


@dataclass(frozen=True)
class Flip:
    prompt_row: str
    case: str
    item_id: str
    triple: str
    field: str
    values: tuple[tuple[str, str], ...]  # (run id, value) in run order


def flips(roots: Sequence[RootData], subset: Subset = Subset()) -> list[Flip]:
    """Every bug point and trap whose bucket or feasibility differs between runs of one row."""
    out = []
    for row, group in group_by_row([r for r in roots if r.has_triage]).items():
        if len(group) < 2:
            continue
        per_run = {rd.run_id: {(i.case, i.item_id): i for i in root_items(rd, subset) if i.kind != "unannotated"}
                   for rd in group}
        keys = sorted(set().union(*per_run.values()))
        for key in keys:
            for fld in ("bucket", "feasibility"):
                vals = []
                for rd in group:
                    it = per_run[rd.run_id].get(key)
                    v = (getattr(it, fld) if it and it.reaches_llm else None) or (it.fate if it else "-")
                    vals.append((rd.run_id, str(v)))
                if len({v for _, v in vals}) > 1:
                    it = next(per_run[r][key] for r, _ in vals if key in per_run[r])
                    out.append(Flip(row, key[0], key[1], it.triple, fld, tuple(vals)))
    return out


@dataclass(frozen=True)
class Spread:
    n: int
    mean: float | None
    sd: float | None  # sample standard deviation; None for fewer than two values
    min: float | None
    max: float | None


def spread(values: Iterable[float | int | None]) -> Spread:
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return Spread(0, None, None, None, None)
    return Spread(len(vals), statistics.mean(vals), statistics.stdev(vals) if len(vals) > 1 else None,
                  min(vals), max(vals))


def aggregate(metrics: Sequence[RunMetrics]) -> dict[tuple[str, str], dict[str, Spread]]:
    """``(prompt row, view) -> metric -> Spread`` over independent runs."""
    groups: dict[tuple[str, str], list[RunMetrics]] = {}
    for m in metrics:
        groups.setdefault((m.prompt_row or "(static)", m.view), []).append(m)
    return {k: {name: spread(getattr(m, name) for m in ms) for name in AGGREGATED}
            for k, ms in groups.items()}


# ---------------------------------------------------------------------------
# S0: the published results
# ---------------------------------------------------------------------------


class PublishedError(ValueError):
    pass


def load_published(path: Path | str = PUBLISHED_YAML) -> list[dict[str, Any]]:
    """The S0 rows of ``bench/published-results.yaml``, checked.

    Every row must carry every field of :data:`PUBLISHED_FIELDS`, a numeric
    value, a non-empty source, and say whether the number was run by the
    reporting paper, copied from another, or re-based by this project.
    """
    import yaml

    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if not rows:
        raise PublishedError(f"{path}: no rows")
    problems = []
    for n, row in enumerate(rows, 1):
        missing = [k for k in PUBLISHED_FIELDS if row.get(k) in (None, "")]
        if missing:
            problems.append(f"row {n} ({row.get('tool')}, {row.get('metric')}): missing {', '.join(missing)}")
            continue
        if not isinstance(row["value"], (int, float)) or isinstance(row["value"], bool):
            problems.append(f"row {n}: value {row['value']!r} is not a number")
        if row["rerun_or_copied"] not in RERUN_OR_COPIED:
            problems.append(f"row {n}: rerun_or_copied must be one of {RERUN_OR_COPIED}")
    if problems:
        raise PublishedError(f"{path}:\n  " + "\n  ".join(problems))
    return rows


def write_published_csv(rows: Sequence[dict[str, Any]], results_dir: Path) -> Path:
    path = results_dir / "published.csv"
    _write_csv(path, PUBLISHED_FIELDS, [{k: r[k] for k in PUBLISHED_FIELDS} for r in rows])
    return path


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _cell(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(round(v, 6))
    return v


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields))
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(r.get(k)) for k in fields})


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True,
                             timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def scorer_commit() -> dict[str, Any]:
    head = _git("rev-parse", "HEAD")
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    return {"commit": head, "dirty": bool(dirty) if dirty is not None else None}


def results_manifest(roots: Sequence[RootData], subset: Subset, labels: str) -> dict[str, Any]:
    commits = sorted({(rd.freeze or {}).get("git_commit") for rd in roots} - {None})
    return {
        "scorer_version": SCORER_VERSION,
        "date": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # The commit the runs were produced at, from the freeze record; null when
        # a root carries none (a run store made by hand or by the desktop app).
        "tool_git_commit": commits[0] if len(commits) == 1 else (commits or None),
        "scorer_git_commit": scorer_commit(),
        "backend": sorted({b for rd in roots for b in rd.backends}),
        "prompt_rows": sorted({rd.prompt_row for rd in roots if rd.prompt_row}),
        "label_set": labels,
        "case_subset": subset.describe(),
        "input_run_roots": [{"path": str(rd.root), "run_id": rd.run_id, "status": rd.status,
                             "cases": len(rd.cases)} for rd in roots],
    }


def items_rows(rd: RootData, subset: Subset) -> list[dict[str, Any]]:
    return [{"run_id": rd.run_id, "prompt_row": rd.prompt_row, "sample": rd.sample, "case": i.case,
             "item_kind": i.kind, "item_id": i.item_id, "triple": i.triple, "pattern": i.pattern,
             "fate": i.fate, "feasibility": i.feasibility, "bucket": i.bucket, "confidence": i.confidence}
            for i in root_items(rd, subset)]


def cases_rows(rd: RootData, subset: Subset) -> list[dict[str, Any]]:
    """Per-case Inspection Ratio in the records' own order and in triage order.

    Undefined (empty) where a bug point was missed or the case has none; the
    triage column is empty for a case that was not triaged.
    """
    out = []
    for cd in rd.cases:
        if not subset.has_case(cd.subject):
            continue
        if subset.exclude_patterns or not rd.labels.native:
            ev = stage_evals(cd.store, cd.gt, subset.exclude_patterns)
        else:
            ev = cd.evals
        out.append({"run_id": rd.run_id, "case": cd.subject,
                    "ir_static": ev["context"].inspection_ratio if "context" in ev else None,
                    "ir_triage": ev["triage"].inspection_ratio if "triage" in ev else None})
    return out


def write_results(results_dir: Path, roots: Sequence[RootData], subset: Subset, labels: str,
                  *, published: Sequence[dict[str, Any]] | None = None) -> dict[str, list]:
    """The results directory: ``runs.csv``, ``patterns.csv``, ``items.csv``,
    ``agreement.csv``, ``cases.csv``, ``manifest.json`` and, with S0 rows,
    ``published.csv``."""
    results_dir.mkdir(parents=True, exist_ok=True)
    metrics = [m for rd in roots for m in run_metrics(rd, subset)]
    agree = agreement(roots, subset)
    _write_csv(results_dir / "runs.csv", RUNS_FIELDS, (m.csv_row() for m in metrics))
    _write_csv(results_dir / "cases.csv", CASES_FIELDS, (r for rd in roots for r in cases_rows(rd, subset)))
    _write_csv(results_dir / "patterns.csv", PATTERNS_FIELDS, (
        {"run_id": m.run_id, "labels": m.labels, "case_subset": m.case_subset, "view": VIEW_ID[m.view],
         "pattern": p, "bug_points_total": t, "bug_points_detected": d}
        for m in metrics for p, (t, d) in m.patterns.items()))
    _write_csv(results_dir / "items.csv", ITEMS_FIELDS, (r for rd in roots for r in items_rows(rd, subset)))
    _write_csv(results_dir / "agreement.csv", AGREEMENT_FIELDS, (a.csv_row() for a in agree))
    (results_dir / "manifest.json").write_text(
        json.dumps(results_manifest(roots, subset, labels), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    if published is not None:
        write_published_csv(published, results_dir)
    return {"metrics": metrics, "agreement": agree}


def _f(v: Any, d: int = 2) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def _spread_cell(s: Spread, d: int = 2) -> str:
    if s.n == 0:
        return "-"
    if s.n == 1:
        return _f(s.mean, d)
    return f"{_f(s.mean, d)} ± {_f(s.sd, d)} [{_f(s.min, d)}–{_f(s.max, d)}]"


def markdown_report(roots: Sequence[RootData], subset: Subset, labels: str) -> str:
    """The multi-run report: per-run scores, per pattern, spread, agreement, flips."""
    metrics = [m for rd in roots for m in run_metrics(rd, subset)]
    out = ["# Racebench runs — scored", "",
           f"Label set `{labels}` ({label_set(labels).description}). Case subset `{subset.label}`"
           + (f" ({len(subset.cases)} cases)" if subset.cases is not None else "")
           + (f", patterns excluded: {', '.join(sorted(subset.exclude_patterns))}" if subset.exclude_patterns else "")
           + f". Scorer `{SCORER_VERSION}`.", "",
           "NASAC 2019 rule: +2 per bug point, −3 per trap reported. Unannotated detections are not "
           "false positives. S1 = `static only` (everything reaching the LLM); S2 = the LLM's readings.", "",
           "## Runs", "",
           "| run | status | prompt row | backend | cases | sample |", "| --- | --- | --- | --- | --- | --- |"]
    for rd in roots:
        out.append(f"| {rd.run_id} | {rd.status} | `{rd.prompt_row or '-'}` | {', '.join(rd.backends) or '-'} | "
                   f"{sum(1 for c in rd.cases if subset.has_case(c.subject))} | {rd.sample or '-'} |")
    out += ["", "## Scores per run", "",
            "| run | sys | reported = | bugs | traps (FP) | score | recall | precision | IR | unannot. | "
            "uncertain | calls | tokens in/out | not triaged | wall / static / LLM (s) |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m in metrics:
        tok = "-" if m.tokens_in is None else f"{m.tokens_in}/{m.tokens_out}"
        out.append(
            f"| {m.run_id} | {m.system} | {m.view} | {m.bug_points_detected}/{m.bug_points_total} | "
            f"{m.traps_reported}/{m.traps_total} | **{m.score}**/{m.score_max} | {_f(m.recall, 3)} | "
            f"{_f(m.precision, 3)} | {_f(m.inspection_ratio_mean)} | {m.unannotated_reported} | {_f(m.uncertain)} | "
            f"{_f(m.llm_calls)} | {tok} | {_f(m.backend_failures)} | "
            f"{_f(m.wall_s, 0)} / {_f(m.static_s, 1)} / {_f(m.llm_s, 0)} |")
    pats = list(dict.fromkeys(p for m in metrics for p in m.patterns))
    out += ["", "## Recall per access pattern (bug points detected / annotated)", "",
            "| run | reported = | " + " | ".join(pats) + " |", "| --- | --- | " + " | ".join("---" for _ in pats) + " |"]
    for m in metrics:
        out.append(f"| {m.run_id} | {m.view} | "
                   + " | ".join(f"{m.patterns[p][1]}/{m.patterns[p][0]}" if p in m.patterns else "-" for p in pats)
                   + " |")
    agg = aggregate(metrics)
    out += ["", "## Spread over independent runs (mean ± sample sd [min–max])", "",
            "| prompt row | reported = | n | bugs | traps | score | recall | precision | IR | unannot. | "
            "uncertain | calls |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for (row, view), s in agg.items():
        out.append(f"| `{row}` | {view} | {s['score'].n} | {_spread_cell(s['bug_points_detected'], 1)} | "
                   f"{_spread_cell(s['traps_reported'], 1)} | {_spread_cell(s['score'], 1)} | "
                   f"{_spread_cell(s['recall'], 3)} | {_spread_cell(s['precision'], 3)} | "
                   f"{_spread_cell(s['inspection_ratio_mean'])} | {_spread_cell(s['unannotated_reported'], 1)} | "
                   f"{_spread_cell(s['uncertain'], 1)} | {_spread_cell(s['llm_calls'], 0)} |")
    agree = agreement(roots, subset)
    if agree:
        out += ["", "## Agreement between runs of one prompt row", "",
                "Over the candidates both runs reached the LLM with and answered.", "",
                "| prompt row | run A | run B | field | shared | agreement | Cohen's κ |",
                "| --- | --- | --- | --- | --- | --- | --- |"]
        for a in agree:
            out.append(f"| `{a.prompt_row}` | {a.run_a} | {a.run_b} | {a.field} | {a.n_shared} | "
                       f"{_f(a.agreement, 3)} | {_f(a.kappa, 3)} |")
    fl = flips(roots, subset)
    if any(len(g) > 1 for g in group_by_row([r for r in roots if r.has_triage]).values()):
        out += ["", "## Labelled items whose verdict flips across runs", ""]
        if not fl:
            out.append("None: every bug point and trap got the same bucket and feasibility in every run.")
        else:
            out += ["| prompt row | case | item | triple | field | per run |", "| --- | --- | --- | --- | --- | --- |"]
            for f in fl:
                out.append(f"| `{f.prompt_row}` | {f.case[11:14]} | {f.item_id} | {f.triple} | {f.field} | "
                           + ", ".join(f"{r}: {v}" for r, v in f.values) + " |")
    # Trap disposition: which stage earns each rejection (T1 metric).
    out += ["", "## Trap disposition", "",
            "| run | never generated | stage 2 | solver unsat | LLM infeasible | LLM other | reported (likely_real) |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for rd in roots:
        traps = [i for i in root_items(rd, subset) if i.kind == "trap"]
        llm = [i for i in traps if i.reaches_llm]
        out.append(f"| {rd.run_id} | {sum(1 for i in traps if i.fate == 'stage1_absent')} | "
                   f"{sum(1 for i in traps if i.fate == 'stage2')} | {sum(1 for i in traps if i.fate == 'solver')} | "
                   + (f"{sum(1 for i in llm if i.feasibility == 'infeasible')} | "
                      f"{sum(1 for i in llm if i.feasibility != 'infeasible' and i.bucket != 'likely_real')} | "
                      f"{sum(1 for i in llm if i.bucket == 'likely_real')} |" if rd.has_triage
                      else f"- | {len(llm)} (not triaged) | - |"))
    # Recall veto: every bug point S2 calls infeasible, by name.
    vetoed = [(rd.run_id, i) for rd in roots if rd.has_triage for i in root_items(rd, subset)
              if i.kind == "bug" and i.reaches_llm and i.feasibility == "infeasible"]
    if any(rd.has_triage for rd in roots):
        out += ["", "## Bug points the LLM called infeasible (recall loss of the triage)", ""]
        out += [f"- {r}: {i.case} {i.item_id} `{i.triple}` ({i.pattern})" for r, i in vetoed] or ["None."]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# The legacy single-root report -- the earlier script, byte for byte
# ---------------------------------------------------------------------------


def legacy_report(rd: RootData) -> tuple[dict[str, Any], str]:
    """``report.json``'s document and ``report.md``'s text, as the script wrote them
    before the scorer was extended (commit 2063144). Kept identical on purpose:
    a test runs that version of the script next to this one."""
    root = rd.root
    cases, all_rows = [], []
    for cd in rd.cases:
        subj, run, m, rows, ev = cd.subject, cd.run, cd.manifest, cd.rows, cd.evals
        st = {s["name"]: s for s in m["stages"]}
        all_rows += rows
        wall = cd.timing
        cases.append({
            "subject": subj,
            "run": run.name,
            "llm": m.get("llm"),
            "stage1": st["stage1"].get("candidates_out"),
            "stage2": st["stage2"].get("candidates_out"),
            "context": st["context"].get("candidates_out"),
            "stage_ms": {k: st[k].get("wall_ms") for k in STAGES},
            "triage_status": st["triage"]["status"],
            "wall_s": (wall[1] - wall[0]) if wall else None,
            "exit": wall[2] if wall else None,
            "llm_calls": sum(cd.calls.values()),
            "bugs": sum(1 for r in rows if r["gt"] == "bug"),
            "traps": sum(1 for r in rows if r["gt"] == "trap"),
            "ir_static": ev["context"].inspection_ratio if "context" in ev else None,
            "ir_triage": ev["triage"].inspection_ratio if "triage" in ev else None,
            "untriaged": sum(1 for r in rows if r["not_triaged"]),
        })

    bugs = [r for r in all_rows if r["gt"] == "bug"]
    traps = [r for r in all_rows if r["gt"] == "trap"]
    other = [r for r in all_rows if r["gt"] is None and r["fate"] == "llm"]
    # Denominators from the ground truth of the subjects actually in this run.
    gts = [cd.gt for cd in rd.cases]
    n_bugs_gt = sum(len(g.bugs) for g in gts if g)
    n_traps_gt = sum(len(g.traps) for g in gts if g)
    traps_unmatched = n_traps_gt - len(traps)  # traps stage 1 never generated

    scores = {}
    for name, rep in VIEWS.items():
        det = sum(1 for r in bugs if rep(r))
        fp = sum(1 for r in traps if rep(r))
        scores[name] = {"bugs_detected": det, "false_positives": fp,
                        "score": BUG * det + TRAP * fp,
                        "unannotated_reported": sum(1 for r in other if rep(r))}

    t_start, t_end = rd.t_start, rd.t_end
    walls = [c["wall_s"] for c in cases if c["wall_s"] is not None]
    stage_tot = {k: sum((c["stage_ms"][k] or 0) for c in cases) for k in STAGES}
    irs_s = [c["ir_static"] for c in cases if c["ir_static"] is not None]
    irs_t = [c["ir_triage"] for c in cases if c["ir_triage"] is not None]

    def bucket_counts(sel):
        out: dict[str, int] = {}
        for r in sel:
            k = r["fate"] if r["fate"] != "llm" else (r["bucket"] or "untriaged")
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))

    summary = {
        "run_root": str(root),
        "subjects": len(cases),
        "llm": cases[0]["llm"] if cases else None,
        "ground_truth": {"bug_points": n_bugs_gt, "bug_points_generated": len(bugs),
                         "traps": n_traps_gt, "traps_generated": len(traps),
                         "traps_never_generated": traps_unmatched,
                         "suite_totals": [RACEBENCH_SIMPLE_BUG_POINTS, RACEBENCH_SIMPLE_TRAPS]},
        "funnel": {"stage1": sum(c["stage1"] or 0 for c in cases),
                   "stage2": sum(c["stage2"] or 0 for c in cases),
                   "reach_llm": sum(c["context"] or 0 for c in cases)},
        "bugs_by_outcome": bucket_counts(bugs),
        "traps_by_outcome": bucket_counts(traps),
        "unannotated_by_bucket": bucket_counts(other),
        "scores": scores,
        "max_score": BUG * n_bugs_gt,
        "inspection_ratio_mean": {"static": statistics.mean(irs_s) if irs_s else None,
                                  "triage": statistics.mean(irs_t) if irs_t else None},
        "time": {"total_wall_s": (t_end - t_start) if (t_start and t_end) else None,
                 "sum_case_wall_s": sum(walls), "mean_case_wall_s": statistics.mean(walls) if walls else None,
                 "max_case_wall_s": max(walls) if walls else None,
                 "stage_total_ms": stage_tot,
                 "llm_calls": sum(c["llm_calls"] for c in cases)},
        "untriaged": sum(c["untriaged"] for c in cases),
        "cases": cases,
    }
    doc = {"summary": summary, "candidates": all_rows}

    f = lambda v, d=2: "-" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))  # noqa: E731
    out = [f"# Racebench run — {root.name}", "",
           f"Model: `{(summary['llm'] or {}).get('model')}`, prompt row: "
           f"`{(summary['llm'] or {}).get('prompt_config')}`. {len(cases)} subjects.", "",
           "## Score (NASAC 2019 rule: +2 per bug point, −3 per trap reported)", "",
           f"Ground truth of these subjects: {n_bugs_gt} bug points, {n_traps_gt} traps "
           f"({traps_unmatched} never generated by stage 1). Maximum {BUG * n_bugs_gt}. "
           "Detections annotated as neither are not false positives.", "",
           "| reported = | bugs detected | traps reported (FP) | score | unannotated reported |",
           "| --- | --- | --- | --- | --- |"]
    for name, s in scores.items():
        out.append(f"| {name} | {s['bugs_detected']}/{n_bugs_gt} | {s['false_positives']}/"
                   f"{n_traps_gt} | **{s['score']}** | {s['unannotated_reported']} |")
    out += ["", "## Funnel and outcomes", "",
            f"- Candidates: stage 1 {summary['funnel']['stage1']} → stage 2 {summary['funnel']['stage2']} "
            f"→ reach the LLM {summary['funnel']['reach_llm']}.",
            f"- Bug points: {summary['bugs_by_outcome']}",
            f"- Traps (generated): {summary['traps_by_outcome']}",
            f"- Unannotated reaching the LLM: {summary['unannotated_by_bucket']}",
            f"- Not triaged (backend failures, kept as uncertain): {summary['untriaged']}",
            f"- Mean Inspection Ratio: before triage {f(summary['inspection_ratio_mean']['static'])}, "
            f"after triage {f(summary['inspection_ratio_mean']['triage'])}.",
            "", "## Time", "",
            f"- Total wall clock (4 cases in parallel): {f(summary['time']['total_wall_s'], 0)} s; "
            f"sum of per-case wall times {f(summary['time']['sum_case_wall_s'], 0)} s; "
            f"mean per case {f(summary['time']['mean_case_wall_s'], 0)} s, slowest "
            f"{f(summary['time']['max_case_wall_s'], 0)} s.",
            f"- LLM calls: {summary['time']['llm_calls']}.",
            "- Stage totals (ms): " + ", ".join(f"{k} {v}" for k, v in stage_tot.items()) + ".",
            "", "## Per case", "",
            "| case | s1 → s2 → LLM | bugs | traps | calls | wall (s) | build | stage1 | stage2 | solver | triage (ms) | IR before → after |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c in cases:
        sm = c["stage_ms"]
        out.append(f"| {c['subject'][11:14]} | {c['stage1']} → {c['stage2']} → {c['context']} | {c['bugs']} | "
                   f"{c['traps']} | {c['llm_calls']} | {f(c['wall_s'], 0)} | {sm['build']} | {sm['stage1']} | "
                   f"{sm['stage2']} | {sm['solver']} | {sm['triage']} | {f(c['ir_static'])} → {f(c['ir_triage'])} |")
    out += ["", "## Every bug point and trap", "",
            "| case | GT | lines | fate | feasibility (conf) | bucket |", "| --- | --- | --- | --- | --- | --- |"]
    for r in sorted(bugs + traps, key=lambda r: (r["subject"], r["gt"], r["gt_index"] or 0)):
        feas = "-" if r["feasibility"] is None else f"{r['feasibility']} ({f(r['feasibility_confidence'])})"
        out.append(f"| {r['subject'][11:14]} | {r['gt']} #{r['gt_index']} | {tuple(r['lines'])} | {r['fate']} | "
                   f"{feas} | {r['bucket'] or '-'} |")
    return doc, "\n".join(out) + "\n"
