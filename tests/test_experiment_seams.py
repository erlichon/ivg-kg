"""
Tests for the three data/experiment seam formats.

Covers:
  1. GoldQASet (gold_qa.py) -- JSON round-trip, adversarial flag, folds,
                               modality split, stub file loads and validates.
  2. QuestionBank (question_bank.py) -- JSON round-trip, tier coverage,
                                        stub file loads and validates.
  3. AblationManifest (perturbation/base.py) -- stub manifest file round-trips
                                                via AblationManifest.from_json,
                                                perturbation types reconstruct.

Run with:  pytest tests/test_experiment_seams.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ivg_kg.experiment.gold_qa import (
    ExpectedClaimOutcome,
    GoldFold,
    GoldQAItem,
    GoldQASet,
    load_gold_qa_set,
)
from ivg_kg.experiment.question_bank import (
    FactType,
    QuestionBank,
    QuestionBankItem,
    QuestionTier,
    load_question_bank,
)
from ivg_kg.perturbation import (
    AblationManifest,
)
from ivg_kg.schema import ClaimStatus, Modality

# ---------------------------------------------------------------------------
# Shared paths
# ---------------------------------------------------------------------------

FROZEN_DIR = Path("data/frozen/books/books-p0-v1")
GOLD_STUB_PATH = FROZEN_DIR / "gold_qa.stub.json"
BANK_STUB_PATH = FROZEN_DIR / "question_bank.stub.json"
MANIFEST_STUB_PATH = FROZEN_DIR / "manifest.stub.json"


# ---------------------------------------------------------------------------
# Helpers: minimal valid objects
# ---------------------------------------------------------------------------


def _make_gold_item(
    item_id: str = "gq-001",
    adversarial: bool = False,
    fold: GoldFold = GoldFold.CALIBRATION,
    modality: Modality = Modality.STRUCTURE,
    expected_status: ClaimStatus = ClaimStatus.RETRIEVED,
) -> GoldQAItem:
    return GoldQAItem(
        item_id=item_id,
        question="Who wrote The Glass Menagerie?",
        entity_id="Q678832",
        slice_id="books-p0-v1",
        expected_outcomes=[
            ExpectedClaimOutcome(
                claim_text="Tennessee Williams wrote The Glass Menagerie.",
                expected_status=expected_status,
                modality=modality,
            )
        ],
        adversarial_negative=adversarial,
        fold=fold,
    )


def _make_gold_set(items: list[GoldQAItem] | None = None) -> GoldQASet:
    if items is None:
        items = [
            _make_gold_item("gq-001", fold=GoldFold.CALIBRATION),
            _make_gold_item("gq-002", fold=GoldFold.SWEEP),
            _make_gold_item("gq-003", adversarial=True, fold=GoldFold.SWEEP,
                            expected_status=ClaimStatus.FABRICATED),
        ]
    return GoldQASet(set_id="gold-books-stub", slice_id="books-p0-v1", items=items)


def _make_bank_item(
    item_id: str = "qb-001",
    tier: QuestionTier = QuestionTier.ONE_HOP_RETRIEVAL,
    fact_type: FactType | None = FactType.KNOWLEDGE_STRUCTURE,
) -> QuestionBankItem:
    return QuestionBankItem(
        item_id=item_id,
        question="What genre is The Glass Menagerie?",
        tier=tier,
        entity_id="Q678832",
        slice_id="books-p0-v1",
        fact_type=fact_type,
    )


# ===========================================================================
# 1. GoldQASet
# ===========================================================================


class TestGoldQAItemModel:
    def test_basic_construction(self) -> None:
        item = _make_gold_item()
        assert item.item_id == "gq-001"
        assert not item.adversarial_negative
        assert item.fold == GoldFold.CALIBRATION

    def test_adversarial_negative_flag(self) -> None:
        item = _make_gold_item(adversarial=True, expected_status=ClaimStatus.FABRICATED)
        assert item.adversarial_negative is True
        assert item.expected_outcomes[0].expected_status == ClaimStatus.FABRICATED

    def test_json_round_trip(self) -> None:
        item = _make_gold_item("gq-rt", adversarial=True, fold=GoldFold.SWEEP,
                               expected_status=ClaimStatus.FABRICATED)
        dumped = item.model_dump_json()
        restored = GoldQAItem.model_validate_json(dumped)
        assert restored.item_id == item.item_id
        assert restored.adversarial_negative is True
        assert restored.fold == GoldFold.SWEEP
        assert restored.expected_outcomes[0].expected_status == ClaimStatus.FABRICATED

    def test_expected_outcomes_min_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            GoldQAItem(
                item_id="bad",
                question="q",
                entity_id="Q1",
                slice_id="books-p0-v1",
                expected_outcomes=[],  # violates min_length=1
                fold=GoldFold.CALIBRATION,
            )

    def test_modality_preserved_on_expected_outcome(self) -> None:
        item = _make_gold_item(modality=Modality.TEXT)
        assert item.expected_outcomes[0].modality == Modality.TEXT


class TestGoldQASet:
    def test_construction(self) -> None:
        gs = _make_gold_set()
        assert gs.set_id == "gold-books-stub"
        assert len(gs.items) == 3

    def test_calibration_items_selector(self) -> None:
        gs = _make_gold_set()
        cal = gs.calibration_items()
        assert all(it.fold == GoldFold.CALIBRATION for it in cal)
        assert len(cal) >= 1

    def test_sweep_items_selector(self) -> None:
        gs = _make_gold_set()
        sweep = gs.sweep_items()
        assert all(it.fold == GoldFold.SWEEP for it in sweep)
        assert len(sweep) >= 1

    def test_adversarial_items_selector(self) -> None:
        gs = _make_gold_set()
        adv = gs.adversarial_items()
        assert len(adv) >= 1
        assert all(it.adversarial_negative for it in adv)

    def test_adversarial_items_expected_fabricated(self) -> None:
        gs = _make_gold_set()
        adv = gs.adversarial_items()
        for it in adv:
            assert any(
                oc.expected_status == ClaimStatus.FABRICATED
                for oc in it.expected_outcomes
            ), f"adversarial item {it.item_id!r} must have FABRICATED expected outcome"

    def test_items_by_modality_structure(self) -> None:
        gs = _make_gold_set()
        struct_items = gs.items_by_modality(Modality.STRUCTURE)
        assert len(struct_items) >= 1

    def test_assert_complete_passes_for_valid_set(self) -> None:
        gs = _make_gold_set()
        gs.assert_complete()  # must not raise

    def test_assert_complete_fails_no_adversarial(self) -> None:
        items = [
            _make_gold_item("gq-001", fold=GoldFold.CALIBRATION),
            _make_gold_item("gq-002", fold=GoldFold.SWEEP),
        ]
        gs = GoldQASet(set_id="x", slice_id="books-p0-v1", items=items)
        with pytest.raises(ValueError, match="adversarial"):
            gs.assert_complete()

    def test_assert_complete_fails_no_calibration_fold(self) -> None:
        items = [
            _make_gold_item("gq-001", fold=GoldFold.SWEEP),
            _make_gold_item("gq-002", adversarial=True, fold=GoldFold.SWEEP,
                            expected_status=ClaimStatus.FABRICATED),
        ]
        gs = GoldQASet(set_id="x", slice_id="books-p0-v1", items=items)
        with pytest.raises(ValueError, match="calibration"):
            gs.assert_complete()

    def test_assert_complete_fails_no_sweep_fold(self) -> None:
        items = [
            _make_gold_item("gq-001", fold=GoldFold.CALIBRATION),
            _make_gold_item("gq-002", adversarial=True, fold=GoldFold.CALIBRATION,
                            expected_status=ClaimStatus.FABRICATED),
        ]
        gs = GoldQASet(set_id="x", slice_id="books-p0-v1", items=items)
        with pytest.raises(ValueError, match="sweep"):
            gs.assert_complete()

    def test_assert_complete_fails_duplicate_item_ids(self) -> None:
        items = [
            _make_gold_item("dup", fold=GoldFold.CALIBRATION),
            _make_gold_item("dup", adversarial=True, fold=GoldFold.SWEEP,
                            expected_status=ClaimStatus.FABRICATED),
        ]
        gs = GoldQASet(set_id="x", slice_id="books-p0-v1", items=items)
        with pytest.raises(ValueError, match="duplicate"):
            gs.assert_complete()

    def test_assert_complete_fails_adversarial_without_fabricated_outcome(self) -> None:
        # adversarial_negative=True but expected outcome is RETRIEVED, not FABRICATED.
        # assert_complete() must reject this; it silently defeats the section-6 control.
        items = [
            _make_gold_item("gq-001", fold=GoldFold.CALIBRATION),
            _make_gold_item(
                "gq-002",
                adversarial=True,
                fold=GoldFold.SWEEP,
                expected_status=ClaimStatus.RETRIEVED,  # wrong: must be FABRICATED
            ),
        ]
        gs = GoldQASet(set_id="x", slice_id="books-p0-v1", items=items)
        with pytest.raises(ValueError, match="FABRICATED"):
            gs.assert_complete()

    def test_json_round_trip(self) -> None:
        gs = _make_gold_set()
        serialized = gs.to_json()
        restored = GoldQASet.from_json(serialized)
        assert restored.set_id == gs.set_id
        assert len(restored.items) == len(gs.items)
        for orig, rest in zip(gs.items, restored.items, strict=True):
            assert orig.item_id == rest.item_id
            assert orig.adversarial_negative == rest.adversarial_negative
            assert orig.fold == rest.fold

    def test_to_json_produces_valid_json(self) -> None:
        gs = _make_gold_set()
        parsed = json.loads(gs.to_json())
        assert "items" in parsed
        assert parsed["set_id"] == "gold-books-stub"

    def test_schema_version_present(self) -> None:
        gs = _make_gold_set()
        data = json.loads(gs.to_json())
        assert data["schema_version"] == "1.0"


class TestGoldQAStubFile:
    """The stub file at GOLD_STUB_PATH must load, validate, and meet
    minimum structural requirements."""

    def test_stub_file_exists(self) -> None:
        assert GOLD_STUB_PATH.exists(), f"stub file not found: {GOLD_STUB_PATH}"

    def test_stub_file_loads_and_validates(self) -> None:
        gs = load_gold_qa_set(GOLD_STUB_PATH)
        assert isinstance(gs, GoldQASet)
        assert len(gs.items) >= 2

    def test_stub_has_at_least_one_adversarial_item(self) -> None:
        gs = load_gold_qa_set(GOLD_STUB_PATH)
        assert len(gs.adversarial_items()) >= 1, (
            "gold stub must contain >=1 adversarial value-swapped negative"
        )

    def test_stub_adversarial_items_have_fabricated_outcome(self) -> None:
        gs = load_gold_qa_set(GOLD_STUB_PATH)
        for it in gs.adversarial_items():
            assert any(
                oc.expected_status == ClaimStatus.FABRICATED
                for oc in it.expected_outcomes
            ), f"adversarial item {it.item_id!r} must expect FABRICATED"

    def test_stub_assert_complete_passes(self) -> None:
        gs = load_gold_qa_set(GOLD_STUB_PATH)
        gs.assert_complete()

    def test_stub_round_trips_via_to_from_json(self) -> None:
        gs = load_gold_qa_set(GOLD_STUB_PATH)
        restored = GoldQASet.from_json(gs.to_json())
        assert restored.set_id == gs.set_id
        assert len(restored.items) == len(gs.items)


# ===========================================================================
# 2. QuestionBank
# ===========================================================================


class TestQuestionBankItemModel:
    def test_basic_construction(self) -> None:
        item = _make_bank_item()
        assert item.item_id == "qb-001"
        assert item.tier == QuestionTier.ONE_HOP_RETRIEVAL

    def test_json_round_trip(self) -> None:
        item = _make_bank_item("qb-rt", tier=QuestionTier.MULTI_HOP_REASONING,
                               fact_type=None)
        dumped = item.model_dump_json()
        restored = QuestionBankItem.model_validate_json(dumped)
        assert restored.item_id == "qb-rt"
        assert restored.tier == QuestionTier.MULTI_HOP_REASONING
        assert restored.fact_type is None

    def test_fact_type_optional(self) -> None:
        item = _make_bank_item(fact_type=None)
        assert item.fact_type is None

    def test_out_of_slice_default_false(self) -> None:
        item = _make_bank_item()
        assert item.out_of_slice_expected is False


class TestQuestionBank:
    def _make_bank(self) -> QuestionBank:
        items = [
            _make_bank_item("qb-001", tier=QuestionTier.ONE_HOP_RETRIEVAL,
                            fact_type=FactType.KNOWLEDGE_STRUCTURE),
            _make_bank_item("qb-002", tier=QuestionTier.MULTI_HOP_REASONING,
                            fact_type=None),
            _make_bank_item("qb-003", tier=QuestionTier.ABLATED_ENTITY,
                            fact_type=FactType.GENRE_FORM),
        ]
        return QuestionBank(bank_id="bank-books-stub", slice_id="books-p0-v1",
                            items=items)

    def test_tiers_present_covers_all_three(self) -> None:
        bank = self._make_bank()
        tiers = bank.tiers_present()
        assert QuestionTier.ONE_HOP_RETRIEVAL in tiers
        assert QuestionTier.MULTI_HOP_REASONING in tiers
        assert QuestionTier.ABLATED_ENTITY in tiers

    def test_items_by_tier_selector(self) -> None:
        bank = self._make_bank()
        one_hop = bank.items_by_tier(QuestionTier.ONE_HOP_RETRIEVAL)
        assert all(it.tier == QuestionTier.ONE_HOP_RETRIEVAL for it in one_hop)

    def test_json_round_trip(self) -> None:
        bank = self._make_bank()
        serialized = bank.to_json()
        restored = QuestionBank.from_json(serialized)
        assert restored.bank_id == bank.bank_id
        assert len(restored.items) == len(bank.items)
        for orig, rest in zip(bank.items, restored.items, strict=True):
            assert orig.item_id == rest.item_id
            assert orig.tier == rest.tier

    def test_to_json_produces_valid_json(self) -> None:
        bank = self._make_bank()
        parsed = json.loads(bank.to_json())
        assert "items" in parsed
        assert parsed["bank_id"] == "bank-books-stub"

    def test_schema_version_present(self) -> None:
        bank = self._make_bank()
        data = json.loads(bank.to_json())
        assert data["schema_version"] == "1.0"


class TestQuestionBankStubFile:
    """The stub file at BANK_STUB_PATH must load, validate, and span all tiers."""

    def test_stub_file_exists(self) -> None:
        assert BANK_STUB_PATH.exists(), f"stub file not found: {BANK_STUB_PATH}"

    def test_stub_file_loads_and_validates(self) -> None:
        bank = load_question_bank(BANK_STUB_PATH)
        assert isinstance(bank, QuestionBank)
        assert len(bank.items) >= 3

    def test_stub_spans_all_three_tiers(self) -> None:
        bank = load_question_bank(BANK_STUB_PATH)
        tiers = bank.tiers_present()
        assert QuestionTier.ONE_HOP_RETRIEVAL in tiers, "stub missing one_hop_retrieval tier"
        assert QuestionTier.MULTI_HOP_REASONING in tiers, "stub missing multi_hop_reasoning tier"
        assert QuestionTier.ABLATED_ENTITY in tiers, "stub missing ablated_entity tier"

    def test_stub_round_trips_via_to_from_json(self) -> None:
        bank = load_question_bank(BANK_STUB_PATH)
        restored = QuestionBank.from_json(bank.to_json())
        assert restored.bank_id == bank.bank_id
        assert len(restored.items) == len(bank.items)


# ===========================================================================
# 3. AblationManifest stub file round-trip
# ===========================================================================


class TestManifestStubFile:
    """The stub manifest at MANIFEST_STUB_PATH must round-trip through
    AblationManifest.from_json and reconstruct the correct perturbation types."""

    def test_stub_file_exists(self) -> None:
        assert MANIFEST_STUB_PATH.exists(), f"stub file not found: {MANIFEST_STUB_PATH}"

    def test_stub_is_valid_json(self) -> None:
        raw = MANIFEST_STUB_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert "base_slice_id" in parsed
        assert "perturbations" in parsed

    def test_stub_round_trips_via_from_json(self) -> None:
        raw = MANIFEST_STUB_PATH.read_text(encoding="utf-8")
        manifest = AblationManifest.from_json(raw)
        assert isinstance(manifest.base_slice_id, str)
        assert len(manifest.perturbations) >= 2

    def test_stub_contains_text_content_absence(self) -> None:
        raw = MANIFEST_STUB_PATH.read_text(encoding="utf-8")
        manifest = AblationManifest.from_json(raw)
        types = [type(p).__name__ for p in manifest.perturbations]
        assert "TextContentAbsence" in types

    def test_stub_contains_knowledge_absence(self) -> None:
        raw = MANIFEST_STUB_PATH.read_text(encoding="utf-8")
        manifest = AblationManifest.from_json(raw)
        types = [type(p).__name__ for p in manifest.perturbations]
        assert "KnowledgeAbsence" in types

    def test_stub_to_json_from_json_is_stable(self) -> None:
        raw = MANIFEST_STUB_PATH.read_text(encoding="utf-8")
        manifest = AblationManifest.from_json(raw)
        re_serialized = manifest.to_json()
        manifest2 = AblationManifest.from_json(re_serialized)
        assert manifest2.base_slice_id == manifest.base_slice_id
        assert len(manifest2.perturbations) == len(manifest.perturbations)
        for p1, p2 in zip(manifest.perturbations, manifest2.perturbations, strict=True):
            assert p1.id == p2.id
            assert type(p1) is type(p2)

    def test_stub_perturbation_ids_are_stable(self) -> None:
        # Ids must be deterministic: two from_json calls must yield same ids.
        raw = MANIFEST_STUB_PATH.read_text(encoding="utf-8")
        m1 = AblationManifest.from_json(raw)
        m2 = AblationManifest.from_json(raw)
        assert m1.active_entry_ids() == m2.active_entry_ids()
