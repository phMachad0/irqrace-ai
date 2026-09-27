"""The evaluation harness: counting unit, match rule, recall gate.

Both settings this module encodes were open blockers in ``wiki/Open Questions.md``
and were decided on 2026-09-10. They are written down here, in
``docs/evaluation-protocol.md``, and echoed into every run manifest, because
every recall number the project reports divides by the first and is computed with
the second.

**Counting unit: per-triple-instance.** One annotated triple is one defect. The
31 simple Racebench cases carry **48 bug points and 38 planted traps**. The
alternatives measured on the same suite were per-(case, variable) at 33/29 and
per-case at 31 — both coarser, both hiding that ``svp_simple_017_001`` carries
four distinct bug points on one variable. Per-triple-instance is also what
[[BMC4AV (paper)]]'s tables count, so cross-paper comparison stays possible.

**Match rule: same subject, same shared location, same ordered access lines.**
Access *kinds* are compared and reported but are **not** part of the match. Two
measurements justify that:

* the ordered line triple is already unique — ``(case, lines)`` distinguishes all
  86 annotations with zero collisions, and no trap shares a line triple with a
  bug point — so requiring kind equality buys no discrimination;
* 20 annotated accesses name a line that both reads and writes the variable
  (``for (x = 0; x < N; x++)``, ``x = x + 1``). Requiring kind equality would turn
  each of those into a coin flip about which access the detector chose to report.

Matching is against the **corrected** annotations (``bench/racebench-errata.yaml``),
never the raw ones: ``svp_simple_019_001``'s annotations name lines that contain
no access at all, so an exact match against the shipped text scores 0 on its bug
point no matter how good the analyzer is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .candidate import ROLE_ORDER
from .groundtruth import Annotation, SuiteGroundTruth

#: Recorded in every run manifest. Changing either invalidates comparison with
#: every previously reported number, which is the point of putting them there.
COUNTING_UNIT = "per-triple-instance"
MATCH_RULE = "same-subject-same-location-same-ordered-lines"

#: The denominators every recall figure on this suite divides by.
RACEBENCH_SIMPLE_BUG_POINTS = 48
RACEBENCH_SIMPLE_TRAPS = 38


def normalise_variable(name: str) -> str:
    """Reduce an annotation's variable spelling to a base identifier.

    The annotations name the shared location inconsistently: ``*p`` and ``*u``
    for a local pointer, ``*svp_simple_009_001_p`` for a global one,
    ``global_array[1]`` and ``tm_blocks[36]`` for one element,
    ``global_union.header`` for one field. None of those are errors — they are
    the source-level name of the location — but they must be reduced before they
    can be compared with a detector's resolved variable.
    """
    base = name.strip().lstrip("*&")
    for sep in ("[", ".", "->"):
        base = base.split(sep)[0]
    return base.strip()


def candidate_lines(record: dict[str, Any]) -> tuple[int, ...]:
    accesses = sorted(record["accesses"], key=lambda a: ROLE_ORDER.get(a["role"], 99))
    return tuple(a["source"]["line"] for a in accesses)


def candidate_pattern(record: dict[str, Any]) -> str:
    accesses = sorted(record["accesses"], key=lambda a: ROLE_ORDER.get(a["role"], 99))
    return "".join("R" if a["kind"] == "read" else "W" for a in accesses)


def candidate_names(record: dict[str, Any]) -> set[str]:
    """Every source-level name the candidate's location is known by."""
    var = record["variable"]
    names = {normalise_variable(var["name"])}
    names |= {normalise_variable(a) for a in var.get("aliases", [])}
    return {n for n in names if n}


@dataclass
class Match:
    annotation: Annotation
    candidate_id: str | None = None
    #: True when the candidate's access kinds also agree with the annotation.
    #: Not required for a match; reported so that systematic disagreement shows
    #: up rather than hiding.
    kinds_agree: bool | None = None
    #: True when the candidate's variable names include the annotation's.
    #: A False here with a successful match means the location was identified
    #: through aliasing, which is worth seeing.
    name_agrees: bool | None = None
    #: Position of the matching candidate in the reported order, 0-based. Feeds
    #: the Inspection Ratio.
    rank: int | None = None

    @property
    def detected(self) -> bool:
        return self.candidate_id is not None


@dataclass
class SubjectReport:
    subject: str
    bug_matches: list[Match] = field(default_factory=list)
    trap_matches: list[Match] = field(default_factory=list)
    candidates_reported: int = 0
    unmatched_candidates: int = 0

    @property
    def bugs_detected(self) -> int:
        return sum(1 for m in self.bug_matches if m.detected)

    @property
    def traps_reported(self) -> int:
        return sum(1 for m in self.trap_matches if m.detected)

    @property
    def missed(self) -> list[Annotation]:
        return [m.annotation for m in self.bug_matches if not m.detected]


