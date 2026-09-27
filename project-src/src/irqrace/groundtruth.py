"""Parsing Racebench's inline ground-truth annotations.

``2.1_remarks`` marks every defect and every planted false positive as a comment
at the end of the case file: a variable name followed by three accesses with
line numbers, the middle one from an ISR.

    //bug点:
    //1.svp_simple_019_001_global_var1<R#45>,<W#65>,<R#54>

It is not machine-readable without deliberate tolerance. The 31 simple cases use
**four incompatible access grammars**, several section-header spellings, one case
with no header at all, and a handful of outright typos. A strict parser reads 28
bug points where a tolerant one reads 48 — a 42% undercount, with no error
([[Racebench]], [[Soundness and False Negatives]] §7b). Silently reading the
wrong denominator is the worst available failure here, so this module:

* accepts every grammar it has seen, and
* **records every deviation it tolerated**, so the parse is auditable rather than
  merely permissive.

Nothing here corrects the annotations. Where an annotation disagrees with the
source — ``svp_simple_016_001``'s first bug point calls line 33 a read when it is
a write — the parser reports the disagreement and keeps the annotation as
written. Deciding what the ground truth *is* is a separate question from reading
what it *says*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

#: Section headers. `误报` covers both `误报点` ("false positive point") and
#: `可能误报` ("possible false positive"), which svp_simple_022_001 uses instead.
BUG_HEADER = re.compile(r"bug\s*点")
TRAP_HEADER = re.compile(r"误报")

#: `//1.` or `// 1:` — svp_simple_022_001 uses the colon form.
ENTRY_PREFIX = re.compile(r"^\s*(\d+)\s*[.:：、]\s*")

#: One access, in any of the four grammars:
#:
#:   <R#45>      type-then-line, no spaces        most of 001-020
#:   <R,#44>     comma inside the brackets        021, 025, 029, ...
#:   <R, #25>    ... and with a space             023, 026, 028, ...
#:   <W, 41>     ... and with no '#'              027
#:   <#46,R>     line-then-type, fields reversed  031
#:
#: Tolerances folded in deliberately:
#:   `<+`     absorbs the doubled bracket in svp_simple_004_001 (`<<R#52>`)
#:   `>*`     makes the closing bracket optional, for svp_simple_016_001 (`<W#33,`)
#:   `[RrWw]` accepts the lowercase `w` in svp_simple_013_001 (`<w#66>`)
ACCESS = re.compile(
    r"""<+\s*
        (?:
            (?P<type_first>[RrWw])\s*,?\s*\#?\s*(?P<line_after>\d+)
          |
            \#?\s*(?P<line_first>\d+)\s*,\s*(?P<type_after>[RrWw])
        )
        \s*>*""",
    re.VERBOSE,
)

KIND = {"r": "read", "w": "write"}


@dataclass(frozen=True)
class Access:
    kind: str  # "read" | "write"
    line: int
    raw: str

    @property
    def letter(self) -> str:
        return "R" if self.kind == "read" else "W"


@dataclass(frozen=True)
class Annotation:
    """One annotated triple: a bug point or a planted false positive."""

    case: str
    kind: str  # "bug" | "trap"
    index: int  # 1-based within its section, as numbered in the file
    variable: str
    accesses: tuple[Access, ...]
    annotation_line: int  # where the annotation itself sits in the file
    raw: str
    anomalies: tuple[str, ...] = ()

    @property
    def pattern(self) -> str:
        """'RWR', 'WRW', ... in annotation order — A1, B, A2."""
        return "".join(a.letter for a in self.accesses)

    @property
    def lines(self) -> tuple[int, ...]:
        return tuple(a.line for a in self.accesses)

    @property
    def key(self) -> tuple:
        """Identity of this annotation, for the match rule and de-duplication."""
        return (self.case, self.variable, tuple((a.kind, a.line) for a in self.accesses))


@dataclass
class Anomaly:
    """A deviation the parser tolerated. Every one of these is a reason the
    published counts disagree with each other."""

    case: str
    line: int
    code: str
    detail: str


@dataclass
class CaseGroundTruth:
    case: str
    path: Path
    bugs: list[Annotation] = field(default_factory=list)
    traps: list[Annotation] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def all(self) -> list[Annotation]:
        return self.bugs + self.traps


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_accesses(text: str) -> tuple[list[Access], list[str]]:
    accesses: list[Access] = []
    notes: list[str] = []
    for m in ACCESS.finditer(text):
        raw = m.group(0)
        if m.group("type_first"):
            letter, line = m.group("type_first"), int(m.group("line_after"))
            if "#" not in raw:
                notes.append(f"access {raw!r} omits the '#' before the line number")
        else:
            letter, line = m.group("type_after"), int(m.group("line_first"))
            notes.append(f"access {raw!r} is written line-then-type, reversed")
        if letter.islower():
            notes.append(f"access {raw!r} uses a lowercase access type")
        if raw.startswith("<<"):
            notes.append(f"access {raw!r} has a doubled opening bracket")
        if not raw.rstrip().endswith(">"):
            notes.append(f"access {raw!r} is missing its closing bracket")
        accesses.append(Access(kind=KIND[letter.lower()], line=line, raw=raw))
    return accesses, notes


def parse_case(path: Path, case: str | None = None) -> CaseGroundTruth:
    """Parse one case file's annotation block."""
    case = case or path.stem
    gt = CaseGroundTruth(case=case, path=path)
    section: str | None = None

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("//"):
            continue
        body = stripped.lstrip("/").strip()

        if TRAP_HEADER.search(body):
            section = "trap"
            if "误报点" not in body:
                gt.anomalies.append(Anomaly(
                    case, lineno, "nonstandard-trap-header",
                    f"trap section headed {body!r} rather than '误报点'"))
            continue
        if BUG_HEADER.search(body):
            section = "bug"
            continue

        m = ENTRY_PREFIX.match(body)
        if not m:
            continue
        rest = body[m.end():]
        if "<" not in rest:
            continue

        if section is None:
            # svp_simple_022_001 opens with four numbered entries and no header
            # at all. Treating an unheaded list as traps would lose four bug
            # points; reading it as bug points is the recall-safe choice and
            # matches the file's own ordering, where the trap section follows.
            section = "bug"
            gt.anomalies.append(Anomaly(
                case, lineno, "missing-section-header",
                "numbered entries appear before any section header; read as bug points"))

        var = rest[: rest.index("<")].strip().rstrip(",").strip()
        accesses, notes = _parse_accesses(rest)

        if len(accesses) != 3:
            gt.anomalies.append(Anomaly(
                case, lineno, "not-a-triple",
                f"parsed {len(accesses)} access(es), expected 3: {rest!r}"))
        if not var:
            gt.anomalies.append(Anomaly(
                case, lineno, "missing-variable", f"no variable name in {rest!r}"))
        for n in notes:
            gt.anomalies.append(Anomaly(case, lineno, "grammar-deviation", n))

        ann = Annotation(
            case=case, kind=section, index=int(m.group(1)), variable=var,
            accesses=tuple(accesses), annotation_line=lineno, raw=stripped,
            anomalies=tuple(notes),
        )
        (gt.bugs if section == "bug" else gt.traps).append(ann)

    _check_against_source(gt)
    return gt


