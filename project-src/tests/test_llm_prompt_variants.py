"""The T3 prompt variants: each is ``+racebench`` with exactly one change.

``wiki/Lucas Tasks.md`` (T3) compares prompts by how each one changes the
result. A difference between two rows has one cause only if the rows differ in
one asset or one flag, and only if the baselines they are compared against are
still the prompts that were measured. Both are checked here.
"""

import dataclasses
import re

import pytest

from irqrace.cli import main
from irqrace.llm import prompts
from irqrace.llm.prompts import BY_NAME, DEFERRED, EXPERIMENTAL, ROW_HELP, STAGES, PromptConfig

#: The two baselines' identities at commit 2063144, the state that T3's first
#: comparison measures. A change here means a baseline prompt changed -- an
#: edited asset, a reordered row -- and every number reported under the old
#: hash then belongs to another prompt. Update only together with a new run.
BASELINE_HASHES = {
    "+racebench": "acd08354c0bc7f0d",
    "+racebench+c4": "90a18ccc93f98b59",
}

BASE = EXPERIMENTAL["+racebench"]

#: Each variant, and what it does to ``+racebench``'s assets, per question:
#: ``(added, removed)``. Nothing else may differ.
VARIANTS = {
    "+racebench-selfval": {
        "feasibility": ((), ("self_validation.md",)),
        "harmfulness": ((), ("harm_validation.md",)),
    },
    "+racebench+witness": {
        "feasibility": (("racebench_witness.md",), ()),
        "harmfulness": ((), ()),
    },
    "+racebench+location": {
        "feasibility": (("racebench_location.md",), ()),
        "harmfulness": ((), ()),
    },
    "+racebench+effectfree": {
        "feasibility": ((), ()),
        "harmfulness": (("racebench_effectfree.md",), ()),
    },
    "+racebench+rubric": {
        "feasibility": (("racebench_rubric.md",), ()),
        "harmfulness": (("racebench_rubric.md",), ()),
    },
}

NEW_ASSETS = (
    "racebench_witness.md",
    "racebench_location.md",
    "racebench_effectfree.md",
    "racebench_rubric.md",
)


def test_the_baselines_are_the_measured_prompts():
    for name, expected in BASELINE_HASHES.items():
        assert EXPERIMENTAL[name].hash() == expected, name


def test_every_variant_is_selectable_by_name_and_described():
    from irqrace.ui.benchmark_screen import BENCH_PROMPTS, DEFAULT_PROMPT

    every_row = {**BY_NAME, **DEFERRED, **EXPERIMENTAL}
    for name in VARIANTS:
        assert every_row[name].name == name
        assert ROW_HELP[name].strip()
        assert name in BENCH_PROMPTS
    assert BENCH_PROMPTS[:2] == ("+racebench", "+racebench+c4")
    assert DEFAULT_PROMPT == "+racebench+c4"
    assert all(n.isascii() for n in VARIANTS)  # an ASCII hyphen, not a Unicode minus


def test_the_measurement_only_row_says_so():
    assert "não usar" in ROW_HELP["+racebench+effectfree"]


def test_hashes_are_distinct():
    rows = {**BY_NAME, **DEFERRED, **EXPERIMENTAL}
    hashes = [r.hash() for r in rows.values()]
    assert len(set(hashes)) == len(hashes)


@pytest.mark.parametrize("name", VARIANTS)
def test_each_variant_is_the_baseline_with_one_change(name):
    row = EXPERIMENTAL[name]
    for stage in STAGES:
        added, removed = VARIANTS[name][stage]
        expected = tuple(a for a in BASE.assets(stage) if a not in removed) + added
        assert row.assets(stage) == expected, (name, stage)
    # The flags differ only where the variant says so, and nowhere else.
    same = {f.name for f in dataclasses.fields(PromptConfig)} - {"name", "extra", "stage_extra"}
    if name == "+racebench-selfval":
        same -= {"self_validation"}
    for f in same:
        assert getattr(row, f) == getattr(BASE, f), (name, f)


def test_feasibility_add_ons_stay_out_of_the_harmfulness_prompt():
    """A feasibility rule in the harm prompt is a second cause in the comparison."""
    for name, asset in (("+racebench+witness", "Witness:"), ("+racebench+location", "Location:")):
        row = EXPERIMENTAL[name]
        assert asset in row.system_prompt("feasibility")
        assert asset not in row.system_prompt("harmfulness")
        assert row.system_prompt("harmfulness") == BASE.system_prompt("harmfulness")
    eff = EXPERIMENTAL["+racebench+effectfree"]
    assert eff.system_prompt("feasibility") == BASE.system_prompt("feasibility")
    assert "already stored" in eff.system_prompt("harmfulness")


def test_add_ons_come_after_the_benchmark_semantics():
    """An add-on states what it overrides, so it must be read after what it overrides."""
    for name in VARIANTS:
        row = EXPERIMENTAL[name]
        for stage in STAGES:
            names = row.assets(stage)
            for asset in NEW_ASSETS:
                if asset in names:
                    assert names.index(asset) > names.index("racebench_semantics.md")


def test_a_stage_scoped_asset_names_a_real_stage():
    with pytest.raises(ValueError):
        PromptConfig(name="x", stage_extra=(("feasability", "racebench_witness.md"),))


#: Things that would tie an asset to the suite rather than to its semantics:
#: case and file names, line references, the suite's own annotation words, and
#: the identifiers its programs use for their flows and variables.
_SUITE_IDENTIFIERS = re.compile(
    r"svp_|racebench|nasac|bug点|误报|common\.[ch]\b|\.c\b|\bline \d|\bL\d+\b|\bisr_\d|"
    r"\bglobal_var\b|\bidlerun\b|\bMAX_LENGTH\b|\breader\d",
    re.IGNORECASE,
)


def test_the_identifier_guard_catches_what_it_is_for():
    for probe in ("svp_simple_007_001", "Racebench", "line 32", "L52", "isr_1", "可能误报", "common.c"):
        assert _SUITE_IDENTIFIERS.search(probe), probe


@pytest.mark.parametrize("asset", [*NEW_ASSETS, "racebench_semantics.md"])
def test_no_asset_names_the_suite(asset):
    text = (prompts._ASSETS / asset).read_text(encoding="utf-8")
    assert not _SUITE_IDENTIFIERS.findall(text), asset


def test_the_cli_lists_the_variants(capsys):
    assert main(["llm", "prompts"]) == 0
    out = capsys.readouterr().out
    for name in VARIANTS:
        assert name in out
        assert EXPERIMENTAL[name].hash() in out


def test_the_cli_prints_a_variant_per_question(capsys):
    assert main(["llm", "prompts", "+racebench+witness"]) == 0
    out = capsys.readouterr().out
    feas, harm = out.split("system prompt for the harmfulness question")
    assert "Witness:" in feas and "Witness:" not in harm
