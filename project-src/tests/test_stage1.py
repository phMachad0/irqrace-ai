"""Stage 1 end to end: the access set, the derivation, and the recall gate.

The gate is the project's central claim made checkable. These tests also pin the
three findings the gate itself produced, so that a regression shows up as a
failing test naming the cause rather than as a number quietly dropping.
"""
import pytest
from conftest import BENCH_CONFIGS, ERRATA, SUITE

from irqrace.build import build
from irqrace.config import Config
from irqrace.evaluation import match_subject
from irqrace.groundtruth import load_suite
from irqrace.stage1 import UNSERIALIZABLE, derive_candidates
from irqrace.stage1_driver import STAGE1_PATH, run_stage1
from irqrace.toolchain import detect

TC = detect()
pytestmark = [
    pytest.mark.skipif(not TC.ok or not STAGE1_PATH.exists(),
                       reason="analysis binaries not built"),
    pytest.mark.skipif(not (SUITE / "README.md").exists(), reason="racebench not present"),
]

CONFIGS = sorted(BENCH_CONFIGS.glob("*.yaml"))


def analyse(name, tmp_path):
    cfg = Config.load(BENCH_CONFIGS / f"{name}.yaml")
    result = build(cfg, tmp_path / "build")
    return cfg, run_stage1(result.bitcode, cfg)


# -- the access set ---------------------------------------------------------


def test_the_four_unserializable_shapes_are_the_standard_ones():
    """A1 and A2 in one flow, B in another. Exactly these four interleavings
    change the outcome; (R,R,*), (W,R,R) and (W,W,W) are serializable."""
    assert UNSERIALIZABLE == {
        ("read", "write", "read"), ("read", "write", "write"),
        ("write", "write", "read"), ("write", "read", "write"),
    }
    assert ("write", "write", "write") not in UNSERIALIZABLE


def test_same_statement_may_precede_itself_inside_a_loop(tmp_path):
    """`svp_simple_001_001` writes the array in a loop at line 32, so that one
    statement is both A1 and A2 (Soundness Assumptions G2)."""
    _, a = analyse("svp_simple_001_001", tmp_path)
    array = next(o["id"] for o in a["objects"] if o["name"].endswith("global_array"))
    at32 = [x for x in a["accesses"]
            if x["source"]["line"] == 32 and x["object"] == array]
    assert at32 and all(x["in_loop"] for x in at32)
    pairs = {tuple(p) for p in a["may_precede"]}
    assert any((x["id"], x["id"]) in pairs for x in at32)


def test_objects_only_one_flow_reaches_are_dropped(tmp_path):
    """They cannot form a candidate of either class, so keeping them is noise --
    and once stack objects are in scope that noise is every loop counter."""
    _, a = analyse("svp_simple_001_001", tmp_path)
    assert a["objects"]
    for o in a["objects"]:
        assert len(o["flows"]) >= 2, o


def test_mutually_exclusive_branches_do_not_precede_each_other(tmp_path):
    """The two arms of the if/else in `svp_simple_001_001_isr_2` read the array
    at lines 55 and 58. Neither can follow the other in one execution, and the
    CFG proves it -- so no triple is generated from them. That is generation,
    not filtering."""
    _, a = analyse("svp_simple_001_001", tmp_path)
    ids = {x["source"]["line"]: x["id"] for x in a["accesses"] if x["flow"] == "isr_2"}
    pairs = {tuple(p) for p in a["may_precede"]}
    assert (ids[55], ids[58]) not in pairs
    assert (ids[58], ids[55]) not in pairs


def test_a_stack_object_shared_through_a_global_pointer_is_found(tmp_path):
    """`svp_simple_009_001` shares a STACK variable between its task and its ISR
    by storing its address into two global pointers, and its annotated bug point
    is a triple on that object. Restricting stage 1 to module-level globals loses
    it silently; the recall gate is what caught that."""
    cfg, a = analyse("svp_simple_009_001", tmp_path)
    cands = derive_candidates(a, cfg)
    gt = load_suite(SUITE, ERRATA)
    rep = match_subject(gt.by_case("svp_simple_009_001").bugs, cands,
                        subject="svp_simple_009_001")
    assert rep.bugs_detected == 1, "the stack-shared bug point is missing again"


