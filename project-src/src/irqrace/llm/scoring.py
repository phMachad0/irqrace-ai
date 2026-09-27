"""The four numbers this stage is judged by.

From ``wiki/LLM Stage Design.md``, *Testing and evaluation*, in its order:

1. **Recall gate.** Every annotated bug point must survive triage in a reported
   bucket. A bug point ranked ``likely_infeasible`` is a design failure, not a
   tuning issue, and is reportable as such.
2. **Trap rejection.** How many of the planted traps are correctly bucketed low.
   This is the precision measure, and unlike precision it **cannot be gamed by
   dropping candidates** -- which is the whole reason it is the one used here.
3. **Inspection Ratio.** The fraction of the candidate set a reviewer must read,
   in rank order, before having seen every real defect. From
   [[Reducing False Alarms (paper)]] via ``wiki/concepts/Precision Metrics.md``.
4. **Consistency.** Agreement across n runs of the same candidate. [[LLift
   (paper)]] found decomposition and self-validation improved consistency
   independently of accuracy; an unstable verdict is not a usable result.

:func:`score` also enforces the invariant the whole project rests on: the
triaged set must contain **exactly** the candidates that went in. Nothing in
this package is permitted to drop one, and a silent drop here would be
invisible in every number above -- recall would stay high precisely because the
lost candidate stopped being counted.
"""

from __future__ import annotations

import collections
import dataclasses

from irqrace.llm.fixtures import Fixture
from irqrace.llm.verdict import (
    INSPECTION_ORDER,
    Bucket,
    Feasibility,
    Harmfulness,
    Triage,
    bucket_of,
)

#: Buckets that count as "rejected" for trap rejection. Note that
#: ``likely_benign`` counts: a trap correctly identified as harmless is
#: correctly handled, even though it was not called infeasible.
LOW_BUCKETS = frozenset({Bucket.likely_infeasible, Bucket.likely_benign})


def scoring_bucket(triage: Triage, harm_scored: bool = True) -> Bucket:
    """The bucket a candidate is *scored* in, which is not always the one reported.

    With ``harm_scored`` off, only the feasibility answer counts: a feasible
    candidate scores as ``likely_real`` whatever the harmfulness answer said.
    This is the view for [[Racebench]] (decided 2026-09-27, option C in
    ``log.md``). The suite annotates atomicity violations as **program facts**
    -- the interleaving exists -- and many of its readers copy the shared value
    into a local that is never used. A model that calls those benign is
    reasoning correctly, and scoring its harmfulness answer against this ground
    truth punishes the correct answer. So on Racebench the harmfulness verdict is
    still asked, still recorded and still reported, but not scored; it is judged
    on the real-world suite, where the code does something.

    The reported bucket (:attr:`Triage.bucket`) never changes. This is a view
    for measurement, not a second decision policy.
    """
    if harm_scored:
        return triage.bucket
    if triage.feasibility.verdict is Feasibility.feasible:
        # Treat the harm axis as settled in the benchmark's own terms: an
        # interleaving that exists is the annotated defect.
        return bucket_of(Feasibility.feasible, Harmfulness.harmful)
    return bucket_of(triage.feasibility.verdict, None)


def scoring_rank_key(triage: Triage, harm_scored: bool = True) -> tuple[int, float]:
    """Rank order under :func:`scoring_bucket`. Confidence follows the same view:
    without the harm axis, only feasibility confidence breaks ties."""
    if harm_scored:
        return triage.rank_key
    bucket = scoring_bucket(triage, harm_scored=False)
    return (INSPECTION_ORDER.index(bucket), -triage.feasibility.confidence)


class RecallFailure(AssertionError):
    """A bug point was ranked ``likely_infeasible``. Reportable, not catchable."""


