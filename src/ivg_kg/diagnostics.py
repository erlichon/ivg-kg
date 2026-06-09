"""Aggregate a RunSet into per-claim and answer diagnostics (SPEC-text §4.8).

A **RunSet** for a question = the N draws x the active conditions
(``list[GroundingRun]``, each tagged with ``condition`` + ``sample_index``).
This module groups draws by canonical ``claim_key`` and computes the structures
the Analytics panel renders (§4.5 #5/#6): the per-condition status mix (the
stacked-bar small-multiple), the FULL-condition stability scalar, and the RQ2
``absence_leverage`` / ``fabrication_induction`` per modality.

Classification is deterministic given a fixed answer text, so all variance here
is *generation* variance; *classifier* error is reported separately (Trust strip).
This is the books-spine aggregation used by the mock and (later) the real
precompute — it does NOT call any model.
"""
from __future__ import annotations

import math

from ivg_kg.schema import (
    ABSENT,
    AnswerDiagnostics,
    ClaimDiagnostics,
    ClaimStatus,
    Condition,
    GroundingRun,
)

# Real grounding statuses (the three grades); ABSENT is a pseudo-status.
_GROUNDED = {ClaimStatus.RETRIEVED.value, ClaimStatus.REASONED_SUPPORTABLE.value}
_STATUS_PRIORITY = [
    ClaimStatus.RETRIEVED.value,
    ClaimStatus.REASONED_SUPPORTABLE.value,
    ClaimStatus.FABRICATED.value,
]
# condition value -> modality name used in the leverage dicts
_CONDITION_MODALITY = {
    Condition.KNOWLEDGE_ABSENT.value: "knowledge",
    Condition.CONTENT_ABSENT.value: "content",
    Condition.IMAGE_ABSENT.value: "image",
}


def _draws_by_condition(runs: list[GroundingRun]) -> dict[str, list[GroundingRun]]:
    by_cond: dict[str, list[GroundingRun]] = {}
    for r in runs:
        by_cond.setdefault(r.condition.value, []).append(r)
    for cond in by_cond:
        by_cond[cond].sort(key=lambda r: r.sample_index)
    return by_cond


def _status_vector(draws: list[GroundingRun], claim_key: str) -> list[str]:
    """Per-draw status for one claim under one condition; ABSENT when missing."""
    out: list[str] = []
    for draw in draws:
        match = next((c for c in draw.claims if c.claim_key == claim_key), None)
        out.append(match.status.value if match is not None else ABSENT)
    return out


def _fractions(vector: list[str]) -> dict[str, float]:
    n = len(vector)
    if n == 0:
        return {}
    counts: dict[str, int] = {}
    for s in vector:
        counts[s] = counts.get(s, 0) + 1
    return {s: c / n for s, c in counts.items()}


def _p_grounded(vector: list[str]) -> float:
    if not vector:
        return 0.0
    return sum(1 for s in vector if s in _GROUNDED) / len(vector)


def _p_fabricated(vector: list[str]) -> float:
    if not vector:
        return 0.0
    fab = ClaimStatus.FABRICATED.value
    return sum(1 for s in vector if s == fab) / len(vector)


def _stability(full_vector: list[str]) -> float:
    """1 - H(p)/log K over the FULL draws (§4.8). 1.0 when fully reproducible."""
    fr = _fractions(full_vector)
    k = len(fr)
    if k <= 1:
        return 1.0
    entropy = -sum(p * math.log(p) for p in fr.values() if p > 0)
    return 1.0 - entropy / math.log(k)


def _modal(full_vector: list[str]) -> tuple[str, float]:
    """Most-common label under FULL (ties broken by status priority) + fraction."""
    fr = _fractions(full_vector)
    if not fr:
        return ClaimStatus.FABRICATED.value, 0.0
    best = max(
        fr.items(),
        key=lambda kv: (kv[1], -_priority_index(kv[0])),
    )
    return best[0], best[1]


def _priority_index(status: str) -> int:
    return _STATUS_PRIORITY.index(status) if status in _STATUS_PRIORITY else len(_STATUS_PRIORITY)


