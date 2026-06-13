"""Grounding backend entry point (SPEC-text §4.3, seam §3.1).

Defines the stable public entry point for the grounding pipeline.  The two-
graph signature encodes the §3.2 invariant: the immutable GradingReference
(full KG + content labels, never ablated) is always passed separately from the
active_perturbations list that describes what was withheld from the generator.

Slice (#1a) implementation: delegates to ivg_kg.grounding.slice.run_cascade,
which provides simple-but-real claim splitting, label-based linking, token-
overlap entailment, and the §4.3(C) cascade.  Each component is marked as a
SLICE stand-in and will be deepened/replaced by GR5/GR6/GR7/GR8 in GR9/P1.
"""
from __future__ import annotations

import uuid

from ivg_kg.data.reference import reference_id
from ivg_kg.grounding.slice import run_cascade
from ivg_kg.schema import ClaimStatus, GradingReference, GroundingConfig, GroundingRun


def ground_response(
    question: str,
    answer_text: str,
    reference: GradingReference,
    *,
    active_perturbations: list[str],
    config: GroundingConfig,
) -> GroundingRun:
    """Ground an answer against the full reference KG.

    Parameters
    ----------
    question:
        The question posed to the generative model.
    answer_text:
        The model's raw answer text to be grounded.
    reference:
        The immutable full grading reference (KG-full + content labels).
        Never ablated -- perturbations are encoded separately via
        ``active_perturbations``.
    active_perturbations:
        Ordered list of perturbation entry ids that were active when the
        answer was generated (used for per-claim attribution only; does NOT
        change grading -- Invariant #1).
    config:
        Tunable pipeline parameters (k_hops, tau, linker, entailment).

    Returns
    -------
    GroundingRun
        A fully populated grounding run record.
    """
    claims = run_cascade(
        question,
        answer_text,
        reference,
        active_perturbations=active_perturbations,
        config=config,
    )

    ref_id = reference_id(reference)
    run_id = str(uuid.uuid4())

    total = len(claims)
    if total > 0:
        fabricated = sum(1 for c in claims if c.status == ClaimStatus.FABRICATED)
        error_rates = {"structure": fabricated / total, "text": 0.0, "image": 0.0}
    else:
        error_rates = {"structure": 0.0, "text": 0.0, "image": 0.0}

    return GroundingRun(
        run_id=run_id,
        question=question,
        answer_text=answer_text,
        slice=reference.snapshot.slice,
        phase="A",
        claims=claims,
        active_perturbations=list(active_perturbations),
        grading_reference_id=ref_id,
        error_rates=error_rates,
    )
