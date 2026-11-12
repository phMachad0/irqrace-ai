"""Extended Racebench label sets: ``2.1`` (the suite's own) and ``2.2`` (2.1 plus adjudicated).

**DRAFT for gate M4a** (``docs/evaluation-protocol.md``, "DRAFT -- Racebench
2.2"). The suite's authors never claimed their annotations were exhaustive, and
the tool reports candidates nobody annotated. ``2.2`` is the 2.1 ground truth
plus every such candidate a *human* adjudicated from the source and the README,
recorded one triple per entry in ``bench/racebench-2.2.yaml``. This module:

* loads and validates that file (:func:`load_labels`), fail-fast as the errata
  are: an entry that collides with a 2.1 annotation or names a line outside its
  file is an error, not a warning;
* returns the ground truth for a label set (:func:`ground_truth`): ``"2.1"`` is
  exactly :func:`irqrace.groundtruth.load_suite` -- 53 bug points, 33 traps --
  and ``"2.2"`` appends the entries whose verdict is ``bug`` or ``trap`` to a
  *copy* of it, so 2.1 is never touched and the scorer can gain
  ``--labels 2.1|2.2`` by calling one function;
* implements the **equivalence rule** that says when two triples are the same
  defect (:func:`defect_classes`), so every count is reported both as triples
  and as distinct defects (:func:`label_counts`);
* computes the inter-adjudicator agreement (:func:`cohen_kappa`,
  :func:`second_check_agreement`).

Nothing here reads an LLM verdict. The label file holds a human's verdicts; the
equivalence rule is decided from the triples (case, location, lines) alone.
"""

from __future__ import annotations

import copy
import datetime as _dt
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .evaluation import normalise_variable
from .groundtruth import Access, Annotation, CaseGroundTruth, SuiteGroundTruth, load_suite

REPO_ROOT = Path(__file__).resolve().parents[2]
ERRATA = REPO_ROOT / "bench" / "racebench-errata.yaml"
LABELS_22 = REPO_ROOT / "bench" / "racebench-2.2.yaml"

SCHEMA_VERSION = "labels-ext/1.0.0"
LABEL_SETS = ("2.1", "2.2")

#: The four verdicts an adjudicator may record. Only ``bug`` and ``trap`` enter
#: a denominator; ``not-a-defect`` and ``undecided`` are reported as counts.
VERDICTS = ("bug", "trap", "not-a-defect", "undecided")
#: The witness fields a ``bug`` verdict must fill (the template in the protocol).
WITNESS_FIELDS = ("arrival_point", "masking_at_arrival", "guard_values", "effect")
ROLES = ("A1", "B", "A2")
KINDS = ("read", "write")

#: Recorded next to every count, as COUNTING_UNIT and MATCH_RULE are.
EQUIVALENCE_RULE = (
    "same-case-same-location; E1 same three lines | E2 same A1 and A2 | "
    "E3 same B and a shared endpoint; transitive closure over the triples counted"
)

#: Marks an Annotation that came from the label file rather than the suite.
EXTENSION_MARK = "racebench-2.2 extension"


class LabelError(ValueError):
    """The label file is malformed or does not apply cleanly to the suite."""


# ---------------------------------------------------------------------------
# The label file
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntryAccess:
    role: str
    kind: str
    line: int
    flow: str | None = None
    #: Relative to the suite's case directory root; ``None`` = the case file.
    file: str | None = None


@dataclass(frozen=True)
class SecondCheck:
    done: bool
    adjudicator: str | None = None
    verdict: str | None = None
    date: str | None = None


@dataclass(frozen=True)
class LabelEntry:
    id: str
    case: str
    variable: str
    accesses: tuple[EntryAccess, ...]
    verdict: str
    adjudicator: str
    date: str
    witness: dict[str, str] = field(default_factory=dict)
    blocking_reason: str | None = None
    candidate_ids: tuple[str, ...] = ()
    second_check: SecondCheck = SecondCheck(done=False)
    notes: str | None = None

    @property
    def lines(self) -> tuple[int, ...]:
        return tuple(a.line for a in self.accesses)

    @property
    def pattern(self) -> str:
        return "".join("R" if a.kind == "read" else "W" for a in self.accesses)


@dataclass
class LabelSet:
    path: Path | None
    label_set: str
    base: str
    entries: list[LabelEntry]

    def by_verdict(self) -> Counter:
        return Counter(e.verdict for e in self.entries)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _iso(value: Any) -> str | None:
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()[:10]
    if isinstance(value, str):
        try:
            return _dt.date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            return None
    return None


