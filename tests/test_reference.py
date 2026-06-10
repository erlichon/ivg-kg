"""Tests for DA4 — Grading-reference assembly (reference.py).

Test-first: these tests are written before the implementation and define
the expected contract of every public function.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from ivg_kg.schema import (
    ContentLabel,
    GradingReference,
    KGEdge,
    KGNode,
    KGSnapshot,
    Modality,
    ValueType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_snapshot() -> KGSnapshot:
    """A minimal KG-full snapshot for testing."""
    return KGSnapshot(
        snapshot_id="snap-001",
        slice="books",
        domain_qid="Q571",
        nodes=[
            KGNode(id="Q571", label="book", description="a written work"),
        ],
        edges=[
            KGEdge(
                subject_id="Q571",
                property_id="P31",
                property_label="instance of",
                object_id="Q571",
                object_label="book",
                value_type=ValueType.ITEM,
            )
        ],
    )


@pytest.fixture()
def sample_labels() -> list[ContentLabel]:
    """A small set of TEXT content labels for a book entity."""
    return [
        ContentLabel(
            entity_id="Q571",
            modality=Modality.TEXT,
            fact="is a play",
            source="description",
        ),
        ContentLabel(
            entity_id="Q571",
            modality=Modality.TEXT,
            fact="central to the Western tradition",
            source="description",
        ),
    ]


@pytest.fixture()
def assembled_ref(minimal_snapshot, sample_labels) -> GradingReference:
    from ivg_kg.data.reference import assemble_reference

    return assemble_reference(minimal_snapshot, sample_labels)


# ---------------------------------------------------------------------------
# assemble_reference
# ---------------------------------------------------------------------------


class TestAssembleReference:
    def test_returns_grading_reference(self, assembled_ref):
        assert isinstance(assembled_ref, GradingReference)

    def test_snapshot_preserved(self, assembled_ref, minimal_snapshot):
        assert assembled_ref.snapshot == minimal_snapshot

    def test_content_labels_preserved(self, assembled_ref, sample_labels):
        assert assembled_ref.content_labels == sample_labels

    def test_json_round_trip(self, assembled_ref):
        """model_dump_json / model_validate_json must reconstruct an equal object."""
        json_str = assembled_ref.model_dump_json()
        reloaded = GradingReference.model_validate_json(json_str)
        assert reloaded == assembled_ref

    def test_empty_labels_allowed(self, minimal_snapshot):
        from ivg_kg.data.reference import assemble_reference

        ref = assemble_reference(minimal_snapshot, [])
        assert ref.content_labels == []
        assert isinstance(ref, GradingReference)


# ---------------------------------------------------------------------------
# make_text_content_label
# ---------------------------------------------------------------------------


class TestMakeTextContentLabel:
    def test_modality_is_text(self):
        from ivg_kg.data.reference import make_text_content_label

        label = make_text_content_label("Q571", "is a novel")
        assert label.modality == Modality.TEXT

    def test_entity_id_and_fact(self):
        from ivg_kg.data.reference import make_text_content_label

        label = make_text_content_label("Q42", "comprises three volumes")
        assert label.entity_id == "Q42"
        assert label.fact == "comprises three volumes"

    def test_default_source(self):
        from ivg_kg.data.reference import make_text_content_label

        label = make_text_content_label("Q42", "some fact")
        assert label.source == "description"

    def test_custom_source(self):
        from ivg_kg.data.reference import make_text_content_label

        label = make_text_content_label("Q42", "some fact", source="infobox")
        assert label.source == "infobox"

    def test_never_image_modality(self):
        from ivg_kg.data.reference import make_text_content_label

        label = make_text_content_label("Q42", "fact")
        assert label.modality != Modality.IMAGE


# ---------------------------------------------------------------------------
# author_books_content_labels
# ---------------------------------------------------------------------------


class TestAuthorBooksContentLabels:
    """Tests for the batch authoring helper."""

    def test_produces_content_labels(self):
        from ivg_kg.data.reference import author_books_content_labels

        facts = [
            ("Q571", "is a play", "description"),
            ("Q571", "central to the Western tradition", "description"),
        ]
        labels = author_books_content_labels(facts)
        assert len(labels) == 2
        assert all(isinstance(lb, ContentLabel) for lb in labels)

    def test_all_text_modality(self):
        from ivg_kg.data.reference import author_books_content_labels

        facts = [("Q100", "is a novel", "description"), ("Q200", "three volumes", "description")]
        labels = author_books_content_labels(facts)
        assert all(lb.modality == Modality.TEXT for lb in labels)

    def test_no_image_labels_emitted(self):
        from ivg_kg.data.reference import author_books_content_labels

        facts = [("Q1", "fact one", "description"), ("Q2", "fact two", "custom")]
        labels = author_books_content_labels(facts)
        assert all(lb.modality != Modality.IMAGE for lb in labels)

    def test_entity_id_and_fact_and_source_correct(self):
        from ivg_kg.data.reference import author_books_content_labels

        facts = [("Q42", "comprises three volumes", "infobox")]
        labels = author_books_content_labels(facts)
        assert labels[0].entity_id == "Q42"
        assert labels[0].fact == "comprises three volumes"
        assert labels[0].source == "infobox"

    def test_deterministic_ordering(self):
        from ivg_kg.data.reference import author_books_content_labels

        facts = [
            ("Q300", "fact c", "description"),
            ("Q100", "fact a", "description"),
            ("Q200", "fact b", "description"),
        ]
        labels_a = author_books_content_labels(facts)
        labels_b = author_books_content_labels(facts)
        assert labels_a == labels_b

    def test_ordering_is_input_order(self):
        """author_books_content_labels preserves input order (explicit contract)."""
        from ivg_kg.data.reference import author_books_content_labels

        facts = [
            ("Q300", "fact c", "description"),
            ("Q100", "fact a", "description"),
            ("Q200", "fact b", "description"),
        ]
        labels = author_books_content_labels(facts)
        assert labels[0].entity_id == "Q300"
        assert labels[1].entity_id == "Q100"
        assert labels[2].entity_id == "Q200"

    def test_empty_input(self):
        from ivg_kg.data.reference import author_books_content_labels

        assert author_books_content_labels([]) == []


# ---------------------------------------------------------------------------
# reference_id
# ---------------------------------------------------------------------------


class TestReferenceId:
    def test_returns_string(self, assembled_ref):
        from ivg_kg.data.reference import reference_id

        rid = reference_id(assembled_ref)
        assert isinstance(rid, str)
        assert len(rid) > 0

    def test_deterministic_same_reference(self, assembled_ref):
        from ivg_kg.data.reference import reference_id

        rid1 = reference_id(assembled_ref)
        rid2 = reference_id(assembled_ref)
        assert rid1 == rid2

    def test_identical_references_same_id(self, minimal_snapshot, sample_labels):
        from ivg_kg.data.reference import assemble_reference, reference_id

        ref_a = assemble_reference(minimal_snapshot, sample_labels)
        ref_b = assemble_reference(minimal_snapshot, list(sample_labels))
        assert reference_id(ref_a) == reference_id(ref_b)

    def test_different_label_different_id(self, minimal_snapshot, sample_labels):
        from ivg_kg.data.reference import assemble_reference, reference_id

        ref_a = assemble_reference(minimal_snapshot, sample_labels)
        changed_labels = list(sample_labels) + [
            ContentLabel(
                entity_id="Q999",
                modality=Modality.TEXT,
                fact="new fact",
                source="description",
            )
        ]
        ref_b = assemble_reference(minimal_snapshot, changed_labels)
        assert reference_id(ref_a) != reference_id(ref_b)

    def test_different_snapshot_id_different_id(self, minimal_snapshot, sample_labels):
        from ivg_kg.data.reference import assemble_reference, reference_id

        ref_a = assemble_reference(minimal_snapshot, sample_labels)
        alt_snapshot = KGSnapshot(
            snapshot_id="snap-DIFFERENT",
            slice=minimal_snapshot.slice,
            domain_qid=minimal_snapshot.domain_qid,
            nodes=minimal_snapshot.nodes,
            edges=minimal_snapshot.edges,
        )
        ref_b = assemble_reference(alt_snapshot, sample_labels)
        assert reference_id(ref_a) != reference_id(ref_b)

    def test_no_random_no_time(self, assembled_ref):
        """reference_id must not depend on time or random state."""
        from ivg_kg.data.reference import reference_id

        ids = {reference_id(assembled_ref) for _ in range(10)}
        assert len(ids) == 1


# ---------------------------------------------------------------------------
# freeze_reference / load_reference
# ---------------------------------------------------------------------------


class TestFreezeLoadReference:
    def test_round_trip_equal(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference, load_reference

        out_dir = freeze_reference(assembled_ref, tmp_path / "ref")
        loaded = load_reference(out_dir)
        assert loaded == assembled_ref

    def test_snapshot_json_exists(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference

        out_dir = freeze_reference(assembled_ref, tmp_path / "ref")
        assert (out_dir / "snapshot.json").exists()

    def test_content_labels_json_exists(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference

        out_dir = freeze_reference(assembled_ref, tmp_path / "ref")
        assert (out_dir / "content_labels.json").exists()

    def test_content_labels_json_is_valid_json(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference

        out_dir = freeze_reference(assembled_ref, tmp_path / "ref")
        raw = (out_dir / "content_labels.json").read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, list)

    def test_content_labels_json_deterministic(self, assembled_ref, tmp_path):
        """Same reference frozen twice yields identical content_labels.json bytes."""
        from ivg_kg.data.reference import freeze_reference

        dir_a = freeze_reference(assembled_ref, tmp_path / "ref_a")
        dir_b = freeze_reference(assembled_ref, tmp_path / "ref_b")
        content_a = (dir_a / "content_labels.json").read_text(encoding="utf-8")
        content_b = (dir_b / "content_labels.json").read_text(encoding="utf-8")
        assert content_a == content_b

    def test_load_reconstructs_snapshot(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference, load_reference

        out_dir = freeze_reference(assembled_ref, tmp_path / "ref")
        loaded = load_reference(out_dir)
        assert loaded.snapshot == assembled_ref.snapshot

    def test_load_reconstructs_content_labels(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference, load_reference

        out_dir = freeze_reference(assembled_ref, tmp_path / "ref")
        loaded = load_reference(out_dir)
        assert loaded.content_labels == assembled_ref.content_labels

    def test_freeze_creates_directory(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference

        nested = tmp_path / "deep" / "nested" / "ref"
        out_dir = freeze_reference(assembled_ref, nested)
        assert out_dir.is_dir()

    def test_freeze_returns_path_object(self, assembled_ref, tmp_path):
        from ivg_kg.data.reference import freeze_reference

        out_dir = freeze_reference(assembled_ref, tmp_path / "ref")
        assert isinstance(out_dir, Path)

    def test_no_pickle_in_module(self):
        """The reference module must not import pickle anywhere."""
        import ivg_kg.data.reference as ref_module

        source = inspect.getsource(ref_module)
        assert "import pickle" not in source
        assert "pickle.dump" not in source
        assert "pickle.load" not in source


# ---------------------------------------------------------------------------
# Invariant #1 — no withhold/ablate on GradingReference
# ---------------------------------------------------------------------------


class TestInvariantNeverAblated:
    def test_grading_reference_has_no_withhold_method(self, assembled_ref):
        assert not hasattr(assembled_ref, "withhold")
        assert not hasattr(assembled_ref, "ablate")

    def test_module_exposes_no_ablation_function(self):
        import ivg_kg.data.reference as ref_module

        public_names = [name for name in dir(ref_module) if not name.startswith("_")]
        for name in public_names:
            assert "withhold" not in name.lower(), f"Found ablation-related name: {name}"
            assert "ablate" not in name.lower(), f"Found ablation-related name: {name}"

    def test_no_ablation_strings_in_source(self):
        """Structural guard: module source must not define withhold/ablate logic."""
        import ivg_kg.data.reference as ref_module

        source = inspect.getsource(ref_module)
        # Ensure no ablation function is defined (def withhold / def ablate)
        assert "def withhold" not in source
        assert "def ablate" not in source

    def test_reference_id_is_importable_from_module(self):
        """Smoke test: all public symbols import cleanly."""
        from ivg_kg.data.reference import (
            assemble_reference,
            author_books_content_labels,
            freeze_reference,
            load_reference,
            make_text_content_label,
            reference_id,
        )

        assert callable(assemble_reference)
        assert callable(author_books_content_labels)
        assert callable(freeze_reference)
        assert callable(load_reference)
        assert callable(make_text_content_label)
        assert callable(reference_id)

    def test_module_only_imports_allowed_deps(self):
        """reference.py must only import ivg_kg, stdlib, and nothing else."""
        import ivg_kg.data.reference as ref_module

        source = inspect.getsource(ref_module)
        # These provider SDKs must not appear
        forbidden = ["import requests", "import boto3", "import openai", "import anthropic"]
        for forbidden_import in forbidden:
            assert forbidden_import not in source, f"Forbidden import found: {forbidden_import}"
