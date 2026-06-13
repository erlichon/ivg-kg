"""
Tests for GR3: context assembly (grounding/context.py).

Run with:  pytest tests/test_context.py -v
"""

from __future__ import annotations

import copy

import pytest

from ivg_kg.grounding.context import assemble_context, build_full_context
from ivg_kg.perturbation import KnowledgeAbsence, TextContentAbsence
from ivg_kg.schema import (
    ContentLabel,
    GenerationContext,
    GradingReference,
    KGEdge,
    KGNode,
    KGSnapshot,
    Modality,
    TripleRef,
    ValueType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FOCUS_ID = "Q1"
OTHER_ID = "Q2"

NODE_FOCUS = KGNode(id=FOCUS_ID, label="Focus Book", description="A great novel.")
NODE_OTHER = KGNode(id=OTHER_ID, label="Other Entity", description=None)

# Outgoing edge from focus entity
EDGE_FOCUS_A = KGEdge(
    subject_id=FOCUS_ID,
    property_id="P31",
    property_label="instance of",
    object_id="Q571",
    object_label="book",
    value_type=ValueType.ITEM,
)
EDGE_FOCUS_B = KGEdge(
    subject_id=FOCUS_ID,
    property_id="P50",
    property_label="author",
    object_id=OTHER_ID,
    object_label="Other Entity",
    value_type=ValueType.ITEM,
)
# Edge where focus entity is the OBJECT (incoming), not the subject
EDGE_INCOMING = KGEdge(
    subject_id=OTHER_ID,
    property_id="P737",
    property_label="influenced by",
    object_id=FOCUS_ID,
    object_label="Focus Book",
    value_type=ValueType.ITEM,
)
# Edge from another subject entirely
EDGE_OTHER = KGEdge(
    subject_id=OTHER_ID,
    property_id="P31",
    property_label="instance of",
    object_id="Q5",
    object_label="human",
    value_type=ValueType.ITEM,
)

LABEL_TEXT_A = ContentLabel(
    entity_id=FOCUS_ID,
    modality=Modality.TEXT,
    fact="It was published in 1851.",
    source="wiki",
)
LABEL_TEXT_B = ContentLabel(
    entity_id=FOCUS_ID,
    modality=Modality.TEXT,
    fact="The author is Herman Melville.",
    source="wiki",
)
# Image-modality label for focus entity - must be ignored
LABEL_IMAGE = ContentLabel(
    entity_id=FOCUS_ID,
    modality=Modality.IMAGE,
    fact="Cover shows a whale.",
    source="wiki",
)
# Text label for OTHER entity - must be ignored when building context for FOCUS
LABEL_OTHER = ContentLabel(
    entity_id=OTHER_ID,
    modality=Modality.TEXT,
    fact="Melville was an American novelist.",
    source="wiki",
)


def make_reference(
    nodes: list[KGNode] | None = None,
    edges: list[KGEdge] | None = None,
    content_labels: list[ContentLabel] | None = None,
) -> GradingReference:
    """Build a minimal GradingReference for testing."""
    return GradingReference(
        snapshot=KGSnapshot(
            snapshot_id="snap-test",
            slice="books",
            domain_qid="Q571",
            nodes=nodes if nodes is not None else [NODE_FOCUS, NODE_OTHER],
            edges=edges
            if edges is not None
            else [EDGE_FOCUS_A, EDGE_FOCUS_B, EDGE_INCOMING, EDGE_OTHER],
        ),
        content_labels=content_labels if content_labels is not None else [],
    )


# ---------------------------------------------------------------------------
# 1. build_full_context - basic shape
# ---------------------------------------------------------------------------


class TestBuildFullContextBasicShape:
    def test_returns_generation_context(self) -> None:
        ref = make_reference()
        ctx = build_full_context(ref, FOCUS_ID)
        assert isinstance(ctx, GenerationContext)

    def test_entity_id_set(self) -> None:
        ref = make_reference()
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.entity_id == FOCUS_ID

    def test_triples_are_outgoing_only(self) -> None:
        ref = make_reference()
        ctx = build_full_context(ref, FOCUS_ID)
        # Must include both outgoing edges
        assert EDGE_FOCUS_A in ctx.triples
        assert EDGE_FOCUS_B in ctx.triples

    def test_triples_exclude_incoming_edge(self) -> None:
        # EDGE_INCOMING has subject_id=OTHER_ID, object_id=FOCUS_ID
        ref = make_reference()
        ctx = build_full_context(ref, FOCUS_ID)
        assert EDGE_INCOMING not in ctx.triples

    def test_triples_exclude_other_subject_edges(self) -> None:
        ref = make_reference()
        ctx = build_full_context(ref, FOCUS_ID)
        assert EDGE_OTHER not in ctx.triples

    def test_triple_count_exact(self) -> None:
        ref = make_reference()
        ctx = build_full_context(ref, FOCUS_ID)
        # Only EDGE_FOCUS_A and EDGE_FOCUS_B are outgoing from FOCUS_ID
        assert len(ctx.triples) == 2

    def test_edge_order_preserved(self) -> None:
        # Edges supplied in a specific order; outgoing subset preserves that order.
        ref = make_reference(edges=[EDGE_OTHER, EDGE_FOCUS_B, EDGE_INCOMING, EDGE_FOCUS_A])
        ctx = build_full_context(ref, FOCUS_ID)
        # EDGE_FOCUS_B appears before EDGE_FOCUS_A in the snapshot
        assert ctx.triples.index(EDGE_FOCUS_B) < ctx.triples.index(EDGE_FOCUS_A)

    def test_image_path_is_none(self) -> None:
        ref = make_reference()
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.image_path is None


# ---------------------------------------------------------------------------
# 2. build_full_context - description assembly
# ---------------------------------------------------------------------------


class TestDescriptionAssembly:
    def test_node_description_with_no_labels(self) -> None:
        # Node has description; no text labels. Description = node.description.
        ref = make_reference(content_labels=[])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is not None
        assert "A great novel" in ctx.description

    def test_node_null_description_with_text_labels(self) -> None:
        # Node with null description + text labels -> description from labels only.
        node_null = KGNode(id=FOCUS_ID, label="Focus Book", description=None)
        ref = make_reference(
            nodes=[node_null, NODE_OTHER],
            content_labels=[LABEL_TEXT_A, LABEL_TEXT_B],
        )
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is not None
        assert "1851" in ctx.description
        assert "Melville" in ctx.description

    def test_node_nonnull_description_with_text_labels(self) -> None:
        # Node description + text labels: both present, joined.
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is not None
        assert "A great novel" in ctx.description
        assert "1851" in ctx.description

    def test_no_description_no_labels_gives_none(self) -> None:
        node_null = KGNode(id=FOCUS_ID, label="Focus Book", description=None)
        ref = make_reference(nodes=[node_null, NODE_OTHER], content_labels=[])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is None

    def test_image_labels_ignored(self) -> None:
        # IMAGE-modality labels must not appear in description.
        node_null = KGNode(id=FOCUS_ID, label="Focus Book", description=None)
        ref = make_reference(nodes=[node_null, NODE_OTHER], content_labels=[LABEL_IMAGE])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is None

    def test_other_entity_text_labels_ignored(self) -> None:
        # Labels for OTHER_ID must not appear when building context for FOCUS_ID.
        node_null = KGNode(id=FOCUS_ID, label="Focus Book", description=None)
        ref = make_reference(nodes=[node_null, NODE_OTHER], content_labels=[LABEL_OTHER])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is None

    def test_duplicate_fact_deduped(self) -> None:
        # If node.description already contains (or IS) the label fact, it should
        # not appear twice.
        duplicate_label = ContentLabel(
            entity_id=FOCUS_ID,
            modality=Modality.TEXT,
            fact="A great novel",  # exact substring of NODE_FOCUS.description
            source="wiki",
        )
        ref = make_reference(content_labels=[duplicate_label])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is not None
        # "A great novel" should appear only once
        assert ctx.description.count("A great novel") == 1

    def test_empty_string_node_description_treated_as_null(self) -> None:
        # description="" (empty string) should behave like None for assembly.
        node_empty = KGNode(id=FOCUS_ID, label="Focus Book", description="")
        ref = make_reference(nodes=[node_empty, NODE_OTHER], content_labels=[LABEL_TEXT_A])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is not None
        assert "1851" in ctx.description
        # The empty string must not prefix the output
        assert not ctx.description.startswith(". ")

    def test_label_order_preserved_in_description(self) -> None:
        # The labels are appended in their list order.
        ref = make_reference(
            nodes=[KGNode(id=FOCUS_ID, label="F", description=None), NODE_OTHER],
            content_labels=[LABEL_TEXT_A, LABEL_TEXT_B],
        )
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is not None
        pos_a = ctx.description.find("1851")
        pos_b = ctx.description.find("Melville")
        assert pos_a < pos_b


# ---------------------------------------------------------------------------
# 3. build_full_context - KeyError for unknown entity_id
# ---------------------------------------------------------------------------


class TestKeyErrorForUnknownEntity:
    def test_raises_key_error_for_absent_entity(self) -> None:
        ref = make_reference()
        with pytest.raises(KeyError, match="not in reference snapshot"):
            build_full_context(ref, "Q9999")

    def test_error_message_contains_entity_id(self) -> None:
        ref = make_reference()
        with pytest.raises(KeyError) as exc_info:
            build_full_context(ref, "Q_MISSING")
        assert "Q_MISSING" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Non-mutation invariant
# ---------------------------------------------------------------------------


class TestNonMutation:
    def test_build_full_context_does_not_mutate_reference(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A, LABEL_IMAGE])
        snapshot_before = ref.model_dump()
        _ = build_full_context(ref, FOCUS_ID)
        assert ref.model_dump() == snapshot_before

    def test_assemble_context_does_not_mutate_reference(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        snapshot_before = ref.model_dump()
        p = KnowledgeAbsence(triples=[TripleRef(subject_id=FOCUS_ID, property_id="P31")])
        _ = assemble_context(ref, FOCUS_ID, perturbations=[p])
        assert ref.model_dump() == snapshot_before

    def test_assemble_context_does_not_mutate_reference_content_labels(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A, LABEL_TEXT_B])
        labels_before = [lbl.model_dump() for lbl in ref.content_labels]
        _ = assemble_context(ref, FOCUS_ID, perturbations=[TextContentAbsence(entity_id=FOCUS_ID)])
        assert [lbl.model_dump() for lbl in ref.content_labels] == labels_before