def _parse_entry(raw: Any, where: str, errors: list[str]) -> LabelEntry | None:
    if not isinstance(raw, dict):
        errors.append(f"{where}: an entry must be a mapping")
        return None
    start = len(errors)
    eid = _text(raw.get("id"))
    if not eid:
        errors.append(f"{where}: missing id")
    where = f"{where} ({eid})" if eid else where
    case = _text(raw.get("case"))
    variable = _text(raw.get("variable"))
    for name, value in (("case", case), ("variable", variable)):
        if not value:
            errors.append(f"{where}: missing {name}")

    accesses: list[EntryAccess] = []
    triple = raw.get("triple")
    if not isinstance(triple, list) or len(triple) != 3:
        errors.append(f"{where}: triple must list exactly three accesses, A1, B, A2")
    else:
        for role, acc in zip(ROLES, triple):
            if not isinstance(acc, dict):
                errors.append(f"{where}: access {role} must be a mapping")
                continue
            if acc.get("role", role) != role:
                errors.append(f"{where}: access {role} is labelled {acc.get('role')!r}; order is A1, B, A2")
            kind = acc.get("kind")
            if kind not in KINDS:
                errors.append(f"{where}: access {role} kind {kind!r} is not read/write")
            line = acc.get("line")
            if not isinstance(line, int) or isinstance(line, bool) or line < 1:
                errors.append(f"{where}: access {role} line {line!r} is not a positive integer")
            accesses.append(EntryAccess(
                role=role, kind=kind, line=line if isinstance(line, int) else 0,
                flow=_text(acc.get("flow")), file=_text(acc.get("file"))))

    verdict = raw.get("verdict")
    if verdict not in VERDICTS:
        errors.append(f"{where}: verdict {verdict!r} is not one of {', '.join(VERDICTS)}")

    witness_raw = raw.get("witness") or {}
    if not isinstance(witness_raw, dict):
        errors.append(f"{where}: witness must be a mapping")
        witness_raw = {}
    witness = {k: _text(witness_raw.get(k)) for k in WITNESS_FIELDS}
    unknown = set(witness_raw) - set(WITNESS_FIELDS)
    if unknown:
        errors.append(f"{where}: unknown witness field(s) {sorted(unknown)}")
    blocking = _text(raw.get("blocking_reason"))
    if verdict == "bug":
        missing = [k for k in WITNESS_FIELDS if not witness[k]]
        if missing:
            errors.append(
                f"{where}: a bug verdict needs a concrete interleaving witness; "
                f"empty: {', '.join(missing)}")
        if blocking:
            errors.append(f"{where}: a bug verdict has no blocking_reason")
    elif verdict in VERDICTS and not blocking:
        errors.append(f"{where}: verdict {verdict!r} needs a blocking_reason")

    adjudicator = _text(raw.get("adjudicator"))
    if not adjudicator:
        errors.append(f"{where}: missing adjudicator")
    date = _iso(raw.get("date"))
    if not date:
        errors.append(f"{where}: date {raw.get('date')!r} is not an ISO date")

    sc_raw = raw.get("second_check") or {"done": False}
    if not isinstance(sc_raw, dict) or not isinstance(sc_raw.get("done"), bool):
        errors.append(f"{where}: second_check.done must be true or false")
        sc = SecondCheck(done=False)
    else:
        sc = SecondCheck(
            done=sc_raw["done"], adjudicator=_text(sc_raw.get("adjudicator")),
            verdict=sc_raw.get("verdict"), date=_iso(sc_raw.get("date")))
        if sc.done:
            if not sc.adjudicator:
                errors.append(f"{where}: second_check is done but names no adjudicator")
            elif adjudicator and sc.adjudicator == adjudicator:
                errors.append(f"{where}: the second check must be by a different person")
            if sc.verdict not in VERDICTS:
                errors.append(f"{where}: second_check.verdict {sc.verdict!r} is not a verdict")

    cids = raw.get("candidate_ids") or []
    if not isinstance(cids, list):
        errors.append(f"{where}: candidate_ids must be a list")
        cids = []

    if len(errors) > start:
        return None
    return LabelEntry(
        id=eid, case=case, variable=variable, accesses=tuple(accesses),
        verdict=verdict, adjudicator=adjudicator, date=date, witness=witness,
        blocking_reason=blocking, candidate_ids=tuple(str(c) for c in cids),
        second_check=sc, notes=_text(raw.get("notes")))


