"""Stage B — proposing an interrupt-specific fix, with a required witness.

``wiki/Roadmap.md`` W7. The last stage before re-verification, and the one that
connects the two literatures this project sits between: [[SDRacer (paper)]] is
the only concurrency source that repairs and [[SkipAnalyzer (paper)]] the only
LLM source that does, and neither has met the other.

Three things shape the design, all from ``wiki/concepts/LLM-Assisted Repair.md``.

**The witness is required, and it comes first.** [[SAST-Genius (paper)]]'s
reusable idea is that its model produces a proof-of-concept rather than a
verdict: an artifact can be checked, a claim cannot. The analogue here is a
concrete interleaving -- the preemption point, the firing flow, the order of
the three accesses, and the state that differs from every serial execution.
That is checkable against the masking analysis and encodable as a CBMC
assertion, and a fix whose author cannot state it is fixing the wrong thing.

**The vocabulary is closed and interrupt-specific.** [[SDRacer (paper)]] §4
enumerates it. A model reaching for a mutex has fallen back on thread
concurrency, which does not apply under asymmetric preemption, so
:class:`Strategy` does not offer one.

**Logic Rate is scored on effect, not text.** [[SkipAnalyzer (paper)]] compares
patches to hand-written fixes and reports 97.3% on Null Dereference; its own
stated limitation is that "logically correct" means an author agreed. Comparing
diffs textually would score formatting. :func:`logic_rate` instead compares
what the patch *does* -- strategy, the interrupts it masks, and the region it
covers -- against the reference fix, so two patches that protect the same
interval with the same interrupts agree even when written differently.

**Latency is a correctness property**, which is why ``latency_note`` is
mandatory rather than advisory. SDRacer measured repair overhead below 0.09 on
9 of 11 subjects and markedly worse on two, because disabling interrupts
changed the main task's control flow. A patch that masks interrupts across a
long loop has traded a race for a deadline miss.
"""

from __future__ import annotations

import dataclasses
import enum
import re
from typing import Any

from pydantic import BaseModel, Field

from irqrace.llm.backends import ChatRequest
from irqrace.llm.client import TriageClient, render_record
from irqrace.llm.prompts import PromptConfig


class Strategy(str, enum.Enum):
    """The closed repair vocabulary. No mutex, by construction."""

    #: disable_isr(n) before A1, enable_isr(n) after A2.
    mask_interval = "mask_interval"
    #: Mask around one access. Race pairs only -- on a triple this protects the
    #: endpoints and leaves the gap the remote access was already landing in.
    mask_access = "mask_access"
    #: Widen a critical section that already exists nearby.
    extend_section = "extend_section"
    #: Merge two adjacent sections whose gap is the defect.
    merge_sections = "merge_sections"


class Witness(BaseModel):
    """The interleaving that makes this a defect. Required, and stated first."""

    firing_flow: str = Field(
        description="Which flow preempts, by id — e.g. 'isr_2'."
    )
    preemption_point: str = Field(
        description=(
            "Where it fires, with a line number: between which two statements "
            "of the interrupted flow."
        )
    )
    access_order: list[str] = Field(
        description="Execution order of the accesses by role, e.g. ['A1','B','A2']."
    )
    divergence: str = Field(
        description=(
            "The value or state after this interleaving that differs from every "
            "serial execution. This is what makes it a defect rather than a "
            "reordering."
        )
    )


class Patch(BaseModel):
    """A proposed fix. Field order is the order the model must think in."""

    reasoning: str
    witness: Witness
    strategy: Strategy
    masked_irqs: list[int] = Field(
        description="Interrupt numbers the patch masks. -1 means all."
    )
    covers_from_line: int
    covers_to_line: int
    latency_note: str = Field(
        description=(
            "What the critical section now covers, and whether it is bounded. "
            "Required even when the answer is 'a few statements'."
        )
    )
    diff: str = Field(description="Unified diff against the file as given.")


@dataclasses.dataclass(frozen=True)
class ReferenceFix:
    """A hand-written fix, for Logic Rate. The ground truth of this stage."""

    candidate_id: str
    strategy: Strategy
    masked_irqs: frozenset[int]
    covers_from_line: int
    covers_to_line: int
    #: Why this is the right fix, and what a plausible wrong one looks like.
    rationale: str
    #: Set when masking the obvious interrupt alone leaves a hole.
    also_mask_note: str = ""


REPAIR_TASK = (
    "This candidate has been judged a real defect. Propose a fix."
)