# ---------------------------------------------------------------------------
# 5. assemble_context with no perturbations == build_full_context
# ---------------------------------------------------------------------------


class TestAssembleContextNoPerturbations:
    def test_no_perturbations_equals_build_full(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        full = build_full_context(ref, FOCUS_ID)
        assembled = assemble_context(ref, FOCUS_ID, perturbations=())
        assert assembled.model_dump() == full.model_dump()

    def test_no_perturbations_default_arg(self) -> None:
        ref = make_reference()
        full = build_full_context(ref, FOCUS_ID)
        assembled = assemble_context(ref, FOCUS_ID)
        assert assembled.model_dump() == full.model_dump()


# ---------------------------------------------------------------------------
# 6. assemble_context with KnowledgeAbsence
# ---------------------------------------------------------------------------


class TestAssembleContextKnowledgeAbsence:
    def test_matching_triple_removed_from_assembled(self) -> None:
        ref = make_reference()
        triple_ref = TripleRef(subject_id=FOCUS_ID, property_id="P31", object_id="Q571")
        p = KnowledgeAbsence(triples=[triple_ref])

        full_ctx = build_full_context(ref, FOCUS_ID)
        assembled = assemble_context(ref, FOCUS_ID, perturbations=[p])

        # Full context still includes the edge
        assert EDGE_FOCUS_A in full_ctx.triples
        # Assembled context excludes it
        assert EDGE_FOCUS_A not in assembled.triples
        # The other outgoing edge is still present
        assert EDGE_FOCUS_B in assembled.triples

    def test_full_context_unaffected_by_ablation(self) -> None:
        # build_full_context must remain unchanged: ablation is isolated to assemble_context.
        ref = make_reference()
        triple_ref = TripleRef(subject_id=FOCUS_ID, property_id="P31", object_id="Q571")
        p = KnowledgeAbsence(triples=[triple_ref])

        full_ctx = build_full_context(ref, FOCUS_ID)
        _ = assemble_context(ref, FOCUS_ID, perturbations=[p])
        # build_full_context result is not mutated (call it again to verify determinism)
        full_ctx2 = build_full_context(ref, FOCUS_ID)
        assert full_ctx.model_dump() == full_ctx2.model_dump()

    def test_reference_content_labels_unchanged_after_ablation(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A, LABEL_TEXT_B])
        labels_before = copy.deepcopy(ref.content_labels)
        triple_ref = TripleRef(subject_id=FOCUS_ID, property_id="P31")
        p = KnowledgeAbsence(triples=[triple_ref])
        _ = assemble_context(ref, FOCUS_ID, perturbations=[p])
        assert ref.content_labels == labels_before


