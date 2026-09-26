"""The neutral interface every model provider is reached through.

The triage stage must not know which model it is talking to. That is partly
engineering hygiene, but mostly it is what turns [[LLift (paper)]]'s central
claim into an experiment this project can run: LLift found that **prompt
architecture dominates model choice**, and the only way to test that here is to
hold the prompt fixed and swap the model. A harness welded to one SDK can cite
that finding; one with a backend seam can check it.

## What the seam has to survive

Three things differ across providers in ways that are *measurable*, so each one
is recorded rather than smoothed over:

**Structured output.** Providers offer anything from a real JSON-Schema mode to
nothing at all. :class:`StructuredMode` names which tier actually served a
response, and it travels with the result -- because a row of the ablation
answered through ``prompted_json`` is not the same experiment as one answered
through ``native_schema``, and discovering that after the fact would invalidate
a comparison rather than explain it.

**Pricing.** A model whose price is unknown must not cost zero. :class:`Usage`
carries the per-MTok rates the backend knew, and :meth:`Usage.cost_usd` returns
``None`` when it did not know them. A silent 0.00 would make an unpriced cloud
model look like a local one.

**Prompt caching.** Anthropic-specific. Cost per candidate is therefore not
comparable across backends, which is a caveat on a table rather than a bug --
but only if :class:`Capabilities` says so out loud.

## What the seam deliberately does not do

It does not retry, rank, or repair a bad answer into a good one. A backend that
cannot produce a parseable verdict raises, and the candidate is reported as an
exclusion. Inventing a verdict to keep a sweep running is how a recall number
becomes fiction.
"""

from __future__ import annotations

import abc
import dataclasses
import enum
import json
import re
from typing import Any


class StructuredMode(str, enum.Enum):
    """How a structured answer was actually obtained. Recorded per response."""

    #: The provider enforced a JSON Schema. Strongest guarantee.
    native_schema = "native_schema"
    #: Coerced through a forced tool/function call.
    tool_call = "tool_call"
    #: Asked for JSON in the prompt and parsed the reply. Weakest, and a
    #: confound worth reporting: the model may return prose, and what it
    #: returns is not schema-checked by anyone but us.
    prompted_json = "prompted_json"


class BackendError(RuntimeError):
    """The provider could not be reached, or answered unusably."""


class RefusalError(BackendError):
    """The model declined the request. Not a verdict, and not scoreable.

    Lives here rather than in the client because refusal is a provider-level
    event with a different shape on every provider -- a ``stop_reason`` on one,
    an HTTP status on another, a sentence of prose on a third. Normalising it
    is the backend's job.
    """


class StructuredOutputError(BackendError):
    """A structured answer was requested and could not be produced."""


@dataclasses.dataclass(frozen=True)
class Capabilities:
    """What a backend can do, so callers can report caveats instead of guessing."""

    structured: StructuredMode
    prompt_caching: bool = False
    temperature: bool = True
    thinking: bool = False

    def caveats(self) -> list[str]:
        out = []
        if self.structured is not StructuredMode.native_schema:
            out.append(
                f"structured output served via {self.structured.value}, not an "
                "enforced schema"
            )
        if not self.prompt_caching:
            out.append("no prompt caching - cost is not comparable with a cached backend")
        if not self.temperature:
            out.append("temperature is not settable; sampling variation is the model's own")
        return out


@dataclasses.dataclass(frozen=True)
class Usage:
    """Tokens and the rates they were priced at, if the backend knew them."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    latency_s: float = 0.0
    #: USD per million tokens. ``None`` means the backend had no price, and
    #: :meth:`cost_usd` then refuses to invent one.
    price_in: float | None = None
    price_out: float | None = None

    CACHE_WRITE_MULTIPLIER = 1.25
    CACHE_READ_MULTIPLIER = 0.10

    @property
    def pricing_known(self) -> bool:
        return self.price_in is not None and self.price_out is not None

    def cost_usd(self) -> float | None:
        if not self.pricing_known:
            return None
        per_in = self.price_in / 1_000_000  # type: ignore[operator]
        return (
            self.input_tokens * per_in
            + self.cache_write_tokens * per_in * self.CACHE_WRITE_MULTIPLIER
            + self.cache_read_tokens * per_in * self.CACHE_READ_MULTIPLIER
            + self.output_tokens * self.price_out / 1_000_000  # type: ignore[operator]
        )


@dataclasses.dataclass
class ChatRequest:
    """One provider-neutral turn.

    :param system: the stable prefix. Backends that support prompt caching mark
        it cacheable; the rest send it as an ordinary system message.
    :param messages: ``{"role": "user"|"assistant", "content": str}``.
    :param schema: a JSON Schema for the answer, or ``None`` for free prose.
    :param cache_system: hint, honoured only where caching exists.
    """

    system: str
    messages: list[dict[str, str]]
    schema: dict[str, Any] | None = None
    schema_name: str = "answer"
    max_tokens: int = 16000
    temperature: float | None = None
    cache_system: bool = True


@dataclasses.dataclass
class ChatResponse:
    """One provider-neutral answer."""

    text: str
    usage: Usage
    #: Populated when :attr:`ChatRequest.schema` was set.
    parsed: dict[str, Any] | None = None
    #: How :attr:`parsed` was obtained. ``None`` for free-prose turns.
    structured_mode: StructuredMode | None = None


class Backend(abc.ABC):
    """One provider. Construct through :func:`irqrace.llm.backends.from_spec`."""

    provider: str = "abstract"

    def __init__(self, model: str):
        self.model = model

    @property
    def spec(self) -> str:
        """``provider:model`` — the identity recorded with every number.

        ``wiki/concepts/Precision Metrics.md`` #8: report the model and the date
        with every measurement. With several providers in play, the model name
        alone is no longer unique, so the spec is what goes in the record.
        """
        return f"{self.provider}:{self.model}"

    @property
    @abc.abstractmethod
    def capabilities(self) -> Capabilities: ...

    @abc.abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse: ...

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} {self.spec}>"


# -- helpers shared by adapters -------------------------------------------


_FENCE = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL)


def strictify(schema: dict[str, Any]) -> dict[str, Any]:
    """Tighten a Pydantic-generated schema for providers with a strict mode.

    Strict JSON-Schema modes generally demand ``additionalProperties: false``
    and every property listed in ``required``. Pydantic emits neither for
    optional fields. Nullability survives the change because Pydantic already
    encodes an optional field as ``anyOf: [T, null]`` -- so making it required
    asks for the key, not for a value.
    """
    out = json.loads(json.dumps(schema))  # deep copy

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(out)
    return out


def json_instructions(schema: dict[str, Any]) -> str:
    """The prompt appendix used by the ``prompted_json`` fallback."""
    return (
        "\n\nRespond with a single JSON object and nothing else — no prose "
        "before or after, no markdown fence. It must validate against this "
        "JSON Schema:\n\n"
        f"{json.dumps(schema, indent=2)}"
    )


def extract_json(text: str) -> dict[str, Any]:
    """Pull one JSON object out of a reply, tolerating fences and preamble.

    Raises rather than returning a partial result. A half-parsed verdict is
    worse than no verdict: it would be scored.
    """
    candidates = []
    if match := _FENCE.search(text):
        candidates.append(match.group(1).strip())
    candidates.append(text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise StructuredOutputError(
        f"no JSON object in the reply (first 200 chars: {text[:200]!r})"
    )