def match_subject(
    annotations: Sequence[Annotation],
    candidates: Sequence[dict[str, Any]],
    *,
    subject: str,
) -> SubjectReport:
    """Match one subject's reported candidates against its annotations.

    Only ``atomicity-triple`` candidates take part. The ground truth is
    triple-shaped, and scoring pair candidates against it is exactly the
    vocabulary confusion the wiki flags in [[IntRace (paper)]], which reports
    triples under a two-access name ([[Pair-Triple Unification]]). Pair coverage
    is a separate number; see :func:`pair_coverage`.
    """
    report = SubjectReport(subject=subject)
    triples = [c for c in candidates if c.get("class") == "atomicity-triple"]
    report.candidates_reported = len(candidates)

    by_lines: dict[tuple[int, ...], list[tuple[int, dict[str, Any]]]] = {}
    for rank, c in enumerate(triples):
        by_lines.setdefault(candidate_lines(c), []).append((rank, c))

    consumed: set[str] = set()
    for ann in annotations:
        m = Match(annotation=ann)
        for rank, cand in by_lines.get(ann.lines, []):
            names = candidate_names(cand)
            base = normalise_variable(ann.variable)
            # The line triple is unique across all 86 annotations, so the name
            # check never has to succeed for the match to be right; it is
            # recorded so that alias-resolved matches stay visible.
            m.candidate_id = cand["id"]
            m.rank = rank
            m.name_agrees = base in names
            m.kinds_agree = candidate_pattern(cand) == ann.pattern
            consumed.add(cand["id"])
            break
        (report.bug_matches if ann.kind == "bug" else report.trap_matches).append(m)

    report.unmatched_candidates = len(triples) - len(consumed)
    return report


def pair_coverage(annotation: Annotation, candidates: Iterable[dict[str, Any]]) -> bool:
    """Is this triple covered by the reported *pair* candidates?

    A triple ``(A1, B, A2)`` is pair-covered when both of its projections,
    ``(A1, B)`` and ``(B, A2)``, appear among the reported race pairs. Reported
    alongside triple recall, never instead of it: a detector that finds both
    pairs has not necessarily found the atomicity violation, which is the whole
    argument of [[Pair-Triple Unification]].
    """
    pairs = {candidate_lines(c) for c in candidates if c.get("class") == "race-pair"}
    a1, b, a2 = annotation.lines
    return (a1, b) in pairs and (b, a2) in pairs


def inspection_ratio(report: SubjectReport) -> float | None:
    """Fraction of the reported list a reviewer must read to find every bug point.

    The headline metric for a recall-first tool, together with recall itself
    ([[Precision Metrics]]). Undefined when a bug point was missed — an
    Inspection Ratio computed over an incomplete detection is meaningless, so it
    returns ``None`` rather than a flattering number.
    """
    if not report.bug_matches:
        return None
    if any(not m.detected for m in report.bug_matches):
        return None
    if report.candidates_reported == 0:
        return None
    deepest = max(m.rank for m in report.bug_matches if m.rank is not None)
    return (deepest + 1) / report.candidates_reported


@dataclass
class SuiteReport:
    subjects: list[SubjectReport] = field(default_factory=list)

    @property
    def bug_points(self) -> int:
        return sum(len(s.bug_matches) for s in self.subjects)

    @property
    def bugs_detected(self) -> int:
        return sum(s.bugs_detected for s in self.subjects)

    @property
    def traps(self) -> int:
        return sum(len(s.trap_matches) for s in self.subjects)

    @property
    def traps_reported(self) -> int:
        return sum(s.traps_reported for s in self.subjects)

    @property
    def candidates_reported(self) -> int:
        return sum(s.candidates_reported for s in self.subjects)

    @property
    def recall(self) -> float | None:
        return self.bugs_detected / self.bug_points if self.bug_points else None

    @property
    def recall_gate_passes(self) -> bool:
        """The gate the whole project is built around: every annotated bug point
        must appear somewhere in the reported set."""
        return self.bug_points > 0 and self.bugs_detected == self.bug_points

    def missed(self) -> list[Annotation]:
        return [a for s in self.subjects for a in s.missed]


def match_suite(
    ground_truth: SuiteGroundTruth,
    candidates_by_subject: dict[str, Sequence[dict[str, Any]]],
) -> SuiteReport:
    out = SuiteReport()
    for case in ground_truth.cases:
        out.subjects.append(match_subject(
            case.all, candidates_by_subject.get(case.case, []), subject=case.case))
    return out


def report_json(report: "SubjectReport", *, stage: str = "stage1") -> dict[str, Any]:
    """The `eval/report.json` slot of a run directory (contract C3).

    Written per run so that a recall figure is never separated from the run that
    produced it, nor from the manifest recording the counting unit and match rule
    it was computed with.
    """
    return {
        "schema_version": "eval/1.0.0",
        "stage": stage,
        "subject": report.subject,
        "counting_unit": COUNTING_UNIT,
        "match_rule": MATCH_RULE,
        "ground_truth": "racebench-2.1_remarks + curated errata",
        "bug_points": len(report.bug_matches),
        "bugs_detected": report.bugs_detected,
        "recall_gate": report.bugs_detected == len(report.bug_matches),
        "traps": len(report.trap_matches),
        "traps_reported": report.traps_reported,
        "candidates_reported": report.candidates_reported,
        "candidates_matching_no_annotation": report.unmatched_candidates,
        "inspection_ratio": inspection_ratio(report),
        "matches": [
            {
                "kind": m.annotation.kind,
                "index": m.annotation.index,
                "variable": m.annotation.variable,
                "pattern": m.annotation.pattern,
                "lines": list(m.annotation.lines),
                "detected": m.detected,
                "candidate_id": m.candidate_id,
                "rank": m.rank,
                "kinds_agree": m.kinds_agree,
                "name_agrees": m.name_agrees,
            }
            for m in report.bug_matches + report.trap_matches
        ],
    }
