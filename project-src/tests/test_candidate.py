"""The fingerprint is Track B's cache key and the run store's join key.

If it ever depends on something that varies between runs, the cache silently
misses and two runs of the same subject stop being comparable.
"""
import copy
import json

from conftest import EXAMPLES

from irqrace.candidate import candidate_id, fingerprint, pattern_of, stamp_identity

BUG = json.loads((EXAMPLES / "c2-bugpoint.json").read_text())


def test_id_is_derived_from_the_fingerprint():
    assert BUG["id"] == candidate_id(BUG["fingerprint"])
    assert fingerprint(BUG) == BUG["fingerprint"]


def test_fingerprint_ignores_run_metadata():
    other = copy.deepcopy(BUG)
    other["emitted_by"] = {"tool_version": "9.9.9", "stage": "stage1",
                           "run_id": "different", "timestamp": "2030-01-01T00:00:00Z"}
    assert fingerprint(other) == fingerprint(BUG)


def test_fingerprint_ignores_later_stage_findings():
    """A candidate is the same candidate before and after stage 2 and the solver.
    Otherwise the stage1 -> stage2 -> solver -> context join breaks."""
    other = copy.deepcopy(BUG)
    other.pop("masking")
    other.pop("preemption")
    other["solver_result"] = {"verdict": "sat"}
    assert fingerprint(other) == fingerprint(BUG)


def test_fingerprint_ignores_key_order():
    other = json.loads(json.dumps(BUG, sort_keys=True))
    assert fingerprint(other) == fingerprint(BUG)


def test_fingerprint_changes_with_an_access_location():
    other = copy.deepcopy(BUG)
    other["accesses"][0]["source"]["line"] += 1
    assert fingerprint(other) != fingerprint(BUG)


def test_fingerprint_changes_with_the_variable():
    other = copy.deepcopy(BUG)
    other["variable"]["name"] = "something_else"
    assert fingerprint(other) != fingerprint(BUG)


def test_fingerprint_is_insensitive_to_the_order_accesses_are_listed_in():
    """Roles carry the ordering; list order must not."""
    other = copy.deepcopy(BUG)
    other["accesses"] = list(reversed(other["accesses"]))
    assert fingerprint(other) == fingerprint(BUG)


def test_pattern_matches_the_annotation_shape():
    assert pattern_of(BUG) == "WRW" == BUG["pattern"]
    trap = json.loads((EXAMPLES / "c2-trap.json").read_text())
    assert pattern_of(trap) == "WRW"


def test_stamp_identity_is_idempotent():
    other = copy.deepcopy(BUG)
    stamp_identity(other)
    stamp_identity(other)
    assert other["id"] == BUG["id"]
