"""Tests for GR6: entity linking + property-alias/inverse canon table (SPEC-text 4.3(B)).

Covers:
- PropertyCanon: load from committed artifact, canonical_property, canonical_triple,
  canonical_triplet_key, idempotency, format-compatibility with diagnostics.triplet_key.
- LabelAliasIndex: exact label match (score 1.0), case-insensitive, out-of-slice -> None,
  link_text semantics, determinism + caching.
- ReFinEDLinker: injectable resolve seam, QID-not-in-slice -> None, no ReFinED import when
  resolve= is provided.
- make_entity_linker: factory routing and ValueError on unknown selector.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from ivg_kg.schema import KGEdge, KGNode, KGSnapshot, ValueType

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
SLICE_DIR = REPO_ROOT / "data" / "frozen" / "books" / "books-p0-v1"


def _make_snapshot() -> KGSnapshot:
    """Small in-memory snapshot for linker tests.

    Nodes:
        Q1: "Beloved" (book, Toni Morrison)
        Q2: "Toni Morrison" (author)
        Q3: "Generation P" (series book, follows nothing, followed by Q4)
        Q4: "Sacred Book of the Werewolf" (series book, follows Q3)
    Edges include the P155/P156 inverse pair so canon tests can use a real triple.
    """
    nodes = [
        KGNode(id="Q1", label="Beloved", description="Novel by Toni Morrison", kind="entity"),
        KGNode(id="Q2", label="Toni Morrison", description="American author", kind="entity"),
        KGNode(id="Q3", label="Generation P", description="Novel by Viktor Pelevin", kind="entity"),
        KGNode(id="Q4", label="Sacred Book of the Werewolf", description="Novel", kind="entity"),
    ]
    edges = [
        KGEdge(
            subject_id="Q1",
            property_id="P50",
            property_label="author",
            object_id="Q2",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q3",
            property_id="P156",
            property_label="followed by",
            object_id="Q4",
            object_label="Sacred Book of the Werewolf",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q4",
            property_id="P155",
            property_label="follows",
            object_id="Q3",
            object_label="Generation P",
            value_type=ValueType.ITEM,
        ),
    ]
    return KGSnapshot(
        snapshot_id="test-snap",
        slice="books-p0-v1",
        domain_qid="Q1",
        nodes=nodes,
        edges=edges,
    )


# ---------------------------------------------------------------------------
# PropertyCanon tests
# ---------------------------------------------------------------------------


class TestPropertyCanon:
    """Tests for PropertyCanon artifact loading and canonicalization."""

    def test_load_reads_committed_artifact(self) -> None:
        """load() with default path reads the real committed artifact."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        assert canon is not None

    def test_canonical_property_known_alias(self) -> None:
        """'written by' -> 'P50'."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        assert canon.canonical_property("written by") == "P50"

    def test_canonical_property_direct_pid(self) -> None:
        """A plain property id maps to itself."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        assert canon.canonical_property("P50") == "P50"

    def test_canonical_property_unknown_returns_none(self) -> None:
        """An unknown surface string -> None."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        result = canon.canonical_property("zzzunknownzzz")
        assert result is None

    def test_canonical_triple_non_inverse_unchanged(self) -> None:
        """A non-inverse triple is returned as-is."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        result = canon.canonical_triple("Q1", "P50", "Q2")
        assert result == ("Q1", "P50", "Q2")

    def test_canonical_triple_inverse_pair_collapses_to_same_key(self) -> None:
        """P156 (followed-by) and P155 (follows) canonical triples must produce
        identical canonical_triplet_key values when they encode the same series edge."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        # Q3 "followed by" Q4 -- P156 is the non-canonical member of the pair
        key_156 = canon.canonical_triplet_key("Q3", "P156", "Q4")
        # Q4 "follows" Q3 -- P155 is the canonical direction; Q4->P155->Q3 means
        # "Q4 follows Q3" -- but after canonicalization of the P156 triple we expect
        # subject/object to be swapped and P156 replaced with P155.
        # So canon of (Q3, P156, Q4) == (Q4, P155, Q3)
        key_155 = canon.canonical_triplet_key("Q4", "P155", "Q3")
        assert key_156 == key_155

    def test_canonical_triple_idempotent(self) -> None:
        """Applying canonical_triple twice returns the same result as once."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        once = canon.canonical_triple("Q3", "P156", "Q4")
        twice = canon.canonical_triple(*once)
        assert once == twice

    def test_canonical_triplet_key_format_compatible_with_diagnostics(self) -> None:
        """canonical_triplet_key on a non-inverse triple == diagnostics.triplet_key."""
        from ivg_kg.diagnostics import triplet_key
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        # P50 is not in any inverse pair -> no swap -> same format
        canon_key = canon.canonical_triplet_key("Q1", "P50", "Q2")
        diag_key = triplet_key("Q1", "P50", "Q2")
        assert canon_key == diag_key

    def test_canonical_triplet_key_format_pipe_separated(self) -> None:
        """canonical_triplet_key produces 'subj|prop|obj' pipe format."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        key = canon.canonical_triplet_key("Qa", "P123", "Qb")
        parts = key.split("|")
        assert len(parts) == 3
        assert parts[0] == "Qa"
        assert parts[1] == "P123"
        assert parts[2] == "Qb"

    def test_canonical_triple_no_flip_when_object_id_is_none(self) -> None:
        """Non-canonical PID with object_id=None must NOT flip (no self-loop)."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        # P156 is non-canonical; with object_id=None there is nothing to flip.
        result = canon.canonical_triple("Q3", "P156", None)
        assert result == ("Q3", "P156", None), (
            f"Expected no flip with object_id=None, got {result!r}"
        )

    def test_canonical_triplet_key_no_flip_when_object_id_is_none(self) -> None:
        """canonical_triplet_key with object_id=None must not produce a self-loop key."""
        from ivg_kg.grounding.link import PropertyCanon

        canon = PropertyCanon.load(SLICE_DIR)
        key = canon.canonical_triplet_key("Q3", "P156", None)
        assert key == "Q3|P156|None", f"Expected 'Q3|P156|None' (no flip), got {key!r}"


