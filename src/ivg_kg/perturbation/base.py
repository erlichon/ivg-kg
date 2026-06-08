"""
PT1: Perturbation ABC, registry, and AblationManifest (SPEC §4.4).

All perturbation types operate on GenerationContext ONLY — never on frozen
KG snapshots or grading references (Invariant #1, SPEC §3.2).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import ClassVar

from ivg_kg.schema import GenerationContext, Modality

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[Perturbation]] = {}


def register_perturbation(cls: type[Perturbation]) -> type[Perturbation]:
    """Class decorator that registers a Perturbation subclass by type_name."""
    _REGISTRY[cls.type_name] = cls
    return cls


def available_perturbations() -> dict[str, type[Perturbation]]:
    """Return a shallow copy of the current registry keyed by type_name."""
    return dict(_REGISTRY)


def perturbation_from_entry(entry: dict) -> Perturbation:
    """Reconstruct a Perturbation instance from a manifest_entry dict."""
    type_name: str = entry["type_name"]
    if type_name not in _REGISTRY:
        raise KeyError(f"Unknown perturbation type_name: {type_name!r}")
    return _REGISTRY[type_name].from_entry(entry)


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class Perturbation(ABC):
    """Abstract base class for all perturbation types.

    Subclasses MUST:
    - Declare a class-level ``type_name`` string unique across the registry.
    - Set ``self.id`` (deterministic, stable for a given type+params).
    - Set ``self.modality``.
    - Implement ``withhold``, ``manifest_entry``, and ``from_entry``.

    ``withhold`` MUST return a NEW ``GenerationContext``; it MUST NOT mutate
    its input (Invariant #1, SPEC §3.2).
    """

    type_name: ClassVar[str]
    modality: ClassVar[Modality]
    id: str

    @abstractmethod
    def withhold(self, ctx: GenerationContext) -> GenerationContext:
        """Return a new GenerationContext with this perturbation applied.

        The input ``ctx`` MUST NOT be mutated.
        """

    @abstractmethod
    def manifest_entry(self) -> dict:
        """Return a JSON-serializable dict sufficient to reconstruct this instance."""

    @classmethod
    @abstractmethod
    def from_entry(cls, entry: dict) -> Perturbation:
        """Reconstruct an instance from a ``manifest_entry`` dict."""

    @classmethod
    def control_spec(cls) -> dict:
        """Return a plain-dict description of the UI control for this type.

        At minimum: type_name, modality, label, params list.
        """
        return {
            "type_name": cls.type_name,
            "modality": cls.modality if isinstance(cls.modality, str) else cls.modality.value,
            "label": cls.type_name.replace("_", " ").title(),
            "params": [],
        }

    @abstractmethod
    def touched_entities(self) -> set[str]:
        """Return the set of entity ids this perturbation acts on.

        Used by ``AblationManifest.entries_touching`` for per-claim attribution.
        """


# ---------------------------------------------------------------------------
# AblationManifest
# ---------------------------------------------------------------------------


class AblationManifest:
    """An ordered list of perturbations applied to a fixed base slice.

    Serializes to / reconstructs from a JSON manifest string using the
    perturbation registry.  All output is deterministic (Invariant #9).
    """

    def __init__(self, base_slice_id: str, perturbations: list[Perturbation]) -> None:
        self.base_slice_id: str = base_slice_id
        self.perturbations: list[Perturbation] = list(perturbations)

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply_all(self, ctx: GenerationContext) -> GenerationContext:
        """Apply all perturbations in order, threading the result.

        The input ``ctx`` is never mutated (Invariant #1).
        """
        current = ctx
        for p in self.perturbations:
            current = p.withhold(current)
        return current

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def active_entry_ids(self) -> list[str]:
        """Return the ordered list of perturbation ids in this manifest."""
        return [p.id for p in self.perturbations]

    def entries_touching(self, entity_ids: Iterable[str]) -> list[str]:
        """Return ids of perturbations whose touched_entities intersect entity_ids.

        Preserves manifest order.  Used for per-claim attribution: pass the
        linked-entity ids of a claim to get which perturbation entries are
        causally relevant to that claim.
        """
        target = set(entity_ids)
        return [p.id for p in self.perturbations if p.touched_entities() & target]

    # ------------------------------------------------------------------
    # Serialization (deterministic)
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize to a deterministic JSON string.

        Key order is fixed (sort_keys=True) so identical manifests produce
        identical bytes across runs (Invariant #9).
        """
        data = {
            "base_slice_id": self.base_slice_id,
            "perturbations": [p.manifest_entry() for p in self.perturbations],
        }
        return json.dumps(data, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> AblationManifest:
        """Reconstruct an AblationManifest from a JSON string."""
        data = json.loads(s)
        perturbations = [perturbation_from_entry(e) for e in data["perturbations"]]
        return cls(base_slice_id=data["base_slice_id"], perturbations=perturbations)
