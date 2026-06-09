"""
SPEC §6 control harness — P0 subset (TS1).

Mapping of tests to §6 bullets:

  test_control_sitelink_band_filter_*
      -> §6 mechanical: sitelink-band filter (inclusive, drops None/missing).

  TestControl_ComposedManifestAttribution
      -> §6 mechanical: composed-manifest attribution (ablate two entities,
         verify per-claim attribution routes to the right perturbation entries
         in manifest order; SPEC §4.4).

  TestControl_SchemaRoundTrip
      -> §6 mechanical: schema round-trip (GroundingRun JSON serialization,
         ClaimStatus enum survival, status_counts() stability; guards
         dcc.Store JSON-serialization contract).

  TestControl_GradeAgainstReferenceInvariant_DataLayer
      -> §6 / §3.2 spine: data-layer assertion — withhold touches only the
         GenerationContext; the GradingReference is NEVER ablated and still
         carries every fact.

  test_control_grade_against_reference_backend_stub_wired
      -> §6 scaffold: asserts the P0 backend raises NotImplementedError;
         documents the seam that TS2 will close.

Deferred to TS2 (require GR8 / GR9 / EX3):
  - undirected-path found (mini-KG regression; needs GR8 path classifier)
  - spurious shared-literal path rejected (literal-node exclusion; needs GR8)
  - false-claim rejection / negative control (needs real GR9 backend)
  - manipulation check (needs GR9)
  - deterministic leverage identity (needs EX3 repair loop)
"""

from __future__ import annotations

import pytest

from ivg_kg.data.graph_store import build_snapshot
from ivg_kg.data.reference import assemble_reference, author_books_content_labels
from ivg_kg.data.wikidata import sitelink_band_filter
from ivg_kg.grounding.backend import ground_response
from ivg_kg.mock.fixtures import mock_grounding_run
from ivg_kg.perturbation import AblationManifest, KnowledgeAbsence, TextContentAbsence
from ivg_kg.schema import (
    ClaimStatus,
    GenerationContext,
    GradingReference,
    GroundingConfig,
    GroundingRun,
    KGEdge,
    TripleRef,
    ValueType,
)

# ---------------------------------------------------------------------------
# §6 Control 1: sitelink-band filter
# ---------------------------------------------------------------------------

# Fixed band used throughout this control (does NOT import BAND_LO/BAND_HI —
# the §6 control must be self-contained and test the FUNCTION, not config).
_BAND = (5, 40)
_LO, _HI = _BAND


def _items_with_counts(counts: list[int | None]) -> list[dict]:
    """Build minimal item dicts from a list of sitelink counts."""
    return [{"id": f"Q{i}", "sitelinks": c} for i, c in enumerate(counts)]


def test_control_sitelink_band_filter_inclusive_and_drops_none() -> None:
    """§6 control: sitelink-band filter.

    Verifies ALL of:
    - Inclusive lower boundary: count == lo is KEPT.
    - Inclusive upper boundary: count == hi is KEPT.
    - lo-1 is DROPPED.
    - hi+1 is DROPPED.
    - Items whose sitelinks value is None are DROPPED.
    - Items whose 'sitelinks' key is absent (missing) are DROPPED.
    - Empty input returns empty output.

    The band (5, 40) is used directly to make the invariant legible.
    The real BAND_LO/BAND_HI config values are tested separately in
    test_wikidata.py; this control tests the FUNCTION invariant.
    """
    # --- inclusive lower boundary ---
    result_lo = sitelink_band_filter(_items_with_counts([_LO]), band=_BAND)
    assert len(result_lo) == 1, f"lo={_LO} must be KEPT (inclusive lower boundary)"

    # --- inclusive upper boundary ---
    result_hi = sitelink_band_filter(_items_with_counts([_HI]), band=_BAND)
    assert len(result_hi) == 1, f"hi={_HI} must be KEPT (inclusive upper boundary)"

    # --- lo-1 dropped ---
    result_below = sitelink_band_filter(_items_with_counts([_LO - 1]), band=_BAND)
    assert result_below == [], f"lo-1={_LO - 1} must be DROPPED"

    # --- hi+1 dropped ---
    result_above = sitelink_band_filter(_items_with_counts([_HI + 1]), band=_BAND)
    assert result_above == [], f"hi+1={_HI + 1} must be DROPPED"

    # --- None count is DROPPED ---
    result_none = sitelink_band_filter(_items_with_counts([None]), band=_BAND)
    assert result_none == [], "sitelinks=None must be DROPPED"

    # --- missing key is DROPPED ---
    result_missing = sitelink_band_filter([{"id": "Q_no_key"}], band=_BAND)
    assert result_missing == [], "missing 'sitelinks' key must be DROPPED"

    # --- empty input ---
    assert sitelink_band_filter([], band=_BAND) == []


