"""Prompt composition — the ablation is a set of configurations, not a set of prompts.

``wiki/LLM Stage Design.md`` §5 asks for an ablation in [[LLift (paper)]]'s
shape: simple prompt -> +domain rules -> +progressive -> +decomposition ->
+self-validation. That is the single most valuable experiment available here,
because it is the one result the concurrency branch has no equivalent of, and
LLift's own table moved recall from 0.15 to 1.00 on prompt architecture alone.

An experiment like that is only trustworthy if the rows differ in exactly the
stated way. So the rows are **compositions of the same assets** rather than five
hand-written prompts: turning a component on adds its markdown file, and nothing
else changes. Editing one asset changes every row that includes it, which is the
intended behaviour.

The assets are markdown files in this package rather than string literals so
that the prompt is reviewable in a diff, and so a prose change is not a code
change.

**The config hash covers the asset contents, not just the flags.** Editing
``domain_rules.md`` without that would leave the result cache serving answers
produced by the previous wording, and the ablation would silently compare a row
against a stale version of itself.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

_ASSETS = Path(__file__).parent

#: Always present, including in the simple-prompt baseline. The code-is-data
#: guard in ``base.md`` is a security control, not an accuracy technique: a
#: comment in analysed source can try to talk the model out of a defect
#: ([[SAST-Genius (paper)]]), and a candidate dismissed that way is a
#: deliberately induced false negative. It is not an ablation variable.
BASE = "base.md"

DOMAIN_RULES = "domain_rules.md"
SELF_VALIDATION = "self_validation.md"
CONTEXT_REQUESTS = "context_requests.md"


def _read(name: str) -> str:
    return (_ASSETS / name).read_text(encoding="utf-8").strip()


@dataclasses.dataclass(frozen=True)
class PromptConfig:
    """One row of the ablation.

    :param name: row label, used in reports and in the cache key.
    :param domain_rules: D#1 -- few-shot teaching of the interrupt pattern table.
    :param progressive: D#2 -- the model may request context through C4.
    :param decomposition: D#3 -- feasibility and harmfulness in separate
        conversations. With this off, both are asked in one turn, which is the
        merge ``wiki/LLM Stage Design.md`` warns turns "benign" into
        "infeasible".
    :param self_validation: D#4 -- recall-biased rules checked before answering.
    :param max_request_rounds: cap on progressive-prompting rounds per
        conversation. Bounds cost and guarantees termination; reaching the cap
        is recorded rather than silently ignored, because a candidate that keeps
        asking is evidence about the context record.
    """

    name: str
    domain_rules: bool = False
    progressive: bool = False
    decomposition: bool = False
    self_validation: bool = False
    max_request_rounds: int = 4

    def assets(self) -> tuple[str, ...]:
        """Asset filenames in render order. Order is part of the cache key."""
        names = [BASE]
        if self.domain_rules:
            names.append(DOMAIN_RULES)
        if self.progressive:
            names.append(CONTEXT_REQUESTS)
        if self.self_validation:
            names.append(SELF_VALIDATION)
        return tuple(names)

    def system_prompt(self) -> str:
        """The stable system prefix, identical for every candidate in a row.

        Nothing candidate-specific goes in here. That is what makes it cacheable
        across a whole 31-subject sweep, and the saving is the reason the
        ablation is affordable at five rows.

        **The baseline row does not reach the cache minimum.** Prompt caching
        needs a prefix of roughly 1024 tokens; ``simple`` is about 565 and the
        full row about 1900, so rows 2-5 cache and row 1 silently does not.
        That is a real confound in the cost column of the ablation table:
        row 1's cost per candidate is not comparable to the others, because
        the difference includes cache eligibility and not only prompt length.
        Report the cost column with that stated, or normalise by reporting
        uncached cost for every row.
        """
        return "\n\n---\n\n".join(_read(n) for n in self.assets())

    def hash(self) -> str:
        """Stable identity of this configuration, including asset contents."""
        payload = {
            "name": self.name,
            "assets": [{"name": n, "sha256": _sha(_read(n))} for n in self.assets()],
            "decomposition": self.decomposition,
            "max_request_rounds": self.max_request_rounds,
        }
        return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")))[:16]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


#: The five rows, cumulative, in the order they are reported. ``ABLATION[-1]``
#: is the full pipeline and is what the deployed stage runs.
ABLATION: tuple[PromptConfig, ...] = (
    PromptConfig(name="simple"),
    PromptConfig(name="+domain", domain_rules=True),
    PromptConfig(name="+progressive", domain_rules=True, progressive=True),
    PromptConfig(
        name="+decomposition",
        domain_rules=True,
        progressive=True,
        decomposition=True,
    ),
    PromptConfig(
        name="+self-validation",
        domain_rules=True,
        progressive=True,
        decomposition=True,
        self_validation=True,
    ),
)

FULL = ABLATION[-1]

BY_NAME = {c.name: c for c in ABLATION}
