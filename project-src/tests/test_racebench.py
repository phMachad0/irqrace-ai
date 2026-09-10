"""The 31 Racebench configurations are generated, not hand-maintained.

The generator reads the suite's own README table, which is the primary source
for the priority convention. These tests check the generated configurations
against the *source files*, because the README is not always right — see
``ENTRY_OVERRIDES``.
"""
import re

import pytest
from conftest import BENCH_CONFIGS, SUITE

from irqrace.config import Config
from irqrace.racebench import ENTRY_OVERRIDES, config_for, parse_readme

pytestmark = pytest.mark.skipif(
    not (SUITE / "README.md").exists(), reason="racebench suite not present"
)


def rows():
    return parse_readme(SUITE / "README.md")


def test_readme_yields_31_simple_cases():
    assert len(rows()) == 31


def test_every_case_has_at_least_one_isr():
    for r in rows():
        assert r["isrs"], r["name"]


def test_irq_number_equals_priority_in_this_suite():
    """The suite sets priority = interrupt number throughout, and states that
    larger means higher. Both halves matter; if the table ever disagreed with
    itself the generator would be encoding a guess."""
    for r in rows():
        for isr in r["isrs"]:
            assert isr["irq"] == isr["priority"], (r["name"], isr)


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["name"])
def test_generated_config_matches_the_source_file(row):
    """Every configured entry point must actually be defined in the C file.

    This is the recall-critical check: a flow whose entry point does not exist
    contributes no accesses, and the loss is invisible in the output.
    """
    cfg = Config.from_dict(config_for(row, SUITE))
    text = (SUITE / row["case"] / row["file"]).read_text()
    for flow in cfg.flows:
        assert re.search(rf"\b{re.escape(flow.entry)}\s*\(", text), (
            f"{row['name']}: configured entry {flow.entry!r} is not defined in the source"
        )


def test_readme_names_two_main_entry_points_wrongly():
    """Regression guard for the finding that produced ``ENTRY_OVERRIDES``.

    The README says ``svp_simple_028_001_main``; the file defines
    ``svp_simple_028_001__main``, with two underscores. If a future revision of
    the suite fixes the table, this test fails and the override should be
    deleted rather than left to mask the change.
    """
    for name, real in ENTRY_OVERRIDES.items():
        row = next(r for r in rows() if r["name"] == name)
        case_dir = row["case"]
        text = (SUITE / case_dir / row["file"]).read_text()
        assert row["main"] != real, f"README now agrees; drop the override for {name}"
        assert not re.search(rf"\b{re.escape(row['main'])}\s*\(", text)
        assert re.search(rf"\b{re.escape(real)}\s*\(", text)


def test_generated_configs_on_disk_are_current():
    """`bench/configs/` is checked in; it must match what the generator produces."""
    import yaml

    for row in rows():
        path = BENCH_CONFIGS / f"{row['name']}.yaml"
        assert path.exists(), f"missing {path}; run `irqrace bench gen-configs`"
        assert yaml.safe_load(path.read_text()) == config_for(row, SUITE), (
            f"{path} is stale; run `irqrace bench gen-configs`"
        )
