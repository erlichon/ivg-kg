"""
Tests for the real books question bank (EX1).

Validates:
  - question_bank.json loads and validates via load_question_bank.
  - Coverage: >= 10 items, unique item_ids, all slice_id == "books-p0-v1".
  - Tier coverage: all three QuestionTier values present.
  - Content fact_type coverage: all four content FactTypes present.
  - Every entity_id exists as a node id in snapshot.json.
  - Gradability guard: every content-only item targets an entity that has
    a non-empty description in the snapshot (SPEC invariant 1 / AC-3).
  - Knowledge-structure triple check: each one_hop_retrieval item with
    fact_type=knowledge_structure must document a triple whose
    (subject_id, property_id, object_id) exists in snapshot edges.

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
# Gradability guard: content-only items must target described entities
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
