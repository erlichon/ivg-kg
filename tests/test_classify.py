"""Tests for GR8 -- three-way classifier cascade (classify.py).

TDD coverage (SPEC-text 4.3(C) + 4.8):
  1. Direct-triple claim    -> RETRIEVED / DIRECT_TRIPLE, single-hop path.
  2. Content-fact claim      -> RETRIEVED / TEXT_CONTENT, node-only path.
  3. Genuine 2-hop claim     -> REASONED_SUPPORTABLE / MULTI_HOP_PATH, not spurious.
  4. Unsupported claim       -> FABRICATED / NONE, empty path, near-miss score.
  5. Decision-order: direct wins over a path that would also support.
  6. Literal-node exclusion: shared-literal path is NOT a multi-hop support.
  7. Canonical orientation: P155 vs P156 PathEdges share a triplet_key.
  8. Spurious (1a) relation_illegitimate.
  9. Spurious (1b) value_absent.
 10. Spurious (2) hub_fragility (forced via stub gate near tau).
 11. Determinism: identical inputs -> identical ClaimRecord (model_dump equal).
 12. active_perturbations pass-through does NOT change the decision.
"""

from __future__ import annotations

from ivg_kg.diagnostics import triplet_key
from ivg_kg.grounding.classify import (
    HUB_DEGREE,
    MARGIN_EPS,
    REASON_HUB_FRAGILITY,
    REASON_RELATION_ILLEGITIMATE,
    REASON_VALUE_ABSENT,
    Classifier,
)
from ivg_kg.grounding.entailment import (
    BaseEntailmentGate,
    LexicalEntailmentGate,
)
from ivg_kg.grounding.link import PropertyCanon
from ivg_kg.schema import (
    ClaimStatus,
    ContentLabel,
    GradingReference,
    GroundingConfig,
    KGEdge,
    KGNode,
    KGSnapshot,
    LinkedEntity,
    Modality,
    SupportSource,
    ValueType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot(nodes: list[KGNode], edges: list[KGEdge]) -> KGSnapshot:
    return KGSnapshot(
        snapshot_id="test-snap",
        slice="books",
        domain_qid="Q1",
        nodes=nodes,
        edges=edges,
    )


def _ref(
    nodes: list[KGNode], edges: list[KGEdge], content: list[ContentLabel] | None = None
) -> GradingReference:
    return GradingReference(snapshot=_snapshot(nodes, edges), content_labels=content or [])


class _StubGate(BaseEntailmentGate):
    """Scripted gate: maps a premise SUBSTRING -> fixed score; else 0.0.

    Used to force a specific cascade branch deterministically. The first
    substring (in insertion order) found in the premise wins.
    """

    def __init__(self, rules: list[tuple[str, float]]) -> None:
        super().__init__()
        self._rules = rules

    def _score(self, premise: str, hypothesis: str) -> float:
        for needle, score in self._rules:
            if needle in premise:
                return score
        return 0.0


_LEXICAL_CONFIG = GroundingConfig(k_hops=2, tau=0.3)


def _lexical_gate() -> LexicalEntailmentGate:
    # The model-free default gate (GroundingConfig.entailment defaults to
    # "minicheck", which needs torch; construct the lexical gate directly).
    return LexicalEntailmentGate()


def _inmem_canon() -> PropertyCanon:
    """Tiny in-memory canon: P50 identity, P156 -> P155 inverse pair."""
    return PropertyCanon(
        alias_map={
            "P50": "P50",
            "written by": "P50",
            "P155": "P155",
            "follows": "P155",
            "P156": "P156",
            "followed by": "P156",
        },
        non_canonical_to_canonical={"P156": "P155"},
    )


# ---------------------------------------------------------------------------
# 1. Direct triple -> RETRIEVED / DIRECT_TRIPLE
# ---------------------------------------------------------------------------


def test_direct_triple_retrieved():
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    clf = Classifier(ref, gate=_lexical_gate(), canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved written by Toni Morrison",
        [LinkedEntity(id="Q10", label="Beloved", link_score=1.0)],
        claim_id="c1",
    )
    assert rec.status == ClaimStatus.RETRIEVED
    assert rec.support_source == SupportSource.DIRECT_TRIPLE
    assert rec.entailment_score is not None and rec.entailment_score > _LEXICAL_CONFIG.tau
    assert len(rec.grounding_path.edges) == 1
    assert rec.grounding_path.node_ids == ["Q10", "Q20"]
    assert rec.spurious_path is False


# ---------------------------------------------------------------------------
# 2. Content fact -> RETRIEVED / TEXT_CONTENT
# ---------------------------------------------------------------------------


def test_content_fact_retrieved():
    nodes = [KGNode(id="Q10", label="Beloved")]
    edges: list[KGEdge] = []
    content = [
        ContentLabel(
            entity_id="Q10",
            modality=Modality.TEXT,
            fact="Beloved is a novel about slavery and memory",
            source="description",
        ),
    ]
    ref = _ref(nodes, edges, content)
    clf = Classifier(ref, gate=_lexical_gate(), canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved is a novel about slavery and memory",
        [LinkedEntity(id="Q10", label="Beloved", link_score=1.0)],
        claim_id="c1",
    )
    assert rec.status == ClaimStatus.RETRIEVED
    assert rec.support_source == SupportSource.TEXT_CONTENT
    assert rec.grounding_path.edges == []
    assert rec.grounding_path.node_ids == ["Q10"]
    assert rec.spurious_path is False


# ---------------------------------------------------------------------------
# 3. Genuine 2-hop path -> REASONED_SUPPORTABLE / MULTI_HOP_PATH
# ---------------------------------------------------------------------------


def test_genuine_multi_hop_supportable():
    # Two books by the same author: book1 - author - book2 (undirected 2 hops).
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Stub gate: no single direct triple or content fact entails the joint claim,
    # but the joint path premise (containing both books + author) does.
    gate = _StubGate(
        [
            ("Beloved written by Toni Morrison Sula", 0.9),  # the 2-hop joint premise
            ("Sula written by Toni Morrison Beloved", 0.9),
        ]
    )
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved and Sula share author Toni Morrison",
        [
            LinkedEntity(id="Q10", label="Beloved", link_score=1.0),
            LinkedEntity(id="Q11", label="Sula", link_score=1.0),
        ],
        claim_id="c1",
        relation_surface="written by",
        object_surface="Toni Morrison",
    )
    assert rec.status == ClaimStatus.REASONED_SUPPORTABLE
    assert rec.support_source == SupportSource.MULTI_HOP_PATH
    assert len(rec.grounding_path.edges) == 2
    assert rec.spurious_path is False
    assert rec.spurious_reason is None


