"""Single-run and multi-run diagnostics (SPEC-text §4.8).

Two modes:

- **Single-run** (`single_run_summary`): one generated answer -> status counts and
  percentages over THAT run's claims. A single sample, so **no SE**.
- **Multi-run** (`aggregate_runset`): N runs of one condition -> per-run answer-level
  status fractions aggregated to **mean +/- SE across the N runs** (the SE of a
  proportion), plus **support-frequency** over stable KG-item IDs (entities,
  triplets) -- the fraction of the N runs in which each item was USED to ground a
  claim ("used" = lies on the support path of >= 1 grounded claim that run).

Claims are **NOT aligned across runs**; only stable KG-item IDs are. All across-run
spread is GENERATION variance (the verifier is deterministic). There is no
``absence_leverage`` / ``fabrication_induction`` scalar and no per-claim cross-run
alignment -- the withhold-from-context experiment is read as the distribution shift
across conditions (each condition aggregated separately). This module calls no model.
"""
from __future__ import annotations

import math

from ivg_kg.schema import (
    AnswerDiagnostics,
    ClaimRecord,
    ClaimStatus,
    GroundingRun,
    SingleRunStatusSummary,
    StatusMeanSE,
)

# The three grades, in fixed order.
_GRADES = [
    ClaimStatus.RETRIEVED.value,
    ClaimStatus.REASONED_SUPPORTABLE.value,
    ClaimStatus.FABRICATED.value,
]
_GROUNDED = {ClaimStatus.RETRIEVED.value, ClaimStatus.REASONED_SUPPORTABLE.value}


def triplet_key(subject_id: str, property_id: str, object_id: str | None) -> str:
    """Canonical triplet KG-item ID: "<subject_id>|<property_id>|<object_id>" (§4.8)."""
    return f"{subject_id}|{property_id}|{object_id}"


def claim_support_items(claim: ClaimRecord) -> set[str]:
    """KG-item IDs on this claim's support path (entities + triplets).

    Empty for a FABRICATED claim (no support path). For a grounded claim: the
    grounding_path's node ids (entities) plus a triplet key per path edge. A
    DIRECT_TRIPLE / TEXT_CONTENT claim carries its single supporting triple / node
    in grounding_path too (the mock populates it), so this reads uniformly.
    """
    if claim.status == ClaimStatus.FABRICATED:
        return set()
    items: set[str] = set(claim.grounding_path.node_ids)
    for e in claim.grounding_path.edges:
        items.add(triplet_key(e.subject_id, e.property_id, e.object_id))
    return items


def support_items_used(run: GroundingRun) -> set[str]:
    """All KG-item IDs used to ground >= 1 claim in this run."""
    used: set[str] = set()
    for claim in run.claims:
        used |= claim_support_items(claim)
    return used


def single_run_summary(run: GroundingRun) -> SingleRunStatusSummary:
    """Status counts + percentages for ONE run (no SE -- a single sample; §4.8)."""
    counts = dict.fromkeys(_GRADES, 0)
    for claim in run.claims:
        if claim.status.value in counts:
            counts[claim.status.value] += 1
    total = sum(counts.values()) or 1
    percentages = {g: counts[g] / total for g in _GRADES}
    return SingleRunStatusSummary(status_counts=counts, status_percentages=percentages)


def proportion_se(p: float, n: int) -> float:
    """SE of a proportion p over n runs: sqrt(p(1-p)/n) (§4.8). 0 when n<=0."""
    if n <= 0:
        return 0.0
    p = min(max(p, 0.0), 1.0)
    return math.sqrt(p * (1.0 - p) / n)


def _per_run_fraction(run: GroundingRun, status: str) -> float:
    total = len(run.claims) or 1
    return sum(1 for c in run.claims if c.status.value == status) / total


def aggregate_runset(runs: list[GroundingRun]) -> AnswerDiagnostics:
    """Aggregate the N runs of one condition into multi-run AnswerDiagnostics (§4.8).

    Per status: the per-run answer-level fraction, averaged across runs (mean), with
    the SE of that proportion. Support-frequency: per KG-item ID, the fraction of
    runs in which the item was used to ground a claim. Deterministic.
    """
    if not runs:
        raise ValueError("aggregate_runset requires at least one run")

    n = len(runs)
    question = runs[0].question

    status_distribution: dict[str, StatusMeanSE] = {}
    for grade in _GRADES:
        fracs = [_per_run_fraction(r, grade) for r in runs]
        mean = sum(fracs) / n
        status_distribution[grade] = StatusMeanSE(mean=mean, se=proportion_se(mean, n))

    # support-frequency: fraction of runs each KG-item was used to ground a claim
    use_counts: dict[str, int] = {}
    for r in runs:
        for item in support_items_used(r):
            use_counts[item] = use_counts.get(item, 0) + 1
    support_frequency = {item: c / n for item, c in use_counts.items()}

    return AnswerDiagnostics(
        question=question,
        n_runs=n,
        status_distribution=status_distribution,
        support_frequency=support_frequency,
    )