def _check_against_source(gt: CaseGroundTruth) -> None:
    """Cross-check each annotated access type against the line it names.

    A heuristic, and deliberately reported rather than applied: where annotation
    and source disagree, the parser keeps the annotation. The known case is
    ``svp_simple_016_001`` bug point 1, which calls line 33 a read while the line
    is ``global_var1 = 0x09;`` — a write. Taken literally that is the only
    "defect" in the suite invisible to a race detector, so whether it is a typo
    or a real (R,R,R) annotation is a ground-truth question for the match rule,
    not something a parser should silently decide.
    """
    lines = gt.path.read_text(encoding="utf-8").splitlines()
    for ann in gt.all:
        for a in ann.accesses:
            if not (1 <= a.line <= len(lines)):
                gt.anomalies.append(Anomaly(
                    gt.case, ann.annotation_line, "line-out-of-range",
                    f"{ann.kind} {ann.index}: line {a.line} is outside the file"))
                continue
            text = lines[a.line - 1]
            kinds = _classify_line(text, ann.variable)
            if kinds is None:
                continue
            if len(kinds) == 2:
                # The line both reads and writes the variable -- `for (x = 0; x <
                # N; x++)`, or `x = x + 1`. Either annotation is defensible, and
                # which one was meant matters for the match rule, so record it
                # without calling it an error.
                gt.anomalies.append(Anomaly(
                    gt.case, ann.annotation_line, "access-type-ambiguous",
                    f"{ann.kind} {ann.index}: {a.raw} names line {a.line}, which both "
                    f"reads and writes the variable: {text.strip()!r}"))
            elif a.kind not in kinds:
                only = next(iter(kinds))
                gt.anomalies.append(Anomaly(
                    gt.case, ann.annotation_line, "access-type-disagrees-with-source",
                    f"{ann.kind} {ann.index}: {a.raw} calls line {a.line} a {a.kind}, "
                    f"but the line only {only}s it: {text.strip()!r}"))


