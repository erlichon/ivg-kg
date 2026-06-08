"""
TextContentAbsence — withholds the description from a GenerationContext.

Modality: TEXT
Withhold semantics: if ctx.entity_id == entity_id, return a copy with
description=None; otherwise return ctx unchanged (as a copy).
"""

from __future__ import annotations

from typing import ClassVar

from ivg_kg.schema import GenerationContext, Modality

from .base import Perturbation, register_perturbation


@register_perturbation
class TextContentAbsence(Perturbation):
    """Withholds the text description from the generation context."""

    type_name: ClassVar[str] = "text_content_absence"
    modality: ClassVar[Modality] = Modality.TEXT

    def __init__(self, entity_id: str) -> None:
        self.entity_id: str = entity_id
        self.id: str = f"text_content_absence:{entity_id}"

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def withhold(self, ctx: GenerationContext) -> GenerationContext:
        """Return a new context with description=None if entity matches.

        The returned context always owns a distinct triples list so that
        mutating it cannot affect the caller's original context
        (Invariant #1, SPEC §3.2).
        """
        if ctx.entity_id == self.entity_id:
            return ctx.model_copy(update={"description": None, "triples": list(ctx.triples)})
        return ctx.model_copy(update={"triples": list(ctx.triples)})

    def manifest_entry(self) -> dict:
        return {
            "type_name": self.type_name,
            "id": self.id,
            "entity_id": self.entity_id,
        }

    @classmethod
    def from_entry(cls, entry: dict) -> TextContentAbsence:
        return cls(entity_id=entry["entity_id"])

    def touched_entities(self) -> set[str]:
        return {self.entity_id}

    # ------------------------------------------------------------------
    # UI control spec
    # ------------------------------------------------------------------

    @classmethod
    def control_spec(cls) -> dict:
        return {
            "type_name": cls.type_name,
            "modality": Modality.TEXT.value,
            "label": "Text Content Absence",
            "params": [{"name": "entity_id", "kind": "entity_id"}],
        }
