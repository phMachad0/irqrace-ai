"""Stage 2 — potential concurrency relationship analysis.

IntRace's cheap filter ([[IntRace (paper)]] §3.2; [[Pipeline Design]], stage 2):
each flow is a block ``(T, I, S, p)`` -- name, interrupt status, timing,
priority -- and a candidate is discarded when its blocks provably cannot
overlap. Rebuilt here for recall, which changes three things:

* **Only a proof discards** (Soundness Assumptions H1, H1d). A candidate leaves
  stage 2 only when the interleaving it describes is impossible under the
  priority and masking model, and every drop writes a line to
  ``stage2/dropped.jsonl`` saying why and which stated assumptions the proof
  rests on. ``irqrace runstore check`` fails a run in which a stage-1 candidate
  vanished without one (C3 rule 6).
* **Timing is left unconstrained** (``S``). Racebench guarantees no periodicity,
  and assuming one is an unsound filter.
* **Masking is a whole-program question**, answered by :mod:`irqrace.masking`:
  another flow may run inside an interval and unmask what the local flow masked.

The two questions are kept apart, as [[Pair-Triple Unification]] requires:

* **pairs -- the point property.** ``(A, B)`` survives if B's flow may run while
  A's flow is at A, or the other way round.
* **triples -- the interval property.** ``(A1, B, A2)`` survives if B's flow may
  run at *any* point of *any* path from A1 to A2 in A1's flow -- callees on the
  path included, directly or nested inside another flow that runs there.

"May run while F is at p" (:meth:`Concurrency.run`) is: every flow whose
interrupt is not masked at p (after interference) and that may preempt F on
priority, plus everything that may in turn run inside those.
"""

from __future__ import annotations

import copy
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable

from .candidate import ROLE_ORDER, stamp_identity
from .config import Config, Flow
from .masking import (D, E, U, MaskAnalysis, MaskAnalysisError, Origin,
                      ProgramError, apply, join, load_program, masked, origins, values)

#: Every drop names the stated assumptions its proof depends on, by their
#: identifiers in wiki/Soundness Assumptions.md. Revisiting an assumption then
#: means grepping dropped.jsonl for it, not re-deriving which results it touched.
RELIES_PRIORITY = ["B1", "E1", "E3", "H1d"]
RELIES_MASKING = ["B1", "E1", "E4", "F1", "F2", "F3", "F5", "F6", "F7", "F8", "F9", "H1d"]
RELIES_NO_PATH = ["B2", "B4", "H1c", "H1d"]


class Stage2Error(RuntimeError):
    pass


# -- may-run relations ------------------------------------------------------


