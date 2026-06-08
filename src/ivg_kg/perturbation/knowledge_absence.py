"""
KnowledgeAbsence — withholds specified triples from a GenerationContext.

Modality: STRUCTURE
Withhold semantics: remove every KGEdge matching ANY of the given TripleRefs.
Match rule:
    edge.subject_id == ref.subject_id
    AND edge.property_id == ref.property_id
    AND (ref.object_id is None OR edge.object_id == ref.object_id)
object_id=None in a ref means "match all objects of that subject+property."
"""

from __future__ import annotations

import hashlib
import json

from ivg_kg.schema import GenerationContext, KGEdge, Modality, TripleRef

from .base import Perturbation, register_perturbation


def _stable_id(triples: list[TripleRef]) -> str:
    """Derive a deterministic, stable id from a set of TripleRefs.

    Sort by (subject_id, property_id, object_id or "") so that the same
    logical set of refs always produces the same id, regardless of the
    order in which they were supplied (Invariant #9).
    """
    sorted_refs = sorted(
        triples,
        key=lambda r: (r.subject_id, r.property_id, r.object_id or ""),
    )
    canonical = json.dumps(
        [
            {"subject_id": r.subject_id, "property_id": r.property_id, "object_id": r.object_id}
            for r in sorted_refs
        ],
        sort_keys=True,
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return f"knowledge_absence:{digest}"


def _edge_matches(edge: KGEdge, ref: TripleRef) -> bool:
    """Return True if edge satisfies the TripleRef selector."""
    if edge.subject_id != ref.subject_id:
        return False
    if edge.property_id != ref.property_id:
        return False
    if ref.object_id is not None and edge.object_id != ref.object_id:
        return False
    return True


@register_perturbation
class KnowledgeAbsence(Perturbation):
    """Withholds specified triples from the generation context."""

    type_name: str = "knowledge_absence"

    def __init__(self, triples: list[TripleRef]) -> None:
        self.triples_to_withhold: list[TripleRef] = list(triples)
        self.id: str = _stable_id(self.triples_to_withhold)
        self.modality: Modality = Modality.STRUCTURE

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def withhold(self, ctx: GenerationContext) -> GenerationContext:
        """Return a new context whose triples exclude all matching edges."""
        filtered = [
            edge
            for edge in ctx.triples
            if not any(_edge_matches(edge, ref) for ref in self.triples_to_withhold)
        ]
        return ctx.model_copy(update={"triples": filtered})

    def manifest_entry(self) -> dict:
        return {
            "type_name": self.type_name,
            "id": self.id,
            "triples": [
                {
                    "subject_id": r.subject_id,
                    "property_id": r.property_id,
                    "object_id": r.object_id,
                }
                for r in self.triples_to_withhold
            ],
        }

    @classmethod
    def from_entry(cls, entry: dict) -> KnowledgeAbsence:
        refs = [
            TripleRef(
                subject_id=t["subject_id"],
                property_id=t["property_id"],
                object_id=t.get("object_id"),
            )
            for t in entry["triples"]
        ]
        return cls(triples=refs)

    def touched_entities(self) -> set[str]:
        """Return the subject_ids of all withheld triple refs."""
        return {r.subject_id for r in self.triples_to_withhold}

    # ------------------------------------------------------------------
    # UI control spec
    # ------------------------------------------------------------------

    @classmethod
    def control_spec(cls) -> dict:
        return {
            "type_name": cls.type_name,
            "modality": Modality.STRUCTURE.value,
            "label": "Knowledge Absence",
            "params": [{"name": "triples", "kind": "triple_selector"}],
        }
