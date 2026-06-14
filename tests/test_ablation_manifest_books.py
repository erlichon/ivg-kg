"""EX2 tests: fixed books ablation manifest + manifest-driven sweep adapter.

TDD suite authored BEFORE manifest.json and ablation.py exist (RED->GREEN).

Coverage:
  1. Manifest loads/validates via AblationManifest.from_json; to_json() round-trips
     (parse-equal AND byte-stable on re-serialize).
  2. Exactly 5 TextContentAbsence entries for the expected entities; exactly 3
     KnowledgeAbsence entries for the expected triples.
  3. Every TextContentAbsence entity_id is a node in snapshot.json; every
     KnowledgeAbsence triple exists in edges.
  4. Adapter: content question under CONTENT_ABSENT -> its TextContentAbsence;
     under KNOWLEDGE_ABSENT -> []; FULL/FULL_NO_EDIT_RERUN -> []; IMAGE_ABSENT ->
     ValueError. Knowledge question under KNOWLEDGE_ABSENT -> its KnowledgeAbsence;
     under CONTENT_ABSENT -> [].
  5. End-to-end smoke: run_sweep with manifest_perturbations_for over full bank.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ivg_kg.data.graph_store import load_snapshot
from ivg_kg.data.reference import assemble_reference, author_books_content_labels
from ivg_kg.experiment import run_sweep
from ivg_kg.experiment.ablation import manifest_perturbations_for
from ivg_kg.experiment.question_bank import load_question_bank
from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.perturbation.base import AblationManifest
from ivg_kg.perturbation.knowledge_absence import KnowledgeAbsence
from ivg_kg.perturbation.text_content_absence import TextContentAbsence
from ivg_kg.schema import Condition, GenerationContext, GroundingConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SLICE_DIR = Path(__file__).parent.parent / "data" / "frozen" / "books" / "books-p0-v1"
_MANIFEST_PATH = _SLICE_DIR / "manifest.json"
_SNAPSHOT_PATH = _SLICE_DIR / "snapshot.json"
_BANK_PATH = _SLICE_DIR / "question_bank.json"
_CONTENT_LABELS_PATH = _SLICE_DIR / "content_labels.json"

# ---------------------------------------------------------------------------
# Expected constants (fixed design)
# ---------------------------------------------------------------------------

EXPECTED_TEXT_ABSENCE_ENTITY_IDS = {
    "Q105485274",  # qb-b004
    "Q96409397",   # qb-b005
    "Q102376902",  # qb-b007
    "Q106995049",  # qb-b008
    "Q1219497",    # qb-b014
}

EXPECTED_KNOWLEDGE_ABSENCE_TRIPLES = [
    ("Q678832",   "P123", "Q744182"),   # qb-b002
    ("Q112169066", "P123", "Q1508259"), # qb-b012
    ("Q4338113",  "P50",  "Q84177"),    # qb-b015
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def manifest() -> AblationManifest:
    raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    return AblationManifest.from_json(raw)


@pytest.fixture(scope="module")
def snapshot_data() -> dict:
    return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bank():
    return load_question_bank(_BANK_PATH)


@pytest.fixture(scope="module")
def reference():
    snapshot = load_snapshot(_SLICE_DIR)
    raw_labels = json.loads(_CONTENT_LABELS_PATH.read_text(encoding="utf-8"))
    facts = [(lb["entity_id"], lb["fact"], lb["source"]) for lb in raw_labels]
    content_labels = author_books_content_labels(facts)
    return assemble_reference(snapshot, content_labels)


# ---------------------------------------------------------------------------
# 1. Round-trip
# ---------------------------------------------------------------------------


def test_manifest_file_exists():
    assert _MANIFEST_PATH.exists(), f"manifest.json not found at {_MANIFEST_PATH}"


def test_manifest_from_json_no_error(manifest):
    assert isinstance(manifest, AblationManifest)


def test_manifest_base_slice_id(manifest):
    assert manifest.base_slice_id == "books-p0-v1"


def test_manifest_to_json_round_trips_byte_stable(manifest):
    raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    reconstructed = AblationManifest.from_json(raw)
    # Byte-stable: re-serializing must produce the same string
    assert reconstructed.to_json() == manifest.to_json()


def test_manifest_to_json_parse_equal(manifest):
    raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    data_original = json.loads(raw)
    data_roundtrip = json.loads(manifest.to_json())
    assert data_roundtrip["base_slice_id"] == data_original["base_slice_id"]
    # Compare perturbation entries by type and identity fields
    rt_entries = {e["id"]: e for e in data_roundtrip["perturbations"]}
    orig_entries = {e["id"]: e for e in data_original["perturbations"]}
    assert rt_entries == orig_entries


# ---------------------------------------------------------------------------
# 2. Counts and identity
# ---------------------------------------------------------------------------


def test_manifest_has_5_text_content_absence(manifest):
    tca = [p for p in manifest.perturbations if isinstance(p, TextContentAbsence)]
    assert len(tca) == 5, f"Expected 5 TextContentAbsence, got {len(tca)}"


def test_manifest_has_3_knowledge_absence(manifest):
    ka = [p for p in manifest.perturbations if isinstance(p, KnowledgeAbsence)]
    assert len(ka) == 3, f"Expected 3 KnowledgeAbsence, got {len(ka)}"


def test_manifest_text_absence_entity_ids(manifest):
    tca = [p for p in manifest.perturbations if isinstance(p, TextContentAbsence)]
    actual = {p.entity_id for p in tca}
    assert actual == EXPECTED_TEXT_ABSENCE_ENTITY_IDS


def test_manifest_knowledge_absence_triples(manifest):
    ka = [p for p in manifest.perturbations if isinstance(p, KnowledgeAbsence)]
    actual = set()
    for k in ka:
        for ref in k.triples_to_withhold:
            actual.add((ref.subject_id, ref.property_id, ref.object_id))
    expected = {(s, p, o) for s, p, o in EXPECTED_KNOWLEDGE_ABSENCE_TRIPLES}
    assert actual == expected


# ---------------------------------------------------------------------------
# 3. Slice integrity
# ---------------------------------------------------------------------------


def test_text_absence_entity_ids_are_in_snapshot(manifest, snapshot_data):
    node_ids = {n["id"] for n in snapshot_data["nodes"]}
    tca = [p for p in manifest.perturbations if isinstance(p, TextContentAbsence)]
    for p in tca:
        assert p.entity_id in node_ids, f"entity {p.entity_id} not in snapshot nodes"


def test_knowledge_absence_triples_exist_in_snapshot(manifest, snapshot_data):
    edges = snapshot_data["edges"]
    edge_set = {(e["subject_id"], e["property_id"], e["object_id"]) for e in edges}
    ka = [p for p in manifest.perturbations if isinstance(p, KnowledgeAbsence)]
    for k in ka:
        for ref in k.triples_to_withhold:
            key = (ref.subject_id, ref.property_id, ref.object_id)
            assert key in edge_set, f"triple {key} not found in snapshot edges"


# ---------------------------------------------------------------------------
# 4. Adapter behaviour
# ---------------------------------------------------------------------------


def _get_item(bank, item_id):
    for it in bank.items:
        if it.item_id == item_id:
            return it
    raise KeyError(item_id)


def test_adapter_full_returns_empty_for_all(manifest, bank, reference):
    fn = manifest_perturbations_for(manifest)
    for item in bank.items:
        result = fn(item, Condition.FULL, reference)
        assert result == [], f"FULL should return [] for {item.item_id}"


def test_adapter_full_no_edit_rerun_returns_empty(manifest, bank, reference):
    fn = manifest_perturbations_for(manifest)
    for item in bank.items:
        result = fn(item, Condition.FULL_NO_EDIT_RERUN, reference)
        assert result == [], f"FULL_NO_EDIT_RERUN should return [] for {item.item_id}"


def test_adapter_image_absent_raises(manifest, bank, reference):
    fn = manifest_perturbations_for(manifest)
    item = bank.items[0]
    with pytest.raises(ValueError):
        fn(item, Condition.IMAGE_ABSENT, reference)


# Content questions: CONTENT_ABSENT -> their TextContentAbsence; KNOWLEDGE_ABSENT -> []
@pytest.mark.parametrize("item_id,entity_id", [
    ("qb-b004", "Q105485274"),
    ("qb-b005", "Q96409397"),
    ("qb-b007", "Q102376902"),
    ("qb-b008", "Q106995049"),
    ("qb-b014", "Q1219497"),
])
def test_adapter_content_item_content_absent(manifest, bank, reference, item_id, entity_id):
    fn = manifest_perturbations_for(manifest)
    item = _get_item(bank, item_id)
    result = fn(item, Condition.CONTENT_ABSENT, reference)
    assert len(result) == 1
    assert isinstance(result[0], TextContentAbsence)
    assert result[0].entity_id == entity_id


@pytest.mark.parametrize("item_id", ["qb-b004", "qb-b005", "qb-b007", "qb-b008", "qb-b014"])
def test_adapter_content_item_knowledge_absent_returns_empty(manifest, bank, reference, item_id):
    fn = manifest_perturbations_for(manifest)
    item = _get_item(bank, item_id)
    result = fn(item, Condition.KNOWLEDGE_ABSENT, reference)
    assert result == [], f"content-arm item {item_id} should have no knowledge absence"


# Knowledge questions: KNOWLEDGE_ABSENT -> their KnowledgeAbsence; CONTENT_ABSENT -> []
@pytest.mark.parametrize("item_id,subject,prop,obj", [
    ("qb-b002", "Q678832",    "P123", "Q744182"),
    ("qb-b012", "Q112169066", "P123", "Q1508259"),
    ("qb-b015", "Q4338113",   "P50",  "Q84177"),
])
def test_adapter_knowledge_item_knowledge_absent(manifest, bank, reference, item_id, subject, prop, obj):
    fn = manifest_perturbations_for(manifest)
    item = _get_item(bank, item_id)
    result = fn(item, Condition.KNOWLEDGE_ABSENT, reference)
    assert len(result) == 1
    assert isinstance(result[0], KnowledgeAbsence)
    refs = result[0].triples_to_withhold
    assert len(refs) == 1
    assert refs[0].subject_id == subject
    assert refs[0].property_id == prop
    assert refs[0].object_id == obj


@pytest.mark.parametrize("item_id", ["qb-b002", "qb-b012", "qb-b015"])
def test_adapter_knowledge_item_content_absent_returns_empty(manifest, bank, reference, item_id):
    fn = manifest_perturbations_for(manifest)
    item = _get_item(bank, item_id)
    result = fn(item, Condition.CONTENT_ABSENT, reference)
    assert result == [], f"knowledge-arm item {item_id} should have no text content absence"


# Items whose entity_id does not appear in ANY manifest entry: both conditions return [].
# qb-b001 (Q678832), qb-b003 (Q678832), qb-b006 (Q112169066), qb-b009 (Q4338113),
# qb-b010 (Q105485274) all share entity_id with a manifest entry, so they DO receive
# that perturbation under the matching condition (the adapter indexes by entity_id).
# Only items whose entity_id appears in no manifest entry return [] for both arms.
@pytest.mark.parametrize("item_id", ["qb-b011", "qb-b013"])
def test_adapter_truly_neutral_item_returns_empty_both_arms(manifest, bank, reference, item_id):
    fn = manifest_perturbations_for(manifest)
    item = _get_item(bank, item_id)
    assert fn(item, Condition.CONTENT_ABSENT, reference) == []
    assert fn(item, Condition.KNOWLEDGE_ABSENT, reference) == []


# Items sharing entity_id with a knowledge-arm manifest entry also receive it.
# qb-b001/qb-b003 share Q678832 with the qb-b002 knowledge-absence entry;
# qb-b006 shares Q112169066 with qb-b012; qb-b009 shares Q4338113 with qb-b015.
@pytest.mark.parametrize("item_id,entity_id", [
    ("qb-b001", "Q678832"),
    ("qb-b003", "Q678832"),
    ("qb-b006", "Q112169066"),
    ("qb-b009", "Q4338113"),
])
def test_adapter_entity_overlap_knowledge_arm(manifest, bank, reference, item_id, entity_id):
    """Shared-entity items get the knowledge-arm perturbation under KNOWLEDGE_ABSENT."""
    fn = manifest_perturbations_for(manifest)
    item = _get_item(bank, item_id)
    result = fn(item, Condition.KNOWLEDGE_ABSENT, reference)
    assert len(result) == 1
    assert isinstance(result[0], KnowledgeAbsence)
    assert entity_id in result[0].touched_entities()
    # Under CONTENT_ABSENT these items get nothing (no text-absence entry for them).
    assert fn(item, Condition.CONTENT_ABSENT, reference) == []


# qb-b010 shares Q105485274 with the content-arm entry qb-b004.
def test_adapter_entity_overlap_content_arm(manifest, bank, reference):
    """qb-b010 (Q105485274, multi-hop) shares entity with the content-arm entry."""
    fn = manifest_perturbations_for(manifest)
    item = _get_item(bank, "qb-b010")
    result = fn(item, Condition.CONTENT_ABSENT, reference)
    assert len(result) == 1
    assert isinstance(result[0], TextContentAbsence)
    assert result[0].entity_id == "Q105485274"
    # Under KNOWLEDGE_ABSENT: no knowledge-arm entry for Q105485274.
    assert fn(item, Condition.KNOWLEDGE_ABSENT, reference) == []


# ---------------------------------------------------------------------------
# 5. End-to-end smoke: run_sweep with manifest_perturbations_for
# ---------------------------------------------------------------------------


class _CannedStubClient(BaseAIClient):
    """Offline canned generator for smoke tests (no model, no network)."""

    def _generate(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        answer = (
            "The Glass Menagerie was written by Tennessee Williams. "
            "Random House is the publisher. "
            f"[seed={seed}]"
        )
        return GenerationResult(answer=answer)


def test_end_to_end_sweep_smoke(manifest, bank, reference):
    fn = manifest_perturbations_for(manifest)
    config = GroundingConfig(
        entailment="lexical",
        linker="label_alias",
        extractor="rule_based",
        tau=0.4,
    )
    runset = run_sweep(
        bank,
        reference,
        _CannedStubClient(),
        conditions=[Condition.FULL, Condition.CONTENT_ABSENT, Condition.KNOWLEDGE_ABSENT],
        n_runs=1,
        config=config,
        perturbations_for=fn,
    )
    # One run per (item, condition)
    expected_run_count_min = len(bank.items) * 3  # 3 conditions
    assert len(runset.runs) >= expected_run_count_min
    # All items appear in the runset
    item_ids_in_runs = {r.run_id.split("--")[0] for r in runset.runs}
    for item in bank.items:
        assert item.item_id in item_ids_in_runs, f"item {item.item_id} missing from runs"