def parse_labels(doc: Any, *, path: Path | None = None) -> LabelSet:
    """Validate a parsed label document; raise :class:`LabelError` listing every problem."""
    where = str(path) if path else "<labels>"
    errors: list[str] = []
    if not isinstance(doc, dict):
        raise LabelError(f"{where}: not a mapping")
    if doc.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{where}: schema_version {doc.get('schema_version')!r}, expected {SCHEMA_VERSION!r}")
    label_set = str(doc.get("label_set", ""))
    if label_set != "2.2":
        errors.append(f"{where}: label_set {label_set!r}, expected '2.2'")
    base = str(doc.get("base", ""))
    if base != "2.1":
        errors.append(f"{where}: base {base!r}, expected '2.1'")
    raw_entries = doc.get("entries")
    if raw_entries is None:
        raw_entries = []
    if not isinstance(raw_entries, list):
        errors.append(f"{where}: entries must be a list")
        raw_entries = []

    entries: list[LabelEntry] = []
    for n, raw in enumerate(raw_entries, start=1):
        entry = _parse_entry(raw, f"{where}: entry {n}", errors)
        if entry is not None:
            entries.append(entry)

    ids = Counter(e.id for e in entries)
    for eid, n in ids.items():
        if n > 1:
            errors.append(f"{where}: id {eid} is used {n} times")
    keys = Counter((e.case, _sites_of_entry(e)) for e in entries)
    for (case, sites), n in keys.items():
        if n > 1:
            errors.append(f"{where}: {case} lines {tuple(s[1] for s in sites)} are labelled {n} times")
    if errors:
        raise LabelError("\n".join(errors))
    return LabelSet(path=path, label_set=label_set, base=base, entries=entries)


def load_labels(path: Path | str = LABELS_22, *, suite: SuiteGroundTruth | None = None) -> LabelSet:
    """Load ``bench/racebench-2.2.yaml``; with ``suite``, also check it against 2.1."""
    import yaml

    path = Path(path)
    labels = parse_labels(yaml.safe_load(path.read_text(encoding="utf-8")), path=path)
    if suite is not None:
        check_against_suite(labels, suite)
    return labels


def check_against_suite(labels: LabelSet, suite: SuiteGroundTruth) -> None:
    """Fail-fast cross-check of the entries against the 2.1 ground truth.

    2.2 only *adds* labels to triples 2.1 left unannotated: an entry whose line
    triple is already a 2.1 annotation in that case is an error (the match rule's
    key is the line triple, so the two labels could not be told apart). So is an
    entry naming an unknown case, or a line outside its file.
    """
    errors: list[str] = []
    cases = {c.case: c for c in suite.cases}
    for e in labels.entries:
        case = cases.get(e.case)
        if case is None:
            errors.append(f"{e.id}: unknown case {e.case!r}")
            continue
        n_lines = len(case.path.read_text(encoding="utf-8").splitlines())
        for a in e.accesses:
            if a.file is None and a.line > n_lines:
                errors.append(f"{e.id}: {a.role} line {a.line} is outside {case.path.name} ({n_lines} lines)")
        mine = _sites_of_entry(e)
        for ann in case.all:
            if _sites_of_annotation(ann, case) == mine:
                errors.append(
                    f"{e.id}: {e.case} lines {e.lines} are already 2.1 {ann.kind} {ann.index}; "
                    "2.2 labels only triples 2.1 left unannotated")
    if errors:
        raise LabelError("\n".join(errors))


# ---------------------------------------------------------------------------
# Ground truth per label set
# ---------------------------------------------------------------------------


def is_extension(ann: Annotation) -> bool:
    """Whether ``ann`` came from the 2.2 label file rather than the suite."""
    return any(a.startswith(EXTENSION_MARK) for a in ann.anomalies)


def extension_annotation(entry: LabelEntry, *, kind: str, index: int) -> Annotation:
    accesses = tuple(
        Access(kind=a.kind, line=a.line, raw=f"<{'R' if a.kind == 'read' else 'W'}#{a.line}>", file=a.file)
        for a in entry.accesses
    )
    return Annotation(
        case=entry.case, kind=kind, index=index, variable=entry.variable,
        accesses=accesses, annotation_line=0,
        raw=f"racebench-2.2.yaml#{entry.id}",
        anomalies=(f"{EXTENSION_MARK}: {entry.id} ({entry.verdict}, {entry.adjudicator}, {entry.date})",),
    )


