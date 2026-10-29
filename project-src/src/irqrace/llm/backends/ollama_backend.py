"""Ollama, for local models.

Worth having for a reason beyond convenience. Every cost number in this project
is a cloud number, and the Roadmap's risk register sets a $30 trigger on
fixture spend. A local backend makes prompt iteration free: the expensive
sweeps stay on the measured model, while the hundred small "does the request
block parse" runs cost nothing.

It is also the honest floor of the ablation. If a 7B local model with the full
prompt architecture beats a frontier model with the simple prompt, that is
[[LLift (paper)]]'s thesis reproduced on interrupt concurrency -- and it is a
far stronger claim than any single-model table.

Local models are **unpriced, not free**: :meth:`Usage.cost_usd` returns ``None``
rather than 0.00, so a local run never silently lands in a cost column next to
a cloud one.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from irqrace.llm.backends.openai_backend import USER_AGENT
from irqrace.llm.backends.base import (
    Backend,
    BackendError,
    Capabilities,
    ChatRequest,
    ChatResponse,
    StructuredMode,
    Usage,
    extract_json,
    json_instructions,
)

DEFAULT_HOST = "http://localhost:11434"


class OllamaBackend(Backend):
    provider = "ollama"

    def __init__(self, model: str, *, host: str | None = None, transport: Any = None):
        super().__init__(model)
        self.host = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).rstrip("/")
        self._transport = transport
        self._schema_supported = True

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            structured=(
                StructuredMode.native_schema
                if self._schema_supported
                else StructuredMode.prompted_json
            ),
            prompt_caching=False,
            temperature=True,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        data = self._post(self._body(request))
        elapsed = time.perf_counter() - started

        text = (data.get("message") or {}).get("content") or ""
        return ChatResponse(
            text=text,
            parsed=extract_json(text) if request.schema is not None else None,
            structured_mode=(
                None
                if request.schema is None
                else (
                    StructuredMode.native_schema
                    if self._schema_supported
                    else StructuredMode.prompted_json
                )
            ),
            usage=self._usage(data, elapsed),
        )

    def _body(self, request: ChatRequest) -> dict[str, Any]:
        messages = [{"role": "system", "content": request.system}]
        messages += [dict(m) for m in request.messages]

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": request.max_tokens},
        }
        if request.temperature is not None:
            body["options"]["temperature"] = request.temperature

        if request.schema is not None:
            if self._schema_supported:
                # Ollama takes a JSON Schema directly in `format`. Older builds
                # accept only the string "json", and older still ignore it --
                # hence the prompt appendix as well, which costs a few tokens
                # and removes a whole class of silent failure.
                body["format"] = request.schema
            messages[-1]["content"] += json_instructions(request.schema)
        return body

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        if self._transport is not None:
            return self._transport(body)

        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as fh:
                return json.loads(fh.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            if e.code == 400 and "format" in detail:
                self._schema_supported = False
                return self._post({k: v for k, v in body.items() if k != "format"})
            raise BackendError(f"{self.host} returned {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise BackendError(
                f"cannot reach Ollama at {self.host}: {e.reason}. "
                "Is `ollama serve` running?"
            ) from None

    @staticmethod
    def _usage(data: dict[str, Any], elapsed: float) -> Usage:
        return Usage(
            input_tokens=data.get("prompt_eval_count") or 0,
            output_tokens=data.get("eval_count") or 0,
            latency_s=elapsed,
            # Deliberately unpriced. Local compute is not free, it is
            # unmetered, and a 0.00 in a cost table is a claim.
            price_in=None,
            price_out=None,
        )
