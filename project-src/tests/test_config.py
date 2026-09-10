import copy

import pytest
from conftest import EXAMPLES

from irqrace.config import Config, ConfigError

BASE = {
    "subject": {"name": "t", "sources": ["t.c"]},
    "flows": [
        {"id": "main", "kind": "task", "entry": "t_main", "priority": 0},
        {"id": "isr_1", "kind": "isr", "entry": "t_isr_1", "irq": 1, "priority": 1},
        {"id": "isr_2", "kind": "isr", "entry": "t_isr_2", "irq": 2, "priority": 2},
    ],
    "masking": {"primitives": [{"function": "disable_isr", "effect": "disable"}]},
    "semantics": {},
}


def cfg(**over):
    d = copy.deepcopy(BASE)
    for k, v in over.items():
        d[k] = v
    return Config.from_dict(d)


def test_defaults_are_applied():
    c = cfg()
    assert c.build["flags"] == ["-g", "-O0", "-Xclang", "-disable-O0-optnone"]
    assert c.semantics["isr_arrival"] == "unbounded"
    assert c.semantics["equal_priority_preemption"] is True
    assert c.analysis["alias"] == "may"
    assert c.data["externals"]["default"] == "may-read-write-reachable"
    assert c.masking_primitives[0].irq_arg == 0
    assert c.masking_primitives[0].all_value == -1


def test_priority_convention_is_larger_is_higher():
    """Getting this backwards drops exactly the real preemptions and reports
    exactly the impossible ones (Contradictions #3), so it is pinned by a test."""
    c = cfg()
    main, isr1, isr2 = c.flows
    assert c.can_preempt(isr1, main) is True
    assert c.can_preempt(isr2, isr1) is True
    assert c.can_preempt(isr1, isr2) is False
    assert c.can_preempt(main, isr1) is False


def test_equal_priority_defaults_to_preemptible():
    flows = copy.deepcopy(BASE["flows"])
    flows[2]["priority"] = 1  # two ISRs sharing priority 1, as in svp_real_002
    c = cfg(flows=flows)
    a, b = c.flows[1], c.flows[2]
    assert c.can_preempt(a, b) is True
    assert any("share priority 1" in n for n in c.notes)

    strict = Config.from_dict({**copy.deepcopy(BASE), "flows": flows,
                               "semantics": {"equal_priority_preemption": False}})
    assert strict.can_preempt(strict.flows[1], strict.flows[2]) is False


def test_reentrancy_is_off_by_default():
    c = cfg()
    assert c.can_preempt(c.flows[1], c.flows[1]) is False


def test_isr_without_irq_is_rejected():
    flows = [BASE["flows"][0], {"id": "isr_1", "kind": "isr", "entry": "x", "priority": 1}]
    with pytest.raises(ConfigError, match="no irq number"):
        cfg(flows=flows)


def test_duplicate_irq_is_rejected():
    flows = copy.deepcopy(BASE["flows"])
    flows[2]["irq"] = 1
    with pytest.raises(ConfigError, match="share interrupt number"):
        cfg(flows=flows)


def test_duplicate_entry_function_is_rejected():
    flows = copy.deepcopy(BASE["flows"])
    flows[2]["entry"] = flows[1]["entry"]
    with pytest.raises(ConfigError, match="share entry function"):
        cfg(flows=flows)


def test_a_task_is_required():
    flows = [f for f in copy.deepcopy(BASE["flows"]) if f["kind"] != "task"]
    with pytest.raises(ConfigError, match="no flow of kind 'task'"):
        cfg(flows=flows)


def test_unsound_externals_setting_is_flagged():
    c = Config.from_dict({**copy.deepcopy(BASE), "externals": {"default": "none"}})
    assert any("UNSOUND" in n for n in c.notes)


def test_all_irqs_expands_the_all_value():
    assert cfg().all_irqs == [1, 2]


def test_hash_is_stable_and_ignores_run_id():
    a = cfg()
    b = Config.from_dict({**copy.deepcopy(BASE), "output": {"run_id": "whatever"}})
    assert a.hash() == b.hash()


def test_hash_changes_when_semantics_change():
    a = cfg()
    b = Config.from_dict({**copy.deepcopy(BASE),
                          "semantics": {"equal_priority_preemption": False}})
    assert a.hash() != b.hash()


def test_example_config_loads():
    c = Config.load(EXAMPLES / "c1-svp_simple_001_001.yaml")
    assert c.name == "svp_simple_001_001"
    assert [f.id for f in c.flows] == ["main", "isr_1", "isr_2"]
    assert c.all_irqs == [1, 2]
