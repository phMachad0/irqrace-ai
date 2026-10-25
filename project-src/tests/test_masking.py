"""Stage 2 on hand-built programs: one test per rule the masking analysis obeys.

The programs are written directly in the event-CFG shape `irqrace-stage1` emits
(`stage1/accesses.json`, key `program`), so each soundness rule can be pinned in
isolation without compiling C. The Racebench cases that motivated the rules are
named in the docstrings; `test_stage2.py` checks the real ones.
"""
import pytest

from irqrace.candidate import stamp_identity
from irqrace.config import Config
from irqrace.masking import MaskAnalysis, MaskAnalysisError, load_program, masked, origins
from irqrace.stage2 import Stage2

# -- a tiny DSL for event CFGs ---------------------------------------------


def acc(line, kind="write"):
    return {"k": "access", "line": line, "kind": kind}


def call(callee, *args, line=0):
    return {"k": "call", "line": line, "callees": [callee] if callee else [],
            "resolution": "direct" if callee else "unresolved", "args": list(args)}


def dis(n, line=0):
    return call("disable_isr", n, line=line)


def en(n, line=0):
    return call("enable_isr", n, line=line)


def block(*events, succ=(), exit=False):
    return {"succ": list(succ), "exit": exit, "events": list(events)}


def fn(name, *blocks):
    return {"name": name, "file": "t.c", "blocks": list(blocks)}


def straight(name, *events):
    return fn(name, block(*events, exit=True))


FLOWS = {
    "main": {"id": "main", "kind": "task", "entry": "main", "priority": 0},
    "isr_1": {"id": "isr_1", "kind": "isr", "entry": "isr_1", "irq": 1, "priority": 1},
    "isr_2": {"id": "isr_2", "kind": "isr", "entry": "isr_2", "irq": 2, "priority": 2},
}


def config(*flows, initial="all-enabled", models=(), primitives=None, **semantics):
    return Config.from_dict({
        "subject": {"name": "t", "sources": ["t.c"]},
        "flows": [dict(FLOWS[f]) if isinstance(f, str) else f for f in flows],
        "masking": {
            "primitives": primitives or [
                {"function": "disable_isr", "effect": "disable"},
                {"function": "enable_isr", "effect": "enable"}],
            "initial_state": initial,
        },
        "semantics": semantics,
        "externals": {"models": [{"function": m, "effect": "none"} for m in models]},
    })


def analysis_of(cfg, *fns):
    """Wrap functions as stage1/accesses.json: one access per (flow, access event)."""
    by_name = {f["name"]: f for f in fns}
    accesses = []
    for flow in cfg.flows:
        seen, work = [], [flow.entry]
        while work:
            name = work.pop()
            if name in seen or name not in by_name:
                continue
            seen.append(name)
            for blk in by_name[name]["blocks"]:
                for e in blk["events"]:
                    work.extend(e.get("callees", []))
        for name in seen:
            for b, blk in enumerate(by_name[name]["blocks"]):
                for k, e in enumerate(blk["events"]):
                    if e["k"] == "access":
                        accesses.append({
                            "id": len(accesses), "flow": flow.id, "function": name,
                            "kind": e["kind"], "object": 1,
                            "point": {"block": b, "event": k},
                            "source": {"file": "t.c", "line": e["line"], "column": 0}})
    return {"program": {"functions": list(fns)}, "accesses": accesses}


def run(cfg, *fns):
    a = analysis_of(cfg, *fns)
    return MaskAnalysis(load_program(a), cfg).run(), a


def state_at(m, flow, line, *, local=False):
    for fn_name in m.reach[flow]:
        for b, blk in enumerate(m.prog[fn_name].blocks):
            for k, ev in enumerate(blk.events):
                if ev.kind == "access" and ev.line == line:
                    return m.state(flow, (fn_name, b, k), local=local)
    raise AssertionError(f"no access at line {line} in {flow}")


def is_masked(m, c, n):
    return masked(c[m.idx[n]])


def candidate(a, *specs):
    """A minimal C2 record over the accesses at (flow, line), in role order A1, B, A2."""
    assert len(specs) == 3
    out = []
    for role, (flow, line) in zip(("A1", "B", "A2"), specs):
        x = next(x for x in a["accesses"] if x["flow"] == flow and x["source"]["line"] == line)
        out.append({"role": role, "kind": x["kind"], "flow": flow, "function": x["function"],
                    "source": {"file": "t.c", "line": line}, "ir": {"access": x["id"]}})
    rec = {
        "schema_version": "c2/2.0.0", "id": "", "fingerprint": "0" * 64,
        "class": "atomicity-triple",
        "pattern": "".join("R" if o["kind"] == "read" else "W" for o in out),
        "subject": {"name": "t"}, "variable": {"name": "v", "declared_type": "int"},
        "accesses": out, "flows": [], "provenance": {"entries": []},
        "static_features": {},
    }
    return stamp_identity(rec)


