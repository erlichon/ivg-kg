"""
ImageContentAbsence — withholds the image path from a GenerationContext.

Modality: IMAGE
Withhold semantics: if ctx.entity_id == entity_id, return a copy with
image_path=None; otherwise return ctx unchanged (as a copy).

NOTE: This class defines the PERTURBATION-SEAM contract only (SPEC §4.4,
Invariant #8).  Taxa/image-fetching/rasterization/P181 query logic is NOT
included here and MUST NOT be added to this file.
"""

from __future__ import annotations

from typing import ClassVar

from ivg_kg.schema import GenerationContext, Modality

from .base import Perturbation, register_perturbation


@register_perturbation
class ImageContentAbsence(Perturbation):
    """Withholds the range-map image from the generation context."""

    type_name: ClassVar[str] = "image_content_absence"
    modality: ClassVar[Modality] = Modality.IMAGE

    def __init__(self, entity_id: str) -> None:
        self.entity_id: str = entity_id
        self.id: str = f"image_content_absence:{entity_id}"

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def withhold(self, ctx: GenerationContext) -> GenerationContext:
        """Return a new context with image_path=None if entity matches.

        The returned context always owns a distinct triples list so that
        mutating it cannot affect the caller's original context
        (Invariant #1, SPEC §3.2).
        """
        if ctx.entity_id == self.entity_id:
            return ctx.model_copy(update={"image_path": None, "triples": list(ctx.triples)})
        return ctx.model_copy(update={"triples": list(ctx.triples)})

    def manifest_entry(self) -> dict:
        return {
            "type_name": self.type_name,
            "id": self.id,
            "entity_id": self.entity_id,
        }

    @classmethod
    def from_entry(cls, entry: dict) -> ImageContentAbsence:
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
            "modality": Modality.IMAGE.value,
            "label": "Image Content Absence",
            "params": [{"name": "entity_id", "kind": "entity_id"}],
        }