class Concurrency:
    """Which flows may run while a given flow is at a given point.

    **Context-sensitive in the entry state of nested activations.** A flow X
    that fires at point p starts in the state at p -- not in X's global entry
    state, which is the union over every point X may fire at anywhere. An
    activation of X nested inside an interval started inside that interval, so
    what may run inside *it* is decided from the state where it started
    (:meth:`inside`). States inside X are kept relative to X's entry
    (``rel_points``) precisely so they can be re-concretised per firing point.

    Using the global entry instead is sound but blind to exactly the planted
    traps of svp_simple_027/028/030: an ISR that may fire before ``main``'s
    ``disable_isr(-1)`` makes it look as if anything may run inside it, ever.
    Where the recursion meets itself (equal priorities, re-entrancy) it falls
    back to the global answer, which is sound.
    """

    def __init__(self, m: MaskAnalysis):
        self.m = m
        ids = [f.id for f in m.flows]
        # Ignoring masking altogether: who could ever run while F is active.
        self.static_run: dict[str, set[str]] = {}
        for F in ids:
            seen: set[str] = set()
            work = deque(G.id for G in m.preempters[F])
            while work:
                g = work.popleft()
                if g in seen:
                    continue
                seen.add(g)
                work.extend(X.id for X in m.preempters[g])
            self.static_run[F] = seen
        # Flows that may fire somewhere in G's own code.
        self.direct_any: dict[str, set[str]] = {
            F: {G.id for _, c in m.all_points(F) for G in m.direct(F, c)} for F in ids}
        # Flows that may run while G is active, transitively. A fixpoint because
        # equal priorities may make preemption cyclic.
        self.nested: dict[str, set[str]] = {F: set() for F in ids}
        changed = True
        while changed:
            changed = False
            for F in ids:
                acc = set(self.direct_any[F])
                for X in self.direct_any[F]:
                    acc |= self.nested[X]
                if acc != self.nested[F]:
                    self.nested[F] = acc
                    changed = True
        self._cache: dict[tuple[str, Any], frozenset[str]] = {}
        self._inside: dict[tuple[str, Any], frozenset[str]] = {}
        self._stack: set[tuple[str, Any]] = set()
        self.rel_points = {F: self._relative_points(F) for F in ids}

    def _relative_points(self, X: str) -> list[Any]:
        """Every reachable point of X's code, as a state relative to X's entry."""
        m = self.m
        entry_fn = m.by_id[X].entry
        if entry_fn not in m.prog:
            return []
        sym: dict[str, Any] = {entry_fn: m.symbolic}
        changed = True
        while changed:
            changed = False
            for fn in m.reach[X]:
                base, pts = sym.get(fn), m.points.get((X, fn))
                if base is None or pts is None:
                    continue
                for b, blk in enumerate(m.prog[fn].blocks):
                    for k, ev in enumerate(blk.events):
                        rel = apply(pts[b][k], base) if ev.kind == "call" else None
                        if rel is None:
                            continue
                        for callee in ev.callees:
                            if callee in m.prog:
                                new = join(sym.get(callee), rel)
                                if new != sym.get(callee):
                                    sym[callee] = new
                                    changed = True
        out = []
        for fn in m.reach[X]:
            base, pts = sym.get(fn), m.points.get((X, fn))
            if base is None or pts is None:
                continue
            for row in pts:
                for s in row:
                    rel = apply(s, base)
                    if rel is not None:
                        out.append(rel)
        return out

    def inside(self, X: str, entry) -> frozenset[str]:
        """Flows that may run while X is active, X having started in ``entry``."""
        key = (X, entry)
        if key in self._inside:
            return self._inside[key]
        if key in self._stack:
            return frozenset(self.nested[X])  # a preemption cycle: the global answer
        self._stack.add(key)
        acc: set[str] = set()
        for rel in self.rel_points[X]:
            acc |= self.run(X, apply(rel, entry))
        self._stack.discard(key)
        self._inside[key] = frozenset(acc)
        return self._inside[key]

    def direct(self, flow: str, c) -> set[str]:
        if c is None:
            # A point the masking model finds unreachable. Never a basis for a
            # drop: fall back to priority alone.
            return {G.id for G in self.m.preempters[flow]}
        return {G.id for G in self.m.direct(flow, c)}

    def run(self, flow: str, c) -> frozenset[str]:
        if c is None:
            return frozenset(self.static_run[flow])
        key = (flow, c)
        if key not in self._cache:
            d = self.direct(flow, c)
            acc = set(d)
            for X in d:
                acc |= self.inside(X, c)
            self._cache[key] = frozenset(acc)
        return self._cache[key]

    def depth(self, flow: str, c, target: str) -> int | None:
        """Smallest number of stacked preemptions at which ``target`` runs."""
        level = {(X, c) for X in self.direct(flow, c)}
        seen: set[tuple[str, Any]] = set()
        d = 1
        while level:
            if any(X == target for X, _ in level):
                return d
            seen |= level
            nxt: set[tuple[str, Any]] = set()
            for X, entry in level:
                for rel in self.rel_points[X]:
                    cq = apply(rel, entry)
                    nxt |= {(Y, cq) for Y in self.direct(X, cq)} if cq is not None else set()
            level = nxt - seen
            d += 1
        return None


# -- the supergraph, for intervals -------------------------------------------


