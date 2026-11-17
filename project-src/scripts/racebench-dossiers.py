#!/usr/bin/env python3
"""Blind adjudication dossiers for the unannotated Racebench candidates (T2, Racebench 2.2).

    python scripts/racebench-dossiers.py RUN_ROOT [RUN_ROOT ...] --out DIR --all
    python scripts/racebench-dossiers.py RUN_ROOT --out DIR --likely-real-plus-sample K --seed S

Each RUN_ROOT is one run directory (it holds ``manifest.json``) or a directory
of them, one per case. The script lists every context record -- every candidate
that reaches the LLM stage -- whose ordered line triple matches **no** 2.1
annotation of its case (the match rule's key: same lines, files agreeing),
groups the triples by the equivalence rule (``irqrace.labels_ext``, protocol
"Rule E"), and writes one Markdown dossier per group:

    DIR/README.md          what the set is, the rule, the list of dossiers   (blind)
    DIR/groups.csv         every triple in a dossier, its group and siblings (blind)
    DIR/dossiers/*.md      one per group, with a blank witness form per triple (blind)
    DIR/selection.csv      how the triples were selected -- NOT blind; the
                           adjudicator does not open it

**Blindness.** A dossier carries the case, the triple, the variable, the flows
and their priorities, the static masking facts (stage 2 / the context record),
the solver's result and the static provenance facts -- every one labelled as
tool output -- the numbered source of every function involved, and the README's
arrival-model rules. It never carries anything from ``llm/``: no bucket, no
answer of either triage conversation, no confidence, no reasoning. ``--all``
never opens ``llm/`` at all. ``--likely-real-plus-sample`` reads the buckets to
choose, writes what it read only to ``selection.csv``, and the dossiers are the
same files ``--all`` would write for the chosen triples (ordered by case and
line, never by triage rank; siblings that were not chosen are left out, because
listing them would tell the adjudicator which bucket they were in).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from irqrace.evaluation import _files_agree, candidate_lines, candidate_pattern  # noqa: E402
from irqrace.groundtruth import CaseGroundTruth, SuiteGroundTruth  # noqa: E402
from irqrace.labels_ext import (  # noqa: E402
    EQUIVALENCE_RULE, ROLES, Triple, defect_classes, ground_truth, triple_from_annotation,
    triple_from_record,
)
from irqrace.racebench import locate_suite  # noqa: E402
from irqrace.runstore import find_runs  # noqa: E402
from irqrace.source_context import find_definition, function_extent  # noqa: E402

#: The README's arrival-model rules, as the project translates them (the same
#: wording as bench/racebench/VENDORED.md). The Chinese original is quoted from
#: the suite's README next to each, found by these markers.
README_RULES = (
    ("打断",
     "Test cases do not consider the periodicity of interrupts: an interrupt may preempt the main "
     "program or a lower-priority interrupt whenever it is enabled, at an indeterminate moment, "
     "position and number of times."),
    ("enable_isr(n)",
     "Interrupt numbers are those used by the interrupt switch functions the cases provide. "
     "enable_isr(n) and disable_isr(n) can be treated as unlock and lock primitives; n is the "
     "interrupt number, and n = -1 means masking / unmasking all interrupts."),
    ("优先级数字越大",
     "A larger priority number means a higher priority."),
)


# ---------------------------------------------------------------------------
# Collecting
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_runs(paths: list[Path], *, latest: bool = False) -> dict[str, Path]:
    """subject -> run directory. Two runs of one subject are an error unless ``latest``."""
    found: dict[str, list[Path]] = {}
    for p in paths:
        runs = [p] if (p / "manifest.json").exists() else find_runs(p)
        if not runs:
            raise SystemExit(f"{p}: neither a run directory nor a directory of runs")
        for r in runs:
            subject = _read_json(r / "manifest.json")["subject"]["name"]
            found.setdefault(subject, []).append(r)
    out: dict[str, Path] = {}
    for subject, runs in sorted(found.items()):
        runs = sorted(set(runs))
        if len(runs) > 1 and not latest:
            listing = "\n  ".join(str(r) for r in runs)
            raise SystemExit(f"{subject} has {len(runs)} runs; pass one, or --latest:\n  {listing}")
        out[subject] = runs[-1]
    return out


def read_contexts(run: Path) -> list[dict[str, Any]]:
    return [_read_json(p) for p in sorted((run / "context").glob("*.json"))]


def read_buckets(run: Path) -> dict[str, str]:
    """candidate id -> bucket. Used ONLY to select; never written into a dossier."""
    path = run / "llm" / "triage.jsonl"
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec["candidate_id"]] = rec.get("bucket") or "not_triaged"
    return out


def triple_key(case: str, sites: tuple) -> str:
    """``case@A1-B-A2``; files appear only when a site is outside the case file."""
    if all(s[0] == f"{case}.c" for s in sites):
        return f"{case}@{'-'.join(str(s[1]) for s in sites)}"
    return f"{case}@{'-'.join(f'{s[0]}:{s[1]}' for s in sites)}"


@dataclass
class TripleSet:
    """The records of one run sharing one ordered line triple (rule E1)."""

    case: str
    run: Path
    records: list[dict[str, Any]]
    triple: Triple
    annotated: bool
    selected: bool = True
    selected_by: str = "all"
    buckets: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.triple.key

    @property
    def lines(self) -> tuple[int, ...]:
        return self.triple.lines


def annotated(record: dict[str, Any], case: CaseGroundTruth) -> bool:
    """Whether the scorer's match rule pairs ``record``'s lines with some annotation."""
    lines = candidate_lines(record)
    return any(ann.lines == lines and _files_agree(ann, record) for ann in case.all)


def triple_sets(run: Path, case: CaseGroundTruth) -> list[TripleSet]:
    by_sites: dict[tuple, list[dict[str, Any]]] = {}
    for rec in read_contexts(run):
        by_sites.setdefault(triple_from_record(rec).sites, []).append(rec)
    out = []
    for sites, recs in sorted(by_sites.items(), key=lambda kv: (tuple(s[1] for s in kv[0]), kv[0])):
        recs = sorted(recs, key=lambda r: r["id"])
        names = frozenset().union(*(triple_from_record(r).names for r in recs))
        t = Triple(key=triple_key(case.case, sites), case=case.case, names=names, sites=sites,
                   label="unannotated: " + ", ".join(r["id"] for r in recs))
        out.append(TripleSet(case=case.case, run=run, records=recs, triple=t,
                             annotated=annotated(recs[0], case)))
    return out


def select(sets: list[TripleSet], *, mode: str, k: int = 0, seed: int = 0) -> None:
    """Mark ``selected``, over every case at once (the sample is K in total, not per case).

    ``likely-real-plus-sample`` reads buckets; ``all`` does not open ``llm/``.
    """
    pending = [s for s in sets if not s.annotated]
    if mode == "all":
        for s in pending:
            s.selected, s.selected_by = True, "all"
        return
    pool: list[TripleSet] = []
    cache: dict[Path, dict[str, str]] = {}
    for s in pending:
        buckets = cache.setdefault(s.run, read_buckets(s.run))
        s.buckets = sorted({buckets.get(r["id"], "not_triaged") for r in s.records})
        if "likely_real" in s.buckets:
            s.selected, s.selected_by = True, "likely_real"
        elif not set(s.buckets) - {"not_triaged"}:
            # Never triaged: there is no bucket to bury it in, so it is checked.
            s.selected, s.selected_by = True, "not_triaged"
        else:
            s.selected, s.selected_by = False, "pool"
            pool.append(s)
    pool.sort(key=lambda s: s.key)
    for s in random.Random(seed).sample(pool, min(k, len(pool))):
        s.selected, s.selected_by = True, f"sample(seed={seed})"


# ---------------------------------------------------------------------------
# Source
# ---------------------------------------------------------------------------


def _source_file(record: dict[str, Any], rel: str) -> Path | None:
    roots = [Path(record["subject"].get("source_root") or "."), locate_suite()]
    for root in roots:
        if root is not None and (root / rel).is_file():
            return root / rel
    return None


def _numbered(lines: list[str], start: int, end: int) -> str:
    width = len(str(end))
    return "\n".join(f"{n:>{width}}  {lines[n - 1]}" for n in range(start, end + 1))


def function_listings(records: list[dict[str, Any]]) -> list[tuple[str, str, int, int, str]]:
    """(function, file, first, last, numbered text) for every function involved.

    The functions are the union, over the group's records, of the functions in
    their ``enclosing_source`` (the deciding functions stage 3 chose: the ones
    holding A1/B/A2, their call paths, and every flow that touches the variable
    or the mask), plus any access or call-path function not among them. Each is
    re-read from the case file and cut with :func:`function_extent`, so a
    function stage 3 truncated or dropped for size is shown whole.
    """
    wanted: list[tuple[str, str | None, int | None, int | None]] = []
    seen: set[str] = set()

    def want(name: str, file: str | None, start: int | None, end: int | None) -> None:
        if name and name not in seen:
            seen.add(name)
            wanted.append((name, file, start, end))

    for rec in records:
        for e in rec.get("enclosing_source", []):
            want(e["function"], e["file"], e["line_start"], e["line_end"])
    for rec in records:
        for a in rec["accesses"]:
            want(a["function"], a["source"]["file"], None, None)
            for fr in a.get("call_path", {}).get("frames", []):
                want(fr["function"], a["source"]["file"], None, None)

    out = []
    for name, rel, start, end in wanted:
        path = _source_file(records[0], rel) if rel else None
        if path is not None:
            lines = path.read_text(encoding="utf-8").splitlines()
            first = find_definition(lines, name) or start
            if first:
                last = function_extent(lines, first, hint_end=end) or end or first
                out.append((name, rel, first, last, _numbered(lines, first, min(last, len(lines)))))
                continue
        enc = next((e for rec in records for e in rec.get("enclosing_source", [])
                    if e["function"] == name), None)
        if enc is not None:  # the file is not on this machine: the record's copy
            code = enc["code"].splitlines()
            text = "\n".join(f"{enc['line_start'] + i:>4}  {c}" for i, c in enumerate(code))
            out.append((name, enc["file"], enc["line_start"], enc["line_end"], text))
    return out


def declarations(record: dict[str, Any], listings: list[tuple[str, str, int, int, str]]) -> str | None:
    """The case file's top level before its first function: globals, macros, prototypes.

    Starts after the last ``#include``, so the file's header comment is skipped,
    and stops before the first function -- the annotation block at the end of
    the file is never reached.
    """
    rel = record["variable"].get("decl", {}).get("file") or record["accesses"][0]["source"]["file"]
    path = _source_file(record, rel)
    if path is None:
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    starts = [first for _, f, first, _, _ in listings if Path(f).name == Path(rel).name]
    if not starts:
        return None
    stop = min(starts) - 1
    begin = max((n for n in range(1, stop + 1) if lines[n - 1].lstrip().startswith("#include")), default=0) + 1
    while begin <= stop and not lines[begin - 1].strip():
        begin += 1
    while stop >= begin and not lines[stop - 1].strip():
        stop -= 1
    return _numbered(lines, begin, stop) if begin <= stop else None


def readme_rules(suite_root: Path | None, case: str) -> tuple[list[tuple[str, str]], str | None]:
    """[(original, translation)] for the arrival-model rules, and the case's table row."""
    text = ""
    if suite_root is not None and (suite_root / "README.md").is_file():
        text = (suite_root / "README.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    rules = []
    for marker, english in README_RULES:
        original = next((l.strip().strip("*").lstrip("* ").strip("*").strip() for l in lines if marker in l), "")
        rules.append((original, english))
    row = next((l.strip() for l in lines if f"{case}.c" in l and l.lstrip().startswith("|")), None)
    return rules, row


# ---------------------------------------------------------------------------
# Rendering -- everything below writes what a dossier contains. Nothing in it
# may read llm/ (the blindness test feeds it triage files full of markers).
# ---------------------------------------------------------------------------


def _mask(state: dict[str, Any] | None) -> str:
    if not state:
        return "not recorded"
    parts = [f"irq {n} enabled" for n in state.get("enabled", [])]
    parts += [f"irq {n} disabled" for n in state.get("disabled", [])]
    parts += [f"irq {n} unknown" for n in state.get("unknown", [])]
    return ", ".join(parts) or "no interrupt in scope"


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _flow_rows(record: dict[str, Any], masking: dict[str, Any] | None) -> list[str]:
    rows = ["| flow | kind | entry | irq | priority | may be preempted by (stage 2) | unmasks in own code (stage 2) |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    flows = (masking or {}).get("flows", {})
    for f in record.get("flows", []):
        m = flows.get(f["id"], {})
        rows.append("| " + " | ".join(_cell(x) for x in (
            f["id"], f["kind"], f"`{f['entry']}`", f.get("irq") if f.get("irq") is not None else "-",
            f.get("priority"), ", ".join(m.get("may_be_preempted_by", [])) or "-",
            ", ".join(str(i) for i in m.get("unmasks_in_own_code", [])) or "-")) + " |")
    return rows


def _entry_states(masking: dict[str, Any] | None) -> list[str]:
    out = []
    for fid, m in sorted((masking or {}).get("flows", {}).items()):
        for irq, states in sorted((m.get("entry_state") or {}).items()):
            vals = "; ".join(f"{s.get('value')} ({s.get('origin')})" for s in states)
            out.append(f"- `{fid}` enters with irq {irq}: {vals}")
    return out


#: Shown once per dossier (flows, preemption) or per record from its own fields (solver).
_SHOWN_ELSEWHERE = {"solver_result", "flows", "preemption"}


def _facts(rec: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(e.get("fact", ""), e.get("status", ""), e.get("note", ""))
            for e in (rec.get("provenance") or {}).get("entries", [])
            if e.get("fact") not in _SHOWN_ELSEWHERE]


def _fact_line(fact: tuple[str, str, str]) -> str:
    return f"- `{fact[0]}` [{fact[1]}]: {_cell(fact[2])}"


def _record_block(rec: dict[str, Any], common: set[tuple[str, str, str]] = frozenset()) -> list[str]:
    out = [f"**Record `{rec['id']}`** — shape {candidate_pattern(rec)}", "",
           "| role | kind | file:line | function | flow | masking at the access (stage 2) | in loop | code |",
           "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    order = {r: i for i, r in enumerate(ROLES)}
    for a in sorted(rec["accesses"], key=lambda a: order.get(a["role"], 99)):
        loop = a.get("loop_context") or {}
        heads = ", ".join(str(n["header"]["line"]) for n in loop.get("nest", []) if n.get("header"))
        out.append("| " + " | ".join(_cell(x) for x in (
            a["role"], a["kind"], f"{Path(a['source']['file']).name}:{a['source']['line']}",
            f"`{a['function']}`", a["flow"], _mask(a.get("masking")),
            f"yes (header {heads})" if loop.get("in_loop") else "no",
            f"`{a['source'].get('snippet', '').strip()}`")) + " |")
    interval = (rec.get("masking") or {}).get("interval") or {}
    pre = rec.get("preemption") or {}
    sol = rec.get("solver_result") or {}
    out += ["", "Static facts about this record (tool output, not a judgement on the defect):", ""]
    if interval:
        out.append(
            f"- masking over the interval {interval.get('from_role')}..{interval.get('to_role')}: "
            f"enabled somewhere {interval.get('enabled_somewhere') or []}, disabled throughout "
            f"{interval.get('disabled_throughout') or []}, unknown {interval.get('unknown') or []}, "
            f"re-enabled within the interval by {interval.get('reenabled_within_interval_by') or []}")
    if pre:
        out.append(
            f"- preemption: `{pre.get('preempting_flow')}` into `{pre.get('preempted_flow')}`, priority "
            f"relation {pre.get('priority_relation')}, nesting depth {pre.get('nesting_depth')}, timing "
            f"{pre.get('timing')}")
    if sol:
        at = (sol.get("assignment") or {}).get("preempted_at") or {}
        where = f", preemption placed at line {at.get('line')} of `{at.get('function')}`" if at else ""
        out.append(
            f"- solver ({sol.get('engine')} {sol.get('engine_version')}): result `{sol.get('verdict')}`{where}; "
            f"left unconstrained: {', '.join(sol.get('unconstrained') or []) or 'nothing'}. "
            "`sat` means *not refuted* by an over-approximate encoding; it is not a witness.")
    out += [_fact_line(f) for f in _facts(rec) if f not in common]
    return out


def witness_form(ts: TripleSet) -> str:
    rec = ts.records[0]
    order = {r: i for i, r in enumerate(ROLES)}
    accs = sorted(rec["accesses"], key=lambda a: order.get(a["role"], 99))
    lines = []
    for a in accs:
        f = Path(a["source"]["file"]).name
        extra = "" if f == f"{ts.case}.c" else f", file: {f}"
        lines.append(f"    - {{role: {a['role']}, kind: {a['kind']}, line: {a['source']['line']}, "
                     f"flow: {a['flow']}{extra}}}")
    kinds = sorted({candidate_pattern(r) for r in ts.records})
    alt = (f"  # the tool reports these lines with kinds {', '.join(kinds)}; "
           "keep the kinds the witness uses\n") if len(kinds) > 1 else ""
    return "\n".join([
        "```yaml",
        "- id: R22-____",
        f"  case: {ts.case}",
        f"  variable: {rec['variable']['name']}",
        f"  triple:            # A1, B, A2\n{alt}" + "\n".join(lines),
        f"  candidate_ids: [{', '.join(r['id'] for r in ts.records)}]",
        "  verdict:           # bug | trap | not-a-defect | undecided",
        "  witness:           # all four required for bug",
        "    arrival_point:       # function and the two lines B's flow arrives between",
        "    masking_at_arrival:  # B's irq there, and why it is unmasked (which enable_isr, on which path)",
        "    guard_values:        # values that make every guard on A1, B and A2 pass",
        f"    effect:              # observable change in A1/A2; shape {'/'.join(kinds)}",
        "  blocking_reason:   # required unless bug: what makes it unreachable, effect-free or undecidable",
        "  adjudicator:",
        "  date:",
        "  second_check: {done: false, adjudicator: null, verdict: null, date: null}",
        "  notes:",
        "```",
    ])


def render_dossier(group_id: str, sets: list[TripleSet], members: list[Triple],
                   edges: list[tuple[str, str, str]], case: CaseGroundTruth,
                   suite_root: Path | None) -> str:
    run = sets[0].run
    records = [r for s in sets for r in s.records]
    masking_path = run / "stage2" / "masking.json"
    masking = _read_json(masking_path) if masking_path.exists() else None
    first = records[0]
    listings = function_listings(records)
    decls = declarations(first, listings)
    rules, row = readme_rules(suite_root, case.case)
    labels = {t.key: t.label for t in members}
    out = [
        f"# Dossier {group_id}",
        "",
        f"**Case** `{case.case}` · **location** `{first['variable']['name']}` "
        f"(`{first['variable'].get('declared_type', '')}`, declared "
        f"{Path(first['variable'].get('decl', {}).get('file', '')).name}:"
        f"{first['variable'].get('decl', {}).get('line', '?')}) · "
        f"**{len(sets)} triple(s) to adjudicate** · run `{run.name}`",
        "",
        "Blind dossier for Racebench 2.2 (protocol: `docs/evaluation-protocol.md`, \"DRAFT -- Racebench "
        "2.2\"). Decide every triple from the source and the README rules below. Everything marked "
        "*tool output* is a static fact from stages 1-3; none of it is a judgement on the defect.",
        "",
        "## Grouping (rule E)",
        "",
        f"Rule: {EQUIVALENCE_RULE}.",
        "",
        "| triple (A1, B, A2) | what it is |",
        "| --- | --- |",
    ]
    for t in members:
        out.append(f"| ({', '.join(str(l) for l in t.lines)}) | {_cell(labels[t.key])} |")
    out += ["", "Sibling links:", ""]
    for a, b, why in edges:
        out.append(f"- {why}: {a} ~ {b}")
    if not edges:
        out.append("- none (a group of one)")
    if any(t.label.startswith("2.1") for t in members):
        out += ["", "The suite's own labels are listed because the grouping uses them. They are not "
                "evidence about the triples below: the suite plants traps as siblings of its bug points "
                "(12 of 2.1's groups mix the two), so every triple gets its own verdict."]

    out += ["", "## Interrupt model", "", "README of the suite (original, then the project's translation):", ""]
    for original, english in rules:
        if original:
            out.append(f"> {original}")
            out.append(">")
        out.append(f"> *{english}*")
        out.append("")
    if row:
        out += ["Case row of the README table (case, main entry, handler/irq/priority):", "", f"`{row}`", ""]
    out += ["Flows (configuration and stage 2, tool output):", ""] + _flow_rows(first, masking)
    states = _entry_states(masking)
    if states:
        out += ["", "Masking state each flow may start with (stage 2, tool output):", ""] + states

    common = set(_facts(records[0]))
    for rec in records[1:]:
        common &= set(_facts(rec))
    if common:
        out += ["", "Static facts shared by every record below (tool output):", ""]
        out += [_fact_line(f) for f in _facts(records[0]) if f in common]

    out += ["", "## Triples", ""]
    for n, ts in enumerate(sets, start=1):
        out += [f"### T{n}. ({', '.join(str(l) for l in ts.lines)}) — `{ts.key}`", ""]
        for rec in ts.records:
            out += _record_block(rec, common) + [""]
        out += ["Witness form:", "", witness_form(ts), ""]

    out += ["## Source", ""]
    if decls:
        out += [f"Top level of `{Path(first['variable']['decl']['file']).name}` before its first function:",
                "", "```c", decls, "```", ""]
    for name, rel, start, end, text in listings:
        out += [f"`{name}` — {Path(rel).name}:{start}-{end}", "", "```c", text, "```", ""]
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def build(runs: dict[str, Path], out: Path, *, mode: str, k: int = 0, seed: int = 0,
          selection_out: Path | None = None, suite: SuiteGroundTruth | None = None,
          log=print) -> dict[str, Any]:
    suite_root = locate_suite()
    suite = suite or ground_truth("2.1")
    cases = {c.case: c for c in suite.cases}
    (out / "dossiers").mkdir(parents=True, exist_ok=True)

    per_case: list[tuple[CaseGroundTruth, list[TripleSet]]] = []
    for subject, run in runs.items():
        case = cases.get(subject)
        if case is None:
            log(f"  {subject}: no Racebench ground truth here, skipped")
            continue
        per_case.append((case, triple_sets(run, case)))
    all_sets = [s for _, sets in per_case for s in sets]
    select(all_sets, mode=mode, k=k, seed=seed)

    dossiers: list[tuple[str, Path, list[TripleSet]]] = []
    group_rows: list[list[Any]] = []
    with_annotation = 0
    for case, sets in per_case:
        subject = case.case
        chosen = [s for s in sets if not s.annotated and s.selected]
        n_records = sum(len(s.records) for s in sets)
        n_un = sum(len(s.records) for s in sets if not s.annotated)
        log(f"  {subject}: {n_records} records reach the LLM, {n_un} unannotated "
            f"in {sum(not s.annotated for s in sets)} triples; {len(chosen)} triples chosen")
        if not chosen:
            continue
        by_key = {s.triple.key: s for s in chosen}
        anns = [triple_from_annotation(a, case) for a in case.all]
        for cls in defect_classes([s.triple for s in chosen] + anns):
            mine = [by_key[t.key] for t in cls.members if t.key in by_key]
            if not mine:
                continue
            gid = cls.id
            path = out / "dossiers" / f"{gid.replace('/', '-')}.md"
            path.write_text(render_dossier(gid, mine, cls.members, cls.edges, case, suite_root),
                            encoding="utf-8")
            dossiers.append((gid, path, mine))
            with_annotation += any(t.label.startswith("2.1") for t in cls.members)
            for s in mine:
                sib = sorted({f"{why}:{b if a == s.triple.key else a}" for a, b, why in cls.edges
                              if s.triple.key in (a, b)})
                group_rows.append([gid, s.key, s.case, s.records[0]["variable"]["name"],
                                   *s.lines, " ".join(r["id"] for r in s.records), " ".join(sib)])

    with (out / "groups.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "triple", "case", "variable", "a1", "b", "a2", "candidate_ids", "siblings"])
        w.writerows(group_rows)

    unannotated = [s for s in all_sets if not s.annotated]
    sel_path = selection_out or (out / "selection.csv")
    sel_path.parent.mkdir(parents=True, exist_ok=True)
    with sel_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["triple", "case", "a1", "b", "a2", "records", "buckets", "selected", "selected_by",
                    "mode", "k", "seed"])
        for s in sorted(unannotated, key=lambda s: s.key):
            w.writerow([s.key, s.case, *s.lines, len(s.records), " ".join(s.buckets) or "-",
                        "yes" if s.selected else "no", s.selected_by, mode, k, seed])

    summary = {
        "runs": len(runs),
        "records_reaching_llm": sum(len(s.records) for s in all_sets),
        "unannotated_records": sum(len(s.records) for s in unannotated),
        "unannotated_triples": len(unannotated),
        "chosen_triples": sum(len(m) for _, _, m in dossiers),
        "dossiers": len(dossiers),
        "groups_with_an_annotated_member": with_annotation,
    }
    readme = [
        "# Racebench 2.2 — adjudication dossiers",
        "",
        "Blind dossiers (protocol: `project-src/docs/evaluation-protocol.md`, \"DRAFT -- Racebench 2.2\").",
        "Do **not** open `selection.csv`: it records how the triples were chosen and is the only file "
        "here that is not blind.",
        "",
        f"- equivalence rule: {EQUIVALENCE_RULE}",
        f"- runs: {len(runs)}; dossiers: {summary['dossiers']}; triples to adjudicate: {summary['chosen_triples']}",
        "- transcribe each filled form into `project-src/bench/racebench-2.2.yaml`, rejections included",
        "",
        "| dossier | triples | lines |",
        "| --- | --- | --- |",
    ]
    for gid, path, mine in dossiers:
        readme.append(f"| [{gid}](dossiers/{path.name}) | {len(mine)} | "
                      f"{'; '.join('(' + ', '.join(map(str, s.lines)) + ')' for s in mine)} |")
    (out / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_root", nargs="+", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    how = ap.add_mutually_exclusive_group(required=True)
    how.add_argument("--all", action="store_true", help="every unannotated triple (never reads llm/)")
    how.add_argument("--likely-real-plus-sample", type=int, metavar="K",
                     help="every likely_real triple plus K sampled from the other buckets")
    ap.add_argument("--seed", type=int, default=None, help="required with --likely-real-plus-sample")
    ap.add_argument("--selection-out", type=Path, default=None,
                    help="where selection.csv goes (default: OUT/selection.csv)")
    ap.add_argument("--latest", action="store_true", help="keep the latest run when a subject has several")
    args = ap.parse_args(argv)
    if args.likely_real_plus_sample is not None and args.seed is None:
        ap.error("--likely-real-plus-sample needs --seed, so the sample can be redrawn")
    mode = "all" if args.all else "likely-real-plus-sample"
    runs = collect_runs(args.run_root, latest=args.latest)
    print(f"{len(runs)} run(s); writing {args.out}", flush=True)
    summary = build(runs, args.out, mode=mode, k=args.likely_real_plus_sample or 0,
                    seed=args.seed or 0, selection_out=args.selection_out,
                    log=lambda m: print(m, flush=True))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
