"""Reading Racebench's ``2.1_remarks`` annotations, tolerantly.

**Ownership note.** ``wiki/Roadmap.md`` assigns the canonical annotation parser
to Track A, W2 -- the one that certifies the 48/38 ground truth and backs the
match rule used in scoring. That does not exist yet, and Track B cannot build a
single fixture without reading these annotations. This module is therefore a
**fixture-building aid**, written in Track B's lane and deliberately narrow: it
reports what the files say. It does not define the counting unit and it does
not implement the candidate-to-bug-point match rule, both of which are open
blockers in the Roadmap and both of which belong to Track A. When the canonical
parser lands, the two must be reconciled and this one should lose its
independent count.

## Why tolerance is not optional here

The suite's annotations follow **four incompatible grammars** plus several
one-off errors (``wiki/benchmarks/Racebench.md``). A strict reader silently
returns 28 of the bug points and raises nothing -- a 42% undercount that looks
like a clean run. That is recorded in the wiki as a prediction; it reproduces
exactly.

Grammars observed across the 31 simple cases:

===========================  ==================================  ============
Form                         Example                             Cases
===========================  ==================================  ============
comma-separated              ``<W#32>,<R#55>,<W#35>``            most
juxtaposed, no commas        ``<W#43><R#63><W#44>``              001, 019
comma inside the brackets    ``<R,#44>, <W,#79>``                021, 022, 025
spaced, comma inside         ``<R, #25>, <W, #39>``              023-030
line-then-type, reversed     ``<#46,R> <#90,W>``                 031
===========================  ==================================  ============

And the outright errors, each of which this reader recovers from rather than
skipping: a doubled bracket (``<<R#52>``, case 004), a missing closing bracket
(``<W#33,``, case 016), a missing ``#`` (``<W, 41>``, case 027), and a
lowercase access type (``<w#66>``, case 013) -- the last of which is **not**
in the wiki's catalogue.

Section headers vary too: ``//bug点:``, ``// bug点：`` with a full-width colon,
``//误报点:``, ``// 误报点：``, and ``// 可能误报`` ("possible false positive").
Entry numbering is ``1.`` or ``1:``.

And in ``svp_simple_022_001`` there is **no bug-point header at all**: four
numbered entries sit bare after the code, followed by a ``可能误报`` block. A
reader that requires a header before it will accept an entry loses exactly
those four, which is the whole gap between 44 and the suite's 48.

## The parsing strategy

Rather than match a grammar, find the **bracket groups** and pull a type letter
and a line number out of each one independently. Order inside the brackets, the
presence of ``#``, the separator and the case of the letter then all stop
mattering, and the four grammars collapse into one rule. Everything before the
first ``<`` is the variable name, verbatim.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Literal

Kind = Literal["bug_point", "trap"]

#: Where the suite might be. ``tests/conftest.py`` and ``cli.py`` both hardcode
#: an absolute path into Track A's checkout, which makes every suite-dependent
#: test unrunnable on any other machine -- ``pytest tests`` currently fails at
#: *collection* there. Rather than edit Track A's files from this branch, Track
#: B looks in the documented location and lets the environment override.
#: ``CLAUDE.md``: "Tool artifacts and benchmarks live outside the vault, one
#: directory up: ``../racebench``".
#: ``…/<vault>/project-src/src/irqrace/llm/annotations.py`` — parents[3] is
#: ``project-src``, parents[4] the vault, parents[5] the directory holding it,
#: which is where ``../racebench`` resolves to.
_SUITE_CANDIDATES = (
    Path(__file__).resolve().parents[5] / "racebench" / "2.1_remarks",
    Path("/home/pedro/Documentos/tcc/racebench/2.1_remarks"),
)


def locate_suite() -> Path | None:
    """The ``2.1_remarks`` directory, or ``None`` if the suite is not here."""
    import os

    if env := os.environ.get("IRQRACE_RACEBENCH"):
        path = Path(env)
        path = path if path.name == "2.1_remarks" else path / "2.1_remarks"
        return path if path.is_dir() else None
    return next((p for p in _SUITE_CANDIDATES if p.is_dir()), None)

#: Section headers. ``可能误报`` ("possible false positive") is a trap section
#: under a different name, and case 022 uses only that one.
_BUG_HEADER = re.compile(r"^\s*//\s*bug\s*点\s*[:：]?\s*$", re.IGNORECASE)
_TRAP_HEADER = re.compile(r"^\s*//\s*(?:误报点|可能误报)\s*[:：]?\s*$")

#: An entry line: ``//1.``, ``// 1.``, ``// 1:``.
_ENTRY = re.compile(r"^\s*//\s*(\d+)\s*[.:]\s*(.*)$")

#: A type letter and a line number, in either order, anywhere in a fragment.
_TYPE = re.compile(r"[RrWw]")
_LINE = re.compile(r"\d+")

#: What a numbered entry means when it appears before any section header.
#: ``svp_simple_022_001`` is the only case that does this, and its four
#: headerless entries are bug points -- they are followed by a separate
#: ``可能误报`` block holding the traps. Requiring a header costs exactly those
#: four and the loss is silent, which is why this default is explicit rather
#: than a skip.
DEFAULT_SECTION: Kind = "bug_point"


@dataclasses.dataclass(frozen=True)
class Access:
    kind: Literal["read", "write"]
    line: int

    @property
    def letter(self) -> str:
        return "R" if self.kind == "read" else "W"


@dataclasses.dataclass(frozen=True)
class Annotation:
    """One annotated triple, as the file states it."""

    subject: str
    kind: Kind
    index: int
    variable: str
    accesses: tuple[Access, ...]
    raw: str

    @property
    def pattern(self) -> str:
        """Access shape in role order, e.g. ``WRW``."""
        return "".join(a.letter for a in self.accesses)

    @property
    def is_triple(self) -> bool:
        return len(self.accesses) == 3


def parse_accesses(text: str) -> tuple[list[Access], str]:
    """Pull accesses out of an annotation body. Returns (accesses, variable).

    Everything before the first ``<`` is the variable name. Each subsequent
    ``<``-delimited fragment yields one access if it contains both a type
    letter and a number -- which is what makes the reader indifferent to field
    order, missing ``#``, missing ``>``, doubled ``<`` and letter case.
    """
    head, sep, rest = text.partition("<")
    if not sep:
        return [], text.strip()

    variable = head.strip()
    accesses: list[Access] = []
    for fragment in rest.split("<"):
        type_match = _TYPE.search(fragment)
        line_match = _LINE.search(fragment)
        if not (type_match and line_match):
            continue
        accesses.append(
            Access(
                kind="read" if type_match.group().upper() == "R" else "write",
                line=int(line_match.group()),
            )
        )
    return accesses, variable


def parse_file(path: Path, subject: str | None = None) -> list[Annotation]:
    """Read one annotated case."""
    subject = subject or path.stem
    out: list[Annotation] = []
    section: Kind | None = None

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if _BUG_HEADER.match(raw):
            section = "bug_point"
            continue
        if _TRAP_HEADER.match(raw):
            section = "trap"
            continue
        entry = _ENTRY.match(raw)
        if not entry:
            # A blank or a stray comment does not close a section; anything
            # else does. Being strict here is what stops the reader running on
            # into unrelated trailing comments.
            if raw.strip() and not raw.strip().startswith("//"):
                section = None
            continue

        index, body = int(entry.group(1)), entry.group(2)
        accesses, variable = parse_accesses(body)
        if not accesses:
            continue
        out.append(
            Annotation(
                subject=subject,
                kind=section or DEFAULT_SECTION,
                index=index,
                variable=variable,
                accesses=tuple(accesses),
                raw=raw.strip(),
            )
        )
    return out


def parse_suite(remarks_dir: Path) -> list[Annotation]:
    """Read every simple case in ``2.1_remarks``, in case order."""
    out: list[Annotation] = []
    for case_dir in sorted(remarks_dir.glob("svp_simple_*")):
        if not case_dir.is_dir():
            continue
        for source in sorted(case_dir.glob("*.c")):
            out.extend(parse_file(source))
    return out


def counts(annotations: list[Annotation]) -> dict[str, int]:
    return {
        "bug_points": sum(1 for a in annotations if a.kind == "bug_point"),
        "traps": sum(1 for a in annotations if a.kind == "trap"),
        "subjects": len({a.subject for a in annotations}),
    }


def verify_against_source(
    annotation: Annotation, source: Path, variable: str | None = None
) -> list[str]:
    """Check each annotated line actually mentions the variable.

    This is the cheap half of the match-rule problem the Roadmap leaves open.
    It does not decide whether a *reported candidate* matches an annotation; it
    only asks whether the annotation points at a line containing the name it
    names. That is enough to catch the off-by-one in ``svp_simple_001_001``,
    where the middle access of the first trap points at ``int reader2;`` -- a
    declaration -- while the read is on the next line.
    """
    name = (variable or annotation.variable).lstrip("*").split("[")[0].split(".")[0]
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    problems = []
    for access in annotation.accesses:
        if not 1 <= access.line <= len(lines):
            problems.append(f"line {access.line} is outside the file")
            continue
        text = lines[access.line - 1]
        if name and name not in text:
            problems.append(
                f"<{access.letter}#{access.line}> points at a line that does not "
                f"mention {name!r}: {text.strip()!r}"
            )
    return problems
