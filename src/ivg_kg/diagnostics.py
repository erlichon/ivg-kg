"""Aggregate a RunSet into per-slot and answer diagnostics (SPEC-text §4.8).

A **RunSet** for a question = the **N generation draws x the active conditions**
(``list[GroundingRun]``, each tagged with ``condition`` + ``sample_index``). The
N per-condition draws are the stochastic GENERATOR sampled N times under each
ablation; the verifier that grades them is deterministic and always grades
against the full KG, so all within-condition spread is GENERATION variance, not
repeated grading.

Because the verifier is deterministic AND grades against the full KG, a VARIANT
(a fixed head+relation+value) has exactly one status, invariant across draws and
conditions. So ``stability`` / ``absence_leverage`` / ``fabrication_induction``
are degenerate at the variant level and are computed at the **SLOT** level
(``slot_key`` = head+relation): per draw the outcome is the status of whichever
variant filled the slot (or ``absent``), and that outcome varies because the
generator picks different variants. This module groups draws by ``slot_key`` and
emits the structures the Analytics panel renders (§4.5 #5/#6). It does NOT call
any model; the verifier's systematic *error* is reported separately (Trust strip).
"""
from __future__ import annotations

import math

from ivg_kg.schema import (
    ABSENT,
    AnswerDiagnostics,
    ClaimDiagnostics,
    ClaimRecord,
    ClaimStatus,
    Condition,
    GroundingRun,
    VariantStat,
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


def _variant_value(claim: ClaimRecord) -> str:
    """The normalized value of the variant = claim_key with its slot_key prefix stripped."""
    key = claim.claim_key or ""
    if claim.slot_key and key.startswith(claim.slot_key + "|"):
        return key[len(claim.slot_key) + 1 :]
    return key


def _slot_claims_in_draw(draw: GroundingRun, slot_key: str) -> list[ClaimRecord]:
    return [c for c in draw.claims if c.slot_key == slot_key]


def _slot_outcome(draw: GroundingRun, slot_key: str) -> str:
    """The slot's per-draw outcome: the filling variant's status, or ABSENT.

    If a draw asserts more than one variant of the slot (intra-answer
    contradiction), the highest-priority status is taken as the outcome.
    """
    matches = _slot_claims_in_draw(draw, slot_key)
    if not matches:
        return ABSENT
    return min(matches, key=lambda c: _priority_index(c.status.value)).status.value


def _outcome_vector(draws: list[GroundingRun], slot_key: str) -> list[str]:
    return [_slot_outcome(draw, slot_key) for draw in draws]


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


def _presence_rate(vector: list[str]) -> float:
    """Fraction of draws the slot is filled at all (1 - P[absent])."""
    if not vector:
        return 0.0
    return sum(1 for s in vector if s != ABSENT) / len(vector)


def _stability(full_vector: list[str]) -> float:
    """1 - H(p)/log K over the FULL-draw outcomes (§4.8). 1.0 = fully reproducible."""
    fr = _fractions(full_vector)
    k = len(fr)
    if k <= 1:
        return 1.0
    entropy = -sum(p * math.log(p) for p in fr.values() if p > 0)
    return 1.0 - entropy / math.log(k)


def _modal(full_vector: list[str]) -> tuple[str, float]:
    """Most-common outcome under FULL (ties broken by status priority) + fraction."""
    fr = _fractions(full_vector)
    if not fr:
        return ABSENT, 0.0
    best = max(
        fr.items(),
        key=lambda kv: (kv[1], -_priority_index(kv[0])),
    )
    return best[0], best[1]


def _priority_index(status: str) -> int:
    return _STATUS_PRIORITY.index(status) if status in _STATUS_PRIORITY else len(_STATUS_PRIORITY)


def _slot_keys_in_order(full_draws: list[GroundingRun]) -> list[str]:
    """slot_keys ordered by first appearance across the FULL draws."""
    seen: list[str] = []
    for draw in full_draws:
        for c in draw.claims:
            if c.slot_key and c.slot_key not in seen:
                seen.append(c.slot_key)
    return seen


def _representative(full_draws: list[GroundingRun], slot_key: str) -> ClaimRecord | None:
    """A representative claim for the slot (first FULL-draw occurrence)."""
    for draw in full_draws:
        for c in draw.claims:
            if c.slot_key == slot_key:
                return c
    return None


def _variant_stats(
    by_cond: dict[str, list[GroundingRun]], slot_key: str
) -> list[VariantStat]:
    """Per-variant breakdown for a slot: each value's fixed status + per-condition counts.

    Variants are ordered by total draw count (descending), then by status
    priority — so the dominant variant leads the breakdown. Deterministic.
    """
    # (value, status) -> {condition -> count}; plus a representative text per value.
    freq: dict[tuple[str, str], dict[str, int]] = {}
    text_by_value: dict[str, str] = {}
    first_seen: dict[tuple[str, str], int] = {}
    order = 0
    for cond, draws in by_cond.items():
        for draw in draws:
            for c in _slot_claims_in_draw(draw, slot_key):
                value = _variant_value(c)
                vk = (value, c.status.value)
                if vk not in freq:
                    freq[vk] = {}
                    first_seen[vk] = order
                    order += 1
                freq[vk][cond] = freq[vk].get(cond, 0) + 1
                text_by_value.setdefault(value, c.text)

    def _total(vk: tuple[str, str]) -> int:
        return sum(freq[vk].values())

    # Read order: by status grade (retrieved -> supportable -> fabricated), then
    # most-frequent variant first, then first-seen — stable and deterministic.
    variant_keys = sorted(
        freq,
        key=lambda vk: (_priority_index(vk[1]), -_total(vk), first_seen[vk]),
    )
    return [
        VariantStat(
            normalized_value=value,
            status=ClaimStatus(status),
            text=text_by_value.get(value, ""),
            draw_frequency=dict(freq[(value, status)]),
        )
        for (value, status) in variant_keys
    ]


def _intra_answer_contradiction(full_draws: list[GroundingRun], slot_key: str) -> bool:
    """True if any single FULL draw asserts two distinct variants of the slot."""
    for draw in full_draws:
        values = {_variant_value(c) for c in _slot_claims_in_draw(draw, slot_key)}
        if len(values) > 1:
            return True
    return False


def aggregate_runset(runs: list[GroundingRun]) -> AnswerDiagnostics:
    """Aggregate a RunSet (the N generation draws x conditions) into AnswerDiagnostics.

    Deterministic: identical input -> identical output. Diagnostics are anchored
    on ``slot_key``; every claim must carry one (claims without a slot are ignored
    for slot grouping).
    """
    if not runs:
        raise ValueError("aggregate_runset requires at least one run")

    by_cond = _draws_by_condition(runs)
    full_draws = by_cond.get(Condition.FULL.value, [])
    if not full_draws:
        raise ValueError("RunSet must contain at least one FULL-condition draw")

    question = full_draws[0].question
    n_full = len(full_draws)
    slot_keys = _slot_keys_in_order(full_draws)

    claim_diags: list[ClaimDiagnostics] = []
    for slot in slot_keys:
        rep = _representative(full_draws, slot)
        if rep is None:
            continue

        status_by_condition: dict[str, dict[str, float]] = {}
        vectors: dict[str, list[str]] = {}
        for cond, draws in by_cond.items():
            vec = _outcome_vector(draws, slot)
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

        # modal outcome may be ABSENT; surface a status for the chip via priority.
        modal_cs = (
            ClaimStatus(modal_status)
            if modal_status in _STATUS_PRIORITY
            else (rep.status if rep.status.value in _STATUS_PRIORITY else ClaimStatus.FABRICATED)
        )

        claim_diags.append(
            ClaimDiagnostics(
                slot_key=slot,
                text=rep.text,
                presence_rate=round(_presence_rate(full_vec), 4),
                variants=_variant_stats(by_cond, slot),
                intra_answer_contradiction=_intra_answer_contradiction(full_draws, slot),
                stability=round(_stability(full_vec), 4),
                modal_status=modal_cs,
                modal_fraction=round(modal_fraction, 4),
                n_full=n_full,
                status_by_condition=status_by_condition,
                absence_leverage=absence_leverage,
                fabrication_induction=fabrication_induction,
                spurious_path=rep.spurious_path,
                spurious_reason=rep.spurious_reason,
            )
        )

    # Answer-level distribution: fraction of claims in each grade over the N FULL
    # draws — the three-grade column chart (#5). Per draw, fraction = (#claims of
    # status) / (#emitted claims). This varies across draws because GENERATION
    # varies (which slots are filled by which variants); the error bars in the
    # chart are the SE of the proportion, not a per-draw std (§4.8).
    per_draw: dict[str, list[float]] = {s: [] for s in _STATUS_PRIORITY}
    for draw in full_draws:
        statuses = [c.status.value for c in draw.claims]
        emitted = len(statuses) or 1
        for s in _STATUS_PRIORITY:
            per_draw[s].append(statuses.count(s) / emitted)

    def _mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    # Not rounded: the three grades then sum to exactly 1.0 (within float epsilon).
    dist = {s: _mean(per_draw[s]) for s in _STATUS_PRIORITY}
    fab = ClaimStatus.FABRICATED.value

    return AnswerDiagnostics(
        question=question,
        n_generations=n_full,
        status_distribution=dist,
        fabrication_rate=dist[fab],
        claim_diagnostics=claim_diags,
    )