def _classify_line(text: str, variable: str) -> set[str] | None:
    """Which kinds of access to *variable* does this one line perform?

    Returns ``{"read"}``, ``{"write"}``, ``{"read", "write"}``, or ``None`` when
    the question cannot be answered from a single line — the variable does not
    appear under the name the annotation uses (``svp_simple_011_001`` annotates
    a dereference as ``*u`` while the source writes ``*svp_simple_011_001_u``),
    or the statement spans several lines.

    Rough by construction. It exists to *flag* annotation/source disagreements
    for the hand count, never to overrule an annotation.
    """
    base = variable.lstrip("*").split("[")[0].split(".")[0].split("->")[0].strip()
    if not base:
        return None
    code = text.split("//")[0]
    occurrences = list(re.finditer(rf"\b{re.escape(base)}\b", code))
    if not occurrences:
        return None

    kinds: set[str] = set()
    suffix = r"(?:\s*\[[^\]]*\]|\s*\.\w+|\s*->\w+)*"

    # Compound assignment and increment/decrement are a read AND a write.
    if re.search(rf"\b{re.escape(base)}\b{suffix}\s*(?:\+|-|\*|/|%|\||&|\^|<<|>>)=", code) or \
       re.search(rf"\b{re.escape(base)}\b{suffix}\s*(?:\+\+|--)", code) or \
       re.search(rf"(?:\+\+|--)\s*\b{re.escape(base)}\b", code):
        return {"read", "write"}

    assign = re.search(rf"\b{re.escape(base)}\b{suffix}\s*(?<![=!<>])=(?!=)", code)
    if assign:
        kinds.add("write")
        # A second occurrence anywhere means the line reads it too: the RHS of
        # `x = x + 1`, or the condition of `for (x = 0; x < N; ...)`.
        if len(occurrences) > 1:
            kinds.add("read")
    else:
        kinds.add("read")
    return kinds


# ---------------------------------------------------------------------------
# Suite level
# ---------------------------------------------------------------------------