# ---------------------------------------------------------------------------
# LabelAliasIndex tests
# ---------------------------------------------------------------------------


class TestLabelAliasIndex:
    """Tests for LabelAliasIndex (default offline linker)."""

    @pytest.fixture()
    def snapshot(self) -> KGSnapshot:
        return _make_snapshot()

    def test_exact_label_match_score_one(self, snapshot: KGSnapshot) -> None:
        """Exact normalized label match returns link_score=1.0."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        result = linker.link("Beloved")
        assert result is not None
        assert result.id == "Q1"
        assert result.link_score == 1.0

    def test_case_insensitive_match(self, snapshot: KGSnapshot) -> None:
        """Matching is case-insensitive."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        result = linker.link("beloved")
        assert result is not None
        assert result.id == "Q1"

    def test_whitespace_insensitive_match(self, snapshot: KGSnapshot) -> None:
        """Leading/trailing whitespace is stripped before matching."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        result = linker.link("  Beloved  ")
        assert result is not None
        assert result.id == "Q1"

    def test_out_of_slice_returns_none(self, snapshot: KGSnapshot) -> None:
        """A mention not in the snapshot -> None (unresolved)."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        result = linker.link("Nonexistent Book Title XYZ")
        assert result is None

    def test_link_text_returns_linked_and_unresolved(self, snapshot: KGSnapshot) -> None:
        """link_text on a claim returns (linked, unresolved) tuple."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        text = "Beloved was written by Toni Morrison"
        linked, unresolved = linker.link_text(text)
        linked_ids = {e.id for e in linked}
        assert "Q1" in linked_ids
        assert "Q2" in linked_ids
        # unresolved should be a list of strings
        assert isinstance(unresolved, list)
        for item in unresolved:
            assert isinstance(item, str)

    def test_link_text_empty_input(self, snapshot: KGSnapshot) -> None:
        """Empty or whitespace text -> ([], [])."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        linked, unresolved = linker.link_text("")
        assert linked == []
        assert unresolved == []

        linked2, unresolved2 = linker.link_text("   ")
        assert linked2 == []
        assert unresolved2 == []

    def test_link_text_deterministic(self, snapshot: KGSnapshot) -> None:
        """Repeated calls to link_text on the same text return the same result."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        text = "Toni Morrison wrote Beloved"
        r1 = linker.link_text(text)
        r2 = linker.link_text(text)
        assert r1 == r2

    def test_link_caching(self, snapshot: KGSnapshot) -> None:
        """Two link() calls on the same mention return equal results (cache-served)."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        r1 = linker.link("Beloved")
        r2 = linker.link("Beloved")
        assert r1 == r2
        # should be the same object (cached)
        assert r1 is r2

    def test_link_label_returned(self, snapshot: KGSnapshot) -> None:
        """The returned LinkedEntity carries the node's label."""
        from ivg_kg.grounding.link import LabelAliasIndex

        linker = LabelAliasIndex(snapshot)
        result = linker.link("Toni Morrison")
        assert result is not None
        assert result.label == "Toni Morrison"
        assert result.id == "Q2"

    def test_alias_collision_first_node_wins(self) -> None:
        """When two nodes share the same normalized label, the FIRST node wins."""
        from ivg_kg.grounding.link import LabelAliasIndex
        from ivg_kg.schema import KGNode, KGSnapshot

        # Two nodes with identical normalized labels; Q_a comes before Q_b in list order.
        nodes = [
            KGNode(id="Q_a", label="Shared Label", description="first", kind="entity"),
            KGNode(id="Q_b", label="shared label", description="second", kind="entity"),
        ]
        snap = KGSnapshot(
            snapshot_id="collision-snap",
            slice="test",
            domain_qid="Q_a",
            nodes=nodes,
            edges=[],
        )
        linker = LabelAliasIndex(snap)
        result = linker.link("Shared Label")
        assert result is not None
        # First-node-wins: Q_a must be returned, not Q_b.
        assert result.id == "Q_a", f"Expected Q_a (first-node-wins), got {result.id!r}"

    def test_graded_substring_match_deterministic_tie_break(self) -> None:
        """Graded substring match selects the best score; ties broken by lower node id."""
        from ivg_kg.grounding.link import LabelAliasIndex
        from ivg_kg.schema import KGNode, KGSnapshot

        # Two nodes with DIFFERENT labels of equal length (6 chars each).
        # Both labels appear as substrings in the mention "forest valley road" (18 chars).
        # score = 6 / max(6, 18) = 6/18 for both -> tie -> lower id wins.
        # "Q_a" < "Q_z" lexicographically, so Q_a must be returned.
        nodes = [
            KGNode(id="Q_z", label="Forest", description="", kind="entity"),
            KGNode(id="Q_a", label="Valley", description="", kind="entity"),
        ]
        snap = KGSnapshot(
            snapshot_id="tiebreak-snap",
            slice="test",
            domain_qid="Q_z",
            nodes=nodes,
            edges=[],
        )
        linker = LabelAliasIndex(snap)
        # "forest valley road" matches both "forest" and "valley" at equal scores.
        # Tie-break: lower id (Q_a < Q_z) wins.
        result = linker.link("forest valley road")
        assert result is not None
        assert result.link_score > 0.0
        assert result.link_score < 1.0, "Should be a graded (substring) score, not exact."
        # Lower node id wins on tie.
        assert result.id == "Q_a", f"Expected Q_a (lower id tie-break), got {result.id!r}"
        # Result is deterministic across repeated calls (cache).
        result2 = linker.link("forest valley road")
        assert result2 is result, "Cache should return the same object on repeated calls."