# ---------------------------------------------------------------------------
# 7. assemble_context with TextContentAbsence
# ---------------------------------------------------------------------------


class TestAssembleContextTextContentAbsence:
    def test_description_withheld_from_assembled(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        p = TextContentAbsence(entity_id=FOCUS_ID)
        assembled = assemble_context(ref, FOCUS_ID, perturbations=[p])
        assert assembled.description is None

    def test_full_context_still_has_description(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        p = TextContentAbsence(entity_id=FOCUS_ID)
        full_ctx = build_full_context(ref, FOCUS_ID)
        _ = assemble_context(ref, FOCUS_ID, perturbations=[p])
        assert full_ctx.description is not None

    def test_reference_content_labels_unchanged_after_text_ablation(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A, LABEL_TEXT_B])
        labels_snapshot = [lbl.model_dump() for lbl in ref.content_labels]
        p = TextContentAbsence(entity_id=FOCUS_ID)
        _ = assemble_context(ref, FOCUS_ID, perturbations=[p])
        assert [lbl.model_dump() for lbl in ref.content_labels] == labels_snapshot

    def test_triples_still_present_after_text_ablation(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        p = TextContentAbsence(entity_id=FOCUS_ID)
        assembled = assemble_context(ref, FOCUS_ID, perturbations=[p])
        assert EDGE_FOCUS_A in assembled.triples
        assert EDGE_FOCUS_B in assembled.triples


# ---------------------------------------------------------------------------
# 8. Ordering: two perturbations applied in sequence
# ---------------------------------------------------------------------------


class TestPerturbationOrdering:
    def test_both_perturbations_applied(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        p_text = TextContentAbsence(entity_id=FOCUS_ID)
        p_know = KnowledgeAbsence(
            triples=[TripleRef(subject_id=FOCUS_ID, property_id="P31", object_id="Q571")]
        )
        assembled = assemble_context(ref, FOCUS_ID, perturbations=[p_text, p_know])
        assert assembled.description is None
        assert EDGE_FOCUS_A not in assembled.triples
        assert EDGE_FOCUS_B in assembled.triples

    def test_order_is_preserved(self) -> None:
        # Both TextContentAbsence and KnowledgeAbsence withhold in order;
        # verify the result reflects BOTH, not just one.
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        p1 = TextContentAbsence(entity_id=FOCUS_ID)
        p2 = KnowledgeAbsence(triples=[TripleRef(subject_id=FOCUS_ID, property_id="P50")])
        assembled = assemble_context(ref, FOCUS_ID, perturbations=[p1, p2])
        assert assembled.description is None  # p1 withheld it
        assert EDGE_FOCUS_B not in assembled.triples  # p2 withheld it (P50 = author)
        assert EDGE_FOCUS_A in assembled.triples  # P31 not withheld

    def test_reference_unchanged_after_two_perturbations(self) -> None:
        ref = make_reference(content_labels=[LABEL_TEXT_A, LABEL_TEXT_B])
        snapshot_before = ref.model_dump()
        p1 = TextContentAbsence(entity_id=FOCUS_ID)
        p2 = KnowledgeAbsence(triples=[TripleRef(subject_id=FOCUS_ID, property_id="P31")])
        _ = assemble_context(ref, FOCUS_ID, perturbations=[p1, p2])
        assert ref.model_dump() == snapshot_before


# ---------------------------------------------------------------------------
# 9. Edge-case description branches
# ---------------------------------------------------------------------------


class TestDescriptionEdgeCases:
    def test_whitespace_only_description_no_labels_gives_none(self) -> None:
        # description="   " strips to "" which is falsy -> treated as null.
        # With no TEXT content labels for the entity, result must be None.
        node_ws = KGNode(id=FOCUS_ID, label="Focus Book", description="   ")
        ref = make_reference(nodes=[node_ws, NODE_OTHER], content_labels=[])
        ctx = build_full_context(ref, FOCUS_ID)
        assert ctx.description is None


# ---------------------------------------------------------------------------
# 10. No-op perturbation (KnowledgeAbsence matching no outgoing triple)
# ---------------------------------------------------------------------------


class TestNoOpPerturbation:
    def test_nonmatching_knowledge_absence_is_noop(self) -> None:
        # TripleRef uses a subject_id/property_id that does not exist among
        # the focus entity's outgoing triples -> assemble_context result must
        # equal build_full_context result.
        ref = make_reference(content_labels=[LABEL_TEXT_A])
        p = KnowledgeAbsence(triples=[TripleRef(subject_id=FOCUS_ID, property_id="P999")])
        full = build_full_context(ref, FOCUS_ID)
        assembled = assemble_context(ref, FOCUS_ID, perturbations=[p])
        assert assembled.model_dump() == full.model_dump()
