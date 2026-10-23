"""The interrupt-mask analysis stage 2 rests on.

An abstract interpreter over the event CFG that ``irqrace-stage1`` emits
(``stage1/accesses.json``, key ``program``). For every flow and every program
point it computes which interrupts may be enabled there, and -- because the
answer is used to *discard* candidates -- it computes it in the direction that
can only lose precision, never recall.

**The rule** ([[Pipeline Design]], stage 2; Soundness Assumptions F1): an
interrupt counts as masked at a point only if it is masked on every path
reaching that point. The domain makes that structural: each interrupt carries
the *set* of values it may have, and it is masked only when that set is exactly
``{D}``.

**The part the obvious implementation gets wrong** (``docs/masking-semantics.md``):
the mask is one piece of hardware state shared by every flow. An ISR that
preempts the main task and calls ``enable_isr(2)`` changes what the main task
sees afterwards. So the state at a point is not a property of the local CFG:

* **Interference.** At every point where a flow ``G`` may fire, the state may
  additionally take any value ``G`` can leave behind when it returns. Repeated to
  a closure, because what ``G`` leaves may let another flow fire. Whether the
  hardware restores the mask on return is platform-dependent, so the analysis
  takes the union -- an ISR's enables can break a proof in the flow it
  preempted, its disables never help one (assumption F7).
* **ISR entry.** An ISR starts in whatever state the flow it preempted was in.
  That is the union of the states at *every* point where it may fire, in every
  flow -- including points before the main task's first masking call
  (assumption F8). It is never "the state at the point the author had in mind".

**Symbolic entry values.** States inside a function are expressed relative to
its entry: a value ``K`` means "whatever it was when this function (or this
ISR) started". A call applies the callee's summary to the caller's own state, so
an ``idlerun()`` called once with irq 2 masked and once with it enabled does not
return "maybe enabled" to both. ``K`` is replaced by the concrete entry state
only when a decision has to be made (``concretise``).

**Every value carries its origin** -- the ``disable_isr(2)`` at line 28, the
``enable_isr(2)`` at line 46 in ``isr_1``, the initial state. A proof is then
explainable, and so is a doubt: "irq 2 is not proven masked here because
``isr_1`` may run first and its ``enable_isr(2)`` persists" is the sentence the
LLM stage and the thesis both need.

**Fixpoint.** The whole computation is one monotone system over a finite
lattice, solved by Kleene iteration from bottom. Intermediate iterates are *not*
sound -- they under-approximate -- so the loop runs to convergence or raises; a
partial result is never returned. (``docs/masking-semantics.md`` originally said
to iterate downward from "everything may run" so that every iterate is sound;
that is also correct, but it can converge to a strictly larger fixpoint when
flows may preempt each other cyclically -- equal priorities, re-entrancy -- and
the least fixpoint is the precise answer. The trade is recorded there.)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

from .config import Config, Flow

# -- the abstract domain ----------------------------------------------------

#: Disabled, enabled, unknown (not decided -- treated as enabled), and the
#: symbolic "as it was on entry".
D, E, U, K = "D", "E", "U", "K"


@dataclass(frozen=True, order=True)
class Origin:
    """Where a mask value came from. The evidence a proof -- or a doubt -- rests on."""

    kind: str  # mask | initial | external | asm | unresolved | hardware | entry | unreachable
    function: str = ""
    line: int = 0
    text: str = ""

    def describe(self) -> str:
        if self.kind == "initial":
            return f"the initial state ({self.text})"
        if self.kind == "hardware":
            return "the hardware masking an ISR's own interrupt on entry"
        if self.kind == "entry":
            return "the state on entry"
        where = f"line {self.line} in {self.function}" if self.line else self.function
        if self.kind == "mask":
            return f"{self.text} at {where}"
        if self.kind == "external":
            return f"the unmodelled external call {self.text} at {where}"
        if self.kind == "asm":
            return f"inline assembly at {where}"
        if self.kind == "unreachable":
            return "a point the masking model finds unreachable, read as unknown"
        return f"an unresolved indirect call at {where}"


ENTRY = Origin("entry")

#: One cell per configured interrupt: the set of (value, origin) it may hold.
Cell = frozenset
#: A program state: one cell per interrupt, in ``Config.all_irqs`` order.
#: ``None`` is bottom -- the point is unreachable.
State = "tuple[Cell, ...] | None"


def join(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return tuple(x | y for x, y in zip(a, b))


def apply(summary, state):
    """Substitute ``state`` for the symbolic ``K`` values of ``summary``.

    Used both to apply a callee's summary at a call site and to concretise a
    symbolic state against a function's entry state -- the same operation.
    """
    if summary is None or state is None:
        return None
    out = []
    for cell_sum, cell_in in zip(summary, state):
        acc: set = set()
        for v, o in cell_sum:
            if v == K:
                acc |= cell_in
            else:
                acc.add((v, o))
        out.append(frozenset(acc))
    return tuple(out)


concretise = apply


def strip_entry(state):
    """The values a summary *sets*, without the ones it merely passes through."""
    if state is None:
        return None
    return tuple(frozenset(x for x in cell if x[0] != K) for cell in state)


def values(cell) -> set[str]:
    return {v for v, _ in cell}


def masked(cell) -> bool:
    """Masked on every path: the only reading of "masked" this project uses."""
    return bool(cell) and all(v == D for v, _ in cell)


def origins(cell, *wanted: str) -> list[Origin]:
    return sorted({o for v, o in cell if v in wanted})


# -- the program model ------------------------------------------------------


@dataclass(frozen=True)
class Event:
    kind: str  # access | call | asm
    line: int
    callees: tuple[str, ...] = ()
    resolution: str = "direct"
    args: tuple[int | None, ...] = ()


@dataclass(frozen=True)
class Block:
    succ: tuple[int, ...]
    exit: bool
    events: tuple[Event, ...]


@dataclass(frozen=True)
class Function:
    name: str
    file: str
    blocks: tuple[Block, ...]


class ProgramError(ValueError):
    pass


def load_program(analysis: dict[str, Any]) -> dict[str, Function]:
    try:
        fns = analysis["program"]["functions"]
    except KeyError as e:
        raise ProgramError(
            "stage1/accesses.json has no program model; it was produced by an "
            "irqrace-stage1 older than W5 -- rebuild with scripts/build-analysis.sh "
            "and re-run stage 1") from e
    out: dict[str, Function] = {}
    for f in fns:
        blocks = tuple(
            Block(
                succ=tuple(b["succ"]),
                exit=bool(b["exit"]),
                events=tuple(
                    Event(kind=e["k"], line=e.get("line", 0),
                          callees=tuple(e.get("callees", ())),
                          resolution=e.get("resolution", "direct"),
                          args=tuple(e.get("args", ())))
                    for e in b["events"]),
            )
            for b in f["blocks"])
        out[f["name"]] = Function(name=f["name"], file=f.get("file", ""), blocks=blocks)
    return out


#: A program point: (function, block index, k), the state *before* event k.
#: k == len(events) is the end of the block.
Point = tuple


def may_preempt(cfg: Config, high: Flow, low: Flow) -> bool:
    """May ``high`` start running while ``low`` is active, ignoring masking?

    Priority comes from ``Config.can_preempt`` (larger number = higher, E1;
    equal priority per E2; re-entrancy per E3). Nesting (E5) is the one extra
    condition: with it off, nothing preempts an ISR.
    """
    if not high.is_isr:
        return False
    if low.is_isr and not cfg.semantics["nesting"]:
        return False
    return cfg.can_preempt(high, low)


class MaskAnalysisError(RuntimeError):
    pass


class MaskAnalysis:
    """Per flow, per function, per point: the interrupts that may be enabled."""

    #: A finite lattice guarantees termination; this bound exists only so that
    #: a bug shows up as an error instead of a hang. It is never a cut-off:
    #: hitting it raises, because an unconverged iterate is not sound.
    MAX_ROUNDS = 1000

    def __init__(self, program: dict[str, Function], cfg: Config):
        self.prog = program
        self.cfg = cfg
        self.irqs: list[int] = cfg.all_irqs
        self.idx = {n: i for i, n in enumerate(self.irqs)}
        self.flows: list[Flow] = cfg.flows
        self.by_id = {f.id: f for f in self.flows}
        self.isrs = [f for f in self.flows if f.is_isr]
        self.primitives = {p.function: p for p in cfg.masking_primitives}
        self.modelled = {m["function"] for m in cfg.data["externals"]["models"]}
        self.externals_default = cfg.data["externals"]["default"]
        self.preempters: dict[str, list[Flow]] = {
            F.id: [G for G in self.flows if may_preempt(cfg, G, F)] for F in self.flows}
        self.reach: dict[str, list[str]] = {F.id: self._reachable(F.entry) for F in self.flows}

        init = cfg.data["masking"]["initial_state"]
        v0 = {"all-enabled": E, "all-disabled": D, "unknown": U}[init]
        o0 = Origin("initial", text=f"masking.initial_state = {init}")
        self.initial = tuple(frozenset({(v0, o0)}) for _ in self.irqs)
        self.symbolic = tuple(frozenset({(K, ENTRY)}) for _ in self.irqs)

        self.points: dict[tuple[str, str], list[list[Any]]] = {}
        self.summary: dict[tuple[str, str], Any] = {}
        self.fn_entry: dict[tuple[str, str], Any] = {}
        self.isr_entry: dict[str, Any] = {G.id: None for G in self.isrs}
        self.effect: dict[str, Any] = {G.id: None for G in self.isrs}
        self.local_points: dict[tuple[str, str], list[list[Any]]] = {}
        self.local_summary: dict[tuple[str, str], Any] = {}
        self.rounds = 0

    # -- reachability ----------------------------------------------------

    def _reachable(self, entry: str) -> list[str]:
        if entry not in self.prog:
            return []
        seen = [entry]
        work = deque([entry])
        while work:
            fn = work.popleft()
            for blk in self.prog[fn].blocks:
                for ev in blk.events:
                    for c in ev.callees:
                        if c in self.prog and c not in seen:
                            seen.append(c)
                            work.append(c)
        return seen

    # -- transfer functions ----------------------------------------------

    def _set(self, s, targets: Iterable[int], v: str, o: Origin):
        if s is None:
            return None
        cells = list(s)
        for n in targets:
            if n in self.idx:
                cells[self.idx[n]] = frozenset({(v, o)})
        return tuple(cells)

    def _smear(self, s, v: str, o: Origin):
        """Every interrupt may now also hold ``v``: an effect that cannot be pinned."""
        if s is None:
            return None
        return tuple(c | {(v, o)} for c in s)

    def _mask(self, prim, fn: str, ev: Event, s):
        v = D if prim.effect == "disable" else E
        if prim.irq_arg is None:
            return self._set(s, self.irqs, v, Origin("mask", fn, ev.line, f"{prim.function}()"))
        arg = ev.args[prim.irq_arg] if prim.irq_arg < len(ev.args) else None
        if arg is None:
            o = Origin("mask", fn, ev.line, f"{prim.function}(<non-constant>)")
            mode = prim.non_constant_arg
            if mode == "none":
                return s
            if mode == "all":
                return self._set(s, self.irqs, v, o)
            # 'unknown': the argument may name any interrupt, or none. A disable
            # may leave each one as it was or masked -- which can never make it
            # masked on every path. An enable may unmask any of them.
            return self._smear(s, D if v == D else U, o)
        o = Origin("mask", fn, ev.line, f"{prim.function}({arg})")
        if prim.all_value is not None and arg == prim.all_value:
            # F4: "all" means exactly the configured interrupts.
            return self._set(s, self.irqs, v, o)
        return self._set(s, [arg], v, o)

    def _call(self, flow: str, fn: str, ev: Event, callee: str, s, local: bool):
        if callee in self.primitives:
            return self._mask(self.primitives[callee], fn, ev, s)
        if callee in self.prog:
            table = self.local_summary if local else self.summary
            return apply(table.get((flow, callee)), s)
        if callee in self.modelled or self.externals_default == "none":
            # F6: a modelled external leaves the mask alone.
            return s
        # F6: an unmodelled external may write the interrupt-enable register.
        return self._smear(s, U, Origin("external", fn, ev.line, f"{callee}()"))

    def _transfer(self, flow: str, fn: str, ev: Event, s, local: bool):
        if s is None or ev.kind == "access":
            return s
        if ev.kind == "asm":
            return self._smear(s, U, Origin("asm", fn, ev.line))
        if not ev.callees:
            return self._smear(s, U, Origin("unresolved", fn, ev.line))
        out = None
        for callee in ev.callees:
            out = join(out, self._call(flow, fn, ev, callee, s, local))
        return out

    # -- interference ----------------------------------------------------

    def fires(self, G: Flow, c) -> bool:
        """May ``G``'s interrupt be taken in concrete state ``c``?"""
        if c is None:
            return False
        if G.irq not in self.idx:
            return True
        return not masked(c[self.idx[G.irq]])

    def direct(self, flow: str, c) -> list[Flow]:
        return [G for G in self.preempters[flow] if self.fires(G, c)]

    def _close(self, flow: str, fn: str, s):
        """Apply, to a closure, everything a flow firing here may leave behind."""
        if s is None:
            return None
        entry = self.fn_entry.get((flow, fn))
        while True:
            c = concretise(s, entry)
            grown = s
            for G in self.direct(flow, c):
                grown = join(grown, self.effect.get(G.id))
            if grown == s:
                return s
            s = grown

    # -- one function in one flow ----------------------------------------

    def _analyse(self, flow: str, fn: str, *, local: bool = False):
        f = self.prog[fn]
        ins: list[Any] = [None] * len(f.blocks)
        ins[0] = self.symbolic
        pts: list[list[Any]] = [[None] * (len(b.events) + 1) for b in f.blocks]
        exit_state = None
        work = deque([0])
        queued = {0}
        while work:
            b = work.popleft()
            queued.discard(b)
            blk = f.blocks[b]
            s = ins[b] if local else self._close(flow, fn, ins[b])
            pts[b][0] = s
            for k, ev in enumerate(blk.events):
                s = self._transfer(flow, fn, ev, s, local)
                if not local:
                    s = self._close(flow, fn, s)
                pts[b][k + 1] = s
            if s is None:
                continue
            if blk.exit:
                exit_state = join(exit_state, s)
            for t in blk.succ:
                new = join(ins[t], s)
                if new != ins[t]:
                    ins[t] = new
                    if t not in queued:
                        work.append(t)
                        queued.add(t)
        return pts, exit_state

    # -- entries ---------------------------------------------------------

    def _entries(self):
        fn_entry: dict[tuple[str, str], Any] = {}
        isr_entry: dict[str, Any] = {G.id: None for G in self.isrs}
        for F in self.flows:
            for fn in self.reach[F.id]:
                pts = self.points.get((F.id, fn))
                if pts is None:
                    continue
                entry = self.fn_entry.get((F.id, fn))
                for b, blk in enumerate(self.prog[fn].blocks):
                    for k in range(len(blk.events) + 1):
                        c = concretise(pts[b][k], entry)
                        if c is None:
                            continue
                        if k < len(blk.events):
                            for callee in blk.events[k].callees:
                                if callee in self.prog:
                                    key = (F.id, callee)
                                    fn_entry[key] = join(fn_entry.get(key), c)
                        # F8: an ISR starts in the state of any point it may fire at.
                        for G in self.direct(F.id, c):
                            isr_entry[G.id] = join(isr_entry[G.id], c)
        if self.cfg.data["masking"]["isr_entry_masks_self"]:
            hw = frozenset({(D, Origin("hardware"))})
            for G in self.isrs:
                if isr_entry[G.id] is not None and G.irq in self.idx:
                    cells = list(isr_entry[G.id])
                    cells[self.idx[G.irq]] = hw
                    isr_entry[G.id] = tuple(cells)
        # The entry function of a flow is reached from the flow's own start, not
        # (only) from call sites; re-assert that after the call-site joins.
        for F in self.flows:
            if F.entry in self.prog:
                start = self.initial if not F.is_isr else isr_entry[F.id]
                fn_entry[(F.id, F.entry)] = join(fn_entry.get((F.id, F.entry)), start)
        return fn_entry, isr_entry

    # -- the fixpoint ----------------------------------------------------

    def run(self) -> "MaskAnalysis":
        for F in self.flows:
            if F.entry in self.prog:
                self.fn_entry[(F.id, F.entry)] = None if F.is_isr else self.initial
        for rnd in range(1, self.MAX_ROUNDS + 1):
            before = (dict(self.summary), dict(self.fn_entry),
                      dict(self.isr_entry), dict(self.effect))
            for F in self.flows:
                for fn in self.reach[F.id]:
                    pts, ex = self._analyse(F.id, fn)
                    self.points[(F.id, fn)] = pts
                    self.summary[(F.id, fn)] = ex
            self.fn_entry, self.isr_entry = self._entries()
            self.effect = {G.id: strip_entry(self.summary.get((G.id, G.entry)))
                           for G in self.isrs}
            if (self.summary, self.fn_entry, self.isr_entry, self.effect) == before:
                self.rounds = rnd
                break
        else:
            raise MaskAnalysisError(
                f"masking analysis did not converge in {self.MAX_ROUNDS} rounds; "
                "refusing to use an intermediate iterate, which is not sound")
        self._run_local()
        return self

    def _run_local(self) -> None:
        """The same analysis with interference switched off.

        Used only to *explain*: an interrupt masked here but not in the real
        analysis was re-enabled by another flow, and the context record names
        it (``reenabled_within_interval_by``). Never used to decide anything --
        it is precisely the unsound view the real analysis exists to replace.
        """
        for _ in range(self.MAX_ROUNDS):
            before = dict(self.local_summary)
            for F in self.flows:
                for fn in self.reach[F.id]:
                    pts, ex = self._analyse(F.id, fn, local=True)
                    self.local_points[(F.id, fn)] = pts
                    self.local_summary[(F.id, fn)] = ex
            if self.local_summary == before:
                return
        raise MaskAnalysisError("local masking view did not converge")

    # -- queries ---------------------------------------------------------

    def state(self, flow: str, point: Point, *, local: bool = False):
        """The concrete state at a point of ``flow``; ``None`` if unreachable."""
        fn, b, k = point
        table = self.local_points if local else self.points
        pts = table.get((flow, fn))
        if pts is None:
            return None
        return concretise(pts[b][k], self.fn_entry.get((flow, fn)))

    def symbolic_points(self, flow: str) -> Iterable[tuple[Point, Any]]:
        for fn in self.reach[flow]:
            pts = self.points.get((flow, fn))
            if pts is None:
                continue
            for b, row in enumerate(pts):
                for k, s in enumerate(row):
                    yield (fn, b, k), s

    def all_points(self, flow: str) -> Iterable[tuple[Point, Any]]:
        for p, _ in self.symbolic_points(flow):
            yield p, self.state(flow, p)

    def describe_state(self, c) -> dict[str, Any] | None:
        """JSON-able form of a concrete state, origins included."""
        if c is None:
            return None
        return {
            str(n): sorted(
                ({"value": v, "origin": o.describe()} for v, o in c[i]),
                key=lambda x: (x["value"], x["origin"]))
            for n, i in self.idx.items()
        }