@dataclasses.dataclass(frozen=True)
class Score:
    n_candidates: int
    n_bug_points: int
    n_traps: int

    recall: float
    missed: tuple[str, ...]
    trap_rejection: float
    traps_kept_high: tuple[str, ...]
    inspection_ratio: float
    bucket_counts: dict[str, int]
    #: Candidates the row was supposed to cover, including any the backend
    #: refused or failed on. ``n_candidates`` counts only those actually
    #: scored, so the two differ exactly when something was excluded.
    n_expected: int = 0
    #: Whether the harmfulness answer counted. See :func:`scoring_bucket`.
    #: ``bucket_counts`` always shows the buckets as *reported*, so the harm
    #: answers stay visible even when they are not scored.
    harm_scored: bool = True

    @property
    def coverage(self) -> float:
        """Share of the intended candidate set that was actually scored."""
        return self.n_candidates / self.n_expected if self.n_expected else 1.0

    @property
    def complete(self) -> bool:
        return self.coverage >= 1.0

    @property
    def gate_passed(self) -> bool:
        """Passing requires a **complete** row, not merely no misses.

        Two ways this reported green having measured almost nothing, both
        reached in practice rather than imagined:

        * Recall over an empty set is 1.0, so a row where every candidate was
          excluded looked like a pass. Requiring ``n_bug_points > 0`` fixed
          that — and was not enough.
        * A row that scored 3 of 20 after the endpoint rate-limited eleven
          candidates and DNS dropped six then reported "PASS, 3/3 bug points"
          and "trap rejection 100% (0/0)". Three bug points satisfy the first
          guard, and trap rejection over zero traps is vacuously perfect.

        So a partial row does not pass. Its numbers are real but they describe
        whichever candidates happened to survive, which is not a sample of
        anything.
        """
        return self.n_bug_points > 0 and self.recall == 1.0 and self.complete

    def report(self) -> str:
        gate = "PASS" if self.gate_passed else "FAIL"
        lines = []
        if not self.complete:
            lines.append(
                f"INCOMPLETE — {self.n_candidates}/{self.n_expected} candidates "
                f"scored ({self.coverage:.0%}). The figures below describe the "
                f"survivors, not the set; this row is not a measurement."
            )
        lines += [
            f"recall gate:      {gate} — {self.recall:.1%} "
            f"({self.n_bug_points - len(self.missed)}/{self.n_bug_points} bug points "
            f"survived triage)",
            (
                "trap rejection:   n/a — no traps were scored"
                if self.n_traps == 0
                else f"trap rejection:   {self.trap_rejection:.1%} "
                f"({self.n_traps - len(self.traps_kept_high)}/{self.n_traps} traps bucketed low)"
            ),
            f"inspection ratio: {self.inspection_ratio:.1%} "
            f"({self._to_read()}/{self.n_candidates} candidates read to find them all)",
            "buckets reported: "
            + ", ".join(
                f"{b.value}={self.bucket_counts.get(b.value, 0)}"
                for b in INSPECTION_ORDER
            ),
        ]
        if not self.harm_scored:
            lines.append(
                "harmfulness:      asked and reported, not scored — feasibility "
                "alone decides the figures above (Racebench annotates program facts)"
            )
        if self.missed:
            lines.append(
                "  [!] ranked likely_infeasible: " + ", ".join(self.missed)
            )
        return "\n".join(lines)

    def _to_read(self) -> int:
        return round(self.inspection_ratio * self.n_candidates)


def score(
    fixtures: list[Fixture],
    triages: list[Triage],
    n_expected: int | None = None,
    *,
    harm_scored: bool = True,
) -> Score:
    """Score one row of the ablation.

    :param n_expected: how many candidates the row was meant to cover. Pass
        the full fixture count when some were excluded, so the result knows it
        is partial; omitting it assumes ``fixtures`` is the whole set.
    :param harm_scored: whether the harmfulness answer counts toward the
        figures. Off for Racebench -- see :func:`scoring_bucket`.

    :raises ValueError: if the triaged set is not exactly the input set. This
        is the no-drop invariant, checked rather than assumed.
    """
    by_id = {t.candidate_id: t for t in triages}
    expected = {f.candidate_id for f in fixtures}
    got = set(by_id)

    if got != expected:
        missing = sorted(expected - got)
        extra = sorted(got - expected)
        raise ValueError(
            "the triaged set does not match the input set — the LLM stage may "
            "never drop a candidate.\n"
            f"  dropped: {missing or 'none'}\n"
            f"  invented: {extra or 'none'}"
        )

    bug_points = [f for f in fixtures if f.is_real]
    traps = [f for f in fixtures if not f.is_real]

    missed = tuple(
        f.candidate_id
        for f in bug_points
        if scoring_bucket(by_id[f.candidate_id], harm_scored)
        is Bucket.likely_infeasible
    )
    recall = (
        (len(bug_points) - len(missed)) / len(bug_points) if bug_points else 1.0
    )

    kept_high = tuple(
        f.candidate_id
        for f in traps
        if scoring_bucket(by_id[f.candidate_id], harm_scored) not in LOW_BUCKETS
    )
    trap_rejection = (
        (len(traps) - len(kept_high)) / len(traps) if traps else 1.0
    )

    counts = collections.Counter(t.bucket.value for t in triages)

    return Score(
        n_candidates=len(fixtures),
        n_expected=len(fixtures) if n_expected is None else n_expected,
        n_bug_points=len(bug_points),
        n_traps=len(traps),
        recall=recall,
        missed=missed,
        trap_rejection=trap_rejection,
        traps_kept_high=kept_high,
        inspection_ratio=inspection_ratio(fixtures, triages, harm_scored=harm_scored),
        bucket_counts=dict(counts),
        harm_scored=harm_scored,
    )