def test_control_sitelink_band_filter_mixed_batch() -> None:
    """§6 control: sitelink-band filter over a mixed batch.

    A batch containing lo, hi, lo-1, hi+1, None, and a missing-key item:
    exactly the two boundary items (lo and hi) survive.
    """
    items = [
        {"id": "keep_lo", "sitelinks": _LO},
        {"id": "keep_hi", "sitelinks": _HI},
        {"id": "drop_below", "sitelinks": _LO - 1},
        {"id": "drop_above", "sitelinks": _HI + 1},
        {"id": "drop_none", "sitelinks": None},
        {"id": "drop_missing"},  # no 'sitelinks' key
    ]
    result = sitelink_band_filter(items, band=_BAND)
    kept_ids = {r["id"] for r in result}
    assert kept_ids == {"keep_lo", "keep_hi"}
    assert len(result) == 2


# ---------------------------------------------------------------------------
# §6 Control 2: composed-manifest attribution
# ---------------------------------------------------------------------------

# Books-domain entities for the two-perturbation manifest.
_E1 = "Q_E1"  # book entity — TextContentAbsence will act on description
_E2 = "Q_E2"  # author entity — KnowledgeAbsence will act on triples
_E_OTHER = "Q_E_OTHER"  # unrelated entity (no perturbation touches it)

# A TripleRef that anchors the KnowledgeAbsence perturbation on E2.
_E2_TRIPLE_REF = TripleRef(subject_id=_E2, property_id="P50", object_id="Q_AUTHOR")


class TestControlComposedManifestAttribution:
    """§6 control: composed-manifest attribution (SPEC §4.4).

    Two perturbations on DIFFERENT entities in a single AblationManifest:
      - Entry 0: TextContentAbsence("Q_E1")  — ablates E1's description
      - Entry 1: KnowledgeAbsence([TripleRef("Q_E2", "P50", ...)])
                                               — ablates E2's structural triple

    Per-claim attribution uses manifest.entries_touching(<linked entity ids>)
    to determine which perturbation entries are causally relevant to each claim.
    """

    @pytest.fixture()
    def manifest(self) -> AblationManifest:
        p_text = TextContentAbsence(_E1)
        p_know = KnowledgeAbsence([_E2_TRIPLE_REF])
        return AblationManifest(base_slice_id="books-test-v1", perturbations=[p_text, p_know])

    @pytest.fixture()
    def p_text_id(self) -> str:
        return TextContentAbsence(_E1).id

    @pytest.fixture()
    def p_know_id(self) -> str:
        return KnowledgeAbsence([_E2_TRIPLE_REF]).id

    def test_manifest_has_two_entries_in_order(
        self, manifest: AblationManifest, p_text_id: str, p_know_id: str
    ) -> None:
        ids = manifest.active_entry_ids()
        assert ids == [p_text_id, p_know_id]

    def test_claim_linking_only_e1_attributed_to_text_entry(
        self, manifest: AblationManifest, p_text_id: str, p_know_id: str
    ) -> None:
        """A claim whose linked entities are {E1} only → attributed to text entry."""
        attributed = manifest.entries_touching({_E1})
        assert attributed == [p_text_id], (
            f"Expected only the TextContentAbsence id {p_text_id!r}; got {attributed!r}"
        )
        assert p_know_id not in attributed

    def test_claim_linking_only_e2_attributed_to_knowledge_entry(
        self, manifest: AblationManifest, p_text_id: str, p_know_id: str
    ) -> None:
        """A claim whose linked entities are {E2} only → attributed to knowledge entry."""
        attributed = manifest.entries_touching({_E2})
        assert attributed == [p_know_id], (
            f"Expected only the KnowledgeAbsence id {p_know_id!r}; got {attributed!r}"
        )
        assert p_text_id not in attributed

    def test_claim_linking_both_attributed_to_both_in_manifest_order(
        self, manifest: AblationManifest, p_text_id: str, p_know_id: str
    ) -> None:
        """A claim linking both E1 and E2 → attributed to BOTH, in manifest order."""
        attributed = manifest.entries_touching({_E1, _E2})
        assert len(attributed) == 2
        assert attributed[0] == p_text_id, "text entry must come first (manifest order)"
        assert attributed[1] == p_know_id, "knowledge entry must come second"

    def test_claim_linking_unrelated_entity_attributed_to_none(
        self, manifest: AblationManifest
    ) -> None:
        """A claim linking only an unrelated entity → attributed to [] (none)."""
        attributed = manifest.entries_touching({_E_OTHER})
        assert attributed == [], f"Unrelated entity must yield []; got {attributed!r}"

    def test_attribution_uses_real_perturbation_ids(
        self, manifest: AblationManifest
    ) -> None:
        """Assertions use the actual .id attributes — not hardcoded strings."""
        p_text = TextContentAbsence(_E1)
        p_know = KnowledgeAbsence([_E2_TRIPLE_REF])
        # Verify that the ids in the manifest match the freshly constructed ones.
        ids = manifest.active_entry_ids()
        assert p_text.id in ids
        assert p_know.id in ids