class FlowGraph:
    """Program points of one flow, linked through calls and returns.

    Context-insensitive: a callee returns to every call site in the flow. That
    adds paths that do not exist, which can only add interval points -- the
    sound direction.
    """

    def __init__(self, m: MaskAnalysis, flow: str):
        self.succ: dict[tuple, list[tuple]] = {}
        self.pred: dict[tuple, list[tuple]] = {}
        prog = m.prog

        def edge(a, b):
            self.succ.setdefault(a, []).append(b)
            self.pred.setdefault(b, []).append(a)

        for fn in m.reach[flow]:
            for b, blk in enumerate(prog[fn].blocks):
                n = len(blk.events)
                for k, ev in enumerate(blk.events):
                    here, nxt = (fn, b, k), (fn, b, k + 1)
                    bodies = [c for c in ev.callees if c in prog] if ev.kind == "call" else []
                    if len(bodies) < len(ev.callees) or not bodies:
                        edge(here, nxt)  # falls through: no call, or a target without a body
                    for g in bodies:
                        edge(here, (g, 0, 0))
                        for eb, eblk in enumerate(prog[g].blocks):
                            if eblk.exit:
                                edge((g, eb, len(eblk.events)), nxt)
                for t in blk.succ:
                    edge((fn, b, n), (fn, t, 0))
        self._fwd: dict[tuple, frozenset] = {}
        self._bwd: dict[tuple, frozenset] = {}

    @staticmethod
    def _closure(start, adj) -> frozenset:
        seen = {start}
        work = deque([start])
        while work:
            for y in adj.get(work.popleft(), ()):
                if y not in seen:
                    seen.add(y)
                    work.append(y)
        return frozenset(seen)

    def interval(self, after_a1: tuple, before_a2: tuple) -> frozenset:
        """Every point on some path from just after A1 to just before A2."""
        if after_a1 not in self._fwd:
            self._fwd[after_a1] = self._closure(after_a1, self.succ)
        if before_a2 not in self._bwd:
            self._bwd[before_a2] = self._closure(before_a2, self.pred)
        return self._fwd[after_a1] & self._bwd[before_a2]


# -- verdicts -----------------------------------------------------------------


@dataclass
class Verdict:
    keep: bool
    preemption: dict[str, Any]
    per_access: dict[str, dict[str, list[int]]]
    interval: dict[str, Any] | None = None
    reason: str | None = None
    proof: str | None = None
    relies_on: list[str] = field(default_factory=list)
    notes: list[dict[str, str]] = field(default_factory=list)
    any_masking: bool = False


@dataclass
class Stage2Result:
    kept: list[dict[str, Any]]
    dropped: list[dict[str, Any]]
    report: dict[str, Any]


def _relation(cfg: Config, high: Flow, low: Flow) -> str:
    if high.priority > low.priority:
        return "strictly-higher"
    if high.priority == low.priority:
        return "equal"
    return "strictly-lower"


def _cite(os: Iterable[Origin], limit: int = 4) -> str:
    os = list(os)
    text = "; ".join(o.describe() for o in os[:limit])
    if len(os) > limit:
        text += f"; and {len(os) - limit} more"
    return text or "nothing"


