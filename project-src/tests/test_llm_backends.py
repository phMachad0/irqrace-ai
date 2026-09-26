"""The provider seam.

Every backend is exercised through an injected transport, so the whole file
runs offline and without a credential of any kind.
"""

import json

import pytest

from irqrace.llm.backends import (
    BackendError,
    ChatRequest,
    StructuredMode,
    StructuredOutputError,
    Usage,
    from_spec,
)
from irqrace.llm.backends.base import extract_json, strictify
from irqrace.llm.backends.ollama_backend import OllamaBackend
from irqrace.llm.backends.openai_backend import OpenAICompatibleBackend
from irqrace.llm.verdict import FeasibilityAnswer

SCHEMA = FeasibilityAnswer.model_json_schema()
ANSWER = {"reasoning": "isr_2 preempts", "verdict": "feasible", "confidence": 0.8}


def _request(schema=SCHEMA):
    return ChatRequest(
        system="sys", messages=[{"role": "user", "content": "go"}], schema=schema
    )


# -- the registry ---------------------------------------------------------


@pytest.mark.parametrize(
    "spec,provider,model",
    [
        ("anthropic:claude-opus-5", "anthropic", "claude-opus-5"),
        ("openai:gpt-4o", "openai", "gpt-4o"),
        ("ollama:qwen2.5-coder:32b", "ollama", "qwen2.5-coder:32b"),
    ],
)
def test_specs_round_trip(spec, provider, model):
    """Ollama tags contain colons, so only the first one separates."""
    backend = from_spec(spec)
    assert backend.provider == provider
    assert backend.model == model
    assert backend.spec == spec


def test_an_unknown_provider_names_the_known_ones_and_the_generic_escape():
    with pytest.raises(BackendError, match="IRQRACE_OPENAI_BASE_URL"):
        from_spec("bedrock:claude")


def test_a_provider_without_a_model_is_rejected():
    with pytest.raises(BackendError, match="needs a model"):
        from_spec("ollama:")


# -- pricing honesty ------------------------------------------------------


def test_an_unpriced_model_costs_none_not_zero():
    """A 0.00 in a cost column is a claim; None is the absence of one."""
    u = Usage(input_tokens=1000, output_tokens=100)
    assert u.cost_usd() is None
    assert not u.pricing_known


def test_a_priced_model_computes_cache_tiers():
    u = Usage(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_read_tokens=1_000_000,
        price_in=5.0,
        price_out=25.0,
    )
    assert u.cost_usd() == pytest.approx(5.0 + 25.0 + 0.5)


def test_a_local_model_is_unpriced_rather_than_free():
    backend = OllamaBackend("llama3", transport=lambda body: {
        "message": {"content": json.dumps(ANSWER)},
        "prompt_eval_count": 10,
        "eval_count": 5,
    })
    response = backend.chat(_request())
    assert response.usage.cost_usd() is None


# -- schema handling ------------------------------------------------------


def test_strictify_closes_objects_and_requires_every_property():
    out = strictify(SCHEMA)
    assert out["additionalProperties"] is False
    assert set(out["required"]) == set(out["properties"])
    # Nullability survives: an optional field is required as a *key*, and its
    # type already admits null.
    assert "blocking_element" in out["required"]


def test_strictify_does_not_mutate_its_input():
    before = json.dumps(SCHEMA, sort_keys=True)
    strictify(SCHEMA)
    assert json.dumps(SCHEMA, sort_keys=True) == before


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here is my answer:\n```\n{"a": 1}\n```',
        'Sure! {"a": 1} — hope that helps.',
    ],
)
def test_json_is_extracted_through_fences_and_preamble(text):
    assert extract_json(text) == {"a": 1}


def test_unparseable_output_raises_rather_than_returning_a_partial():
    """A half-parsed verdict is worse than none: it would be scored."""
    with pytest.raises(StructuredOutputError):
        extract_json("I'm afraid I can't determine that.")


# -- OpenAI-compatible ----------------------------------------------------