@dataclass
class SuiteGroundTruth:
    cases: list[CaseGroundTruth]

    @property
    def bugs(self) -> list[Annotation]:
        return [a for c in self.cases for a in c.bugs]

    @property
    def traps(self) -> list[Annotation]:
        return [a for c in self.cases for a in c.traps]

    @property
    def anomalies(self) -> list[Anomaly]:
        return [x for c in self.cases for x in c.anomalies]

    def shape_distribution(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for group, items in (("bug", self.bugs), ("trap", self.traps)):
            for ann in items:
                out.setdefault(ann.pattern, {"bug": 0, "trap": 0})[group] += 1
        return out

    def by_case(self, case: str) -> CaseGroundTruth:
        return next(c for c in self.cases if c.case == case)


def parse_suite(suite_root: Path) -> SuiteGroundTruth:
    """Parse every ``svp_simple_NNN`` case in ``2.1_remarks``."""
    cases: list[CaseGroundTruth] = []
    for d in sorted(Path(suite_root).glob("svp_simple_*")):
        if not d.is_dir():
            continue
        src = d / f"{d.name}_001.c"
        if src.exists():
            cases.append(parse_case(src, case=src.stem))
    return SuiteGroundTruth(cases=cases)


# ---------------------------------------------------------------------------
# Errata
# ---------------------------------------------------------------------------


class ErrataError(RuntimeError):
    """The errata file does not apply cleanly to the suite."""


@dataclass(frozen=True)
class Correction:
    case: str
    kind: str
    index: int
    reason: str
    confidence: str
    as_written: str
    corrected: tuple[Access, ...]
    evidence: str


def load_errata(path: Path) -> list[Correction]:
    import yaml

    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema_version") != "errata/1.0.0":
        raise ErrataError(f"{path}: unexpected schema_version {doc.get('schema_version')!r}")
    out: list[Correction] = []
    for c in doc["corrections"]:
        accesses = tuple(
            Access(kind=k, line=int(n), raw=f"<{'R' if k == 'read' else 'W'}#{n}>")
            for k, n in c["corrected"]
        )
        if len(accesses) != 3:
            raise ErrataError(f"{path}: correction for {c['case']} is not a triple")
        out.append(Correction(
            case=c["case"], kind=c["kind"], index=int(c["index"]),
            reason=c["reason"], confidence=c["confidence"],
            as_written=c["as_written"], corrected=accesses,
            evidence=" ".join(c["evidence"].split()),
        ))
    return out


def apply_errata(suite: SuiteGroundTruth, corrections: list[Correction]) -> list[str]:
    """Apply corrections in place. Returns a report line per correction.

    An errata entry that matches no annotation is an **error**, not a warning:
    it means the suite changed under the errata, and every number measured
    against it is suspect until someone looks.
    """
    report: list[str] = []
    for corr in corrections:
        try:
            case = suite.by_case(corr.case)
        except StopIteration:
            raise ErrataError(f"errata names unknown case {corr.case!r}") from None
        bucket = case.bugs if corr.kind == "bug" else case.traps
        target = next((a for a in bucket if a.index == corr.index), None)
        if target is None:
            raise ErrataError(
                f"errata names {corr.case} {corr.kind} {corr.index}, which the "
                "parser did not find; the suite or the parser has changed")
        if target.raw.replace(" ", "") not in corr.as_written.replace(" ", "") and \
           corr.as_written.replace(" ", "") not in target.raw.replace(" ", ""):
            raise ErrataError(
                f"errata for {corr.case} {corr.kind} {corr.index} quotes\n"
                f"  {corr.as_written!r}\nbut the file now reads\n  {target.raw!r}")

        fixed = Annotation(
            case=target.case, kind=target.kind, index=target.index,
            variable=target.variable, accesses=corr.corrected,
            annotation_line=target.annotation_line, raw=target.raw,
            anomalies=target.anomalies + (f"corrected by errata: {corr.reason}",),
        )
        bucket[bucket.index(target)] = fixed
        report.append(
            f"{corr.case} {corr.kind} {corr.index}: {target.pattern}{target.lines} "
            f"-> {fixed.pattern}{fixed.lines}  ({corr.reason}, {corr.confidence})")
    return report


def load_suite(suite_root: Path, errata: Path | None = None) -> SuiteGroundTruth:
    """Parse the suite and apply the curated errata.

    This is the entry point the evaluation harness uses. Reading the raw
    annotations without the errata is available through :func:`parse_suite`, and
    is what the "as written" column of any comparison table should come from.
    """
    suite = parse_suite(suite_root)
    if errata is not None:
        apply_errata(suite, load_errata(errata))
    return suite