def extend(suite: SuiteGroundTruth, labels: LabelSet, *, not_a_defect_as_trap: bool = False) -> SuiteGroundTruth:
    """A copy of ``suite`` with the label file's bug and trap entries appended.

    New annotations are numbered after the case's highest 2.1 index of their
    kind, in entry-id order, so ``(kind, index)`` stays unique and stable.
    ``undecided`` never enters; ``not-a-defect`` enters as a trap only when
    ``not_a_defect_as_trap`` (an open decision at gate M4a).
    """
    check_against_suite(labels, suite)
    out = copy.deepcopy(suite)
    cases = {c.case: c for c in out.cases}
    kinds = {"bug": "bug", "trap": "trap"}
    if not_a_defect_as_trap:
        kinds["not-a-defect"] = "trap"
    for entry in sorted(labels.entries, key=lambda e: e.id):
        kind = kinds.get(entry.verdict)
        if kind is None:
            continue
        case = cases[entry.case]
        bucket = case.bugs if kind == "bug" else case.traps
        index = max((a.index for a in bucket), default=0) + 1
        bucket.append(extension_annotation(entry, kind=kind, index=index))
    return out


def ground_truth(
    label_set: str = "2.1",
    *,
    suite_root: Path | None = None,
    errata: Path | None = ERRATA,
    labels_path: Path | None = None,
    not_a_defect_as_trap: bool = False,
) -> SuiteGroundTruth:
    """The ground truth for ``label_set``: ``"2.1"`` (53/33) or ``"2.2"``.

    ``"2.1"`` is :func:`irqrace.groundtruth.load_suite` unchanged. ``"2.2"`` is
    :func:`extend` of it with ``labels_path`` (default ``bench/racebench-2.2.yaml``).
    """
    if label_set not in LABEL_SETS:
        raise LabelError(f"unknown label set {label_set!r}; known: {', '.join(LABEL_SETS)}")
    if suite_root is None:
        from .racebench import locate_suite

        suite_root = locate_suite()
        if suite_root is None:
            raise LabelError("the Racebench suite is not available (bench/racebench or IRQRACE_RACEBENCH)")
    suite = load_suite(Path(suite_root), Path(errata) if errata else None)
    if label_set == "2.1":
        return suite
    labels = load_labels(labels_path or LABELS_22)
    return extend(suite, labels, not_a_defect_as_trap=not_a_defect_as_trap)


# ---------------------------------------------------------------------------
# The equivalence rule
# ---------------------------------------------------------------------------

#: A site is (file name, line). Racebench names files relative to the suite and
#: annotations name none (one case file each), so the file is reduced to its
#: name and an annotation's accesses default to the case file.
Site = tuple[str, int]


def _site(file: str | None, line: int, default_file: str) -> Site:
    return (Path(file).name if file else default_file, int(line))


def _case_file(case: str) -> str:
    return f"{case}.c"


def _sites_of_entry(e: LabelEntry) -> tuple[Site, Site, Site]:
    return tuple(_site(a.file, a.line, _case_file(e.case)) for a in e.accesses)  # type: ignore[return-value]


def _sites_of_annotation(ann: Annotation, case: CaseGroundTruth | None = None) -> tuple[Site, ...]:
    default = case.path.name if case is not None else _case_file(ann.case)
    return tuple(_site(a.file, a.line, default) for a in ann.accesses)


@dataclass(frozen=True)
class Triple:
    """The equivalence rule's view of a triple: nothing but case, location, sites."""

    key: str
    case: str
    names: frozenset[str]
    sites: tuple[Site, Site, Site]
    #: What the triple is, for reports: "2.1 bug 1", "2.2 R22-004", "c0955b8e...".
    label: str = ""

    @property
    def a1(self) -> Site:
        return self.sites[0]

    @property
    def b(self) -> Site:
        return self.sites[1]

    @property
    def a2(self) -> Site:
        return self.sites[2]

    @property
    def lines(self) -> tuple[int, int, int]:
        return tuple(s[1] for s in self.sites)  # type: ignore[return-value]


def triple_from_annotation(ann: Annotation, case: CaseGroundTruth | None = None) -> Triple:
    origin = ann.raw if is_extension(ann) else f"2.1 {ann.kind} {ann.index}"
    return Triple(
        key=f"{ann.case}:{ann.kind}:{ann.index}", case=ann.case,
        names=frozenset({normalise_variable(ann.variable)}) - {""},
        sites=_sites_of_annotation(ann, case),  # type: ignore[arg-type]
        label=origin,
    )


def triple_from_record(record: dict[str, Any]) -> Triple:
    """A C2 candidate or context record as a :class:`Triple`."""
    from .evaluation import candidate_names

    order = {r: i for i, r in enumerate(ROLES)}
    accesses = sorted(record["accesses"], key=lambda a: order.get(a["role"], 99))
    case = record["subject"]["name"]
    return Triple(
        key=record["id"], case=case, names=frozenset(candidate_names(record)),
        sites=tuple(_site(a["source"]["file"], a["source"]["line"], _case_file(case)) for a in accesses),  # type: ignore[arg-type]
        label=record["id"],
    )


