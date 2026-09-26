"""The triage output contract — four buckets, and why the model never picks one.

This module encodes the rule the whole project follows: **a solver may drop a
candidate; the LLM may not** (``wiki/Thesis Goal.md``, *The decision policy*).
Two mechanisms enforce it here rather than in prose:

* The model is never asked for a bucket. It answers two narrow questions --
  *is this interleaving feasible?* and *if feasible, is it harmful?* -- and
  :func:`bucket_of` derives the bucket from the pair. A model cannot reach for
  ``likely_infeasible`` as a way of expressing low confidence, because the word
  is not in its vocabulary; it has to claim infeasibility of a specific
  interleaving, which is a checkable statement.
* The derivation is recall-biased by construction: any ``uncertain`` on either
  axis yields ``uncertain``, never a low bucket.

Splitting the two questions is D#3 from ``wiki/LLM Stage Design.md``.
Feasibility is a program-semantics question and harmfulness is an intent
question; merging them is how "benign" quietly becomes "infeasible", which is a
recall loss wearing a precision costume.

Field order in the response models is deliberate: the explanation precedes the
verdict everywhere, so the model reasons before it commits ([[IRIS (paper)]],
via ``wiki/concepts/Prompt Architecture.md``). Reordering these classes changes
the measured result.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class Feasibility(str, enum.Enum):
    """Can the reported interleaving actually occur?"""

    feasible = "feasible"
    uncertain = "uncertain"
    infeasible = "infeasible"


class Harmfulness(str, enum.Enum):
    """Given that it occurs, does it matter?"""

    harmful = "harmful"
    uncertain = "uncertain"
    benign = "benign"


class Bucket(str, enum.Enum):
    """The reported bucket. Derived, never chosen -- see :func:`bucket_of`."""

    likely_real = "likely_real"
    uncertain = "uncertain"
    likely_benign = "likely_benign"
    likely_infeasible = "likely_infeasible"


#: Inspection order. A reviewer reads buckets in this order, and the Inspection
#: Ratio in :mod:`irqrace.llm.scoring` is computed against it. ``uncertain``
#: sits second on purpose: the cost of ranking a real defect there is one extra
#: candidate read, which is the trade the decision policy exists to make.
INSPECTION_ORDER: tuple[Bucket, ...] = (
    Bucket.likely_real,
    Bucket.uncertain,
    Bucket.likely_benign,
    Bucket.likely_infeasible,
)


def bucket_of(feasibility: Feasibility, harmfulness: Harmfulness | None) -> Bucket:
    """Derive the reported bucket from the model's two answers.

    The table is recall-biased: uncertainty on either axis wins over any
    confident low bucket, and ``likely_infeasible`` is reachable only from an
    explicit ``infeasible`` feasibility claim.

    ``harmfulness`` is ``None`` when the harmfulness conversation did not run --
    which is correct when feasibility came back ``infeasible``, and is treated
    as uncertainty in every other case rather than as absence of harm.
    """
    if feasibility is Feasibility.infeasible:
        return Bucket.likely_infeasible
    if feasibility is Feasibility.uncertain:
        return Bucket.uncertain
    # feasible from here on
    if harmfulness is Harmfulness.harmful:
        return Bucket.likely_real
    if harmfulness is Harmfulness.benign:
        return Bucket.likely_benign
    return Bucket.uncertain


class FeasibilityAnswer(BaseModel):
    """D#3 conversation (i). Explanation first, then the verdict."""

    reasoning: str = Field(
        description=(
            "Step through the interleaving concretely: which flow holds the "
            "shared variable when, which flow preempts where, and what the "
            "masking state is at that point. Cite line numbers from the record."
        )
    )
    blocking_element: str | None = Field(
        default=None,
        description=(
            "If and only if the verdict is 'infeasible': the single element that "
            "makes it impossible -- a specific critical section, a priority "
            "relation, or an interrupt that is never enabled. Name it precisely "
            "enough that the same element can be checked against other "
            "candidates. Leave null otherwise."
        ),
    )
    verdict: Feasibility
    confidence: float = Field(ge=0.0, le=1.0)


class HarmfulnessAnswer(BaseModel):
    """D#3 conversation (ii). Only asked when feasibility is not ``infeasible``."""

    reasoning: str = Field(
        description=(
            "Apply the stated harmfulness criterion to this variable. Do not "
            "re-litigate feasibility here."
        )
    )
    criterion_matched: str | None = Field(
        default=None,
        description=(
            "Which clause of the stated criterion fired -- 'feeds a branch', "
            "'indexes an array or pointer', or the named reason for benignity. "
            "A benign verdict with no criterion named is not acceptable."
        ),
    )
    verdict: Harmfulness
    confidence: float = Field(ge=0.0, le=1.0)