def inspection_ratio(
    fixtures: list[Fixture], triages: list[Triage], *, harm_scored: bool = True
) -> float:
    """Fraction of the ranked list a reviewer reads to see every real defect.

    Ranking is by :attr:`Triage.rank_key` -- bucket order, then confidence, then
    bug points last among exact ties (pessimistic, so the figure never depends
    on how candidate ids happen to sort). The
    ratio is the 1-based position of the *last* bug point in that order divided
    by the total, so a single bug point sunk to the bottom costs the full 100%.
    That sharpness is the point: it is what distinguishes this from precision,
    which would barely move.

    Returns 0.0 when there are no bug points to find.
    """
    by_id = {t.candidate_id: t for t in triages}
    real = {f.candidate_id for f in fixtures if f.is_real}
    if not real:
        return 0.0

    # Ties -- same bucket, same confidence -- put bug points *after* the other
    # candidates they tie with: the worst case for the reviewer. Breaking them by
    # candidate id, as this did until 2026-09-27, ordered them by a hash, and on
    # the `+domain` row that alone moved the ratio anywhere between 60% and 75%.
    ordered = sorted(
        (f.candidate_id for f in fixtures),
        key=lambda cid: (scoring_rank_key(by_id[cid], harm_scored), cid in real, cid),
    )
    last = max(i for i, cid in enumerate(ordered, start=1) if cid in real)
    return last / len(ordered)


def vote(runs: list[list[Triage]]) -> list[Triage]:
    """Collapse n runs into one verdict per candidate, recall-biased on ties.

    ``wiki/LLM Stage Design.md`` lists majority voting under mechanics. The
    detail that matters is the tie-break, and it is not "pick one": a tie
    between ``likely_real`` and ``likely_infeasible`` resolves to the bucket
    **earlier in inspection order**, which costs a reviewer a candidate rather
    than hiding one. Resolving ties toward the lower bucket would reintroduce,
    through the voting layer, exactly the recall loss the decision policy
    forbids at the verdict layer.

    The returned :class:`Triage` is the winning run's, so its explanation is
    one a model actually gave rather than a synthesis of several.
    """
    if not runs:
        raise ValueError("no runs to vote over")

    by_candidate: dict[str, list[Triage]] = collections.defaultdict(list)
    for run in runs:
        for t in run:
            by_candidate[t.candidate_id].append(t)

    out = []
    for triages in by_candidate.values():
        counts = collections.Counter(t.bucket for t in triages)
        top = max(counts.values())
        tied = [b for b, n in counts.items() if n == top]
        winner = min(tied, key=INSPECTION_ORDER.index)
        # Among runs that chose the winning bucket, keep the most confident,
        # so the reported explanation is the strongest statement of it.
        out.append(
            max(
                (t for t in triages if t.bucket is winner),
                key=lambda t: -t.rank_key[1],
            )
        )
    return out


def blocking_element_groups(triages: list[Triage]) -> dict[str, list[str]]:
    """Group candidates by the element a model said makes them infeasible.

    [[IRIS (paper)]]'s pruning, adapted to a pipeline that may not drop. IRIS
    asks *which element* is spurious when the model rejects a candidate and
    propagates that to every other candidate involving it, removing them. Here
    nothing is removed -- the rule forbids it -- so the same information is
    used the other way: candidates sharing a blocking element are reported as
    a group, because a reviewer who checks one has effectively checked all of
    them.

    That improves Inspection Ratio without touching recall, which is the only
    form of pruning this design permits. Groups of one are omitted.
    """
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for t in triages:
        element = t.feasibility.blocking_element
        if element:
            groups[element.strip()].append(t.candidate_id)
    return {k: v for k, v in sorted(groups.items()) if len(v) > 1}


def consistency(runs: list[list[Triage]]) -> dict[str, float]:
    """Per-candidate agreement across n runs, plus the mean.

    Agreement is the share of runs landing on the modal bucket. A candidate
    answered identically every time scores 1.0; one split evenly across two
    buckets over four runs scores 0.5.
    """
    if len(runs) < 2:
        raise ValueError("consistency needs at least two runs")

    per_candidate: dict[str, list[Bucket]] = collections.defaultdict(list)
    for run in runs:
        for t in run:
            per_candidate[t.candidate_id].append(t.bucket)

    out: dict[str, float] = {}
    for cid, buckets in per_candidate.items():
        modal = collections.Counter(buckets).most_common(1)[0][1]
        out[cid] = modal / len(buckets)

    out["__mean__"] = sum(v for k, v in out.items() if k != "__mean__") / len(
        per_candidate
    )
    return out
