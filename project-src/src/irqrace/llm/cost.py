"""Token, latency and cost accounting across providers.

``wiki/Roadmap.md`` W2 asks for a cost model before any measured row exists,
and ``wiki/concepts/Precision Metrics.md`` #8 asks that **the model and the
date go with every number**. With several providers reachable, the model name
alone stopped being unique, so what travels with a number is the backend spec
(``anthropic:claude-opus-5``, ``ollama:qwen2.5-coder:32b``).

Two honesty rules the aggregate enforces, both of which exist because the
alternative is a table that reads plausibly and is wrong:

* **Unpriced is not free.** A backend that did not know its rates contributes
  tokens but no dollars, and :meth:`Spend.report` says how many requests were
  unpriced instead of quietly dividing by all of them.
* **Spend never merges providers.** ``$0.4 per candidate`` across a mix of
  Opus and a local 7B is not a number anything can be concluded from.

The Roadmap's risk register sets a concrete trigger -- more than $30 on
fixtures by W5 means cutting majority-voting runs from 3 to 1 outside the final
measurement. :class:`Spend` is what makes that observable rather than
remembered.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt

from irqrace.llm.backends.base import Usage


@dataclasses.dataclass
class Spend:
    """Running total for one backend, with the provenance a number needs."""

    spec: str
    started: str = dataclasses.field(
        default_factory=lambda: _dt.datetime.now(_dt.timezone.utc).isoformat(
            timespec="seconds"
        )
    )
    candidates: int = 0
    requests: int = 0
    unpriced_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0

    def record(self, usage: Usage) -> None:
        self.requests += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cache_write_tokens += usage.cache_write_tokens
        self.cache_read_tokens += usage.cache_read_tokens
        self.latency_s += usage.latency_s

        priced = usage.cost_usd()
        if priced is None:
            self.unpriced_requests += 1
        else:
            self.cost_usd += priced

    @property
    def fully_priced(self) -> bool:
        return self.requests > 0 and self.unpriced_requests == 0

    @property
    def cost_per_candidate(self) -> float | None:
        """``None`` when any request was unpriced — a partial total is not one."""
        if not self.candidates or not self.fully_priced:
            return None
        return self.cost_usd / self.candidates

    def report(self) -> str:
        lines = [
            f"{self.spec} · {self.started} · {self.candidates} candidates, "
            f"{self.requests} requests",
            f"  tokens: {self.input_tokens:,} in / {self.output_tokens:,} out"
            + (f", {self.cache_read_tokens:,} cached" if self.cache_read_tokens else ""),
        ]

        if self.fully_priced:
            per = self.cost_per_candidate or 0.0
            lines.append(
                f"  cost:   ${self.cost_usd:.4f} total, ${per:.4f} per candidate"
            )
        elif self.unpriced_requests == self.requests:
            lines.append("  cost:   unpriced backend — tokens only, no dollar total")
        else:
            lines.append(
                f"  cost:   ${self.cost_usd:.4f} over "
                f"{self.requests - self.unpriced_requests}/{self.requests} requests; "
                f"{self.unpriced_requests} unpriced, so there is no per-candidate figure"
            )

        if not self.cache_read_tokens and self.cache_write_tokens:
            lines.append(
                "  [!] cache written but never read — check the system prefix "
                "for an invalidator"
            )
        lines.append(f"  time:   {self.latency_s:.1f}s total")
        return "\n".join(lines)