# ---------------------------------------------------------------------------
# ReFinEDLinker tests
# ---------------------------------------------------------------------------


class TestReFinEDLinker:
    """Tests for ReFinEDLinker with injectable resolve seam (no model download)."""

    @pytest.fixture()
    def snapshot(self) -> KGSnapshot:
        return _make_snapshot()

    def test_resolve_stub_in_slice_returns_entity(self, snapshot: KGSnapshot) -> None:
        """With resolve stub mapping mention -> in-slice QID, returns LinkedEntity."""
        from ivg_kg.grounding.link import ReFinEDLinker

        def stub(mention: str) -> str | None:
            if mention == "Beloved":
                return "Q1"
            return None

        linker = ReFinEDLinker(snapshot, resolve=stub)
        result = linker.link("Beloved")
        assert result is not None
        assert result.id == "Q1"
        assert result.label == "Beloved"

    def test_resolve_stub_out_of_slice_returns_none(self, snapshot: KGSnapshot) -> None:
        """With resolve stub returning QID not in snapshot -> None (unresolved)."""
        from ivg_kg.grounding.link import ReFinEDLinker

        def stub(mention: str) -> str | None:
            return "Q9999"  # not in snapshot

        linker = ReFinEDLinker(snapshot, resolve=stub)
        result = linker.link("Whatever")
        assert result is None

    def test_resolve_stub_none_mention_returns_none(self, snapshot: KGSnapshot) -> None:
        """Stub returning None for a mention -> link() returns None."""
        from ivg_kg.grounding.link import ReFinEDLinker

        def stub(mention: str) -> str | None:
            return None

        linker = ReFinEDLinker(snapshot, resolve=stub)
        result = linker.link("Unknown Thing")
        assert result is None

    def test_refined_not_imported_when_resolve_injected(self, snapshot: KGSnapshot) -> None:
        """ReFinED model is NOT imported or loaded when resolve= is provided."""
        from ivg_kg.grounding.link import ReFinEDLinker

        # Remove 'refined' from sys.modules to detect import side-effects.
        for key in list(sys.modules.keys()):
            if "refined" in key.lower():
                del sys.modules[key]

        def stub(mention: str) -> str | None:
            return "Q1"

        linker = ReFinEDLinker(snapshot, resolve=stub)
        linker.link("Beloved")

        # No refined module should have been imported.
        for key in sys.modules:
            assert "refined" not in key.lower(), f"Unexpected import: {key}"


# ---------------------------------------------------------------------------
# make_entity_linker factory tests
# ---------------------------------------------------------------------------


class TestMakeEntityLinker:
    """Tests for the make_entity_linker factory function."""

    @pytest.fixture()
    def snapshot(self) -> KGSnapshot:
        return _make_snapshot()

    def test_label_alias_selector(self, snapshot: KGSnapshot) -> None:
        """'label_alias' -> LabelAliasIndex."""
        from ivg_kg.grounding.link import LabelAliasIndex, make_entity_linker

        linker = make_entity_linker("label_alias", snapshot)
        assert isinstance(linker, LabelAliasIndex)

    def test_refined_selector(self, snapshot: KGSnapshot) -> None:
        """'refined' -> ReFinEDLinker."""
        from ivg_kg.grounding.link import ReFinEDLinker, make_entity_linker

        linker = make_entity_linker("refined", snapshot)
        assert isinstance(linker, ReFinEDLinker)

    def test_unknown_selector_raises(self, snapshot: KGSnapshot) -> None:
        """Unknown selector raises ValueError."""
        from ivg_kg.grounding.link import make_entity_linker

        with pytest.raises(ValueError):
            make_entity_linker("nope", snapshot)
