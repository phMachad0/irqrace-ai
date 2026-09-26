"""Anthropic, through the official SDK.

The one adapter that uses a vendor SDK, because this is the provider the
project is primarily measured on and the SDK carries two things worth having:
an enforced JSON-Schema output mode, and prompt caching -- which is what makes
a 31-subject sweep at five ablation rows affordable at all.

Credentials resolve the SDK's own way (``ANTHROPIC_API_KEY``, an
``ANTHROPIC_AUTH_TOKEN``, or a profile from ``ant auth login``). Nothing here
reads a key, so importing the module never requires one.
"""

from __future__ import annotations

import time
from typing import Any

from irqrace.llm.backends.base import (
    BackendError,
    Backend,
    Capabilities,
    ChatRequest,
    ChatResponse,
    RefusalError,
    StructuredMode,
    StructuredOutputError,
    Usage,
)

#: USD per million tokens, first-party rates. Absent model -> unpriced, and
#: `Usage.cost_usd()` then returns None rather than zero.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5": (10.00, 50.00),
}

DEFAULT_MODEL = "claude-opus-5"


class AnthropicBackend(Backend):
    provider = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL, *, client: Any = None):
        super().__init__(model)
        self._client = client

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            structured=StructuredMode.native_schema,
            prompt_caching=True,
            # Removed on the current models; passing it is a 400. Callers are
            # told rather than having their setting silently dropped.
            temperature=False,
            thinking=True,
        )

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ModuleNotFoundError:
                raise BackendError(
                    "the Anthropic SDK is not installed. "
                    "`pip install -e '.[llm-anthropic]'`, or use an "
                    "OpenAI-compatible or Ollama backend, which need nothing "
                    "beyond the standard library."
                ) from None
            try:
                self._client = anthropic.Anthropic()
            except Exception as e:  # missing or malformed credentials
                raise BackendError(
                    f"could not construct the Anthropic client: {e}. Set "
                    "ANTHROPIC_API_KEY, or run `ant auth login`."
                ) from None
        return self._client

    def chat(self, request: ChatRequest) -> ChatResponse:
        system: list[dict[str, Any]] = [{"type": "text", "text": request.system}]
        if request.cache_system:
            system[0]["cache_control"] = {"type": "ephemeral"}

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": system,
            "messages": request.messages,
        }

        started = time.perf_counter()
        if request.schema is None:
            response = self.client.messages.create(**kwargs)
        else:
            response = self.client.messages.parse(
                **kwargs,
                output_config={
                    "format": {
                        "type": "json_schema",
                        "schema": request.schema,
                    }
                },
            )
        elapsed = time.perf_counter() - started

        self._guard_refusal(response)
        return ChatResponse(
            text=self._text(response),
            parsed=self._parsed(response, request),
            structured_mode=(
                None if request.schema is None else StructuredMode.native_schema
            ),
            usage=self._usage(response, elapsed),
        )

    # -- plumbing ---------------------------------------------------------

    @staticmethod
    def _guard_refusal(response: Any) -> None:
        if getattr(response, "stop_reason", None) != "refusal":
            return
        details = getattr(response, "stop_details", None)
        raise RefusalError(
            "the model declined this request "
            f"(category={getattr(details, 'category', None)})"
        )

    @staticmethod
    def _text(response: Any) -> str:
        return "".join(
            b.text for b in getattr(response, "content", []) if b.type == "text"
        )

    @staticmethod
    def _parsed(response: Any, request: ChatRequest) -> dict[str, Any] | None:
        if request.schema is None:
            return None
        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise StructuredOutputError(
                f"no structured output (stop={getattr(response, 'stop_reason', '?')})"
            )
        # `messages.parse` returns a model instance when handed a Pydantic
        # class and a dict when handed a raw schema; normalise to a dict.
        return parsed if isinstance(parsed, dict) else parsed.model_dump(mode="json")

    def _usage(self, response: Any, elapsed: float) -> Usage:
        u = getattr(response, "usage", None)
        price_in, price_out = PRICING.get(self.model, (None, None))
        return Usage(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            latency_s=elapsed,
            price_in=price_in,
            price_out=price_out,
        )