# ---------------------------------------------------------------------------
# 4. Unsupported -> FABRICATED / NONE
# ---------------------------------------------------------------------------


def test_unsupported_fabricated():
    nodes = [KGNode(id="Q10", label="Beloved")]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Stub: a non-zero near-miss below tau on the only edge.
    gate = _StubGate([("Beloved written by", 0.2)])
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Dune was written by Frank Herbert",
        [],
        claim_id="c1",
    )
    assert rec.status == ClaimStatus.FABRICATED
    assert rec.support_source == SupportSource.NONE
    assert rec.grounding_path.edges == []
    assert rec.grounding_path.node_ids == []
    assert rec.spurious_path is False
    assert rec.entailment_score == 0.2


# ---------------------------------------------------------------------------
# 5. Decision-order precedence: direct beats path
# ---------------------------------------------------------------------------


def test_direct_beats_path():
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Both the direct edge and the joint path score above tau; direct must win.
    gate = _StubGate(
        [
            ("Beloved written by Toni Morrison Sula", 0.95),
            ("Sula written by Toni Morrison Beloved", 0.95),
            ("Beloved written by Toni Morrison", 0.8),
            ("written by", 0.8),
        ]
    )
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved written by Toni Morrison",
        [],
        claim_id="c1",
    )
    assert rec.status == ClaimStatus.RETRIEVED
    assert rec.support_source == SupportSource.DIRECT_TRIPLE


# ---------------------------------------------------------------------------
# 6. Literal-node exclusion: shared-literal path is NOT used
# ---------------------------------------------------------------------------