# ---------------------------------------------------------------------------
# §6 Control 3: schema round-trip
# ---------------------------------------------------------------------------


class TestControlSchemaRoundTrip:
    """§6 control: schema round-trip (GroundingRun JSON serialization contract).

    Uses mock_grounding_run() which contains all three ClaimStatus values and
    a multi-hop path.  Guards the dcc.Store JSON-serialization contract.
    """

    def test_round_trip_is_equal(self) -> None:
        """model_dump_json() -> model_validate_json() yields an equal object."""
        original = mock_grounding_run()
        serialized = original.model_dump_json()
        reconstructed = GroundingRun.model_validate_json(serialized)
        assert reconstructed == original

    def test_claim_status_survives_as_enum_members(self) -> None:
        """ClaimStatus fields deserialize as ClaimStatus members, not bare strings."""
        original = mock_grounding_run()
        serialized = original.model_dump_json()
        reconstructed = GroundingRun.model_validate_json(serialized)
        for claim in reconstructed.claims:
            assert isinstance(claim.status, ClaimStatus), (
                f"claim {claim.claim_id}: expected ClaimStatus instance, "
                f"got {type(claim.status).__name__!r}"
            )

    def test_status_counts_stable_after_round_trip(self) -> None:
        """status_counts() returns the same mapping before and after round-trip."""
        original = mock_grounding_run()
        original_counts = original.status_counts()
        serialized = original.model_dump_json()
        reconstructed = GroundingRun.model_validate_json(serialized)
        reconstructed_counts = reconstructed.status_counts()
        assert reconstructed_counts == original_counts

    def test_all_three_statuses_present_after_round_trip(self) -> None:
        """mock_grounding_run() covers all three statuses; all survive round-trip."""
        reconstructed = GroundingRun.model_validate_json(mock_grounding_run().model_dump_json())
        counts = reconstructed.status_counts()
        assert set(counts.keys()) == {s.value for s in ClaimStatus}
        for status in ClaimStatus:
            assert counts[status.value] >= 0  # always present (even if zero)
        # The mock actually has RETRIEVED, REASONED_SUPPORTABLE, FABRICATED claims.
        assert counts[ClaimStatus.RETRIEVED.value] > 0
        assert counts[ClaimStatus.REASONED_SUPPORTABLE.value] > 0
        assert counts[ClaimStatus.FABRICATED.value] > 0

    def test_no_bare_reasoned_string_in_status_values(self) -> None:
        """Invariant #5: status values use 'reasoned-supportable', never 'reasoned'.

        The enum value is the authoritative string; this test guards against
        any accidental alias or serialization shortcut.
        """
        original = mock_grounding_run()
        json_text = original.model_dump_json()
        # The literal string "reasoned" must only appear as part of
        # "reasoned-supportable" — never as a standalone status value.
        assert '"reasoned"' not in json_text, (
            "Found bare '\"reasoned\"' in serialized JSON — must be "
            "'\"reasoned-supportable\"' (Invariant #5)"
        )
        assert '"reasoned-supportable"' in json_text

    def test_multi_hop_path_edges_survive_round_trip(self) -> None:
        """PathEdge list (including traversed_forward) survives serialization."""
        original = mock_grounding_run()
        reconstructed = GroundingRun.model_validate_json(original.model_dump_json())
        # Find the MULTI_HOP_PATH claim in the reconstructed run.
        from ivg_kg.schema import SupportSource

        multi_hop_claims = [
            c for c in reconstructed.claims if c.support_source == SupportSource.MULTI_HOP_PATH
        ]
        assert len(multi_hop_claims) >= 1
        for claim in multi_hop_claims:
            assert len(claim.grounding_path.edges) >= 1
            for edge in claim.grounding_path.edges:
                # traversed_forward is a bool — must be preserved exactly.
                assert isinstance(edge.traversed_forward, bool)


