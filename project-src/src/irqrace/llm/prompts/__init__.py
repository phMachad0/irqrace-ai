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
HARMFULNESS = "harmfulness.md"
SELF_VALIDATION = "self_validation.md"
HARM_VALIDATION = "harm_validation.md"
CONTEXT_REQUESTS = "context_requests.md"

#: The two questions of the decomposed rows. ``None`` is the combined turn of
#: rows 1-2, which answers both and so gets every asset.
STAGES = ("feasibility", "harmfulness")


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
    #: Extra assets appended to every question's prompt -- an experimental
    #: benchmark-semantics add-on, say. Part of the cache key like any asset.
    extra: tuple[str, ...] = ()

    def assets(self, stage: str | None = None) -> tuple[str, ...]:
        """Asset filenames in render order. Order is part of the cache key.

        Per question: the feasibility question gets the interrupt pattern table
        and the feasibility checklist, the harmfulness question the
        pattern-specific harm criterion and its own two-rule checklist. The
        feasibility checklist leans toward ``uncertain`` for reasons about
        reachability; applied to harmfulness it turned correct ``benign``
        answers into ``uncertain`` (wiki: Triage Study 2026-10-26).
        ``stage=None`` is the combined turn and every asset.
        """
        feas, harm = stage in (None, "feasibility"), stage in (None, "harmfulness")
        names = [BASE]
        if self.domain_rules:
            if feas:
                names.append(DOMAIN_RULES)
            if harm:
                names.append(HARMFULNESS)
        if self.progressive:
            names.append(CONTEXT_REQUESTS)
        if self.self_validation:
            if feas:
                names.append(SELF_VALIDATION)
            if harm and self.decomposition:
                names.append(HARM_VALIDATION)
        # Last: an add-on states which earlier rules it overrides, and a rule
        # that comes after it would read as the final word.
        names.extend(self.extra)
        return tuple(names)

    def system_prompt(self, stage: str | None = None) -> str:
        """The stable system prefix, identical for every candidate in a row.

        Nothing candidate-specific goes in here. That is what makes it cacheable
        across a whole 31-subject sweep, and the saving is the reason the
        ablation is affordable at every row.

        **The baseline row does not reach the cache minimum.** Prompt caching
        needs a prefix of roughly 1024 tokens; ``simple`` is about 565 and the
        full row about 1900, so rows 2-5 cache and row 1 silently does not.
        That is a real confound in the cost column of the ablation table:
        row 1's cost per candidate is not comparable to the others, because
        the difference includes cache eligibility and not only prompt length.
        Report the cost column with that stated, or normalise by reporting
        uncached cost for every row.
        """
        return "\n\n---\n\n".join(_read(n) for n in self.assets(stage))

    def hash(self) -> str:
        """Stable identity of this configuration, including asset contents."""
        payload = {
            "name": self.name,
            "assets": [
                {"stage": st or "combined", "name": n, "sha256": _sha(_read(n))}
                for st in ((None,) if not self.decomposition else STAGES)
                for n in self.assets(st)
            ],
            "decomposition": self.decomposition,
            "max_request_rounds": self.max_request_rounds,
        }
        return _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")))[:16]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


#: The active rows, cumulative, in the order they are reported. ``ABLATION[-1]``
#: is the full pipeline and is what the deployed stage runs.
#:
#: **Progressive prompting (D#2) is deferred** until the static pipeline exists
#: (2026-09-27, Lucas). Until Track A's resolver lands in W8 the only C4
#: backend is :class:`~irqrace.llm.resolver.RecordBackedResolver`, which can
#: only re-serve the record the model already has or answer ``not_found`` -- so
#: a request round costs a full re-send of the history and cannot add
#: information. No active row opens the request loop; the loop itself and its
#: tests stay, and :data:`DEFERRED` keeps the row's definition for when it
#: returns. The row names below keep their meaning *relative to the row before*,
#: and the config hash changes with the assets, so no cached answer from the
#: progressive versions can be served for these.
ABLATION: tuple[PromptConfig, ...] = (
    PromptConfig(name="simple"),
    PromptConfig(name="+domain", domain_rules=True),
    PromptConfig(name="+decomposition", domain_rules=True, decomposition=True),
    PromptConfig(
        name="+self-validation",
        domain_rules=True,
        decomposition=True,
        self_validation=True,
    ),
)

#: Rows defined but not run. Selecting one by name is an error that says why.
DEFERRED: dict[str, PromptConfig] = {
    "+progressive": PromptConfig(
        name="+progressive", domain_rules=True, progressive=True
    ),
}

FULL = ABLATION[-1]

BY_NAME = {c.name: c for c in ABLATION}

#: Rows outside the ablation, for experiments. Selectable by name wherever a row
#: is; never part of the reported ablation table.
EXPERIMENTAL: dict[str, PromptConfig] = {
    "+racebench": dataclasses.replace(
        FULL, name="+racebench", extra=("racebench_semantics.md",)
    ),
}
