"""Grounding backend entry point (SPEC-text sec 4.3, seam sec 3.1).

Defines the stable public entry point for the grounding pipeline.  The two-
graph signature encodes the sec 3.2 invariant: the immutable GradingReference
(full KG + content labels, never ablated) is always passed separately from the
active_perturbations list that describes what was withheld from the generator.

Real implementation (GR9): wires the real verifier-side pipeline behind the
stable ground_response signature:

    extract  (GR5)  rule-based -> structured (head, relation, tail) claims
    link     (GR6)  label/alias index -> claim entities resolved to KG QIDs
    classify (GR8)  three-way cascade over the FULL reference + entailment gate

The classifier, linker, canon, and gate are constructed ONCE per call (not per
claim) so the NetworkX graph and the gate score cache stay warm across claims.
This replaces the earlier slice stand-in (ivg_kg.grounding.slice.run_cascade),
which remains in place as a tested reference component but is no longer used
here.  Grading is ALWAYS against the full reference; active_perturbations is
attribution metadata only and never alters a decision (Invariant #1).
"""
from __future__ import annotations

import uuid

from ivg_kg.data.reference import reference_id
from ivg_kg.grounding.classify import Classifier
from ivg_kg.grounding.entailment import make_entailment_gate
from ivg_kg.grounding.extract import make_extractor
from ivg_kg.grounding.link import PropertyCanon, make_entity_linker
from ivg_kg.schema import (
    ClaimRecord,
    ClaimStatus,
    GradingReference,
    GroundingConfig,
    GroundingRun,
    LinkedEntity,
)

# Minimum link_score required to accept a head/tail endpoint for multi-hop path
# derivation.  The LabelAliasIndex containment score is
#   len(norm_label) / max(len(norm_label), len(norm_mention))
# so a short node label inside a long span (e.g. "in" matching a 40-char tail)
# can score well below 0.5.  Exact matches score 1.0 and are always accepted.
# 0.5 is chosen as a documented threshold that: (a) passes canonical short
# titles like "Blue Lantern" (score ~1.0 via exact or near-exact match) and
# "DTP(NN)" (exact match -> 1.0), (b) rejects junk containment matches where
# a short label is a substring of a long arbitrary surface span.
MIN_HEAD_TAIL_LINK_SCORE: float = 0.5


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
        Tunable pipeline parameters (k_hops, tau, linker, entailment,
        extractor).

    Returns
    -------
    GroundingRun
        A fully populated grounding run record.
    """
    # Build the pipeline components ONCE per call (not per claim): the linker
    # index, canon table, entailment gate, and classifier graph are all reused
    # across every extracted claim.
    extractor = make_extractor(config.extractor)
    linker = make_entity_linker(config.linker, reference.snapshot)
    canon = PropertyCanon.load()
    gate = make_entailment_gate(config)
    classifier = Classifier(reference, gate=gate, canon=canon, config=config)

    extracted = extractor.extract(answer_text)
    claims: list[ClaimRecord] = []
    for i, claim in enumerate(extracted):
        claim_id = f"c{i + 1}"

        # Resolve linked entities. head/tail give precision for path endpoints;
        # link_text catches mentions the structured parse missed. Dedup by id,
        # preserve discovery order (head, tail, then link_text matches).
        linked: list[LinkedEntity] = []
        seen_ids: set[str] = set()
        unresolved: list[str] = []

        # head/tail are ENDPOINT mentions for path derivation: accept only
        # reliable links (exact match -> score 1.0, or near-exact title match
        # above MIN_HEAD_TAIL_LINK_SCORE).  A sub-threshold link means the
        # label is merely a substring of a long arbitrary span (e.g. "in" inside
        # "in a small apartment during the Great Depression") and would feed a
        # junk multi-hop endpoint.  Sub-threshold links are silently dropped
        # here; link_text() below provides broader mention coverage via
        # label-in-text overlap matches (score always 1.0) and also populates
        # unresolved, so we do not add rejected head/tail mentions to unresolved.
        for mention in (claim.head, claim.tail):
            if not mention:
                continue
            entity = linker.link(mention)
            if entity is not None and entity.link_score >= MIN_HEAD_TAIL_LINK_SCORE:
                if entity.id not in seen_ids:
                    seen_ids.add(entity.id)
                    linked.append(entity)
            elif entity is None and mention not in unresolved:
                unresolved.append(mention)

        text_linked, text_unresolved = linker.link_text(claim.text)
        for entity in text_linked:
            if entity.id not in seen_ids:
                seen_ids.add(entity.id)
                linked.append(entity)
        for token in text_unresolved:
            if token not in unresolved:
                unresolved.append(token)

        record = classifier.classify(
            claim.text,
            linked,
            claim_id=claim_id,
            relation_surface=claim.relation or None,
            object_surface=claim.tail or None,
            active_perturbations=list(active_perturbations),
            unresolved_entities=unresolved,
        )
        claims.append(record)

    ref_id = reference_id(reference)
    run_id = str(uuid.uuid4())

    total = len(claims)
    if total > 0:
        fabricated = sum(1 for c in claims if c.status == ClaimStatus.FABRICATED)
        # text/image axes are out of P0 books scope; structure = fabricated / total.
        error_rates = {"structure": fabricated / total, "text": 0.0, "image": 0.0}
    else:
        # text/image axes are out of P0 books scope; structure = fabricated / total.
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
