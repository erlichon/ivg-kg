"""
FIX 4 -- Gradability proof for committed content labels (EX1 RQ2 invariant).

For each content-only question bank item the true claim text (its content_labels.json
fact) must grade RETRIEVED with support_source=TEXT_CONTENT via the real Classifier
cascade.  This is the offline gradability guarantee that Invariant #1 requires: a
fact withheld from the generation context must still be gradable against the FULL
reference.

Test structure:
  1. Load snapshot + content_labels.json; build GradingReference via assemble_reference.
  2. For each committed ContentLabel:
       a. Classify the fact string against the FULL reference.
       b. Assert status == RETRIEVED.
       c. Assert support_source == TEXT_CONTENT (not DIRECT_TRIPLE -- the fact must
          grade via the content stage, not rescued by a triple).
  3. Assert overall: all five content-only bank items have a matching ContentLabel.

Gate: LexicalEntailmentGate (model-free; deterministic; sufficient for the exact-match
facts authored here).  tau=0.4 (demo config default).

Run with:  pytest tests/test_content_labels_gradability.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ivg_kg.data.reference import load_reference
from ivg_kg.experiment.question_bank import FactType, load_question_bank
from ivg_kg.grounding.classify import Classifier
from ivg_kg.grounding.entailment import LexicalEntailmentGate
from ivg_kg.grounding.link import PropertyCanon
from ivg_kg.schema import ClaimStatus, GroundingConfig, LinkedEntity, SupportSource

FROZEN_DIR = Path("data/frozen/books/books-p0-v1")
BANK_PATH = FROZEN_DIR / "question_bank.json"

CONTENT_FACT_TYPES = {
    FactType.GENRE_FORM,
    FactType.TRADITION_AFFILIATION,
    FactType.SCOPE,
    FactType.DESCRIPTIVE_ROLE,
}

# tau matching demo config (classify.py / test_classify.py convention)
TAU = 0.4


@pytest.fixture(scope="module")
def reference():
    return load_reference(FROZEN_DIR)


@pytest.fixture(scope="module")
def classifier(reference):
    gate = LexicalEntailmentGate()
    canon = PropertyCanon.load()
    config = GroundingConfig(k_hops=2, tau=TAU)
    return Classifier(reference, gate=gate, canon=canon, config=config)


@pytest.fixture(scope="module")
def bank():
    return load_question_bank(BANK_PATH)


# ---------------------------------------------------------------------------
# 1. content_labels.json file exists and is non-empty
# ---------------------------------------------------------------------------


def test_content_labels_file_exists():
    assert (FROZEN_DIR / "content_labels.json").exists(), (
        "content_labels.json is missing from the frozen slice directory"
    )


def test_content_labels_non_empty(reference):
    assert reference.content_labels, "content_labels.json must contain at least one label"


# ---------------------------------------------------------------------------
# 2. Each content label grades RETRIEVED via TEXT_CONTENT (not DIRECT_TRIPLE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entity_id,expected_fact_fragment",
    [
        ("Q105485274", "short story collection"),
        ("Q96409397",  "kagyu"),
        ("Q102376902", "memoir and photobook"),
        ("Q106995049", "anthology"),
        ("Q1219497",   "sanskrit"),
    ],
    ids=[
        "qb-b004-blue-lantern-genre_form",
        "qb-b005-jewel-ornament-tradition",
        "qb-b007-going-south-role",
        "qb-b008-constantinian-scope",
        "qb-b014-seven-wise-masters-tradition",
    ],
)
def test_content_label_grades_retrieved_text_content(
    entity_id: str,
    expected_fact_fragment: str,
    reference,
    classifier: Classifier,
):
    """Classify the committed content label fact; must grade RETRIEVED / TEXT_CONTENT."""
    # Find the committed label for this entity
    labels = [lb for lb in reference.content_labels if lb.entity_id == entity_id]
    assert labels, (
        f"no ContentLabel found for entity {entity_id} in content_labels.json"
    )
    label = labels[0]

    # Confirm the committed fact contains the expected fragment (sanity check)
    assert expected_fact_fragment.lower() in label.fact.lower(), (
        f"ContentLabel fact {label.fact!r} does not contain expected fragment "
        f"{expected_fact_fragment!r}"
    )

    # Classify the exact fact string against the FULL reference
    rec = classifier.classify(
        label.fact,
        [LinkedEntity(id=entity_id, label=entity_id, link_score=1.0)],
        claim_id=f"gradability-{entity_id}",
    )

    assert rec.status == ClaimStatus.RETRIEVED, (
        f"entity {entity_id}: fact {label.fact!r} graded {rec.status} "
        f"(expected RETRIEVED); entailment_score={rec.entailment_score}"
    )
    assert rec.support_source == SupportSource.TEXT_CONTENT, (
        f"entity {entity_id}: fact graded via {rec.support_source} "
        f"(expected TEXT_CONTENT, not rescued by a triple)"
    )
    assert rec.entailment_score is not None and rec.entailment_score > TAU, (
        f"entity {entity_id}: entailment_score={rec.entailment_score} must be > tau={TAU}"
    )


# ---------------------------------------------------------------------------
# 3. Bank content items all have a matching committed ContentLabel
# ---------------------------------------------------------------------------


def test_all_bank_content_items_have_matching_label(bank, reference):
    """Every content-only bank item must have at least one ContentLabel
    committed for its entity in content_labels.json.

    This asserts the coverage invariant: the bank and the labels are co-committed.
    """
    labeled_entities = {lb.entity_id for lb in reference.content_labels}
    missing = [
        (it.item_id, it.entity_id, it.fact_type)
        for it in bank.items
        if it.fact_type in CONTENT_FACT_TYPES and it.entity_id not in labeled_entities
    ]
    assert not missing, (
        "content bank items with no matching ContentLabel in content_labels.json:\n"
        + "\n".join(f"  {item_id} ({eid}, {ft})" for item_id, eid, ft in missing)
    )


# ---------------------------------------------------------------------------
# 4. _best_content_label internal check: each label wins its own fact cleanly
# ---------------------------------------------------------------------------


def test_best_content_label_matches_own_fact(reference, classifier: Classifier):
    """For each committed label, _best_content_label must return that label (or
    one with the same entity_id) with a score above tau when queried with the
    label's own fact string.

    This verifies the content-cascade stage internally without relying on the
    full classify() path.
    """
    failures = []
    for lb in reference.content_labels:
        score, best = classifier._best_content_label(lb.fact)
        if score <= TAU:
            failures.append(
                f"{lb.entity_id}: _best_content_label score={score:.3f} <= tau={TAU}"
            )
        elif best is None or best.entity_id != lb.entity_id:
            # A different entity's label won -- still RETRIEVED but different source.
            # Allow if the winning entity_id matches (may vary if fact strings overlap).
            failures.append(
                f"{lb.entity_id}: winning label entity is {best and best.entity_id!r}, "
                f"expected {lb.entity_id!r}"
            )
    assert not failures, "\n".join(failures)