class Stage2:
    def __init__(self, analysis: dict[str, Any], cfg: Config):
        self.analysis = analysis
        self.cfg = cfg
        self.flows = {f.id: f for f in cfg.flows}
        self.accesses = {a["id"]: a for a in analysis["accesses"]}
        try:
            self.m = MaskAnalysis(load_program(analysis), cfg).run()
        except ProgramError as e:
            raise Stage2Error(str(e)) from e
        except MaskAnalysisError as e:
            raise Stage2Error(str(e)) from e
        self.c = Concurrency(self.m)
        self._graphs: dict[str, FlowGraph] = {}
        # Per flow: the interrupts its *own code* may unmask -- an enable whose
        # event lies in a function the flow reaches. Used to name who broke a
        # critical section, never to decide.
        self.unmasks: dict[str, set[int]] = {}
        for F in self.flows:
            own = set(self.m.reach[F])
            acc: set[int] = set()
            for _, s in self.m.symbolic_points(F):
                if s is None:
                    continue
                for n, i in self.m.idx.items():
                    if any(v in (E, U) and o.function in own for v, o in s[i]):
                        acc.add(n)
            self.unmasks[F] = acc

    # -- helpers ---------------------------------------------------------

    def graph(self, flow: str) -> FlowGraph:
        if flow not in self._graphs:
            self._graphs[flow] = FlowGraph(self.m, flow)
        return self._graphs[flow]

    def _access(self, rec_access: dict[str, Any]) -> dict[str, Any]:
        ir = rec_access.get("ir") or {}
        if "access" not in ir or ir["access"] not in self.accesses:
            raise Stage2Error(
                f"candidate access at line {rec_access['source']['line']} carries no "
                "back-pointer into stage1/accesses.json (C2 Access.ir); re-run stage 1")
        return self.accesses[ir["access"]]

    @staticmethod
    def _pre(a: dict[str, Any]) -> tuple:
        return (a["function"], a["point"]["block"], a["point"]["event"])

    @staticmethod
    def _post(a: dict[str, Any]) -> tuple:
        return (a["function"], a["point"]["block"], a["point"]["event"] + 1)

    def _masking_state(self, c) -> dict[str, list[int]]:
        """C2 MaskingState. Unreachable in the model reads as unknown, never masked."""
        out = {"disabled": [], "enabled": [], "unknown": []}
        for n, i in self.m.idx.items():
            if c is None:
                out["unknown"].append(n)
                continue
            vs = values(c[i])
            if vs == {D}:
                out["disabled"].append(n)
            elif E in vs:
                out["enabled"].append(n)
            else:
                out["unknown"].append(n)
        return out

    def _preemption(self, high: Flow, low: Flow, depth: int | None) -> dict[str, Any]:
        rel = _relation(self.cfg, high, low)
        out: dict[str, Any] = {
            "preempting_flow": high.id,
            "preempted_flow": low.id,
            "priority_relation": rel,
            "equal_priority_assumed_preemptible": (
                bool(self.cfg.semantics["equal_priority_preemption"]) if rel == "equal" else None),
            "timing": "unconstrained",
        }
        if depth is not None:
            out["nesting_depth"] = depth
        return out

    def _why_not_by_priority(self, high: Flow, low: Flow) -> str:
        if not high.is_isr:
            return f"{high.id} is a task, and a task never preempts anything"
        if low.is_isr and not self.cfg.semantics["nesting"]:
            return "nesting is disabled (E5), so nothing preempts an ISR"
        if high.id == low.id:
            return "an ISR does not preempt itself (E3)"
        if high.priority == low.priority:
            return "they share a priority and equal_priority_preemption is false (E2)"
        return (f"{high.id} has priority {high.priority}, lower than {low.id}'s "
                f"{low.priority}, and only a strictly higher priority preempts (E1)")

    def _priority_relies(self, high: Flow, low: Flow, *, triple: bool = False) -> list[str]:
        out = set(RELIES_PRIORITY)
        if high.priority == low.priority:
            out.add("E2")
        if low.is_isr:
            out.add("E5")
        if triple:
            out.add("G2c")  # the interval lies within one activation of the local flow
        return sorted(out)

    def _irq_name(self, flow: Flow) -> str:
        return f"irq {flow.irq} ({flow.id})" if flow.irq is not None else flow.id

    # -- triples ---------------------------------------------------------

    def _triple(self, rec: dict[str, Any]) -> Verdict:
        by_role = {a["role"]: a for a in rec["accesses"]}
        a1, b, a2 = (self._access(by_role[r]) for r in ("A1", "B", "A2"))
        F, H = self.flows[a1["flow"]], self.flows[b["flow"]]
        l1, l2 = by_role["A1"]["source"]["line"], by_role["A2"]["source"]["line"]
        per_access = {
            role: self._masking_state(self.m.state(acc["flow"], self._pre(acc)))
            for role, acc in (("A1", a1), ("B", b), ("A2", a2))}

        interval_pts = self.graph(F.id).interval(self._post(a1), self._pre(a2))
        if not interval_pts:
            return Verdict(
                keep=False, preemption=self._preemption(H, F, None), per_access=per_access,
                reason="no-path", relies_on=list(RELIES_NO_PATH),
                proof=(f"No path through {F.id}'s control flow -- call and return edges "
                       f"included -- leads from line {l1} to line {l2} within one "
                       f"activation of {F.id}, so nothing can fall between them."))

        states = {p: self.m.state(F.id, p) for p in interval_pts}
        runset: set[str] = set()
        depth: int | None = None
        direct_hit = False
        for p, c in states.items():
            r = self.c.run(F.id, c)
            runset |= r
            if H.id in r:
                d = 1 if c is None else self.c.depth(F.id, c, H.id)
                if d is not None:
                    depth = d if depth is None else min(depth, d)
                direct_hit = direct_hit or H.id in self.c.direct(F.id, c)
        unreachable = sum(1 for c in states.values() if c is None)

        # The interval masking state the contract describes.
        cells: dict[int, set] = {n: set() for n in self.m.idx}
        for c in states.values():
            for n, i in self.m.idx.items():
                cells[n] |= c[i] if c is not None else {(U, Origin("unreachable"))}
        enabled = {n for n, cell in cells.items() if E in values(cell)}
        unknown = {n for n, cell in cells.items() if U in values(cell)} - enabled
        locally = set(self.m.idx)
        for p in interval_pts:
            lc = self.m.state(F.id, p, local=True)
            locally &= {n for n, i in self.m.idx.items() if lc is not None and masked(lc[i])}
        # Clause (b) of the interval property: a flow that may run inside the
        # interval and unmasks n in its own code means n is not masked
        # throughout, even when every point of the local flow says it is -- and
        # so does n's own handler being able to run there at all, nested or not.
        handler = {G.irq: G.id for G in self.flows.values() if G.irq is not None}
        nested_unmask = {
            n for n in self.m.idx if n not in enabled | unknown and (
                handler.get(n) in runset
                or any(n in self.unmasks[X] for X in runset if X != F.id))}
        enabled |= nested_unmask
        disabled = set(self.m.idx) - enabled - unknown
        reenabled_by = sorted(X for X in runset if X != F.id and self.unmasks[X] & locally)
        interval = {
            "from_role": "A1", "to_role": "A2",
            "disabled_throughout": sorted(disabled),
            "enabled_somewhere": sorted(enabled),
            "unknown": sorted(unknown),
            "reenabled_within_interval_by": reenabled_by,
        }
        any_masking = any(D in values(cell) for cell in cells.values()) or any(
            st["disabled"] for st in per_access.values())

        keep = H.id in runset
        if keep:
            note = self._interval_note(F, H, l1, l2, cells, depth, direct_hit,
                                       reenabled_by, locally, unreachable)
            return Verdict(
                keep=True, preemption=self._preemption(H, F, depth), per_access=per_access,
                interval=interval, any_masking=any_masking,
                notes=[{"fact": "masking.interval", "status": "overapproximated", "note": note}])

        if H.id not in self.c.static_run[F.id]:
            return Verdict(
                keep=False, preemption=self._preemption(H, F, None), per_access=per_access,
                interval=interval, reason="priority", any_masking=any_masking,
                relies_on=self._priority_relies(H, F, triple=True),
                proof=(f"{H.id} can never run while {F.id} is active, so B cannot fall "
                       f"between line {l1} and line {l2}: "
                       f"{self._why_not_by_priority(H, F)}."))

        n = H.irq
        by = origins(cells[n], D)
        return Verdict(
            keep=False, preemption=self._preemption(H, F, None), per_access=per_access,
            interval=interval, reason="masking", any_masking=any_masking,
            relies_on=sorted(set(RELIES_MASKING) | {"G2c"}
                             | ({"F4"} if any("(-1)" in o.text for o in by) else set())),
            proof=(f"{H.id} may preempt {F.id} on priority, but {self._irq_name(H)} is "
                   f"masked at every point of every path from line {l1} to line {l2} in "
                   f"{F.id} ({len(interval_pts)} program points, callees included), even "
                   f"after every mask change a flow able to run there could make. Masked "
                   f"by: {_cite(by)}. "
                   + (f"Of the flows that may run inside the interval -- "
                      f"{', '.join(sorted(runset))} -- none leaves irq {n} unmasked "
                      f"when it returns, and {H.id} cannot run nested inside any "
                      f"of them." if runset else
                      "No other flow may run inside the interval at all.")))

    def _interval_note(self, F, H, l1, l2, cells, depth, direct_hit, reenabled_by,
                       locally, unreachable) -> str:
        n = H.irq
        head = (f"{H.id} may run within [line {l1}, line {l2}] of {F.id}"
                + (f", at nesting depth {depth}" if depth else ""))
        if n is None or n not in cells:
            return head + "."
        cell = cells[n]
        parts = [head]
        if not direct_hit:
            parts.append(f"only nested inside another flow that runs there, since "
                         f"irq {n} is masked at every point of the interval itself")
        else:
            parts.append(f"irq {n} is not masked on every path there; it may be "
                         f"enabled by: {_cite(origins(cell, E, U))}")
        if F.is_isr and direct_hit and self._starts_unmasked(F, n, cells):
            parts.append(f"{F.id} may itself start with irq {n} unmasked: an ISR begins "
                         f"in the state of whatever point it preempted, and {F.id} may "
                         f"fire wherever irq {n} is unmasked -- including before any "
                         f"masking call in the flows it preempts (F8)")
        if n in locally and reenabled_by:
            parts.append(f"{F.id} masks it itself ({_cite(origins(cell, D))}), but "
                         f"{', '.join(reenabled_by)} may run inside the interval and "
                         f"unmask it -- computed from {F.id}'s own control flow alone, "
                         f"this candidate would have been dropped")
        if unreachable:
            parts.append(f"{unreachable} interval point(s) are unreachable in the "
                         "masking model and were read as unknown")
        return "; ".join(parts) + "."

    def _starts_unmasked(self, F: Flow, n: int, cells) -> bool:
        """Does irq n reach the interval unchanged from F's own entry, unmasked?"""
        entry = self.m.isr_entry.get(F.id)
        if entry is None or n not in self.m.idx:
            return False
        return not masked(entry[self.m.idx[n]]) and bool(
            set(entry[self.m.idx[n]]) & cells[n])

    # -- pairs -----------------------------------------------------------

    def _pair(self, rec: dict[str, Any]) -> Verdict:
        by_role = {a["role"]: a for a in rec["accesses"]}
        a, b = self._access(by_role["A1"]), self._access(by_role["B"])
        L, H = self.flows[a["flow"]], self.flows[b["flow"]]
        la, lb = by_role["A1"]["source"]["line"], by_role["B"]["source"]["line"]
        ca, cb = self.m.state(L.id, self._pre(a)), self.m.state(H.id, self._pre(b))
        per_access = {"A1": self._masking_state(ca), "B": self._masking_state(cb)}
        any_masking = any(st["disabled"] for st in per_access.values())

        for high, low, c, line, other_line in ((H, L, ca, la, lb), (L, H, cb, lb, la)):
            if high.id in self.c.run(low.id, c):
                depth = 1 if c is None else self.c.depth(low.id, c, high.id)
                note = (f"{high.id} may run while {low.id} is at line {line}"
                        + (f" (nesting depth {depth})" if depth else ""))
                if c is not None and high.irq in self.m.idx:
                    cell = c[self.m.idx[high.irq]]
                    if masked(cell):
                        note += (f", nested inside another flow: irq {high.irq} itself is "
                                 f"masked there by {_cite(origins(cell, D))}")
                    else:
                        note += (f": irq {high.irq} is not masked on every path there; "
                                 f"it may be enabled by {_cite(origins(cell, E, U))}")
                return Verdict(
                    keep=True, preemption=self._preemption(high, low, depth),
                    per_access=per_access, any_masking=any_masking,
                    notes=[{"fact": "masking.per_access", "status": "overapproximated",
                            "note": note + "."}])

        if H.id not in self.c.static_run[L.id] and L.id not in self.c.static_run[H.id]:
            return Verdict(
                keep=False, preemption=self._preemption(H, L, None), per_access=per_access,
                reason="priority", any_masking=any_masking,
                relies_on=sorted(set(self._priority_relies(H, L))
                                 | set(self._priority_relies(L, H))),
                proof=(f"Neither flow can run while the other is active: "
                       f"{self._why_not_by_priority(H, L)}; and "
                       f"{self._why_not_by_priority(L, H)}."))

        reasons = []
        for high, low, c, line in ((H, L, ca, la), (L, H, cb, lb)):
            if high.id not in self.c.static_run[low.id]:
                reasons.append(f"{high.id} never runs while {low.id} is active: "
                               f"{self._why_not_by_priority(high, low)}")
            else:
                cell = c[self.m.idx[high.irq]] if c is not None else frozenset()
                reasons.append(
                    f"{high.id} may preempt {low.id} on priority, but "
                    f"{self._irq_name(high)} is masked at line {line} on every path, even "
                    f"after every mask change a flow able to run there could make "
                    f"(masked by {_cite(origins(cell, D))}), and no flow that may run "
                    f"there unmasks it")
        return Verdict(
            keep=False, preemption=self._preemption(H, L, None), per_access=per_access,
            reason="masking", any_masking=any_masking, relies_on=sorted(RELIES_MASKING),
            proof="; ".join(reasons) + ".")

    # -- records ---------------------------------------------------------

    def judge(self, rec: dict[str, Any]) -> Verdict:
        return self._triple(rec) if rec["class"] == "atomicity-triple" else self._pair(rec)

    def _enrich(self, rec: dict[str, Any], v: Verdict) -> dict[str, Any]:
        out = copy.deepcopy(rec)
        out["emitted_by"] = {**rec.get("emitted_by", {}), "stage": "stage2"}
        out["preemption"] = v.preemption
        roles = sorted(v.per_access, key=lambda r: ROLE_ORDER[r])
        for a in out["accesses"]:
            a["masking"] = v.per_access[a["role"]]
        out["masking"] = {"per_access": [{"role": r, "state": v.per_access[r]} for r in roles]}
        if v.interval is not None:
            out["masking"]["interval"] = v.interval
        out.setdefault("static_features", {})["any_masking_present"] = v.any_masking
        sem = self.cfg.semantics
        entries = [e for e in out["provenance"]["entries"] if e["fact"] != "masking"]
        entries.append({
            "fact": "preemption", "status": "assumed_from_config",
            "note": (f"priorities from the C1 file, larger number = higher priority; "
                     f"nesting={sem['nesting']}, equal_priority_preemption="
                     f"{sem['equal_priority_preemption']}, isr_reentrant="
                     f"{sem['isr_reentrant']}, timing unconstrained")})
        entries.extend(v.notes)
        out["provenance"]["entries"] = entries
        before = rec["id"]
        out = stamp_identity(out)
        if out["id"] != before:  # the fingerprint excludes everything stage 2 adds
            raise Stage2Error(f"stage 2 changed the identity of candidate {before}")
        return out

    def _drop(self, rec: dict[str, Any], v: Verdict) -> dict[str, Any]:
        by_role = sorted(rec["accesses"], key=lambda a: ROLE_ORDER[a["role"]])
        return {
            "candidate_id": rec["id"],
            "fingerprint": rec["fingerprint"],
            "stage": "stage2",
            "class": rec["class"],
            "pattern": rec.get("pattern", ""),
            "variable": rec["variable"]["name"],
            "lines": [a["source"]["line"] for a in by_role],
            "local_flow": by_role[0]["flow"],
            "remote_flow": by_role[1]["flow"],
            "reason": v.reason,
            "proof": v.proof,
            "relies_on": v.relies_on,
        }

    def run(self, candidates: Iterable[dict[str, Any]]) -> Stage2Result:
        # Pairs and triples are judged independently, from the same analysis:
        # a pair's verdict never decides a triple's, nor the reverse
        # ([[Pair-Triple Unification]]).
        kept, dropped = [], []
        for rec in candidates:
            v = self.judge(rec)
            if v.keep:
                kept.append(self._enrich(rec, v))
            else:
                dropped.append(self._drop(rec, v))
        return Stage2Result(kept=kept, dropped=dropped, report=self.report())

    def report(self) -> dict[str, Any]:
        """``stage2/masking.json``: the analysis behind every verdict, for debugging
        and for the explorer. Not a contract; read it, do not depend on it."""
        m = self.m
        return {
            "rounds": m.rounds,
            "irqs": m.irqs,
            "flows": {
                F.id: {
                    "priority": F.priority, "irq": F.irq,
                    "may_be_preempted_by": [G.id for G in m.preempters[F.id]],
                    "may_run_inside": sorted(self.c.nested[F.id]),
                    "reachable_functions": m.reach[F.id],
                    "entry_state": m.describe_state(
                        m.isr_entry.get(F.id) if F.is_isr else m.initial),
                    "leaves_behind": m.describe_state(m.effect.get(F.id)) if F.is_isr else None,
                    "unmasks_in_own_code": sorted(self.unmasks[F.id]),
                }
                for F in self.cfg.flows
            },
            "accesses": {
                str(a["id"]): {
                    "flow": a["flow"], "line": a["source"]["line"], "kind": a["kind"],
                    "state": m.describe_state(m.state(a["flow"], self._pre(a))),
                    "local_view": m.describe_state(m.state(a["flow"], self._pre(a), local=True)),
                }
                for a in self.analysis["accesses"]
            },
        }