def test_a_function_called_twice_makes_one_instruction_two_accesses(tmp_path):
    """`svp_simple_029_001` calls `GetTmData` twice in a row, so its single
    `return tm_blocks[tm_name];` is two dynamic accesses. Intra-procedural CFG
    reachability alone says the instruction cannot precede itself."""
    _, a = analyse("svp_simple_029_001", tmp_path)
    inner = [x for x in a["accesses"]
             if x["function"] == "svp_simple_029_001_GetTmData" and x["flow"] == "main"]
    assert inner
    pairs = {tuple(p) for p in a["may_precede"]}
    assert any((x["id"], x["id"]) in pairs for x in inner)


def test_prologue_argument_spills_are_not_accesses(tmp_path):
    """At -O0 clang spills parameters into allocas with no DebugLoc. They have no
    source-level existence and must not become candidates."""
    _, a = analyse("svp_simple_029_001", tmp_path)
    assert all(x["source"]["line"] >= 1 for x in a["accesses"])


def test_every_access_has_a_usable_source_range(tmp_path):
    """Every candidate must map back to a source range (Soundness Assumptions A2).
    Where a DebugLoc is missing the range is recovered and marked, never dropped."""
    for name in ("svp_simple_001_001", "svp_simple_022_001", "svp_simple_031_001"):
        _, a = analyse(name, tmp_path / name)
        for x in a["accesses"]:
            assert x["source"]["line"] >= 1, (name, x)


# -- derivation -------------------------------------------------------------


def test_stage1_never_records_a_drop(tmp_path):
    """Stage 1 is the generator. Only a proof may discard, and only downstream."""
    cfg, a = analyse("svp_simple_001_001", tmp_path)
    cands = derive_candidates(a, cfg)
    assert all(c["solver_result"]["verdict"] == "not_run" for c in cands)
    assert all(c["emitted_by"]["stage"] == "stage1" for c in cands)


def test_candidate_ids_are_unique_and_content_addressed(tmp_path):
    from irqrace.candidate import fingerprint

    cfg, a = analyse("svp_simple_022_001", tmp_path)
    cands = derive_candidates(a, cfg)
    assert len({c["id"] for c in cands}) == len(cands)
    for c in cands:
        assert fingerprint(c) == c["fingerprint"]


def test_pairs_and_triples_are_derived_from_one_access_set(tmp_path):
    """Both classes come from the same accesses; neither is built from the other
    ([[Pair-Triple Unification]])."""
    cfg, a = analyse("svp_simple_001_001", tmp_path)
    cands = derive_candidates(a, cfg)
    triples = [c for c in cands if c["class"] == "atomicity-triple"]
    pairs = [c for c in cands if c["class"] == "race-pair"]
    assert triples and pairs
    assert all(len(c["accesses"]) == 3 for c in triples)
    assert all(len(c["accesses"]) == 2 for c in pairs)
    # Every pair has at least one write; a read/read pair is not a race.
    for c in pairs:
        assert any(x["kind"] == "write" for x in c["accesses"])
    for c in triples:
        shape = tuple(x["kind"] for x in sorted(
            c["accesses"], key=lambda x: {"A1": 0, "B": 1, "A2": 2}[x["role"]]))
        assert shape in UNSERIALIZABLE


def test_a_triple_spans_exactly_two_flows(tmp_path):
    cfg, a = analyse("svp_simple_001_001", tmp_path)
    for c in derive_candidates(a, cfg):
        if c["class"] != "atomicity-triple":
            continue
        by_role = {x["role"]: x["flow"] for x in c["accesses"]}
        assert by_role["A1"] == by_role["A2"] != by_role["B"]


def test_records_conform_to_c2(tmp_path):
    from irqrace import contracts

    cfg, a = analyse("svp_simple_019_001", tmp_path)
    for c in derive_candidates(a, cfg):
        contracts.validate("c2", c, what=c["id"])
