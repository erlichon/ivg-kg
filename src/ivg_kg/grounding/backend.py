"""P0 grounding backend stub (SPEC-text §4.3, seam §3.1).

Defines the stable entry point for the grounding pipeline.  The two-graph
signature encodes the §3.2 invariant: the immutable GradingReference (full
KG + content labels, never ablated) is always passed separately from the
active_perturbations list that describes what was withheld from the generator.

TODO (GR9 / P1): replace the stub body with the real grounding implementation:
    - KG path search (GR3)
    - NLI / MiniCheck entailment gate (GR4)
    - Claim extraction and linking (GR8)
    - Full GroundingRun assembly
"""
from __future__ import annotations

from ivg_kg.schema import GradingReference, GroundingConfig, GroundingRun


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
        Never ablated — perturbations are encoded separately via
        ``active_perturbations``.
    active_perturbations:
        Ordered list of perturbation entry ids that were active when the
        answer was generated (used for per-claim attribution).
    config:
        Tunable pipeline parameters (k_hops, tau, linker, entailment).

    Returns
    -------
    GroundingRun
        A fully populated grounding run record.

    Raises
    ------
    NotImplementedError
        Always — P0 stub only.  Real implementation lands in GR9 (P1).
    """
    raise NotImplementedError("P0 stub — real grounding lands in GR9 (P1).")