class CombinedAnswer(BaseModel):
    """Both questions in one turn — the shape of ablation rows 1 through 3.

    This is the merge D#3 exists to undo, and it is kept faithfully so the
    ablation measures the decomposition rather than an improved version of its
    absence. It lives here, as a named model, rather than inside the client:
    it is one arm of the experiment, so it has to be as reviewable in a diff as
    the arm it is compared against.

    Note what the merge costs, visible in the field list: there is one
    reasoning pass covering two different kinds of question, and the model
    commits to feasibility and harmfulness in the same breath. That is how
    "benign" quietly becomes "infeasible".
    """

    reasoning: str = Field(
        description="Reason about feasibility and harm before either verdict."
    )
    blocking_element: str | None = None
    verdict: Feasibility
    confidence: float = Field(ge=0.0, le=1.0)
    harm_verdict: Harmfulness
    harm_confidence: float = Field(ge=0.0, le=1.0)

    def split(self) -> tuple[FeasibilityAnswer, HarmfulnessAnswer | None]:
        """Project onto the two answers the rest of the pipeline expects."""
        feasibility = FeasibilityAnswer(
            reasoning=self.reasoning,
            blocking_element=self.blocking_element,
            verdict=self.verdict,
            confidence=self.confidence,
        )
        if self.verdict is Feasibility.infeasible:
            return feasibility, None
        return feasibility, HarmfulnessAnswer(
            reasoning=self.reasoning,
            verdict=self.harm_verdict,
            confidence=self.harm_confidence,
        )


class Provenance(BaseModel):
    """How a verdict was produced. Travels with it, never reconstructed.

    ``wiki/concepts/Precision Metrics.md`` #8 asks that the model and the date
    accompany every number. With several providers reachable the model name is
    no longer unique, so ``backend`` carries the full ``provider:model`` spec.

    ``structured_mode`` is here for a sharper reason. A row answered through a
    provider-enforced JSON Schema and a row answered by asking for JSON in the
    prompt are **not the same experiment**: the second can return prose, can
    drift in field naming, and is validated only by us. Discovering after the
    fact that half a table was served by the fallback would invalidate a
    comparison instead of explaining it.
    """

    backend: str
    structured_mode: str | None = None


class Triage(BaseModel):
    """One candidate's triage result. The bucket is derived, not parsed.

    ``candidate_id`` and ``fingerprint`` are copied from the C2 record so the
    result can be joined back without carrying the record around, and so the
    cache in :mod:`irqrace.llm.cache` can key on the fingerprint.
    """

    candidate_id: str
    fingerprint: str
    feasibility: FeasibilityAnswer
    harmfulness: HarmfulnessAnswer | None = None
    produced_by: Provenance | None = None

    @property
    def bucket(self) -> Bucket:
        return bucket_of(
            self.feasibility.verdict,
            self.harmfulness.verdict if self.harmfulness else None,
        )

    @property
    def rank_key(self) -> tuple[int, float]:
        """Sort key for the report: bucket order, then confidence descending.

        Within a bucket, higher confidence first -- so the candidates a reviewer
        is most likely to act on surface first inside ``likely_real``, and the
        weakest ``likely_infeasible`` claims sit closest to the candidates above
        them.
        """
        conf = self.feasibility.confidence
        if self.harmfulness is not None:
            conf = min(conf, self.harmfulness.confidence)
        return (INSPECTION_ORDER.index(self.bucket), -conf)

    def protocol_violations(self) -> list[str]:
        """Where the answer broke a rule the prompt states.

        Reported rather than raised, and the verdict is kept. A violation is
        evidence about the prompt -- the model was told a benign verdict needs
        a named criterion and gave one without -- and discarding the answer
        would discard that evidence along with a candidate the stage may not
        drop.

        Found on the first live run: two real bug points came back
        ``likely_benign`` with ``criterion_matched`` null, which the prompt
        forbids in those words. The schema allowed it because the field is
        nullable, and nullable is right for the *harmful* case where no
        benignity clause applies.
        """
        out = []
        harm = self.harmfulness
        if harm is not None:
            if harm.verdict is Harmfulness.benign and not harm.criterion_matched:
                out.append(
                    "benign verdict with no criterion named; the prompt states "
                    "that is not acceptable"
                )
        feas = self.feasibility
        if feas.verdict is Feasibility.infeasible and not feas.blocking_element:
            out.append(
                "infeasible verdict with no blocking element named; nothing "
                "can be propagated to other candidates and the claim is "
                "uncheckable"
            )
        if feas.verdict is not Feasibility.infeasible and feas.blocking_element:
            out.append(
                "blocking element named on a verdict that is not infeasible"
            )
        return out

    @property
    def explanation(self) -> str:
        """The explanation, as a first-class output rather than a by-product."""
        parts = [self.feasibility.reasoning]
        if self.harmfulness is not None:
            parts.append(self.harmfulness.reasoning)
        return "\n\n".join(parts)
