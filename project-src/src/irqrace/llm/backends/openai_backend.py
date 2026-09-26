"""Any OpenAI-compatible endpoint, over plain HTTP.

One adapter covers OpenAI, Groq, Together, Fireworks, DeepInfra, OpenRouter,
LiteLLM, vLLM and LM Studio, because they all expose ``/v1/chat/completions``.

**Why stdlib HTTP rather than the ``openai`` package.** This is the *generic*
adapter. Depending on one vendor's SDK to talk to a local vLLM server is
backwards, and the surface actually needed here is a single endpoint with three
fields. Plain ``urllib`` keeps the adapter dependency-free, which means a
reviewer can run the ablation against a local model with nothing installed
beyond this repository.

Configuration is by environment, so a new endpoint needs no code:

* ``IRQRACE_OPENAI_BASE_URL`` -- default ``https://api.openai.com/v1``
* ``IRQRACE_OPENAI_API_KEY``, falling back to ``OPENAI_API_KEY``
* ``IRQRACE_OPENAI_PRICING`` -- optional ``model=in,out`` pairs in USD per
  MTok, comma-separated, so a self-hosted or newly-released model can be
  priced without editing this file. Unpriced stays unpriced; it never becomes
  zero.

**Structured output degrades, and says so.** Real OpenAI honours
``response_format: json_schema``; many compatible servers accept the field and
ignore it, and some reject it outright. The adapter tries the strict mode, falls
back to prompted JSON on rejection, and reports which tier served the answer --
because an ablation row answered through the fallback is a different experiment
from one answered through an enforced schema.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any

from irqrace.llm.backends.base import (
    Backend,
    BackendError,
    Capabilities,
    ChatRequest,
    ChatResponse,
    RefusalError,
    StructuredMode,
    Usage,
    extract_json,
    json_instructions,
    strictify,
)

DEFAULT_BASE_URL = "https://api.openai.com/v1"

#: Identify the client. Without this ``urllib`` sends ``Python-urllib/3.x``,
#: which sits on CDN block lists -- Groq's edge answers it with a 403 and
#: Cloudflare error 1010 while accepting the identical request from curl. The
#: failure looks like an auth problem and is not one, so it cost a debugging
#: round; every HTTP client should name itself and this one now does.
USER_AGENT = "irqrace/0.1.0 (+https://tcc.local/irqrace)"

#: Only first-party rates are hard-coded, and sparsely. Everything else is
#: expected to come from IRQRACE_OPENAI_PRICING or stay unpriced.
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


def _env_pricing() -> dict[str, tuple[float, float]]:
    raw = os.environ.get("IRQRACE_OPENAI_PRICING", "").strip()
    out: dict[str, tuple[float, float]] = {}
    for item in filter(None, (p.strip() for p in raw.split(","))):
        try:
            model, rates = item.split("=", 1)
            rate_in, rate_out = rates.split(":", 1) if ":" in rates else rates.split(",", 1)
            out[model.strip()] = (float(rate_in), float(rate_out))
        except ValueError:
            raise BackendError(
                f"IRQRACE_OPENAI_PRICING entry {item!r} is malformed; "
                "expected 'model=IN:OUT' in USD per million tokens"
            ) from None
    return out


class OpenAICompatibleBackend(Backend):
    provider = "openai"

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        transport: Any = None,
        max_retries: int = 6,
    ):
        super().__init__(model)
        self.base_url = (
            base_url
            or os.environ.get("IRQRACE_OPENAI_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self._api_key = (
            api_key
            or os.environ.get("IRQRACE_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        #: Injection point for tests; takes a dict body and returns a dict.
        self._transport = transport
        #: Shared and free tiers meter tokens per minute; a sweep of several
        #: thousand-token records hits that within a few candidates.
        self.max_retries = max_retries
        self.max_backoff_s = 90.0
        self._strict_supported = True

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            structured=(
                StructuredMode.native_schema
                if self._strict_supported
                else StructuredMode.prompted_json
            ),
            prompt_caching=False,
            temperature=True,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()

        if request.schema is None:
            body = self._body(request)
            data = self._post(body)
            mode = None
        elif self._strict_supported:
            try:
                data = self._post(self._body(request, strict=True))
                mode = StructuredMode.native_schema
            except _StrictUnsupported:
                # Latch it off: one rejection means every later request on this
                # endpoint would pay the same round trip.
                self._strict_supported = False
                data = self._post(self._body(request, strict=False))
                mode = StructuredMode.prompted_json
        else:
            data = self._post(self._body(request, strict=False))
            mode = StructuredMode.prompted_json

        elapsed = time.perf_counter() - started
        text, finish = self._content(data)
        if finish == "content_filter":
            raise RefusalError("the endpoint refused this request (content_filter)")

        return ChatResponse(
            text=text,
            parsed=extract_json(text) if request.schema is not None else None,
            structured_mode=mode,
            usage=self._usage(data, elapsed),
        )

    # -- request construction ---------------------------------------------

    def _body(self, request: ChatRequest, *, strict: bool = False) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": request.system}
        ]
        messages += [dict(m) for m in request.messages]

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature

        if request.schema is None:
            return body

        if strict:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "schema": strictify(request.schema),
                    "strict": True,
                },
            }
        else:
            messages[-1]["content"] += json_instructions(request.schema)
        return body

    # -- transport ---------------------------------------------------------

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST with backoff on rate limits.

        Free and shared tiers meter by tokens per minute, and a context record
        is several thousand tokens, so a sweep hits 429 within a few
        candidates. Retrying is not optional here: without it the run reports
        a wall of exclusions that look like failures and are only impatience.

        The wait comes from the ``retry-after`` header when the endpoint sends
        one, otherwise from the delay named in the error message, otherwise a
        fixed fallback. Retries are capped so a genuinely exhausted quota ends
        the run instead of hanging it.
        """
        for attempt in range(self.max_retries + 1):
            try:
                return self._post_once(body)
            except _RateLimited as e:
                if attempt == self.max_retries:
                    raise BackendError(
                        f"rate limited by {self.base_url} after "
                        f"{self.max_retries} retries: {e.detail[:200]}"
                    ) from None
                time.sleep(min(e.retry_after, self.max_backoff_s))
        raise AssertionError("unreachable")

    def _post_once(self, body: dict[str, Any]) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport(body)

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                **(
                    {"Authorization": f"Bearer {self._api_key}"}
                    if self._api_key
                    else {}
                ),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as fh:
                return json.loads(fh.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            if e.code == 400 and "response_format" in detail:
                raise _StrictUnsupported(detail) from None
            if e.code == 429:
                raise _RateLimited(
                    detail, _retry_delay(e.headers.get("retry-after"), detail)
                ) from None
            raise BackendError(f"{self.base_url} returned {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise BackendError(f"cannot reach {self.base_url}: {e.reason}") from None

    # -- response parsing ---------------------------------------------------

    @staticmethod
    def _content(data: dict[str, Any]) -> tuple[str, str | None]:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError):
            raise BackendError(f"no choices in response: {str(data)[:300]}") from None
        return choice.get("message", {}).get("content") or "", choice.get("finish_reason")

    def _usage(self, data: dict[str, Any], elapsed: float) -> Usage:
        u = data.get("usage") or {}
        pricing = {**PRICING, **_env_pricing()}
        price_in, price_out = pricing.get(self.model, (None, None))
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        return Usage(
            input_tokens=max((u.get("prompt_tokens") or 0) - cached, 0),
            output_tokens=u.get("completion_tokens") or 0,
            cache_read_tokens=cached,
            latency_s=elapsed,
            price_in=price_in,
            price_out=price_out,
        )


class _StrictUnsupported(BackendError):
    """This endpoint rejected ``response_format``; fall back to prompted JSON."""


class _RateLimited(BackendError):
    """429. Carries how long the endpoint asked us to wait."""

    def __init__(self, detail: str, retry_after: float):
        super().__init__(detail)
        self.detail = detail
        self.retry_after = retry_after


#: "Please try again in 25.5s" / "in 1m30s", as providers phrase it in the body
#: when they do not send a retry-after header.
_TRY_AGAIN = re.compile(
    r"try again in\s+(?:(\d+)m)?\s*([\d.]+)s", re.IGNORECASE
)


def _retry_delay(header: str | None, detail: str, default: float = 20.0) -> float:
    """Seconds to wait, from the header, else the message, else a fallback.

    A second is added to whatever the provider names: waiting exactly the
    stated time lands on the boundary and is refused again, which turns one
    retry into two.
    """
    if header:
        try:
            return float(header) + 1.0
        except ValueError:
            pass
    if m := _TRY_AGAIN.search(detail):
        minutes = float(m.group(1) or 0)
        return minutes * 60 + float(m.group(2)) + 1.0
    return default