# ---------------------------------------------------------------------------
# §6 Control 4: grade-against-reference invariant scaffold (§3.2 spine)
# ---------------------------------------------------------------------------

# Minimal books-domain fixture for the data-layer assertion.
# Entity Q_E has:
#   - one structural triple: Q_E --P50--> Q_AUTHOR
#   - one content-only text fact: "a debut novel set in Berlin"
_QE = "Q_E"
_QE_LABEL = "The Test Novel"
_QE_DESC = "A debut novel set in Berlin."

_QAUTHOR = "Q_AUTHOR"
_QAUTHOR_LABEL = "Test Author"

_STRUCTURAL_ROW = {
    "subject_id": _QE,
    "subject_label": _QE_LABEL,
    "subject_description": _QE_DESC,
    "property_id": "P50",
    "property_label": "author",
    "object_id": _QAUTHOR,
    "object_label": _QAUTHOR_LABEL,
    "value_type": "item",
}

_CONTENT_FACT = "a debut novel set in Berlin"
_CONTENT_SOURCE = "description"

_STRUCTURAL_EDGE = KGEdge(
    subject_id=_QE,
    property_id="P50",
    property_label="author",
    object_id=_QAUTHOR,
    object_label=_QAUTHOR_LABEL,
    value_type=ValueType.ITEM,
)
_STRUCTURAL_TRIPLE_REF = TripleRef(subject_id=_QE, property_id="P50", object_id=_QAUTHOR)


def _build_full_ctx() -> GenerationContext:
    """Build the full (unablated) GenerationContext for Q_E."""
    return GenerationContext(
        entity_id=_QE,
        triples=[_STRUCTURAL_EDGE],
        description=_QE_DESC,
        image_path=None,
    )


def _build_full_reference() -> GradingReference:
    """Build the KG-full GradingReference for Q_E (never ablated)."""
    snapshot = build_snapshot(
        [_STRUCTURAL_ROW],
        snapshot_id="test-snap-qe",
        slice="books",
        domain_qid=_QE,
    )
    content_labels = author_books_content_labels(
        [(_QE, _CONTENT_FACT, _CONTENT_SOURCE)]
    )
    return assemble_reference(snapshot, content_labels)


