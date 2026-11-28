"""Stage 2 end to end on Racebench: the recall gate, the proofs, and the cases
that taught the masking analysis what it had to model.

The W5 done-when is the gate still at 48/48 after the first stage that is
allowed to discard anything. The other tests pin, per case, the verdicts that
`docs/masking-semantics.md` and the W5 diary argue for, so that a regression
names its cause instead of moving a number.
"""
import json

import pytest
from conftest import BENCH_CONFIGS, ERRATA, SUITE

from irqrace.build import build
from irqrace.config import Config
from irqrace.evaluation import match_subject
from irqrace.groundtruth import load_suite
from irqrace.runstore import RunStore
from irqrace.stage1_driver import STAGE1_PATH, stage1
from irqrace.stage2 import stage2
from irqrace.toolchain import detect

TC = detect()
pytestmark = [
    pytest.mark.skipif(not TC.ok or not STAGE1_PATH.exists(),
                       reason="analysis binaries not built"),
    pytest.mark.skipif(not (SUITE / "README.md").exists(), reason="racebench not present"),
]

CONFIGS = sorted(BENCH_CONFIGS.glob("*.yaml"))


@pytest.fixture(scope="module")
def ground_truth():
    return load_suite(SUITE, ERRATA)


def through_stage2(name, tmp_path):
    cfg = Config.load(BENCH_CONFIGS / f"{name}.yaml")
    store = RunStore.create(cfg, run_root=tmp_path)
    result = build(cfg, store.root / "build")
    stage1(cfg, store, result.bitcode)
    stage2(cfg, store)
    return store


def by_lines(records, *lines):
    for r in records:
        got = r["lines"] if "lines" in r else [a["source"]["line"] for a in r["accesses"]]
        if got == list(lines):
            return r
    return None


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.stem)
def test_recall_gate_holds_after_stage2(path, tmp_path, ground_truth):
    """W5 done-when: every annotated bug point survives the first filter."""
    store = through_stage2(path.stem, tmp_path)
    rep = match_subject(ground_truth.by_case(path.stem).all,
                        store.read_candidates("stage2"), subject=path.stem)
    assert rep.bugs_detected == len(rep.bug_matches), [
        (a.kind, a.index, a.lines) for a in rep.missed]
    assert store.check() == []  # C3 rule 6: nothing vanished without a proof


def test_every_drop_is_a_proof_naming_its_assumptions(tmp_path):
    store = through_stage2("svp_simple_026_001", tmp_path)
    drops = store.read_drops()
    assert drops
    for d in drops:
        assert d["proof"] and d["relies_on"] and "H1d" in d["relies_on"]
    s1 = {c["id"] for c in store.read_candidates("stage1")}
    s2 = {c["id"] for c in store.read_candidates("stage2")}
    assert s1 == s2 | {d["candidate_id"] for d in drops}
    manifest = store.read_manifest()
    st = next(s for s in manifest["stages"] if s["name"] == "stage2")
    assert st["dropped_with_proof"] == len(drops) and st["candidates_in"] == len(s1)


def test_001_bug_point_survives_because_isr_1_reopens_the_section(tmp_path):
    """docs/masking-semantics.md: main masks irq 2 across [32, 35], isr_1 may run
    inside and call enable_isr(2). Computed from main's CFG alone, this
    annotated bug point would be dropped on case 1 of 31."""
    store = through_stage2("svp_simple_001_001", tmp_path)
    rec = by_lines(store.read_candidates("stage2"), 32, 55, 35)
    assert rec is not None
    interval = rec["masking"]["interval"]
    assert interval["reenabled_within_interval_by"] == ["isr_1"]
    assert 2 not in interval["disabled_throughout"]
    assert rec["preemption"]["preempting_flow"] == "isr_2"