def _openai_ok(body):
    return {
        "choices": [{"message": {"content": json.dumps(ANSWER)}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
    }


def test_strict_mode_is_used_when_the_endpoint_supports_it():
    seen = {}

    def transport(body):
        seen.update(body)
        return _openai_ok(body)

    backend = OpenAICompatibleBackend("gpt-4o", transport=transport)
    response = backend.chat(_request())
    assert response.structured_mode is StructuredMode.native_schema
    assert seen["response_format"]["json_schema"]["strict"] is True


def test_a_rejecting_endpoint_falls_back_and_says_so():
    """Many OpenAI-compatible servers accept the shape and refuse the field."""
    from irqrace.llm.backends.openai_backend import _StrictUnsupported

    calls = []

    def transport(body):
        calls.append(body)
        if "response_format" in body:
            raise _StrictUnsupported("response_format not supported")
        return _openai_ok(body)

    backend = OpenAICompatibleBackend("local-model", transport=transport)
    response = backend.chat(_request())

    assert response.structured_mode is StructuredMode.prompted_json
    assert "JSON Schema" in calls[-1]["messages"][-1]["content"]
    # And the caveat is now visible to whoever reports the row.
    assert any("not an enforced schema" in c for c in backend.capabilities.caveats())


def test_the_fallback_latches_so_it_is_paid_for_once():
    calls = []

    def transport(body):
        calls.append(body)
        if "response_format" in body:
            from irqrace.llm.backends.openai_backend import _StrictUnsupported

            raise _StrictUnsupported("nope")
        return _openai_ok(body)

    backend = OpenAICompatibleBackend("local-model", transport=transport)
    backend.chat(_request())
    backend.chat(_request())
    assert sum(1 for c in calls if "response_format" in c) == 1


def test_a_content_filter_is_a_refusal_not_a_verdict():
    from irqrace.llm.backends import RefusalError

    def transport(body):
        return {"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]}

    with pytest.raises(RefusalError):
        OpenAICompatibleBackend("gpt-4o", transport=transport).chat(_request())


def test_env_pricing_lets_a_new_model_be_priced_without_code(monkeypatch):
    monkeypatch.setenv("IRQRACE_OPENAI_PRICING", "my-model=0.5:1.5")
    backend = OpenAICompatibleBackend("my-model", transport=_openai_ok)
    usage = backend.chat(_request()).usage
    assert usage.pricing_known
    assert usage.cost_usd() == pytest.approx(100 * 0.5e-6 + 20 * 1.5e-6)


def test_malformed_env_pricing_is_rejected_rather_than_ignored(monkeypatch):
    monkeypatch.setenv("IRQRACE_OPENAI_PRICING", "broken")
    with pytest.raises(BackendError, match="malformed"):
        OpenAICompatibleBackend("m", transport=_openai_ok).chat(_request())


def test_base_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("IRQRACE_OPENAI_BASE_URL", "http://localhost:8000/v1/")
    assert OpenAICompatibleBackend("m").base_url == "http://localhost:8000/v1"


# -- capabilities are reported, not assumed -------------------------------


def test_every_backend_declares_its_caveats():
    for spec in ("anthropic:claude-opus-5", "openai:gpt-4o", "ollama:llama3"):
        backend = from_spec(spec)
        assert isinstance(backend.capabilities.caveats(), list)


def test_only_the_caching_backend_claims_caching():
    assert from_spec("anthropic:claude-opus-5").capabilities.prompt_caching
    assert not from_spec("openai:gpt-4o").capabilities.prompt_caching
    assert not from_spec("ollama:llama3").capabilities.prompt_caching


def test_the_anthropic_backend_declares_that_temperature_is_unsettable():
    """Current Claude models reject it; saying so beats dropping it silently."""
    caps = from_spec("anthropic:claude-opus-5").capabilities
    assert not caps.temperature
    assert any("temperature" in c for c in caps.caveats())


def test_the_client_identifies_itself():
    """Without a User-Agent, urllib sends 'Python-urllib/3.x', which CDN block
    lists reject -- Groq's edge returns 403 / Cloudflare 1010 while accepting
    the identical request from curl. It reads as an auth failure and is not one."""
    from irqrace.llm.backends.openai_backend import USER_AGENT

    assert USER_AGENT.startswith("irqrace/")
    assert "urllib" not in USER_AGENT


# -- rate limiting ---------------------------------------------------------


@pytest.mark.parametrize(
    "header,detail,expected",
    [
        ("30", "", 31.0),
        (None, "Please try again in 25.5s", 26.5),
        (None, "try again in 1m30s", 91.0),
        (None, "no hint here", 20.0),
        ("garbage", "try again in 5s", 6.0),
    ],
)
def test_the_retry_delay_is_read_from_header_or_message(header, detail, expected):
    """A second is added to whatever the provider names: waiting the exact
    stated time lands on the boundary and is refused again."""
    from irqrace.llm.backends.openai_backend import _retry_delay

    assert _retry_delay(header, detail) == pytest.approx(expected)


def test_a_rate_limit_is_retried_then_succeeds(monkeypatch):
    import irqrace.llm.backends.openai_backend as mod

    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(body):
        calls["n"] += 1
        if calls["n"] < 3:
            raise mod._RateLimited("tokens per minute", 0.01)
        return _openai_ok(body)

    backend = OpenAICompatibleBackend("m", transport=None)
    backend._post_once = flaky
    assert backend.chat(_request()).parsed == ANSWER
    assert calls["n"] == 3


def test_an_exhausted_quota_ends_the_run_rather_than_hanging(monkeypatch):
    import irqrace.llm.backends.openai_backend as mod

    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    backend = OpenAICompatibleBackend("m", max_retries=2)
    backend._post_once = lambda body: (_ for _ in ()).throw(
        mod._RateLimited("quota gone", 0.01)
    )
    with pytest.raises(BackendError, match="after 2 retries"):
        backend.chat(_request())