class TestControlGradeAgainstReferenceInvariantDataLayer:
    """§6 / §3.2 spine — data-layer assertion (P0-runnable half).

    SPEC §3.2: ablation withholds evidence from the GenerationContext ONLY.
    The GradingReference (KG-full triples + curated content labels) is NEVER
    ablated; a fact hidden from the generator remains gradable against KG-full.

    These tests assert the invariant at the DATA LAYER without needing the real
    grounding backend (which is a P0 stub that raises NotImplementedError).
    The classification half is scaffolded in
    test_control_grade_against_reference_backend_stub_wired() below and will be
    completed in TS2 once GR9 lands.
    """

    def test_text_withhold_removes_description_from_generation_context(self) -> None:
        """(a) withhold removes the description from the GENERATION context."""
        ctx = _build_full_ctx()
        assert ctx.description is not None, "precondition: full ctx has a description"

        ablated_ctx = TextContentAbsence(_QE).withhold(ctx)
        assert ablated_ctx.description is None, (
            "TextContentAbsence.withhold must set description=None in the generation context"
        )

    def test_knowledge_withhold_removes_triple_from_generation_context(self) -> None:
        """(a) withhold removes the structural triple from the GENERATION context."""
        ctx = _build_full_ctx()
        assert any(e.property_id == "P50" for e in ctx.triples), (
            "precondition: full ctx contains the P50 triple"
        )

        ablated_ctx = KnowledgeAbsence([_STRUCTURAL_TRIPLE_REF]).withhold(ctx)
        assert not any(e.property_id == "P50" for e in ablated_ctx.triples), (
            "KnowledgeAbsence.withhold must remove the P50 triple from the generation context"
        )

    def test_grading_reference_still_contains_content_label_after_text_withhold(self) -> None:
        """(b) content label survives in the GradingReference after text withhold.

        Withholding the description from the GenerationContext must NOT touch
        the GradingReference.  The content-only fact remains gradable against
        KG-full.
        """
        ctx = _build_full_ctx()
        reference = _build_full_reference()

        # Apply text withhold — this must not mutate reference.
        _ = TextContentAbsence(_QE).withhold(ctx)

        # The content label for Q_E is still in the reference.
        ref_labels_for_qe = [
            lb for lb in reference.content_labels if lb.entity_id == _QE
        ]
        assert len(ref_labels_for_qe) >= 1, (
            "GradingReference must still contain a ContentLabel for Q_E after withhold"
        )
        label_facts = [lb.fact for lb in ref_labels_for_qe]
        assert _CONTENT_FACT in label_facts, (
            f"The withheld fact {_CONTENT_FACT!r} must still be present in the "
            "GradingReference content labels (SPEC §3.2)"
        )

    def test_grading_reference_still_contains_structural_triple_after_knowledge_withhold(
        self,
    ) -> None:
        """(b) structural triple survives in the GradingReference after knowledge withhold.

        Withholding a triple from the GenerationContext must NOT touch the
        GradingReference snapshot.  The triple remains gradable against KG-full.
        """
        ctx = _build_full_ctx()
        reference = _build_full_reference()

        # Apply knowledge withhold — this must not mutate reference.
        _ = KnowledgeAbsence([_STRUCTURAL_TRIPLE_REF]).withhold(ctx)

        # The P50 triple for Q_E is still in the reference snapshot.
        ref_edges = reference.snapshot.edges
        p50_edges = [e for e in ref_edges if e.subject_id == _QE and e.property_id == "P50"]
        assert len(p50_edges) >= 1, (
            "GradingReference.snapshot must still contain the P50 triple for Q_E "
            "after KnowledgeAbsence.withhold (SPEC §3.2)"
        )

    def test_original_ctx_is_unchanged_after_text_withhold(self) -> None:
        """(c) purity: original GenerationContext is unchanged after text withhold."""
        ctx = _build_full_ctx()
        original_description = ctx.description
        original_triple_count = len(ctx.triples)

        _ = TextContentAbsence(_QE).withhold(ctx)

        assert ctx.description == original_description, (
            "TextContentAbsence.withhold must not mutate the input ctx (purity)"
        )
        assert len(ctx.triples) == original_triple_count

    def test_original_ctx_is_unchanged_after_knowledge_withhold(self) -> None:
        """(c) purity: original GenerationContext is unchanged after knowledge withhold."""
        ctx = _build_full_ctx()
        original_triple_count = len(ctx.triples)
        original_triple_ids = [(e.subject_id, e.property_id) for e in ctx.triples]

        _ = KnowledgeAbsence([_STRUCTURAL_TRIPLE_REF]).withhold(ctx)

        assert len(ctx.triples) == original_triple_count, (
            "KnowledgeAbsence.withhold must not mutate the input ctx (purity)"
        )
        assert [(e.subject_id, e.property_id) for e in ctx.triples] == original_triple_ids

    def test_withhold_does_not_alter_reference_snapshot_node_count(self) -> None:
        """(b) additional check: reference snapshot node count is invariant under withhold."""
        reference = _build_full_reference()
        original_node_count = len(reference.snapshot.nodes)
        original_edge_count = len(reference.snapshot.edges)

        ctx = _build_full_ctx()
        # Apply both perturbations.
        _ = TextContentAbsence(_QE).withhold(ctx)
        _ = KnowledgeAbsence([_STRUCTURAL_TRIPLE_REF]).withhold(ctx)

        # Reference is completely untouched.
        assert len(reference.snapshot.nodes) == original_node_count
        assert len(reference.snapshot.edges) == original_edge_count

    def test_ablated_ctx_lacks_description_but_reference_has_content_label(self) -> None:
        """End-to-end data-layer invariant: single assertion encoding §3.2 directly.

        After withholding the description from the generation context:
          - ablated_ctx.description is None  (fact hidden from generator)
          - reference still has a ContentLabel with the same fact (still gradable)

        This is the core §3.2 statement: "a fact hidden from the generator
        stays in the grading reference."
        """
        ctx = _build_full_ctx()
        reference = _build_full_reference()

        ablated_ctx = TextContentAbsence(_QE).withhold(ctx)

        # The generator sees no description.
        assert ablated_ctx.description is None

        # The grader's reference still has the fact.
        ref_label_facts = [lb.fact for lb in reference.content_labels if lb.entity_id == _QE]
        assert _CONTENT_FACT in ref_label_facts, (
            "SPEC §3.2 violated: fact hidden from generator is also absent from "
            "GradingReference; ablation must only affect GenerationContext."
        )

    def test_ablated_ctx_lacks_triple_but_reference_has_edge(self) -> None:
        """End-to-end data-layer invariant for structural triples (§3.2).

        After withholding the P50 triple from the generation context:
          - ablated_ctx has no P50 edge  (structural fact hidden from generator)
          - reference snapshot still has the P50 edge (still gradable)
        """
        ctx = _build_full_ctx()
        reference = _build_full_reference()

        ablated_ctx = KnowledgeAbsence([_STRUCTURAL_TRIPLE_REF]).withhold(ctx)

        # Generator sees no P50 triple.
        assert not any(e.property_id == "P50" for e in ablated_ctx.triples)

        # Grader's reference still has the P50 edge.
        ref_p50 = [
            e
            for e in reference.snapshot.edges
            if e.subject_id == _QE and e.property_id == "P50"
        ]
        assert len(ref_p50) >= 1, (
            "SPEC §3.2 violated: P50 edge hidden from generator is also absent from "
            "GradingReference.snapshot.edges"
        )


