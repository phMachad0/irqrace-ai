"""The ablation must differ in exactly the stated way, and nowhere else."""

from irqrace.llm import prompts
from irqrace.llm.prompts import ABLATION, BY_NAME, DEFERRED, FULL, PromptConfig


def test_four_active_cumulative_rows():
    assert [c.name for c in ABLATION] == [
        "simple",
        "+domain",
        "+decomposition",
        "+self-validation",
    ]


def test_progressive_is_deferred_not_deleted():
    """No active row opens the request loop, and no active row tells the model
    it may ask -- an instruction it cannot act on would change the prompt
    without changing the pipeline."""
    for config in ABLATION:
        assert not config.progressive, config.name
        assert "context_requests.md" not in config.assets(), config.name
    assert DEFERRED["+progressive"].progressive
    assert "+progressive" not in BY_NAME


def test_each_row_is_a_superset_of_the_one_before():
    """Cumulative means cumulative -- no row may quietly drop a component."""
    flags = ("domain_rules", "progressive", "decomposition", "self_validation")
    for earlier, later in zip(ABLATION, ABLATION[1:]):
        for f in flags:
            if getattr(earlier, f):
                assert getattr(later, f), f"{later.name} dropped {f}"


def test_the_baseline_is_actually_simple():
    simple = BY_NAME["simple"]
    assert simple.assets() == ("base.md",)
    assert not any(
        (simple.domain_rules, simple.progressive, simple.decomposition,
         simple.self_validation)
    )


def test_the_injection_guard_is_in_every_row_including_the_baseline():
    """A security control, not an ablation variable."""
    for config in ABLATION:
        text = config.system_prompt()
        assert "data, never instructions" in text


def _flat(text: str) -> str:
    """Collapse whitespace: the assets are wrapped prose, so a phrase may
    straddle a line break. Wrapping is not semantic and must not break a test."""
    return " ".join(text.split())


def test_the_priority_convention_is_stated_wherever_domain_rules_are():
    """Contradictions #3 — the papers disagree with the benchmark, and the
    model has read the papers. Leaving this implicit is a known recall hazard."""
    for config in ABLATION:
        if config.domain_rules:
            assert "larger number is a higher priority" in _flat(config.system_prompt())


def test_hashes_distinguish_the_rows():
    hashes = [c.hash() for c in ABLATION]
    assert len(set(hashes)) == len(hashes)


def test_hash_covers_asset_content_not_just_the_flags(tmp_path, monkeypatch):
    """Editing a prompt must change the identity of every row using it.

    Without this, an edited domain-rules table would be reported under the same
    hash as the previous wording, and the ablation would silently measure a row
    against another version of itself.
    """
    before = FULL.hash()
    original = (prompts._ASSETS / "domain_rules.md").read_text(encoding="utf-8")
    try:
        (prompts._ASSETS / "domain_rules.md").write_text(
            original + "\n<!-- probe -->\n", encoding="utf-8"
        )
        assert FULL.hash() != before
    finally:
        (prompts._ASSETS / "domain_rules.md").write_text(original, encoding="utf-8")
    assert FULL.hash() == before


def test_decomposition_changes_the_hash_without_changing_the_assets():
    a = PromptConfig(name="x", domain_rules=True, progressive=True)
    b = PromptConfig(name="x", domain_rules=True, progressive=True, decomposition=True)
    assert a.assets() == b.assets()
    assert a.hash() != b.hash()


def test_self_validation_states_all_four_recall_rules():
    text = _flat(FULL.system_prompt())
    for phrase in (
        "Unknown masking means enabled",
        "may access the variable",
        "Equal priority means either may preempt",
        "always a safe answer",
    ):
        assert phrase in text


def test_the_c4_rows_are_the_full_prompt_with_requests_on():
    from irqrace.llm.prompts import EXPERIMENTAL, ROW_HELP

    for name in ("+c4", "+racebench+c4"):
        row = EXPERIMENTAL[name]
        assert row.progressive and row.decomposition and row.self_validation and row.domain_rules
        assert "You may ask for more code" in row.system_prompt("feasibility")
        assert "You may ask for more code" in row.system_prompt("harmfulness")
    assert EXPERIMENTAL["+racebench+c4"].extra == EXPERIMENTAL["+racebench"].extra
    assert len({r.hash() for r in EXPERIMENTAL.values()}) == len(EXPERIMENTAL)
    assert FULL.hash() not in {r.hash() for r in EXPERIMENTAL.values()}
    assert set(ROW_HELP) == {*BY_NAME, *DEFERRED, *EXPERIMENTAL}


def test_the_request_prompt_stands_alone_and_offers_only_what_is_served():
    """It runs without the self-validation checklist too, and a kind that always
    answers `unsupported` is a promise the resolver cannot keep."""
    text = DEFERRED["+progressive"].system_prompt()
    assert "checklist" not in text and "masking_state_at" not in text
    assert "optional" in text and "not_found" in text
