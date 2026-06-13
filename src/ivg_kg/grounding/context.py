"""
GR3: Context assembly -- the SOLE ablation site (SPEC-text 3.2 / 4.3).

build_full_context  - builds the UN-ablated GenerationContext for an entity,
                      sourced from the GradingReference (SPEC-text 4.1).
assemble_context    - builds the full context then applies perturbations in
                      the supplied order (full -> p0.withhold -> p1.withhold
                      -> ...).  This is the ONLY location in the codebase
                      where withhold() is called.

Invariants enforced here:
  - The GradingReference is never modified or returned.
  - build_full_context performs NO ablation.
  - All ablation in assemble_context is done exclusively via Perturbation.withhold.
  - All outputs are freshly constructed; no input list/object is aliased.
  - Deterministic: no I/O, no randomness, no time, no network.
"""

from __future__ import annotations

from collections.abc import Sequence

from ivg_kg.perturbation.base import Perturbation
from ivg_kg.schema import GenerationContext, GradingReference, KGEdge, KGNode, Modality

__all__ = ["build_full_context", "assemble_context"]


def _node_for(reference: GradingReference, entity_id: str) -> KGNode:
    """Return the KGNode for entity_id, or raise KeyError if absent."""
    for node in reference.snapshot.nodes:
        if node.id == entity_id:
            return node
    raise KeyError(f"entity_id {entity_id!r} not in reference snapshot")


def _outgoing_triples(reference: GradingReference, entity_id: str) -> list[KGEdge]:
    """Return edges whose subject_id matches entity_id, in snapshot order."""
    return [edge for edge in reference.snapshot.edges if edge.subject_id == entity_id]


def _assemble_description(reference: GradingReference, entity_id: str, node: KGNode) -> str | None:
    """Build the description string from node.description + TEXT content labels.

    Algorithm (SPEC-text 4.1):
      1. Start with node.description if non-null and non-empty (stripped).
      2. Append each TEXT-modality ContentLabel fact for this entity, in list
         order, skipping any fact already present as a substring of accumulated.
         NOTE: the substring dedup match is CASE-SENSITIVE; a change to casefold
         must be a conscious decision.
      3. Join pieces with ". ".  Return None if nothing accumulated.
    """
    pieces: list[str] = []
    accumulated = ""

    node_desc = node.description
    if node_desc is not None:
        stripped = node_desc.strip()
        if stripped:
            pieces.append(stripped)
            accumulated = stripped

    for label in reference.content_labels:
        if label.entity_id != entity_id:
            continue
        if label.modality != Modality.TEXT:
            continue
        fact = label.fact
        if fact in accumulated:
            continue
        pieces.append(fact)
        accumulated = (accumulated + ". " + fact) if accumulated else fact

    if not pieces:
        return None
    return ". ".join(pieces)


def build_full_context(reference: GradingReference, entity_id: str) -> GenerationContext:
    """Build the UN-ablated GenerationContext for entity_id from reference.

    Raises KeyError if entity_id is not a node in reference.snapshot.
    image_path is always None (BOOKS-FIRST HARD GATE).
    """
    node = _node_for(reference, entity_id)
    triples = _outgoing_triples(reference, entity_id)
    description = _assemble_description(reference, entity_id, node)
    return GenerationContext(
        entity_id=entity_id,
        triples=list(triples),
        description=description,
        image_path=None,
    )


def assemble_context(
    reference: GradingReference,
    entity_id: str,
    *,
    perturbations: Sequence[Perturbation] = (),
) -> GenerationContext:
    """Build the full context and apply perturbations in the given order.

    This is the ONLY site in the codebase where ablation (withhold) occurs.
    With perturbations=() the result equals build_full_context(reference, entity_id).
    The reference is never modified.
    """
    ctx = build_full_context(reference, entity_id)
    for perturbation in perturbations:
        ctx = perturbation.withhold(ctx)
    return ctx