def test_001_trap_survives_because_its_label_assumes_an_entry_state(tmp_path):
    """The W5 finding. Racebench labels <W#43><R#63><W#44> a false positive on
    the reasoning that irq 2 stays masked until line 46. Under the suite's own
    README -- interrupts fire whenever enabled, any number of times -- isr_1 may
    start with irq 2 unmasked, two ways: before main's disable_isr(2), and after
    an earlier activation of itself. A sound stage 2 must keep it."""
    store = through_stage2("svp_simple_001_001", tmp_path)
    rec = by_lines(store.read_candidates("stage2"), 43, 64, 44)
    assert rec is not None
    note = next(e["note"] for e in rec["provenance"]["entries"]
                if e["fact"] == "masking.interval")
    assert "F8" in note and "line 46" in note


def test_003_trap_is_rejected_by_masking(tmp_path):
    """global_var2 <R#38>,<W#62>,<R#43>: both reads under disable_isr(1), and the
    only flow that could unmask irq 1 cannot run there. A planted trap stage 2
    rejects with a proof."""
    store = through_stage2("svp_simple_003_001", tmp_path)
    d = by_lines(store.read_drops(), 38, 62, 43)
    assert d is not None and d["reason"] == "masking"
    assert "disable_isr(1) at line 33" in d["proof"]


def test_026_trap_rejected_and_bug_point_kept(tmp_path):
    """Same critical section, two ISRs: isr_1's write is masked out of
    [26, 27], isr_2's is not."""
    store = through_stage2("svp_simple_026_001", tmp_path)
    assert by_lines(store.read_drops(), 26, 40, 27)["reason"] == "masking"
    assert by_lines(store.read_candidates("stage2"), 26, 43, 27) is not None


def test_029_exclusive_call_sites_are_not_a_repetition(tmp_path):
    """Stage 1 counts two call sites of SetTmData in isr_1 as two invocations
    (G2b). They are the two arms of an if/else, so one activation cannot run
    line 83 twice; the flow's supergraph proves it and the triple goes."""
    store = through_stage2("svp_simple_029_001", tmp_path)
    d = by_lines(store.read_drops(), 83, 80, 83)
    assert d is not None and d["reason"] == "no-path"


def test_stage2_records_are_c2_and_keep_their_ids(tmp_path):
    store = through_stage2("svp_simple_019_001", tmp_path)
    s1 = {c["id"]: c for c in store.read_candidates("stage1")}
    for rec in store.read_candidates("stage2"):
        assert rec["fingerprint"] == s1[rec["id"]]["fingerprint"]
        assert rec["emitted_by"]["stage"] == "stage2"
        assert "preemption" in rec and "masking" in rec
        assert rec["class"] == "atomicity-triple" and "interval" in rec["masking"]
    report = json.loads((store.root / "stage2" / "masking.json").read_text())
    assert report["rounds"] >= 1 and set(report["flows"]) == {"main", "isr_1"}


def test_runstore_check_catches_a_silent_stage2_drop(tmp_path):
    """C3 rule 6 is enforced, not described: delete one drop proof and the run
    no longer conforms."""
    store = through_stage2("svp_simple_001_001", tmp_path)
    path = store.root / "stage2" / "dropped.jsonl"
    lines = path.read_text().splitlines()
    assert lines
    path.write_text("\n".join(lines[1:]) + ("\n" if lines[1:] else ""))
    problems = store.check()
    assert any("vanished without a proof" in p for p in problems)


@pytest.mark.parametrize("name,lines", [
    ("svp_simple_027_001", (27, 48, 28)),
    ("svp_simple_028_001", (29, 53, 30)),
    ("svp_simple_030_001", (29, 56, 30)),
])
def test_isr_3_traps_are_rejected_from_the_state_their_nesting_starts_in(name, lines, tmp_path):
    """irq 3 is masked by disable_isr(-1) and nothing that may run inside the
    interval unmasks it. Rejected only because nested activations are judged
    from the state they fire in, not from the ISR's global entry state."""
    store = through_stage2(name, tmp_path)
    d = by_lines(store.read_drops(), *lines)
    assert d is not None and d["reason"] == "masking" and "F4" in d["relies_on"]
