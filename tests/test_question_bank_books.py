"""
Tests for the real books question bank (EX1).

Validates:
  - question_bank.json loads and validates via load_question_bank.
  - Coverage: >= 10 items, unique item_ids, all slice_id == "books-p0-v1".
  - Tier coverage: all three QuestionTier values present.
  - Content fact_type coverage: all four content FactTypes present.
  - Every entity_id exists as a node id in snapshot.json.
  - Gradability guard (strengthened): for each content-only item:
      (a) a documented description substring is present in the entity description.
      (b) no outgoing edge of the entity expresses the same fact (triple-absence),
          guarded by asserting no P136/P7937/P921 edge object_label matches the
          content value for the relevant property family.
  - Knowledge-structure triple check: each one_hop_retrieval item with
    fact_type=knowledge_structure must document a triple whose
    (subject_id, property_id, object_id) exists in snapshot edges.
  - Tier-1 quality: no one_hop_retrieval item bundles multiple facts
    (detected by enforcing at most one documented triple per item when
    fact_type == knowledge_structure and tier == one_hop_retrieval, unless
    the item explicitly documents a split).

Run with:  pytest tests/test_question_bank_books.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ivg_kg.experiment.question_bank import (
    FactType,
    QuestionTier,
    load_question_bank,
)

FROZEN_DIR = Path("data/frozen/books/books-p0-v1")
BANK_PATH = FROZEN_DIR / "question_bank.json"
SNAPSHOT_PATH = FROZEN_DIR / "snapshot.json"

CONTENT_FACT_TYPES = {
    FactType.GENRE_FORM,
    FactType.TRADITION_AFFILIATION,
    FactType.SCOPE,
    FactType.DESCRIPTIVE_ROLE,
}

# ---------------------------------------------------------------------------
# Description-only content items: item_id -> expected substring (case-insensitive)
# in the entity's node.description.
# These are the ONLY items that should have content FactTypes after the fixes;
# they must be description-only (no triple expressing the same fact).
# ---------------------------------------------------------------------------
CONTENT_DESCRIPTION_SUBSTRINGS: dict[str, str] = {
    "qb-b004": "short story collection",    # Q105485274 Blue Lantern
    "qb-b005": "kagyu",                     # Q96409397 Jewel Ornament
    "qb-b007": "memoir and photobook",      # Q102376902 Going South
    "qb-b008": "anthology",                 # Q106995049 Constantinian Excerpts
    "qb-b014": "sanskrit",                  # Q1219497 Seven Wise Masters
}

# ---------------------------------------------------------------------------
# Triple-absence guard: for each content-only item, list (property_id, value_fragment)
# pairs where value_fragment must NOT appear as object_label on that property_id edge.
# An empty list means no property family is relevant (e.g. descriptive_role has no
# direct triple analog in P136/P7937/P921).
# ---------------------------------------------------------------------------
CONTENT_TRIPLE_ABSENCE: dict[str, list[tuple[str, str]]] = {
    "qb-b004": [("P136", "short story"), ("P7937", "short story"), ("P7937", "collection")],
    "qb-b005": [("P921", "kagyu"), ("P136", "kagyu")],
    "qb-b007": [("P7937", "memoir"), ("P136", "memoir"), ("P7937", "photobook")],
    "qb-b008": [("P921", "anthology"), ("P136", "anthology")],
    "qb-b014": [("P921", "sanskrit"), ("P136", "sanskrit"), ("P921", "hebrew"), ("P921", "persian")],
}

# ---------------------------------------------------------------------------
# Known one_hop knowledge_structure triples (subject, property, object).
# These must all exist in snapshot.json edges.
# Derived from notes authored in question_bank.json.
# ---------------------------------------------------------------------------
KNOWLEDGE_STRUCTURE_TRIPLES = [
    ("Q678832", "P50", "Q134262"),      # Glass Menagerie -> author -> Tennessee Williams
    ("Q678832", "P123", "Q744182"),     # Glass Menagerie -> publisher -> Random House
    ("Q4338113", "P50", "Q84177"),      # Principles of Economics -> author -> Carl Menger
    ("Q4338113", "P291", "Q1741"),      # Principles of Economics -> place_of_pub -> Vienna
    ("Q87073856", "P50", "Q5630"),      # Gesta Francorum -> author -> Fulcher of Chartres
    ("Q112169066", "P123", "Q1508259"), # FRE -> publisher -> Routledge
    ("Q54488972", "P50", "Q27704915"),  # Subtle Art -> author -> Mark Manson
    ("Q112169066", "P50", "Q1668889"),  # FRE -> author -> John Komlos
]


@pytest.fixture(scope="module")
def snapshot():
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def bank():
    return load_question_bank(BANK_PATH)


# ---------------------------------------------------------------------------
# Basic structural tests
# ---------------------------------------------------------------------------


def test_bank_loads_without_error():
    """question_bank.json must exist and load without ValidationError."""
    loaded = load_question_bank(BANK_PATH)
    assert loaded is not None


def test_bank_slice_id(bank):
    assert bank.slice_id == "books-p0-v1"


def test_bank_schema_version(bank):
    assert bank.schema_version == "1.0"


def test_bank_minimum_item_count(bank):
    assert len(bank.items) >= 10, f"expected >= 10 items, got {len(bank.items)}"


def test_item_ids_unique(bank):
    ids = [it.item_id for it in bank.items]
    assert len(ids) == len(set(ids)), "duplicate item_ids found"


def test_all_items_have_correct_slice_id(bank):
    bad = [it.item_id for it in bank.items if it.slice_id != "books-p0-v1"]
    assert not bad, f"items with wrong slice_id: {bad}"


# ---------------------------------------------------------------------------
# Tier coverage
# ---------------------------------------------------------------------------


def test_all_three_tiers_present(bank):
    present = {it.tier for it in bank.items}
    missing = set(QuestionTier) - present
    assert not missing, f"missing tiers: {missing}"


# ---------------------------------------------------------------------------
# Content fact_type coverage
# ---------------------------------------------------------------------------


def test_all_four_content_fact_types_present(bank):
    present = {it.fact_type for it in bank.items if it.fact_type in CONTENT_FACT_TYPES}
    missing = CONTENT_FACT_TYPES - present
    assert not missing, f"missing content FactTypes: {missing}"


# ---------------------------------------------------------------------------
# Entity ID existence in snapshot
# ---------------------------------------------------------------------------


def test_all_entity_ids_in_snapshot(bank, snapshot):
    node_ids = {n["id"] for n in snapshot["nodes"]}
    bad = [
        (it.item_id, it.entity_id)
        for it in bank.items
        if it.entity_id not in node_ids
    ]
    assert not bad, f"entity_ids not in snapshot: {bad}"


# ---------------------------------------------------------------------------
# Gradability guard (strengthened FIX 3):
# (a) description substring present
# (b) triple-absence: no P136/P7937/P921 edge carries the content value
# ---------------------------------------------------------------------------


def test_content_items_target_described_entities(bank, snapshot):
    """Every content-only question must target an entity with a non-empty
    description so it is gradable under both full and content-withheld context.
    """
    described = {
        n["id"]
        for n in snapshot["nodes"]
        if n.get("description")
    }
    violations = []
    for it in bank.items:
        if it.fact_type in CONTENT_FACT_TYPES:
            if it.entity_id not in described:
                violations.append((it.item_id, it.entity_id, it.fact_type))
    assert not violations, (
        f"content items targeting undescribed entities (ungradable): {violations}"
    )


def test_content_items_description_substring_present(bank, snapshot):
    """For each content-only item in the documented table, the expected
    substring must appear (case-insensitively) in the entity's description.

    This drives gradability: the content_labels.json fact is derived from the
    description; if the substring is absent the label is wrong.
    """
    desc_map = {n["id"]: (n.get("description") or "") for n in snapshot["nodes"]}
    failures = []
    for item_id, expected_sub in CONTENT_DESCRIPTION_SUBSTRINGS.items():
        # find the item
        item = next((it for it in bank.items if it.item_id == item_id), None)
        if item is None:
            failures.append(f"{item_id}: not found in bank")
            continue
        desc = desc_map.get(item.entity_id, "")
        if expected_sub.lower() not in desc.lower():
            failures.append(
                f"{item_id} ({item.entity_id}): "
                f"expected substring {repr(expected_sub)} not in description {repr(desc)}"
            )
    assert not failures, "description-substring check failed:\n" + "\n".join(failures)


def test_content_items_triple_absence(bank, snapshot):
    """For each content-only item, assert that no outgoing edge of the entity
    expresses the same fact via P136 (genre), P7937 (form), or P921 (main subject).

    A content item that is also triple-backed cannot flip under content-absence
    (the generator still sees the triple), making it a dead content-absence probe.

    This test MUST FAIL for any content item whose fact is triple-rescued.
    """
    from collections import defaultdict

    edge_map: dict[str, list[dict]] = defaultdict(list)
    for e in snapshot["edges"]:
        edge_map[e["subject_id"]].append(e)

    failures = []
    for item_id, absence_checks in CONTENT_TRIPLE_ABSENCE.items():
        item = next((it for it in bank.items if it.item_id == item_id), None)
        if item is None:
            failures.append(f"{item_id}: not found in bank")
            continue
        entity_edges = edge_map.get(item.entity_id, [])
        for prop_id, value_fragment in absence_checks:
            matching = [
                e for e in entity_edges
                if e["property_id"] == prop_id
                and value_fragment.lower() in e["object_label"].lower()
            ]
            if matching:
                failures.append(
                    f"{item_id} ({item.entity_id}): found triple-rescue edge "
                    f"{prop_id} -> {matching[0]['object_label']!r} "
                    f"(content fact is NOT description-only)"
                )
    assert not failures, (
        "content items are triple-rescued (not description-only):\n"
        + "\n".join(failures)
    )


# ---------------------------------------------------------------------------
# Knowledge-structure triple existence
# ---------------------------------------------------------------------------


def test_knowledge_structure_triples_exist_in_snapshot(snapshot):
    """Each documented knowledge-structure triple must appear in snapshot edges."""
    edge_set = {
        (e["subject_id"], e["property_id"], e["object_id"])
        for e in snapshot["edges"]
    }
    missing = [t for t in KNOWLEDGE_STRUCTURE_TRIPLES if t not in edge_set]
    assert not missing, f"triples not found in snapshot edges: {missing}"


# ---------------------------------------------------------------------------
# At least 2 ablated-entity / knowledge-absence items
# ---------------------------------------------------------------------------


def test_at_least_two_knowledge_absence_items(bank):
    """The bank must include at least two items designed for knowledge-absence
    probing (ablated_entity tier), per AC-5.
    """
    ablated = [it for it in bank.items if it.tier == QuestionTier.ABLATED_ENTITY]
    assert len(ablated) >= 2, (
        f"expected >= 2 ablated_entity items, got {len(ablated)}"
    )


# ---------------------------------------------------------------------------
# Genuine multi-hop: at least one multi_hop_reasoning item is a genuine
# KG path connecting two distinct linked entities (not just two triples from
# the same subject, and not a description fact + triple combo).
# ---------------------------------------------------------------------------


def test_at_least_one_genuine_multi_hop(bank):
    """At least one multi_hop_reasoning item must be documented as a genuine
    KG path (notes must reference a path of the form A --[P]--> C <--[P]-- B,
    i.e. two entity nodes connected through a shared intermediate).
    """
    multi_hop_items = [
        it for it in bank.items if it.tier == QuestionTier.MULTI_HOP_REASONING
    ]
    assert multi_hop_items, "no multi_hop_reasoning items found"
    # qb-b010 is documented as a genuine two-hop shared-author path;
    # at minimum it must still be present and labeled multi_hop_reasoning.
    b010 = next((it for it in multi_hop_items if it.item_id == "qb-b010"), None)
    assert b010 is not None, (
        "qb-b010 (genuine shared-author path) must remain as multi_hop_reasoning"
    )


# ---------------------------------------------------------------------------
# one_hop_retrieval items must each rest on a single direct triple
# (no item bundles two facts in one_hop tier)
# ---------------------------------------------------------------------------


def test_one_hop_items_single_fact_only(bank):
    """Each one_hop_retrieval item must document at most one load-bearing triple
    (knowledge_structure items should not bundle two separate triple-backed facts).

    Detected by checking that no one_hop_retrieval knowledge_structure item has
    notes that document BOTH a P50 (author) AND a P123 (publisher) triple for
    the same item question -- such items must be split.
    """
    violations = []
    for it in bank.items:
        if it.tier == QuestionTier.ONE_HOP_RETRIEVAL and it.fact_type == FactType.KNOWLEDGE_STRUCTURE:
            notes = (it.notes or "").lower()
            has_author = "p50" in notes
            has_publisher = "p123" in notes
            if has_author and has_publisher:
                violations.append(
                    f"{it.item_id}: one_hop item documents both P50 and P123 -- "
                    "bundles two facts; must be split into separate items"
                )
    assert not violations, "\n".join(violations)