class RepairClient:
    """Runs the repair stage. Shares the backend seam with triage."""

    def __init__(self, config: PromptConfig, **kwargs: Any):
        # Composition over inheritance: repair reuses the triage client's
        # backend handling, accounting, caching and transcript writing, and
        # differs only in the prompt and the schema.
        self._triage = TriageClient(config, **kwargs)

    @property
    def backend(self):
        return self._triage.backend

    @property
    def spend(self):
        return self._triage.spend

    def repair(self, record: dict[str, Any], repair_prompt: str) -> Patch:
        """Propose one patch. Raises rather than returning a partial fix."""
        response = self._triage._call(
            ChatRequest(
                system=f"{self._triage.config.system_prompt()}\n\n---\n\n{repair_prompt}",
                messages=[
                    {
                        "role": "user",
                        "content": f"{REPAIR_TASK}\n\n{render_record(record)}",
                    }
                ],
                schema=Patch.model_json_schema(),
                schema_name="Patch",
            )
        )
        if response.parsed is None:
            raise RuntimeError("the backend returned no structured patch")
        return Patch.model_validate(response.parsed)


# -- scoring ---------------------------------------------------------------

#: A unified-diff hunk header. Used only to check the diff is a diff.
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", re.M)


def is_wellformed_diff(diff: str) -> bool:
    """Cheap structural check: does this look like a unified diff at all?

    Not Syntax Rate. A patch that is not a diff cannot be applied, let alone
    compiled, and catching that needs no toolchain.
    """
    return bool(_HUNK.search(diff)) and any(
        line.startswith(("+", "-")) for line in diff.splitlines()
    )


def syntax_rate(
    patches: dict[str, Patch], compile_check
) -> tuple[float | None, list[str]]:
    """Fraction of patches a parser accepts.

    ``compile_check`` takes a :class:`Patch` and returns ``True`` if the
    patched source parses, or ``None`` if it could not run -- no compiler, no
    source tree. **A checker that cannot run yields ``None``, never a pass**:
    reporting an unmeasured Syntax Rate of 100% is the same silent success the
    recall gate guards against.
    """
    results, failed = [], []
    for cid, patch in patches.items():
        outcome = compile_check(patch)
        if outcome is None:
            return None, []
        results.append(bool(outcome))
        if not outcome:
            failed.append(cid)
    return (sum(results) / len(results) if results else 0.0), failed


def logic_rate(
    patches: dict[str, Patch], references: dict[str, ReferenceFix]
) -> tuple[float, list[str]]:
    """Fraction of patches whose *effect* matches the hand-written fix.

    Compared on strategy, masked interrupts and covered region rather than on
    diff text, because two correct patches can be written differently and a
    textual comparison would score formatting.

    ``extend_section`` and ``mask_interval`` are accepted for one another when
    the covered region and the interrupts agree: whether a fix widens an
    existing critical section or opens a new one around the same interval is a
    style difference, and the reference names the tidier of the two.
    """
    equivalent = {Strategy.mask_interval, Strategy.extend_section}
    matched, missed = [], []
    for cid, patch in patches.items():
        ref = references.get(cid)
        if ref is None:
            missed.append(f"{cid}: no reference fix")
            continue
        ok = (
            (patch.strategy == ref.strategy
             or {patch.strategy, ref.strategy} <= equivalent)
            and set(patch.masked_irqs) >= ref.masked_irqs
            and patch.covers_from_line <= ref.covers_from_line
            and patch.covers_to_line >= ref.covers_to_line
        )
        matched.append(ok)
        if not ok:
            missed.append(
                f"{cid}: proposed {patch.strategy.value} masking "
                f"{sorted(patch.masked_irqs)} over "
                f"[{patch.covers_from_line}, {patch.covers_to_line}]; reference is "
                f"{ref.strategy.value} masking {sorted(ref.masked_irqs)} over "
                f"[{ref.covers_from_line}, {ref.covers_to_line}]"
            )
    return (sum(matched) / len(matched) if matched else 0.0), missed


def witness_problems(patch: Patch, record: dict[str, Any]) -> list[str]:
    """Check the witness against the record, mechanically.

    This is the half of validation that needs no solver: does the named firing
    flow exist and is it the one the analysis says preempts, and is the access
    order a permutation with the remote access between the local pair? A
    witness that fails here is wrong regardless of how good the diff looks.
    """
    problems = []
    flows = {f["id"] for f in record["flows"]}
    if patch.witness.firing_flow not in flows:
        problems.append(
            f"witness names flow {patch.witness.firing_flow!r}, which is not in "
            f"the record ({', '.join(sorted(flows))})"
        )
    remote = record.get("preemption", {}).get("preempting_flow")
    if remote and patch.witness.firing_flow != remote:
        problems.append(
            f"witness names {patch.witness.firing_flow!r} as the preempting flow; "
            f"the analysis says {remote!r}"
        )
    order = patch.witness.access_order
    if sorted(order) != ["A1", "A2", "B"]:
        problems.append(f"access order {order} is not a permutation of A1, B, A2")
    elif order.index("B") != 1:
        problems.append(
            f"access order {order} does not place the remote access between the "
            "local pair, so it does not describe an atomicity violation"
        )
    return problems