def _claim_keys_in_order(full_draws: list[GroundingRun]) -> list[str]:
    """claim_keys ordered by first appearance across the FULL draws."""
    seen: list[str] = []
    for draw in full_draws:
        for c in draw.claims:
            if c.claim_key and c.claim_key not in seen:
                seen.append(c.claim_key)
    return seen


def _representative(full_draws: list[GroundingRun], claim_key: str):
    for draw in full_draws:
        for c in draw.claims:
            if c.claim_key == claim_key:
                return c
    return None


def aggregate_runset(runs: list[GroundingRun]) -> AnswerDiagnostics:
    """Aggregate a RunSet (list of GroundingRun draws) into AnswerDiagnostics.

    Deterministic: identical input -> identical output. Requires every claim to
    carry a ``claim_key`` (claims without one are ignored for grouping).
    """
    if not runs:
        raise ValueError("aggregate_runset requires at least one run")

    by_cond = _draws_by_condition(runs)
    full_draws = by_cond.get(Condition.FULL.value, [])
    if not full_draws:
        raise ValueError("RunSet must contain at least one FULL-condition draw")

    question = full_draws[0].question
    n_full = len(full_draws)
    claim_keys = _claim_keys_in_order(full_draws)

    claim_diags: list[ClaimDiagnostics] = []
    for key in claim_keys:
        rep = _representative(full_draws, key)
        if rep is None:
            continue

        status_by_condition: dict[str, dict[str, float]] = {}
        vectors: dict[str, list[str]] = {}
        for cond, draws in by_cond.items():
            vec = _status_vector(draws, key)
            vectors[cond] = vec
            status_by_condition[cond] = _fractions(vec)

        full_vec = vectors[Condition.FULL.value]
        modal_status, modal_fraction = _modal(full_vec)

        absence_leverage: dict[str, float] = {}
        fabrication_induction: dict[str, float] = {}
        p_grounded_full = _p_grounded(full_vec)
        p_fab_full = _p_fabricated(full_vec)
        for cond, vec in vectors.items():
            modality = _CONDITION_MODALITY.get(cond)
            if modality is None:
                continue
            absence_leverage[modality] = round(p_grounded_full - _p_grounded(vec), 4)
            fabrication_induction[modality] = round(_p_fabricated(vec) - p_fab_full, 4)

        claim_diags.append(
            ClaimDiagnostics(
                claim_key=key,
                text=rep.text,
                status=ClaimStatus(modal_status) if modal_status in _STATUS_PRIORITY else rep.status,
                support_source=rep.support_source,
                stability=round(_stability(full_vec), 4),
                modal_status=ClaimStatus(modal_status)
                if modal_status in _STATUS_PRIORITY
                else rep.status,
                modal_fraction=round(modal_fraction, 4),
                n_full=n_full,
                status_by_condition=status_by_condition,
                absence_leverage=absence_leverage,
                fabrication_induction=fabrication_induction,
                spurious_path=rep.spurious_path,
                spurious_reason=rep.spurious_reason,
            )
        )

    # Answer-level distribution as the MEAN +/- STD of the per-draw status
    # fraction over the N FULL draws — the three-grade column chart with error
    # bars (#5). Per draw, fraction = (#claims of status) / (#emitted claims).
    per_draw: dict[str, list[float]] = {s: [] for s in _STATUS_PRIORITY}
    for draw in full_draws:
        statuses = [c.status.value for c in draw.claims]
        emitted = len(statuses) or 1
        for s in _STATUS_PRIORITY:
            per_draw[s].append(statuses.count(s) / emitted)

    def _mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    def _std(xs: list[float]) -> float:
        if not xs:
            return 0.0
        m = _mean(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))  # population std

    dist = {s: round(_mean(per_draw[s]), 4) for s in _STATUS_PRIORITY}
    dist_std = {s: round(_std(per_draw[s]), 4) for s in _STATUS_PRIORITY}
    fab = ClaimStatus.FABRICATED.value

    return AnswerDiagnostics(
        question=question,
        n_generations=n_full,
        status_distribution=dist,
        status_distribution_std=dist_std,
        fabrication_rate=dist[fab],
        fabrication_rate_std=dist_std[fab],
        claim_diagnostics=claim_diags,
    )
