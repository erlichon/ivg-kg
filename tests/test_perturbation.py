"""
Tests for PT1: Perturbation interface, registry, and AblationManifest.

Run with:  pytest tests/test_perturbation.py -v
"""

from __future__ import annotations

import pytest

from ivg_kg.perturbation import (
    AblationManifest,
    ImageContentAbsence,
    KnowledgeAbsence,
    Perturbation,
    TextContentAbsence,
    available_perturbations,
    perturbation_from_entry,
)
from ivg_kg.schema import GenerationContext, KGEdge, TripleRef, ValueType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EDGE_A = KGEdge(
    subject_id="Q1",
    property_id="P31",
    property_label="instance of",
    object_id="Q5",
    object_label="human",
    value_type=ValueType.ITEM,
)

EDGE_B = KGEdge(
    subject_id="Q1",
    property_id="P21",
    property_label="sex or gender",
    object_id="Q6581097",
    object_label="male",
    value_type=ValueType.ITEM,
)

EDGE_C = KGEdge(
    subject_id="Q2",
    property_id="P31",
    property_label="instance of",
    object_id="Q5",
    object_label="human",
    value_type=ValueType.ITEM,
)


def make_ctx(
    entity_id: str = "Q1",
    description: str | None = "A test description.",
    image_path: str | None = "/images/Q1.jpg",
    extra_edges: list[KGEdge] | None = None,
) -> GenerationContext:
    edges = [EDGE_A, EDGE_B] + (extra_edges or [])
    return GenerationContext(
        entity_id=entity_id,
        triples=edges,
        description=description,
        image_path=image_path,
    )


# ---------------------------------------------------------------------------
# TextContentAbsence
# ---------------------------------------------------------------------------


