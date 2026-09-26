"""Backend registry — one string selects a provider and a model.

``provider:model``, everywhere a model is named: on the command line, in a
config file, in the ``emitted_by`` of a result, in the ablation table. One
string that is both the selector and the identity means a number can never be
reported without saying what produced it.

Registering a new provider is one entry in :data:`REGISTRY`; nothing in the
triage stage imports a provider module directly.
"""

from __future__ import annotations

from typing import Any, Callable

from irqrace.llm.backends.base import (
    Backend,
    BackendError,
    Capabilities,
    ChatRequest,
    ChatResponse,
    RefusalError,
    StructuredMode,
    StructuredOutputError,
    Usage,
)

__all__ = [
    "Backend",
    "BackendError",
    "Capabilities",
    "ChatRequest",
    "ChatResponse",
    "RefusalError",
    "StructuredMode",
    "StructuredOutputError",
    "Usage",
    "from_spec",
    "REGISTRY",
]


def _anthropic(model: str, **kw: Any) -> Backend:
    from irqrace.llm.backends.anthropic_backend import (
        DEFAULT_MODEL,
        AnthropicBackend,
    )

    return AnthropicBackend(model or DEFAULT_MODEL, **kw)


def _openai(model: str, **kw: Any) -> Backend:
    from irqrace.llm.backends.openai_backend import OpenAICompatibleBackend

    return OpenAICompatibleBackend(model, **kw)


def _ollama(model: str, **kw: Any) -> Backend:
    from irqrace.llm.backends.ollama_backend import OllamaBackend

    return OllamaBackend(model, **kw)


#: ``provider -> factory``. The OpenAI entry is the generic one: point
#: ``IRQRACE_OPENAI_BASE_URL`` at Groq, Together, OpenRouter, LiteLLM, vLLM or
#: LM Studio and it serves them all, so most "new provider" requests need no
#: code at all.
REGISTRY: dict[str, Callable[..., Backend]] = {
    "anthropic": _anthropic,
    "openai": _openai,
    "ollama": _ollama,
}

DEFAULT_SPEC = "anthropic:claude-opus-5"


def from_spec(spec: str = DEFAULT_SPEC, **kwargs: Any) -> Backend:
    """Build a backend from ``provider:model``.

    The model half may itself contain colons -- Ollama tags look like
    ``qwen2.5-coder:32b`` -- so only the first colon separates.

    >>> from_spec("ollama:qwen2.5-coder:32b").spec
    'ollama:qwen2.5-coder:32b'
    """
    provider, _, model = spec.partition(":")
    provider = provider.strip().lower()
    if provider not in REGISTRY:
        raise BackendError(
            f"unknown provider {provider!r}; known: {', '.join(sorted(REGISTRY))}. "
            "For any OpenAI-compatible endpoint use 'openai:<model>' and set "
            "IRQRACE_OPENAI_BASE_URL."
        )
    if not model:
        if provider != "anthropic":
            raise BackendError(f"'{provider}:' needs a model, e.g. '{provider}:llama3'")
        model = ""
    return REGISTRY[provider](model, **kwargs)
