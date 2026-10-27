"""Reading C source text for the context record: function extents and macros.

Debug info gives a function's first line and the highest line any of its
instructions carries, which is usually -- not always -- the closing brace. The
record used to show ``line_end + 1`` "to be safe", and on a file whose next line
is a comment that comment went to the model with the code. On Racebench the next
line is the ground-truth header (``//bug点:``). So the extent is now found the
way a reader finds it: from the line the function starts on, to the brace that
closes its body.

All of this is text processing over the program under analysis, and the
results are evidence for the model, never inputs to a soundness decision.
"""

from __future__ import annotations

import re

_LINE_COMMENT = re.compile(r"//.*$")
_STRING = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
_DEFINE = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)(\([^)]*\))?\s*(.*?)\s*$")
_IDENT = re.compile(r"[A-Za-z_]\w*")


def _code_only(line: str, in_block: bool) -> tuple[str, bool]:
    """``line`` without comments and string literals; tracks ``/* */`` state."""
    out = []
    i = 0
    while i < len(line):
        if in_block:
            j = line.find("*/", i)
            if j < 0:
                return "".join(out), True
            i, in_block = j + 2, False
            continue
        j = line.find("/*", i)
        segment = line[i:] if j < 0 else line[i:j]
        out.append(_LINE_COMMENT.sub("", _STRING.sub('""', segment)))
        if j < 0 or "//" in _STRING.sub('""', segment):
            break
        i, in_block = j + 2, True
    return "".join(out), in_block


def function_extent(lines: list[str], start: int, hint_end: int | None = None) -> int | None:
    """Last line of the function whose definition starts on ``start`` (1-based).

    Counts braces from ``start``, ignoring comments and literals, and returns
    the line where the body's opening brace is closed. ``None`` when the braces
    do not balance within the file (macro-generated bodies, say); the caller
    then falls back to ``hint_end``, never to a line past it.
    """
    depth, opened, in_block = 0, False, False
    for n in range(start, len(lines) + 1):
        code, in_block = _code_only(lines[n - 1], in_block)
        for ch in code:
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
                if opened and depth == 0:
                    return n
        if not opened and code.rstrip().endswith(";"):
            return None  # a prototype, not a definition
    return hint_end


def find_definition(lines: list[str], name: str) -> int | None:
    """First line of ``name``'s definition (not a prototype or a call), or None.

    A definition is ``name(`` whose matching ``)`` is followed by ``{``: a call
    is followed by ``;`` or an operator, a prototype by ``;``.
    """
    pattern = re.compile(rf"(^|[\s\*]){re.escape(name)}\s*\(")
    in_block = False
    for n, raw in enumerate(lines, start=1):
        code, in_block = _code_only(raw, in_block)
        if code.lstrip().startswith("#"):
            continue
        for m in pattern.finditer(code):
            tail = code[m.end() - 1 :] + " " + " ".join(
                _code_only(l, False)[0] for l in lines[n : n + 4]
            )
            depth = 0
            for i, ch in enumerate(tail):
                depth += ch == "("
                depth -= ch == ")"
                if depth == 0:
                    if tail[i + 1 :].lstrip().startswith("{"):
                        return n
                    break
    return None


def macro_definitions(lines: list[str]) -> dict[str, tuple[int, str]]:
    """``#define`` name -> (line, replacement text), object- and function-like."""
    out: dict[str, tuple[int, str]] = {}
    for n, raw in enumerate(lines, start=1):
        m = _DEFINE.match(raw)
        if m:
            params = m.group(2) or ""
            out[m.group(1)] = (n, f"{params} {m.group(3)}".strip())
    return out


def identifiers(code: str) -> set[str]:
    in_block = False
    found: set[str] = set()
    for raw in code.splitlines():
        text, in_block = _code_only(raw, in_block)
        found |= set(_IDENT.findall(text))
    return found