# ---------------------------------------------------------------------------
# §6 Control 4 (scaffold): classification half — P0 backend stub is wired
# ---------------------------------------------------------------------------


@pytest.mark.skip(
    reason=(
        "grade-against-reference FULL control (classify a withheld-evidence claim "
        "against KG-full and confirm it grades grounded) is completed in TS2 against "
        "the real GR9 backend.  This test documents the stub seam."
    )
)
def test_control_grade_against_reference_classification_half_ts2() -> None:  # pragma: no cover
    """TS2 will replace this skip with a real grounding call against GR9.

    The assertion: ground_response(question, withheld_answer, reference, ...) must
    return a GroundingRun where the claim about the withheld fact is still
    graded RETRIEVED or REASONED_SUPPORTABLE (because the reference is full).
    """
    raise AssertionError("TS2 placeholder — should not reach here")


def test_control_grade_against_reference_backend_stub_wired() -> None:
    """§6 scaffold: P0 backend raises NotImplementedError (stub is wired).

    Documents that ground_response() is intentionally a P0 stub.
    TS2 closes this scaffold by replacing the stub body with the real GR9
    implementation and classifying the withheld-evidence claim against KG-full.
    """
    reference = _build_full_reference()
    config = GroundingConfig()
    with pytest.raises(NotImplementedError):
        ground_response(
            question="What is The Test Novel?",
            answer_text="The Test Novel was written by Test Author.",
            reference=reference,
            active_perturbations=[],
            config=config,
        )
