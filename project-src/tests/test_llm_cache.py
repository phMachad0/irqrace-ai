"""The cache key must survive real backend specs."""
import pytest
from irqrace.llm.cache import Cache


@pytest.mark.parametrize(
    "spec",
    [
        "anthropic:claude-opus-5",
        "openai:openai/gpt-oss-120b",   # slash: became a directory on Windows
        "ollama:qwen2.5-coder:32b",     # colon: invalid argument on Windows
    ],
)
def test_a_spec_with_path_characters_round_trips(tmp_path, spec):
    cache = Cache(tmp_path)
    cache.put("f" * 64, "cfg", spec, {"ok": True})
    assert cache.get("f" * 64, "cfg", spec) == {"ok": True}


def test_specs_that_slug_alike_do_not_collide(tmp_path):
    """A collision would serve one model's verdict as another's."""
    cache = Cache(tmp_path)
    cache.put("f" * 64, "cfg", "openai:a/b", {"model": "a/b"})
    cache.put("f" * 64, "cfg", "openai:a-b", {"model": "a-b"})
    assert cache.get("f" * 64, "cfg", "openai:a/b") == {"model": "a/b"}
    assert cache.get("f" * 64, "cfg", "openai:a-b") == {"model": "a-b"}


def test_a_schema_change_invalidates_the_entry(tmp_path):
    """PromptConfig.hash covers the prompt assets; nothing covered the answer
    schema. Adding a field to the verdict changes the experiment as much as
    editing a prompt does, and a stale hit would hide that."""
    cache = Cache(tmp_path)
    cache.put("f" * 64, "cfg", "m", {"v": 1}, schema_hash="aaaaaaaa")
    assert cache.get("f" * 64, "cfg", "m", schema_hash="aaaaaaaa") == {"v": 1}
    assert cache.get("f" * 64, "cfg", "m", schema_hash="bbbbbbbb") is None