def judge(cfg, fns, *specs):
    a = analysis_of(cfg, *fns)
    return Stage2(a, cfg).judge(candidate(a, *specs))


#: The shape of svp_simple_001_001: main masks irq 2, isr_1 unmasks it.
SHAPE_001 = (
    straight("init", en(-1, line=25)),
    straight("main", call("init", line=26), dis(2, line=28), acc(32), acc(35)),
    straight("isr_1", acc(43), acc(44), en(2, line=46)),
    straight("isr_2", acc(55, "read"), acc(64, "read")),
)


# -- the masking analysis ---------------------------------------------------


def test_another_flows_enable_breaks_a_local_masking_proof():
    """docs/masking-semantics.md, the bug point of svp_simple_001_001. Main masks
    irq 2 and never unmasks it, so its own CFG says irq 2 is masked across
    [32, 35]. isr_1 may preempt that interval and calls enable_isr(2), and the
    mask is shared hardware state: the proof is not one (F2, F7)."""
    m, _ = run(config("main", "isr_1", "isr_2"), *SHAPE_001)
    assert is_masked(m, state_at(m, "main", 32, local=True), 2)
    sound = state_at(m, "main", 32)
    assert not is_masked(m, sound, 2)
    assert any(o.line == 46 for o in origins(sound[m.idx[2]], "E"))


def test_an_isr_starts_in_the_union_of_every_state_it_may_preempt():
    """The trap of svp_simple_001_001, read soundly. isr_1 writes at 43 and 44
    before it unmasks irq 2 -- but isr_1 itself may fire before main's
    disable_isr(2), straight after init() enabled everything. Its entry state
    is the union over all its firing points, so irq 2 is not masked there (F8)."""
    m, _ = run(config("main", "isr_1", "isr_2"), *SHAPE_001)
    c = state_at(m, "isr_1", 43)
    assert not is_masked(m, c, 2)
    texts = {o.text for o in origins(c[m.idx[2]], "E")}
    assert "enable_isr(-1)" in texts or any("initial" in t for t in texts)


def test_an_earlier_activation_can_leave_the_next_one_unmasked():
    """The second route to the same trap. Even when main provably masks irq 2
    before isr_1 can ever fire, isr_1 may fire twice (E4): its first activation
    leaves irq 2 unmasked -- enable_isr(2) at line 46 persists (F7) -- and its
    second activation's writes at 43 and 44 are then preemptible by isr_2."""
    fns = (
        straight("main", dis(2, line=28), en(1, line=29), acc(32), acc(35)),
        straight("isr_1", acc(43), acc(44), en(2, line=46)),
        straight("isr_2", acc(55, "read")),
    )
    m, _ = run(config("main", "isr_1", "isr_2", initial="all-disabled"), *fns)
    c = state_at(m, "isr_1", 43)
    assert not is_masked(m, c, 2)
    assert {o.line for o in origins(c[m.idx[2]], "E")} == {46}


def test_when_the_program_guarantees_the_isr_starts_masked_the_proof_holds():
    """Close both routes -- interrupts start off, main masks irq 2 before it
    unmasks irq 1, and isr_1 masks irq 2 again before returning -- and isr_1
    genuinely cannot start with irq 2 unmasked. The analysis proves it:
    soundness is not blanket doubt."""
    fns = (
        straight("main", dis(2, line=28), en(1, line=29), acc(32), acc(35)),
        straight("isr_1", acc(43), acc(44), en(2, line=46), dis(2, line=47)),
        straight("isr_2", acc(55, "read")),
    )
    m, _ = run(config("main", "isr_1", "isr_2", initial="all-disabled"), *fns)
    assert is_masked(m, state_at(m, "isr_1", 43), 2)
    # ... while isr_2 can still run nested inside isr_1, between 46 and 47.
    assert "isr_2" in Stage2(analysis_of(config("main", "isr_1", "isr_2",
                                                initial="all-disabled"), *fns),
                             config("main", "isr_1", "isr_2",
                                    initial="all-disabled")).c.nested["isr_1"]


