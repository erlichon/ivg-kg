"""EX2: manifest-driven perturbations adapter for the offline sweep.

Provides ``manifest_perturbations_for`` -- a factory that wraps an
``AblationManifest`` into a ``perturbations_for`` callable compatible with
``run_sweep``'s ``perturbations_for`` parameter.

Design (SPEC-text sec 4.4 / Invariant #7 books-first):

  FULL / FULL_NO_EDIT_RERUN   -> [] (no withholding)
  CONTENT_ABSENT              -> the manifest's TextContentAbsence entries
                                 whose touched_entities() includes item.entity_id
                                 (empty list for items not in the content arm)
  KNOWLEDGE_ABSENT            -> the manifest's KnowledgeAbsence entries
                                 whose touched_entities() includes item.entity_id
                                 (empty list for items not in the knowledge arm)
  IMAGE_ABSENT / unknown      -> raise ValueError (books-first; Invariant #7)

Each question participates ONLY in the arm it was authored for: content-arm items
return [] under KNOWLEDGE_ABSENT, and knowledge-arm items return [] under
CONTENT_ABSENT. Items in neither arm return [] for both. This is the targeted,
per-question fixed design for the real A3 sweep.

Usage:
    manifest = AblationManifest.from_json(path.read_text())
    fn = manifest_perturbations_for(manifest)
    runset = run_sweep(bank, reference, client, perturbations_for=fn)
"""

from __future__ import annotations

from collections.abc import Callable

from ivg_kg.experiment.question_bank import QuestionBankItem
from ivg_kg.perturbation.base import AblationManifest, Perturbation
from ivg_kg.perturbation.knowledge_absence import KnowledgeAbsence
from ivg_kg.perturbation.text_content_absence import TextContentAbsence
from ivg_kg.schema import Condition, GradingReference

__all__ = ["manifest_perturbations_for"]

# Conditions whose perturbation set is always empty (no withholding).
_NO_WITHHOLD_CONDITIONS = frozenset({Condition.FULL, Condition.FULL_NO_EDIT_RERUN})


def manifest_perturbations_for(
    manifest: AblationManifest,
) -> Callable[[QuestionBankItem, Condition, GradingReference], list[Perturbation]]:
    """Return a perturbations_for callable backed by a fixed AblationManifest.

    The returned callable maps (item, condition, reference) -> list[Perturbation]
    using the manifest's pre-authored entries rather than the harness default
    (which withholds ALL outgoing triples for KNOWLEDGE_ABSENT). The manifest
    approach is targeted: each KnowledgeAbsence entry withholds only the single
    answering triple, keeping the manipulation check clean (SPEC-text sec 6).

    Parameters
    ----------
    manifest:
        A loaded, validated AblationManifest (e.g. books-p0-v1/manifest.json).

    Returns
    -------
    A callable with the same signature as ``default_perturbations_for``.
    """
    # Partition manifest entries once at construction time for O(1) lookup.
    _text_by_entity: dict[str, TextContentAbsence] = {}
    _knowledge_by_entity: dict[str, KnowledgeAbsence] = {}

    for p in manifest.perturbations:
        if isinstance(p, TextContentAbsence):
            _text_by_entity[p.entity_id] = p
        elif isinstance(p, KnowledgeAbsence):
            for entity_id in p.touched_entities():
                _knowledge_by_entity[entity_id] = p

    def _perturbations_for(
        item: QuestionBankItem,
        condition: Condition,
        reference: GradingReference,
    ) -> list[Perturbation]:
        if condition in _NO_WITHHOLD_CONDITIONS:
            return []
        if condition == Condition.CONTENT_ABSENT:
            entry = _text_by_entity.get(item.entity_id)
            return [entry] if entry is not None else []
        if condition == Condition.KNOWLEDGE_ABSENT:
            entry = _knowledge_by_entity.get(item.entity_id)
            return [entry] if entry is not None else []
        # IMAGE_ABSENT and any unknown condition: books-first Invariant #7.
        raise ValueError(
            f"Condition {condition!r} is not supported in the books spine "
            f"(IMAGE_ABSENT is post-M-BOOKS; Invariant #7)."
        )

    return _perturbations_for