class TestTextContentAbsence:
    def test_drops_description_for_matching_entity(self) -> None:
        ctx = make_ctx(entity_id="Q1", description="hello")
        p = TextContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.description is None

    def test_leaves_triples_intact(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        p = TextContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.triples == ctx.triples

    def test_leaves_image_intact(self) -> None:
        ctx = make_ctx(entity_id="Q1", image_path="/img.jpg")
        p = TextContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.image_path == "/img.jpg"

    def test_entity_scoped_leaves_other_entity_unchanged(self) -> None:
        ctx = make_ctx(entity_id="Q2", description="other entity")
        p = TextContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.description == "other entity"

    def test_purity_input_unchanged(self) -> None:
        ctx = make_ctx(entity_id="Q1", description="original")
        p = TextContentAbsence(entity_id="Q1")
        _ = p.withhold(ctx)
        assert ctx.description == "original"

    def test_result_is_new_object(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        p = TextContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result is not ctx

    def test_withhold_already_none_description_is_noop(self) -> None:
        ctx = make_ctx(entity_id="Q1", description=None)
        p = TextContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.description is None
        assert result is not ctx  # still a new object


# ---------------------------------------------------------------------------
# ImageContentAbsence
# ---------------------------------------------------------------------------


class TestImageContentAbsence:
    def test_drops_image_for_matching_entity(self) -> None:
        ctx = make_ctx(entity_id="Q1", image_path="/img.jpg")
        p = ImageContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.image_path is None

    def test_leaves_description_intact(self) -> None:
        ctx = make_ctx(entity_id="Q1", description="still here")
        p = ImageContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.description == "still here"

    def test_leaves_triples_intact(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        p = ImageContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.triples == ctx.triples

    def test_entity_scoped_leaves_other_entity_unchanged(self) -> None:
        ctx = make_ctx(entity_id="Q2", image_path="/img.jpg")
        p = ImageContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result.image_path == "/img.jpg"

    def test_purity_input_unchanged(self) -> None:
        ctx = make_ctx(entity_id="Q1", image_path="/img.jpg")
        p = ImageContentAbsence(entity_id="Q1")
        _ = p.withhold(ctx)
        assert ctx.image_path == "/img.jpg"

    def test_result_is_new_object(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        p = ImageContentAbsence(entity_id="Q1")
        result = p.withhold(ctx)
        assert result is not ctx


# ---------------------------------------------------------------------------
# KnowledgeAbsence
# ---------------------------------------------------------------------------


class TestKnowledgeAbsence:
    def test_removes_matching_edge_with_object_id(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        ref = TripleRef(subject_id="Q1", property_id="P31", object_id="Q5")
        p = KnowledgeAbsence(triples=[ref])
        result = p.withhold(ctx)
        remaining_ids = [(e.subject_id, e.property_id) for e in result.triples]
        assert ("Q1", "P31") not in remaining_ids
        assert ("Q1", "P21") in remaining_ids

    def test_removes_all_matching_edges_with_none_object_id(self) -> None:
        # Add a second P31 edge with a different object
        extra = KGEdge(
            subject_id="Q1",
            property_id="P31",
            property_label="instance of",
            object_id="Q99",
            object_label="something",
            value_type=ValueType.ITEM,
        )
        ctx = make_ctx(entity_id="Q1", extra_edges=[extra])
        ref = TripleRef(subject_id="Q1", property_id="P31", object_id=None)
        p = KnowledgeAbsence(triples=[ref])
        result = p.withhold(ctx)
        remaining_props = [e.property_id for e in result.triples]
        assert "P31" not in remaining_props
        assert "P21" in remaining_props

    def test_non_matching_edges_preserved(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        ref = TripleRef(subject_id="Q1", property_id="P999")
        p = KnowledgeAbsence(triples=[ref])
        result = p.withhold(ctx)
        assert result.triples == ctx.triples

    def test_description_and_image_untouched(self) -> None:
        ctx = make_ctx(entity_id="Q1", description="desc", image_path="/img.jpg")
        ref = TripleRef(subject_id="Q1", property_id="P31", object_id="Q5")
        p = KnowledgeAbsence(triples=[ref])
        result = p.withhold(ctx)
        assert result.description == "desc"
        assert result.image_path == "/img.jpg"

    def test_purity_input_unchanged(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        original_triples = list(ctx.triples)
        ref = TripleRef(subject_id="Q1", property_id="P31", object_id="Q5")
        p = KnowledgeAbsence(triples=[ref])
        _ = p.withhold(ctx)
        assert ctx.triples == original_triples

    def test_result_is_new_object(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        ref = TripleRef(subject_id="Q1", property_id="P31", object_id="Q5")
        p = KnowledgeAbsence(triples=[ref])
        result = p.withhold(ctx)
        assert result is not ctx

    def test_multiple_refs_in_single_perturbation(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        refs = [
            TripleRef(subject_id="Q1", property_id="P31", object_id="Q5"),
            TripleRef(subject_id="Q1", property_id="P21"),
        ]
        p = KnowledgeAbsence(triples=refs)
        result = p.withhold(ctx)
        assert result.triples == []

    def test_object_id_mismatch_does_not_remove(self) -> None:
        ctx = make_ctx(entity_id="Q1")
        # EDGE_A has object_id="Q5"; ref specifies Q999
        ref = TripleRef(subject_id="Q1", property_id="P31", object_id="Q999")
        p = KnowledgeAbsence(triples=[ref])
        result = p.withhold(ctx)
        # EDGE_A should still be present
        assert any(e.property_id == "P31" for e in result.triples)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_all_three_classes_registered(self) -> None:
        reg = available_perturbations()
        type_names = {cls.type_name for cls in reg.values()}
        assert "text_content_absence" in type_names
        assert "knowledge_absence" in type_names
        assert "image_content_absence" in type_names

    def test_register_perturbation_returns_class(self) -> None:
        reg = available_perturbations()
        assert reg["text_content_absence"] is TextContentAbsence
        assert reg["knowledge_absence"] is KnowledgeAbsence
        assert reg["image_content_absence"] is ImageContentAbsence


# ---------------------------------------------------------------------------
# manifest_entry / perturbation_from_entry round-trip
# ---------------------------------------------------------------------------


class TestManifestEntry:
    def test_text_content_absence_round_trip(self) -> None:
        p = TextContentAbsence(entity_id="Q1")
        entry = p.manifest_entry()
        assert entry["type_name"] == "text_content_absence"
        p2 = perturbation_from_entry(entry)
        assert p2.id == p.id
        assert isinstance(p2, TextContentAbsence)

    def test_image_content_absence_round_trip(self) -> None:
        p = ImageContentAbsence(entity_id="Q42")
        entry = p.manifest_entry()
        p2 = perturbation_from_entry(entry)
        assert p2.id == p.id
        assert isinstance(p2, ImageContentAbsence)

    def test_knowledge_absence_round_trip(self) -> None:
        refs = [
            TripleRef(subject_id="Q1", property_id="P31", object_id="Q5"),
            TripleRef(subject_id="Q2", property_id="P21"),
        ]
        p = KnowledgeAbsence(triples=refs)
        entry = p.manifest_entry()
        p2 = perturbation_from_entry(entry)
        assert p2.id == p.id
        assert isinstance(p2, KnowledgeAbsence)


# ---------------------------------------------------------------------------
# Deterministic IDs
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_text_content_absence_same_id(self) -> None:
        p1 = TextContentAbsence(entity_id="Q1")
        p2 = TextContentAbsence(entity_id="Q1")
        assert p1.id == p2.id

    def test_image_content_absence_same_id(self) -> None:
        p1 = ImageContentAbsence(entity_id="Q42")
        p2 = ImageContentAbsence(entity_id="Q42")
        assert p1.id == p2.id

    def test_knowledge_absence_same_id_regardless_of_ref_order(self) -> None:
        refs_a = [
            TripleRef(subject_id="Q1", property_id="P31", object_id="Q5"),
            TripleRef(subject_id="Q2", property_id="P21"),
        ]
        refs_b = [
            TripleRef(subject_id="Q2", property_id="P21"),
            TripleRef(subject_id="Q1", property_id="P31", object_id="Q5"),
        ]
        p1 = KnowledgeAbsence(triples=refs_a)
        p2 = KnowledgeAbsence(triples=refs_b)
        assert p1.id == p2.id

    def test_different_entities_different_ids(self) -> None:
        p1 = TextContentAbsence(entity_id="Q1")
        p2 = TextContentAbsence(entity_id="Q2")
        assert p1.id != p2.id


# ---------------------------------------------------------------------------
# touched_entities
# ---------------------------------------------------------------------------


class TestTouchedEntities:
    def test_text_content_absence_touches_entity(self) -> None:
        p = TextContentAbsence(entity_id="Q1")
        assert p.touched_entities() == {"Q1"}

    def test_image_content_absence_touches_entity(self) -> None:
        p = ImageContentAbsence(entity_id="Q42")
        assert p.touched_entities() == {"Q42"}

    def test_knowledge_absence_touches_subjects(self) -> None:
        refs = [
            TripleRef(subject_id="Q1", property_id="P31"),
            TripleRef(subject_id="Q2", property_id="P21"),
        ]
        p = KnowledgeAbsence(triples=refs)
        assert p.touched_entities() == {"Q1", "Q2"}


# ---------------------------------------------------------------------------
# AblationManifest
# ---------------------------------------------------------------------------


class TestAblationManifest:
    def _make_manifest(self) -> AblationManifest:
        p_text = TextContentAbsence(entity_id="Q1")
        refs = [TripleRef(subject_id="Q2", property_id="P31", object_id="Q5")]
        p_know = KnowledgeAbsence(triples=refs)
        return AblationManifest(base_slice_id="books-v1", perturbations=[p_text, p_know])

    def test_apply_all_composes_in_order(self) -> None:
        manifest = self._make_manifest()
        ctx = GenerationContext(
            entity_id="Q1",
            triples=[EDGE_A, EDGE_C],
            description="Q1 description",
            image_path="/img.jpg",
        )
        result = manifest.apply_all(ctx)
        assert result.description is None  # TextContentAbsence(Q1) withheld it
        # KnowledgeAbsence refs Q2/P31/Q5 -> EDGE_C should be removed
        assert not any(e.subject_id == "Q2" and e.property_id == "P31" for e in result.triples)
        assert result.image_path == "/img.jpg"  # untouched

    def test_apply_all_does_not_mutate_input(self) -> None:
        manifest = self._make_manifest()
        ctx = GenerationContext(
            entity_id="Q1",
            triples=[EDGE_A],
            description="original",
            image_path="/img.jpg",
        )
        _ = manifest.apply_all(ctx)
        assert ctx.description == "original"
        assert ctx.triples == [EDGE_A]

    def test_active_entry_ids_order(self) -> None:
        manifest = self._make_manifest()
        ids = manifest.active_entry_ids()
        assert ids[0] == TextContentAbsence(entity_id="Q1").id
        assert ids[1] == KnowledgeAbsence(
            triples=[TripleRef(subject_id="Q2", property_id="P31", object_id="Q5")]
        ).id

    def test_to_json_from_json_round_trip(self) -> None:
        manifest = self._make_manifest()
        serialized = manifest.to_json()
        restored = AblationManifest.from_json(serialized)
        assert restored.base_slice_id == manifest.base_slice_id
        assert len(restored.perturbations) == len(manifest.perturbations)
        for orig, rest in zip(manifest.perturbations, restored.perturbations, strict=True):
            assert orig.id == rest.id
            assert type(orig) is type(rest)

    def test_to_json_is_deterministic(self) -> None:
        manifest = self._make_manifest()
        s1 = manifest.to_json()
        s2 = manifest.to_json()
        assert s1 == s2

    def test_from_json_to_json_is_stable(self) -> None:
        manifest = self._make_manifest()
        s1 = manifest.to_json()
        s2 = AblationManifest.from_json(s1).to_json()
        assert s1 == s2

    # ------------------------------------------------------------------
    # Per-claim attribution
    # ------------------------------------------------------------------

    def test_entries_touching_single_entity(self) -> None:
        manifest = self._make_manifest()
        # TextContentAbsence(Q1) touches Q1; KnowledgeAbsence touches Q2
        ids_q1 = manifest.entries_touching({"Q1"})
        assert ids_q1 == [TextContentAbsence(entity_id="Q1").id]

        ids_q2 = manifest.entries_touching({"Q2"})
        assert ids_q2 == [
            KnowledgeAbsence(
                triples=[TripleRef(subject_id="Q2", property_id="P31", object_id="Q5")]
            ).id
        ]

    def test_entries_touching_both_entities(self) -> None:
        manifest = self._make_manifest()
        ids = manifest.entries_touching({"Q1", "Q2"})
        # both perturbations, in manifest order
        assert ids[0] == TextContentAbsence(entity_id="Q1").id
        assert ids[1] == KnowledgeAbsence(
            triples=[TripleRef(subject_id="Q2", property_id="P31", object_id="Q5")]
        ).id

    def test_entries_touching_unrelated_entity(self) -> None:
        manifest = self._make_manifest()
        assert manifest.entries_touching({"Q999"}) == []

    def test_entries_touching_empty_set(self) -> None:
        manifest = self._make_manifest()
        assert manifest.entries_touching(set()) == []


# ---------------------------------------------------------------------------
# control_spec
# ---------------------------------------------------------------------------


class TestControlSpec:
    def test_text_control_spec_has_required_keys(self) -> None:
        spec = TextContentAbsence.control_spec()
        assert spec["type_name"] == "text_content_absence"
        assert "modality" in spec
        assert "label" in spec
        assert "params" in spec

    def test_knowledge_control_spec(self) -> None:
        spec = KnowledgeAbsence.control_spec()
        assert spec["type_name"] == "knowledge_absence"

    def test_image_control_spec(self) -> None:
        spec = ImageContentAbsence.control_spec()
        assert spec["type_name"] == "image_content_absence"

    def test_control_spec_is_serializable(self) -> None:
        import json

        for cls in (TextContentAbsence, KnowledgeAbsence, ImageContentAbsence):
            spec = cls.control_spec()
            # Must not raise
            json.dumps(spec)


# ---------------------------------------------------------------------------
# Perturbation ABC
# ---------------------------------------------------------------------------


class TestPerturbationABC:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            Perturbation()  # type: ignore[abstract]

    def test_subclasses_are_perturbation_instances(self) -> None:
        p = TextContentAbsence(entity_id="Q1")
        assert isinstance(p, Perturbation)