def test_a_critical_section_nobody_can_open_is_masked():
    fns = (straight("main", dis(1, line=9), acc(10), en(1, line=11)),
           straight("isr_1", acc(20, "read")))
    m, _ = run(config("main", "isr_1"), *fns)
    assert is_masked(m, state_at(m, "main", 10), 1)


def test_an_isrs_disable_never_protects_the_flow_it_preempted():
    """Whether the hardware restores the mask on return is platform-specific.
    The union covers both: an ISR's enables may persist, its disables may not
    (F7)."""
    fns = (straight("main", acc(10)),
           straight("isr_1", dis(2, line=20)),
           straight("isr_2", acc(30, "read")))
    m, _ = run(config("main", "isr_1", "isr_2"), *fns)
    assert not is_masked(m, state_at(m, "main", 10), 2)


def test_a_helper_called_inside_and_outside_a_section_does_not_blur_it():
    """Function summaries are applied per call site: `idlerun()` called once
    with irq 1 unmasked and once with it masked must not return "maybe
    unmasked" to both. Svp_simple_001_001 calls idlerun right after disable_isr."""
    fns = (fn("idlerun", block(succ=[0, 1]), block(exit=True)),
           straight("main", call("idlerun"), dis(1, line=9), call("idlerun"),
                    acc(10), en(1)),
           straight("isr_1", acc(20, "read")))
    m, _ = run(config("main", "isr_1"), *fns)
    assert is_masked(m, state_at(m, "main", 10), 1)


def test_an_unmodelled_external_may_unmask_and_a_modelled_one_does_not():
    fns = (straight("main", dis(1), call("vendor_hal"), acc(10)),
           straight("isr_1", acc(20, "read")))
    m, _ = run(config("main", "isr_1"), *fns)
    assert not is_masked(m, state_at(m, "main", 10), 1)  # F6
    m, _ = run(config("main", "isr_1", models=["vendor_hal"]), *fns)
    assert is_masked(m, state_at(m, "main", 10), 1)


def test_inline_assembly_and_unresolved_calls_may_unmask():
    for opaque in ({"k": "asm", "line": 9}, call(None, line=9)):
        fns = (straight("main", dis(1), opaque, acc(10)),
               straight("isr_1", acc(20, "read")))
        m, _ = run(config("main", "isr_1"), *fns)
        assert not is_masked(m, state_at(m, "main", 10), 1)


def test_a_non_constant_disable_never_proves_masking():
    fns = (straight("main", dis(None), acc(10)), straight("isr_1", acc(20, "read")))
    m, _ = run(config("main", "isr_1"), *fns)
    assert not is_masked(m, state_at(m, "main", 10), 1)


def test_disable_minus_one_masks_exactly_the_configured_interrupts():
    fns = (straight("main", dis(-1), acc(10)),
           straight("isr_1", acc(20, "read")), straight("isr_2", acc(30, "read")))
    m, _ = run(config("main", "isr_1", "isr_2"), *fns)
    c = state_at(m, "main", 10)
    assert is_masked(m, c, 1) and is_masked(m, c, 2)  # F4


def test_masked_on_some_paths_is_not_masked():
    """F1: masked only if masked on every path reaching the point."""
    fns = (fn("main",
              block(succ=[1, 2]),
              block(dis(1), succ=[3]),
              block(succ=[3]),
              block(acc(10), exit=True)),
           straight("isr_1", acc(20, "read")))
    m, _ = run(config("main", "isr_1"), *fns)
    assert not is_masked(m, state_at(m, "main", 10), 1)


def test_an_intermediate_iterate_is_never_returned():
    """Kleene iterates from bottom under-approximate until convergence. Hitting
    the round bound must raise, not hand back a partial -- unsound -- answer."""
    cfg = config("main", "isr_1", "isr_2")
    m = MaskAnalysis(load_program(analysis_of(cfg, *SHAPE_001)), cfg)
    m.MAX_ROUNDS = 1
    with pytest.raises(MaskAnalysisError, match="not sound"):
        m.run()


def test_cyclic_preemption_between_equal_priorities_converges():
    """Two ISRs of equal priority may preempt each other (E2). The least fixpoint
    is still reached; neither touches the mask, so neither leaves anything."""
    a = {"id": "isr_a", "kind": "isr", "entry": "isr_a", "irq": 1, "priority": 1}
    b = {"id": "isr_b", "kind": "isr", "entry": "isr_b", "irq": 2, "priority": 1}
    fns = (straight("main", acc(10)), straight("isr_a", acc(20)), straight("isr_b", acc(30)))
    m, _ = run(config("main", a, b), *fns)
    assert m.effect == {"isr_a": tuple(frozenset() for _ in m.irqs),
                        "isr_b": tuple(frozenset() for _ in m.irqs)}