# -- driver -------------------------------------------------------------------


def stage2(cfg: Config, store) -> dict[str, Any]:
    """Run stage 2 over a run store whose stage 1 has completed."""
    t0 = time.perf_counter()
    store.set_stage("stage2", "running")
    try:
        analysis = json.loads((store.root / "stage1" / "accesses.json").read_text())
        candidates = store.read_candidates("stage1")
        result = Stage2(analysis, cfg).run(candidates)
    except (Stage2Error, OSError, KeyError) as e:
        store.set_stage("stage2", "failed", error=str(e))
        store.log("error", "stage2", "stage2-failed", str(e))
        raise Stage2Error(str(e)) from e

    store.append_candidates("stage2", result.kept)
    store.append_drops(result.dropped)
    (store.root / "stage2" / "masking.json").write_text(
        json.dumps(result.report, indent=2, ensure_ascii=False) + "\n")

    wall = int((time.perf_counter() - t0) * 1000)
    store.set_stage("stage2", "ok", candidates_in=len(candidates),
                    candidates_out=len(result.kept),
                    dropped_with_proof=len(result.dropped), wall_ms=wall)
    reasons: dict[str, int] = {}
    for d in result.dropped:
        reasons[d["reason"]] = reasons.get(d["reason"], 0) + 1
    store.log("info", "stage2", "candidates-filtered",
              f"{len(result.kept)} of {len(candidates)} candidates survive; "
              f"{len(result.dropped)} dropped with proof "
              + (f"({', '.join(f'{k} {v}' for k, v in sorted(reasons.items()))})"
                 if reasons else ""),
              rounds=result.report["rounds"])

    def count(recs, cls):
        return sum(1 for r in recs if r["class"] == cls)

    return {
        "in": len(candidates),
        "kept": len(result.kept),
        "dropped": len(result.dropped),
        "triples_in": count(candidates, "atomicity-triple"),
        "triples_kept": count(result.kept, "atomicity-triple"),
        "pairs_in": count(candidates, "race-pair"),
        "pairs_kept": count(result.kept, "race-pair"),
        "reasons": reasons,
        "rounds": result.report["rounds"],
        "wall_ms": wall,
    }