def sibling_reason(t: Triple, u: Triple) -> str | None:
    """Which clause of the equivalence rule makes ``t`` and ``u`` one defect, if any.

    * ``E1`` -- same three sites (they differ only in access kinds, columns, or
      the flow / call path by which a line is reached);
    * ``E2`` -- same A1 and same A2, another B (another ISR, another statement or
      activation of the same one);
    * ``E3`` -- same B, and the A1-A2 pairs share an endpoint (a coarser triple
      and the finer ones it is made of).

    Decided from case, location and sites alone: no masking, no guard, no solver
    result, no triage.
    """
    if t.case != u.case or not (t.names & u.names):
        return None
    if t.sites == u.sites:
        return "E1"
    if t.a1 == u.a1 and t.a2 == u.a2:
        return "E2"
    if t.b == u.b and {t.a1, t.a2} & {u.a1, u.a2}:
        return "E3"
    return None


@dataclass
class DefectClass:
    id: str
    members: list[Triple]
    #: (key, key, clause) for every sibling pair, so the grouping can be shown.
    edges: list[tuple[str, str, str]]


def defect_classes(triples: Sequence[Triple]) -> list[DefectClass]:
    """Connected components of the sibling graph over exactly ``triples``.

    The closure is over the triples given, never over others: a triple judged not
    a bug does not bridge two bug triples into one defect. Class ids are
    ``<case>/D<n>``, numbered by each class's smallest line triple, so the same
    input always gives the same ids.
    """
    items = list(triples)
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edges: list[tuple[int, int, str]] = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            why = sibling_reason(items[i], items[j])
            if why:
                edges.append((i, j, why))
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)

    def order(idx: list[int]) -> tuple:
        first = min(idx, key=lambda k: (items[k].lines, items[k].key))
        return (items[first].case, min(sorted(items[first].names) or [""]), items[first].lines)

    out: list[DefectClass] = []
    counters: Counter = Counter()
    for idx in sorted(groups.values(), key=order):
        case = items[idx[0]].case
        counters[case] += 1
        members = sorted((items[k] for k in idx), key=lambda t: (t.lines, t.key))
        inside = set(idx)
        out.append(DefectClass(
            id=f"{case}/D{counters[case]}", members=members,
            edges=[(items[i].key, items[j].key, why) for i, j, why in edges if i in inside]))
    return out


def label_counts(suite: SuiteGroundTruth) -> dict[str, int]:
    """Bug and trap counts as triples and as distinct defects, plus 2.2 additions.

    A *bug defect* is a class over the bug triples; a *new* bug defect is one
    with no 2.1 member. Traps are classed among themselves the same way.
    """
    bug_triples = [triple_from_annotation(a, c) for c in suite.cases for a in c.bugs]
    trap_triples = [triple_from_annotation(a, c) for c in suite.cases for a in c.traps]
    bug_classes = defect_classes(bug_triples)
    trap_classes = defect_classes(trap_triples)
    ext = {f"{a.case}:{a.kind}:{a.index}" for c in suite.cases for a in c.all if is_extension(a)}
    return {
        "bug_triples": len(bug_triples),
        "bug_defects": len(bug_classes),
        "trap_triples": len(trap_triples),
        "trap_defects": len(trap_classes),
        "bug_triples_added": sum(t.key in ext for t in bug_triples),
        "bug_defects_added": sum(all(t.key in ext for t in d.members) for d in bug_classes),
        "trap_triples_added": sum(t.key in ext for t in trap_triples),
    }


# ---------------------------------------------------------------------------
# Agreement between adjudicators
# ---------------------------------------------------------------------------


def cohen_kappa(pairs: Iterable[tuple[str, str]]) -> float | None:
    """Cohen's kappa over (first, second) label pairs; ``None`` when undefined."""
    pairs = list(pairs)
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(first[k] * second[k] for k in set(first) | set(second)) / (n * n)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def second_check_agreement(labels: LabelSet) -> dict[str, Any]:
    """Agreement on the doubly adjudicated entries: over the four verdicts, and bug / not bug."""
    pairs = [(e.verdict, e.second_check.verdict) for e in labels.entries if e.second_check.done]
    binary = [("bug" if a == "bug" else "not-bug", "bug" if b == "bug" else "not-bug") for a, b in pairs]
    return {
        "n": len(pairs),
        "agree": sum(a == b for a, b in pairs),
        "kappa": cohen_kappa(pairs),
        "kappa_bug_vs_not": cohen_kappa(binary),
    }