# -- stage 2 decisions --------------------------------------------------------


def test_the_001_bug_point_survives_and_names_who_reopened_the_section():
    v = judge(config("main", "isr_1", "isr_2"), SHAPE_001,
              ("main", 32), ("isr_2", 55), ("main", 35))
    assert v.keep
    assert v.interval["reenabled_within_interval_by"] == ["isr_1"]
    assert 2 not in v.interval["disabled_throughout"]


def test_the_001_trap_survives_because_isr_1_may_start_unmasked():
    """Racebench labels it a planted false positive. Under the suite's own
    arrival model the interleaving is reachable, so a sound stage 2 keeps it."""
    v = judge(config("main", "isr_1", "isr_2"), SHAPE_001,
              ("isr_1", 43), ("isr_2", 64), ("isr_1", 44))
    assert v.keep
    assert "F8" in v.notes[0]["note"]


def test_one_critical_section_covering_the_interval_is_dropped_with_a_proof():
    """The planted-trap shape of the LLM Stage Design pattern table, as in
    svp_simple_003_001: nobody can reopen the section, so B cannot fall inside."""
    fns = (straight("main", dis(1, line=9), acc(10, "read"), acc(12, "read"), en(1)),
           straight("isr_1", acc(20)))
    v = judge(config("main", "isr_1"), fns, ("main", 10), ("isr_1", 20), ("main", 12))
    assert not v.keep and v.reason == "masking"
    assert "line 9" in v.proof
    assert {"F1", "F2", "F7", "F8", "H1d", "G2c"} <= set(v.relies_on)


def test_split_critical_sections_keep_the_triple():
    """Each access sits in its own critical section, and the ISR fits in the
    unprotected gap between them (LLM Stage Design, D#1 pattern table): masked
    at A1 and masked at A2, yet not masked throughout -- the interval property
    decides, and the triple survives."""
    cfg = config("main", "isr_1")
    fns = (straight("main", dis(1), acc(10, "read"), en(1, line=11),
                    dis(1, line=12), acc(13, "read"), en(1)),
           straight("isr_1", acc(20)))
    v = judge(cfg, fns, ("main", 10), ("isr_1", 20), ("main", 13))
    assert 1 in v.per_access["A1"]["disabled"] and 1 in v.per_access["A2"]["disabled"]
    assert v.keep and 1 not in v.interval["disabled_throughout"]


def test_a_lower_priority_flow_cannot_fall_inside_a_higher_ones_interval():
    fns = (straight("main", acc(10)), straight("isr_1", acc(20, "read")),
           straight("isr_2", acc(30, "read"), acc(31, "read")))
    v = judge(config("main", "isr_1", "isr_2"), fns,
              ("isr_2", 30), ("isr_1", 20), ("isr_2", 31))
    assert not v.keep and v.reason == "priority" and "E1" in v.relies_on


def test_without_nesting_nothing_preempts_an_isr():
    fns = (straight("main", acc(9)), straight("isr_1", acc(10, "read"), acc(11, "read")),
           straight("isr_2", acc(20)))
    spec = (("isr_1", 10), ("isr_2", 20), ("isr_1", 11))
    assert judge(config("main", "isr_1", "isr_2"), fns, *spec).keep
    v = judge(config("main", "isr_1", "isr_2", nesting=False), fns, *spec)
    assert not v.keep and v.reason == "priority" and "E5" in v.relies_on


def test_equal_priority_preemption_follows_the_setting():
    a = {"id": "isr_a", "kind": "isr", "entry": "isr_a", "irq": 1, "priority": 1}
    b = {"id": "isr_b", "kind": "isr", "entry": "isr_b", "irq": 2, "priority": 1}
    fns = (straight("main", acc(9)), straight("isr_a", acc(10, "read"), acc(11, "read")),
           straight("isr_b", acc(20)))
    spec = (("isr_a", 10), ("isr_b", 20), ("isr_a", 11))
    assert judge(config("main", a, b), fns, *spec).keep
    v = judge(config("main", a, b, equal_priority_preemption=False), fns, *spec)
    assert not v.keep and "E2" in v.relies_on