def test_literal_node_excluded_as_waypoint():
    # Two books sharing a publication-year literal: must NOT form a multi-hop path.
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P577",
            property_label="publication date",
            object_id=None,
            object_label="1987",
            value_type=ValueType.TIME,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P577",
            property_label="publication date",
            object_id=None,
            object_label="1987",
            value_type=ValueType.TIME,
        ),
    ]
    ref = _ref(nodes, edges)
    # Stub would happily score any path premise high; but no entity path exists
    # because the only connection is through a literal waypoint (excluded).
    gate = _StubGate([("publication date", 0.99)])
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved and Sula were both published in 1987",
        # Both book endpoints linked: the only connection between them is via a
        # literal waypoint, which is excluded, so no entity path exists.
        [
            LinkedEntity(id="Q10", label="Beloved", link_score=1.0),
            LinkedEntity(id="Q11", label="Sula", link_score=1.0),
        ],
        claim_id="c1",
    )
    # No multi-hop entity path -> falls through. Direct edges may match the
    # literal premise, so the worst case is RETRIEVED via a single edge, but it
    # must NOT be MULTI_HOP_PATH.
    assert rec.support_source != SupportSource.MULTI_HOP_PATH


# ---------------------------------------------------------------------------
# 7. Canonical orientation: P155 vs P156 share a triplet_key
# ---------------------------------------------------------------------------


def test_canonical_orientation_triplet_key():
    canon = PropertyCanon.load()

    # Orientation A: (Q10, P155 follows, Q11) -- already canonical.
    nodes_a = [KGNode(id="Q10", label="Book A"), KGNode(id="Q11", label="Book B")]
    edges_a = [
        KGEdge(
            subject_id="Q10",
            property_id="P155",
            property_label="follows",
            object_id="Q11",
            object_label="Book B",
            value_type=ValueType.ITEM,
        ),
    ]
    ref_a = _ref(nodes_a, edges_a)
    clf_a = Classifier(
        ref_a, gate=_StubGate([("follows", 0.9)]), canon=canon, config=_LEXICAL_CONFIG
    )
    rec_a = clf_a.classify("Book A follows Book B", [], claim_id="c1")

    # Orientation B: (Q11, P156 followed by, Q10) -- non-canonical; must flip to
    # (Q10, P155, Q11).
    nodes_b = [KGNode(id="Q10", label="Book A"), KGNode(id="Q11", label="Book B")]
    edges_b = [
        KGEdge(
            subject_id="Q11",
            property_id="P156",
            property_label="followed by",
            object_id="Q10",
            object_label="Book A",
            value_type=ValueType.ITEM,
        ),
    ]
    ref_b = _ref(nodes_b, edges_b)
    clf_b = Classifier(
        ref_b, gate=_StubGate([("followed by", 0.9)]), canon=canon, config=_LEXICAL_CONFIG
    )
    rec_b = clf_b.classify("Book B followed by Book A", [], claim_id="c1")

    assert rec_a.status == ClaimStatus.RETRIEVED
    assert rec_b.status == ClaimStatus.RETRIEVED
    e_a = rec_a.grounding_path.edges[0]
    e_b = rec_b.grounding_path.edges[0]
    key_a = triplet_key(e_a.subject_id, e_a.property_id, e_a.object_id)
    key_b = triplet_key(e_b.subject_id, e_b.property_id, e_b.object_id)
    assert key_a == key_b == "Q10|P155|Q11"


# ---------------------------------------------------------------------------
# 8. Spurious (1a) relation_illegitimate
# ---------------------------------------------------------------------------


