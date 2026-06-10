"""
ivg_kg.perturbation — Perturbation interface, registry, and manifest (SPEC-text §4.4).

Importing this package registers all three built-in perturbation types so that
``AblationManifest.from_json`` can reconstruct any of them via the registry.

Public API
----------
Perturbation            — ABC with withhold / manifest_entry / control_spec
AblationManifest        — base_slice_id + ordered perturbations; to_json / from_json
TextContentAbsence      — modality=TEXT; withholds description
KnowledgeAbsence        — modality=STRUCTURE; withholds specified triples
ImageContentAbsence     — modality=IMAGE; withholds image_path
register_perturbation   — class decorator for custom subclasses
available_perturbations — returns the current registry dict
perturbation_from_entry — reconstruct a Perturbation from a manifest_entry dict
"""

from ivg_kg.perturbation.base import (
    AblationManifest,
    Perturbation,
    available_perturbations,
    perturbation_from_entry,
    register_perturbation,
)

# Import subclasses to trigger @register_perturbation side-effects.
from ivg_kg.perturbation.image_content_absence import ImageContentAbsence
from ivg_kg.perturbation.knowledge_absence import KnowledgeAbsence
from ivg_kg.perturbation.text_content_absence import TextContentAbsence

__all__ = [
    "AblationManifest",
    "ImageContentAbsence",
    "KnowledgeAbsence",
    "Perturbation",
    "TextContentAbsence",
    "available_perturbations",
    "perturbation_from_entry",
    "register_perturbation",
]