def test_a_transient_unmask_inside_a_preempting_isr_counts():
    """main masks irq 2 throughout; isr_1 unmasks it and masks it again before
    returning, so nothing persists -- but isr_2 can run nested inside isr_1 in
    between, while main is still inside its interval."""
    fns = (straight("main", dis(2), acc(10, "read"), acc(11, "read")),
           straight("isr_1", en(2, line=40), dis(2, line=41)),
           straight("isr_2", acc(30)))
    v = judge(config("main", "isr_1", "isr_2"), fns, ("main", 10), ("isr_2", 30), ("main", 11))
    assert v.keep and v.preemption["nesting_depth"] == 2
    assert 2 not in v.interval["disabled_throughout"]


def test_no_path_when_a1_only_runs_after_a2():
    """Stage 1 over-approximates may-precede across functions. The flow's
    supergraph has no path from g's access back to f's, so that triple cannot
    happen in one activation -- and the forward one is kept."""
    cfg = config("main", "isr_1")
    fns = (straight("f", acc(10, "read")), straight("g", acc(20, "read")),
           straight("main", call("f"), call("g")), straight("isr_1", acc(30)))
    back = judge(cfg, fns, ("main", 20), ("isr_1", 30), ("main", 10))
    assert not back.keep and back.reason == "no-path"
    assert judge(cfg, fns, ("main", 10), ("isr_1", 30), ("main", 20)).keep


def test_a_function_called_twice_is_an_interval_from_its_access_to_itself():
    """svp_simple_029_001's GetTmData, called twice in a row: one instruction, two
    dynamic accesses (G2b). Two call sites in exclusive branches are not a
    repetition, and the supergraph knows it."""
    cfg = config("main", "isr_1")
    get = straight("get", acc(80, "read"))
    twice = straight("main", call("get"), call("get"))
    assert judge(cfg, (get, twice, straight("isr_1", acc(30))),
                 ("main", 80), ("isr_1", 30), ("main", 80)).keep
    either = fn("main", block(succ=[1, 2]), block(call("get"), succ=[3]),
                block(call("get"), succ=[3]), block(exit=True))
    v = judge(cfg, (get, either, straight("isr_1", acc(30))),
              ("main", 80), ("isr_1", 30), ("main", 80))
    assert not v.keep and v.reason == "no-path"


def test_stage2_never_changes_a_candidates_identity():
    cfg = config("main", "isr_1", "isr_2")
    a = analysis_of(cfg, *SHAPE_001)
    s2 = Stage2(a, cfg)
    rec = candidate(a, ("main", 32), ("isr_2", 55), ("main", 35))
    rec["provenance"]["entries"] = [{"fact": "masking", "status": "unknown"}]
    rec["emitted_by"] = {"stage": "stage1"}
    out = s2.run([rec]).kept[0]
    assert out["id"] == rec["id"] and out["fingerprint"] == rec["fingerprint"]
    assert out["emitted_by"]["stage"] == "stage2"
    assert all(e["status"] != "unknown" for e in out["provenance"]["entries"]
               if e["fact"].startswith("masking"))


def test_a_nested_activation_starts_in_the_state_where_it_fired():
    """svp_simple_027_001's shape. isr_1 may fire before main's disable_isr(-1),
    so isr_1's *global* entry state has irq 3 unmasked and anything may seem to
    run inside it. But an isr_1 nested inside main's interval [27, 28] started
    inside it, with irq 3 masked, and nothing unmasks irq 3 -- so isr_3 cannot
    fall inside the interval. Deciding nesting from the global entry keeps this
    planted trap; deciding it from the firing state proves it."""
    fns = (straight("init", en(-1, line=25)),
           straight("main", call("init"), dis(-1, line=25), en(1, line=26),
                    acc(27, "read"), acc(28)),
           straight("isr_1", acc(40), en(2, line=41)),
           straight("isr_2", acc(44)),
           straight("isr_3", acc(48)))
    cfg = config("main", "isr_1", "isr_2",
                 {"id": "isr_3", "kind": "isr", "entry": "isr_3", "irq": 3, "priority": 3})
    s2 = Stage2(analysis_of(cfg, *fns), cfg)
    assert "isr_3" in s2.c.nested["isr_1"]  # the global, context-free answer
    v = judge(cfg, fns, ("main", 27), ("isr_3", 48), ("main", 28))
    assert not v.keep and v.reason == "masking" and "F4" in v.relies_on
    assert judge(cfg, fns, ("main", 27), ("isr_1", 40), ("main", 28)).keep
    assert judge(cfg, fns, ("main", 27), ("isr_2", 44), ("main", 28)).keep