def test_spurious_relation_illegitimate():
    # Path predicates are all P50 (written by), but the claim's relation is
    # "genre" (P136) -> the path does not carry the claimed relation.
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Score ONLY the joint 2-hop premise (it carries the second book label after
    # the shared author); single direct edges do not contain that substring, so
    # the cascade reaches the multi-hop stage.
    gate = _StubGate([("Toni Morrison Sula", 0.9), ("Toni Morrison Beloved", 0.9)])
    canon = PropertyCanon(
        alias_map={"P50": "P50", "written by": "P50", "P136": "P136", "genre": "P136"},
        non_canonical_to_canonical={},
    )
    clf = Classifier(ref, gate=gate, canon=canon, config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved and Sula share the genre Toni Morrison",
        [
            LinkedEntity(id="Q10", label="Beloved", link_score=1.0),
            LinkedEntity(id="Q11", label="Sula", link_score=1.0),
        ],
        claim_id="c1",
        relation_surface="genre",
        object_surface="Toni Morrison",
    )
    assert rec.status == ClaimStatus.REASONED_SUPPORTABLE
    assert rec.spurious_path is True
    assert rec.spurious_reason == REASON_RELATION_ILLEGITIMATE


# ---------------------------------------------------------------------------
# 9. Spurious (1b) value_absent
# ---------------------------------------------------------------------------


def test_spurious_value_absent():
    # Relation matches (P50), but the asserted object value is absent from the
    # path premise.
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Score ONLY the joint 2-hop premise (carries the second book label).
    gate = _StubGate([("Toni Morrison Sula", 0.9), ("Toni Morrison Beloved", 0.9)])
    canon = PropertyCanon(
        alias_map={"P50": "P50", "written by": "P50"},
        non_canonical_to_canonical={},
    )
    clf = Classifier(ref, gate=gate, canon=canon, config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved and Sula were both written by Maya Angelou",
        [
            LinkedEntity(id="Q10", label="Beloved", link_score=1.0),
            LinkedEntity(id="Q11", label="Sula", link_score=1.0),
        ],
        claim_id="c1",
        relation_surface="written by",
        object_surface="Maya Angelou",  # absent from the path premise
    )
    assert rec.status == ClaimStatus.REASONED_SUPPORTABLE
    assert rec.spurious_path is True
    assert rec.spurious_reason == REASON_VALUE_ABSENT


# ---------------------------------------------------------------------------
# 10. Spurious (2) hub_fragility
# ---------------------------------------------------------------------------


def test_spurious_hub_fragility():
    # Build a hub node of degree >= HUB_DEGREE; a max-length (k_hops) path routes
    # through it with a small margin just above tau.
    hub = KGNode(id="QHUB", label="Genre Fiction")
    leaves = [KGNode(id=f"Q{i}", label=f"Book {i}") for i in range(HUB_DEGREE + 2)]
    nodes = [hub, *leaves]
    edges = [
        KGEdge(
            subject_id=leaf.id,
            property_id="P136",
            property_label="genre",
            object_id="QHUB",
            object_label="Genre Fiction",
            value_type=ValueType.ITEM,
        )
        for leaf in leaves
    ]
    ref = _ref(nodes, edges)
    # Path Q0 - QHUB - Q1 has length 2 == k_hops and routes through the hub.
    # Margin = score - tau = small. tau = 0.3; pick just above tau within MARGIN_EPS.
    # Score ONLY the joint 2-hop premise: "... Genre Fiction Book ..." appears only
    # where two hub edges concatenate, so single direct edges do not match.
    margin_score = _LEXICAL_CONFIG.tau + (MARGIN_EPS / 2.0)
    gate = _StubGate([("Genre Fiction Book", margin_score)])
    canon = PropertyCanon(
        alias_map={"P136": "P136", "genre": "P136"},
        non_canonical_to_canonical={},
    )
    clf = Classifier(ref, gate=gate, canon=canon, config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Book 0 and Book 1 share genre Genre Fiction",
        [
            LinkedEntity(id="Q0", label="Book 0", link_score=1.0),
            LinkedEntity(id="Q1", label="Book 1", link_score=1.0),
        ],
        claim_id="c1",
        relation_surface="genre",  # 1a passes (P136 present on path)
        object_surface="Genre Fiction",  # 1b passes (value on path premise)
    )
    assert rec.status == ClaimStatus.REASONED_SUPPORTABLE
    assert rec.spurious_path is True
    assert rec.spurious_reason == REASON_HUB_FRAGILITY


# ---------------------------------------------------------------------------
# 11. Determinism
# ---------------------------------------------------------------------------


def test_determinism_identical_record():
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    clf = Classifier(ref, gate=_lexical_gate(), canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    args = (
        "Beloved written by Toni Morrison",
        [LinkedEntity(id="Q10", label="Beloved", link_score=1.0)],
    )
    r1 = clf.classify(*args, claim_id="c1")
    r2 = clf.classify(*args, claim_id="c1")
    assert r1.model_dump() == r2.model_dump()


# ---------------------------------------------------------------------------
# 12. active_perturbations passes through, does NOT change the decision
# ---------------------------------------------------------------------------


def test_active_perturbations_passthrough_no_decision_change():
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    clf = Classifier(ref, gate=_lexical_gate(), canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    args = (
        "Beloved written by Toni Morrison",
        [LinkedEntity(id="Q10", label="Beloved", link_score=1.0)],
    )
    without = clf.classify(*args, claim_id="c1")
    with_pert = clf.classify(*args, claim_id="c1", active_perturbations=["manifest:remove-author"])
    assert with_pert.active_perturbations == ["manifest:remove-author"]
    assert without.active_perturbations == []
    assert with_pert.status == without.status
    assert with_pert.support_source == without.support_source
    assert with_pert.entailment_score == without.entailment_score


# ---------------------------------------------------------------------------
# T2. Path tie-break determinism (I2)
# ---------------------------------------------------------------------------


def test_path_tiebreak_is_deterministic():
    # Two distinct 2-hop paths exist (Q10 - Q20 - Q11 and Q10 - Q21 - Q11).
    # The stub gate scores BOTH the same. The chosen path must be the
    # tuple(node_path)-lexicographically smaller one, always.
    nodes = [
        KGNode(id="Q10", label="Book A"),
        KGNode(id="Q11", label="Book B"),
        KGNode(id="Q20", label="Author X"),
        KGNode(id="Q21", label="Author Y"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Author X",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Author X",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q21",
            object_label="Author Y",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q21",
            object_label="Author Y",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Score any joint 2-hop premise identically so both paths tie.
    # The joint serialisation of 2 hops contains both "Book A written by" AND
    # the second edge; a needle present in both joint path serialisations but
    # absent from any single-edge premise achieves this. Both intermediate nodes
    # appear in the premise when serialised as a path (subject of hop2 = waypoint
    # label), so match on "written by Author" which concatenates the two hops.
    # Use "written by Author X written by" as needle -- present in the 2-hop
    # path through Q20 and similar for Q21.
    # Simpler: use the fact that the joint premise contains TWO "written by"
    # substrings; match on "written by" twice -- but _StubGate checks substring
    # presence, not count. Instead use the waypoint label text directly: neither
    # single-edge premise contains BOTH author labels at once.
    # We match on needle "Author X written" or "Author Y written" to capture
    # the waypoint-to-second-edge boundary that only the 2-hop premises have.
    # The 2-hop premise for Q10-Q20-Q11: "Book A written by Author X Book B written by Author X"
    # The 2-hop premise for Q10-Q21-Q11: "Book A written by Author Y Book B written by Author Y"
    # Single-hop premise: "Book A written by Author X" (no second "written by").
    gate = _StubGate(
        [
            ("Author X Book B", 0.9),
            ("Author X Book A", 0.9),
            ("Author Y Book B", 0.9),
            ("Author Y Book A", 0.9),
        ]
    )
    canon = PropertyCanon(
        alias_map={"P50": "P50", "written by": "P50"},
        non_canonical_to_canonical={},
    )
    config = GroundingConfig(k_hops=2, tau=0.3)
    clf = Classifier(ref, gate=gate, canon=canon, config=config)

    endpoints = [
        LinkedEntity(id="Q10", label="Book A", link_score=1.0),
        LinkedEntity(id="Q11", label="Book B", link_score=1.0),
    ]
    rec1 = clf.classify("Book A and Book B share an author", endpoints, claim_id="c1")
    rec2 = clf.classify("Book A and Book B share an author", endpoints, claim_id="c1")

    # Both runs must agree.
    assert rec1.model_dump() == rec2.model_dump()
    # Must be REASONED_SUPPORTABLE (path found) rather than FABRICATED.
    assert rec1.status == ClaimStatus.REASONED_SUPPORTABLE

    # The chosen node_ids must be the lex-smallest among the tied paths.
    # Candidate paths through Q20: ["Q10","Q20","Q11"] or ["Q11","Q20","Q10"]
    # Candidate paths through Q21: ["Q10","Q21","Q11"] or ["Q11","Q21","Q10"]
    # The pair enumeration is (Q10,Q11) and (Q10,Q21) etc.; node_ids returned
    # via all_simple_paths will be direction-consistent; the smallest tuple wins.
    chosen = tuple(rec1.grounding_path.node_ids)
    # All four candidate tuples for completeness.
    all_candidates = [
        ("Q10", "Q20", "Q11"),
        ("Q11", "Q20", "Q10"),
        ("Q10", "Q21", "Q11"),
        ("Q11", "Q21", "Q10"),
    ]
    assert chosen in all_candidates
    # The chosen path must be <= all others with the same score (lex-min).
    for other in all_candidates:
        assert chosen <= other


# ---------------------------------------------------------------------------
# T3. k_hops=1 degenerate: no >=2-hop path -> FABRICATED (no crash)
# ---------------------------------------------------------------------------


def test_k_hops_1_degrades_to_fabricated():
    # With k_hops=1 no multi-hop path can exist; a claim that would require
    # 2 hops must degrade gracefully to FABRICATED.
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Score only the joint 2-hop premise; single edges score 0.
    gate = _StubGate([("Beloved written by Toni Morrison Sula", 0.9)])
    config = GroundingConfig(k_hops=1, tau=0.3)
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=config)
    rec = clf.classify(
        "Beloved and Sula share author Toni Morrison",
        # Both endpoints linked: the multi-hop stage is entered, but with
        # k_hops=1 the cutoff forbids any >=2-hop path, so it degrades.
        [
            LinkedEntity(id="Q10", label="Beloved", link_score=1.0),
            LinkedEntity(id="Q11", label="Sula", link_score=1.0),
        ],
        claim_id="c1",
    )
    # k_hops=1 means cutoff=1 for all_simple_paths, so only direct (1-node) paths
    # exist; the joint 2-hop path is never found.
    assert rec.status == ClaimStatus.FABRICATED
    assert rec.grounding_path.edges == []
    assert rec.grounding_path.node_ids == []


# ---------------------------------------------------------------------------
# T1 (GR9 I1). Multi-hop endpoints are restricted to the claim's linked entities.
# ---------------------------------------------------------------------------


def test_multi_hop_requires_at_least_two_linked_endpoints():
    # A genuine 2-hop entity path exists (Q10 - Q20 - Q11), but the claim links
    # FEWER than two entity endpoints. With the I1 restriction the multi-hop
    # stage is skipped entirely and the claim degrades to FABRICATED, even though
    # the joint path premise would otherwise entail.
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    # Stub scores ONLY the joint 2-hop premise; single edges score 0 so the
    # cascade would reach the multi-hop stage if it were not skipped.
    gate = _StubGate(
        [
            ("Beloved written by Toni Morrison Sula", 0.9),
            ("Sula written by Toni Morrison Beloved", 0.9),
        ]
    )
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    # Only ONE linked endpoint -> multi-hop skipped -> FABRICATED.
    rec = clf.classify(
        "Beloved and Sula share author Toni Morrison",
        [LinkedEntity(id="Q10", label="Beloved", link_score=1.0)],
        claim_id="c1",
    )
    assert rec.status == ClaimStatus.FABRICATED
    assert rec.support_source == SupportSource.NONE
    assert rec.grounding_path.edges == []
    assert rec.grounding_path.node_ids == []


def test_multi_hop_resolves_when_both_endpoints_linked():
    # Same graph, but BOTH endpoints (Q10 and Q11) are linked. The 2-hop path
    # between the two linked endpoints resolves REASONED_SUPPORTABLE.
    nodes = [
        KGNode(id="Q10", label="Beloved"),
        KGNode(id="Q11", label="Sula"),
        KGNode(id="Q20", label="Toni Morrison"),
    ]
    edges = [
        KGEdge(
            subject_id="Q10",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
        KGEdge(
            subject_id="Q11",
            property_id="P50",
            property_label="written by",
            object_id="Q20",
            object_label="Toni Morrison",
            value_type=ValueType.ITEM,
        ),
    ]
    ref = _ref(nodes, edges)
    gate = _StubGate(
        [
            ("Beloved written by Toni Morrison Sula", 0.9),
            ("Sula written by Toni Morrison Beloved", 0.9),
        ]
    )
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=_LEXICAL_CONFIG)
    rec = clf.classify(
        "Beloved and Sula share author Toni Morrison",
        [
            LinkedEntity(id="Q10", label="Beloved", link_score=1.0),
            LinkedEntity(id="Q11", label="Sula", link_score=1.0),
        ],
        claim_id="c1",
        relation_surface="written by",
        object_surface="Toni Morrison",
    )
    assert rec.status == ClaimStatus.REASONED_SUPPORTABLE
    assert rec.support_source == SupportSource.MULTI_HOP_PATH
    assert len(rec.grounding_path.edges) == 2
    assert rec.spurious_path is False


# ---------------------------------------------------------------------------
# T4. Empty reference: no nodes/edges/content -> FABRICATED, no crash
# ---------------------------------------------------------------------------


def test_empty_reference_fabricated():
    ref = _ref(nodes=[], edges=[], content=[])
    gate = _StubGate([])
    config = GroundingConfig(k_hops=2, tau=0.3)
    clf = Classifier(ref, gate=gate, canon=_inmem_canon(), config=config)
    rec = clf.classify(
        "Beloved written by Toni Morrison",
        [],
        claim_id="c1",
    )
    assert rec.status == ClaimStatus.FABRICATED
    assert rec.entailment_score is None
    assert rec.grounding_path.edges == []
    assert rec.grounding_path.node_ids == []
