"""
Tests for schema.py — the central pydantic v2 contract for IVG-KG.

Covers (per task spec):
  a) Full JSON round-trip of a populated GroundingRun with >= 1 ClaimRecord per
     status, including a multi-hop GroundingPath on the REASONED_SUPPORTABLE
     claim (>= 2 PathEdges, one traversed_forward=False).  Assert reconstructed
     == original AND that statuses are still ClaimStatus enum members.
  b) status_counts() returns all three keys with correct counts (including zero).
  c) fabrication_rate() correct on a mixed run and == 0.0 on an empty run.
  d) ClaimStatus.REASONED_SUPPORTABLE.value == "reasoned-supportable".
  e) Mutable defaults are independent across instances.
"""


from ivg_kg.schema import (
    ClaimRecord,
    ClaimStatus,
    ContentLabel,
    GenerationContext,
    GradingReference,
    GroundingConfig,
    GroundingPath,
    GroundingRun,
    KGEdge,
    KGNode,
    KGSnapshot,
    LinkedEntity,
    Modality,
    PathEdge,
    SupportSource,
    TripleRef,
    ValueType,
)

# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------

def _make_path_edge(subject_id: str, forward: bool = True) -> PathEdge:
    return PathEdge(
        subject_id=subject_id,
        subject_label=f"Label {subject_id}",
        property_id="P31",
        property_label="instance of",
        object_id="Q5",
        object_label="human",
        traversed_forward=forward,
    )


def _make_grounding_path_multi_hop() -> GroundingPath:
    """At least 2 PathEdges; one traversed_forward=False."""
    return GroundingPath(
        edges=[
            _make_path_edge("Q42", forward=True),
            _make_path_edge("Q5", forward=False),
        ],
        node_ids=["Q42", "Q5", "Q100"],
    )


def _make_claim_retrieved() -> ClaimRecord:
    return ClaimRecord(
        claim_id="c1",
        text="Douglas Adams is a human.",
        status=ClaimStatus.RETRIEVED,
        support_source=SupportSource.DIRECT_TRIPLE,
        linked_entities=[
            LinkedEntity(id="Q42", label="Douglas Adams", description="British author", link_score=0.95)
        ],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
        entailment_score=0.91,
    )


def _make_claim_reasoned() -> ClaimRecord:
    return ClaimRecord(
        claim_id="c2",
        text="Douglas Adams attended Cambridge.",
        status=ClaimStatus.REASONED_SUPPORTABLE,
        support_source=SupportSource.MULTI_HOP_PATH,
        linked_entities=[
            LinkedEntity(id="Q42", label="Douglas Adams", description=None, link_score=0.88)
        ],
        grounding_path=_make_grounding_path_multi_hop(),
        entailment_score=0.72,
        active_perturbations=["pert-001"],
    )


def _make_claim_fabricated() -> ClaimRecord:
    return ClaimRecord(
        claim_id="c3",
        text="Douglas Adams won the Nobel Prize.",
        status=ClaimStatus.FABRICATED,
        support_source=SupportSource.NONE,
        linked_entities=[],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
        entailment_score=0.12,
        spurious_path=True,
    )


def _make_kg_node() -> KGNode:
    return KGNode(id="Q42", label="Douglas Adams", description="British author", sitelinks=20)


def _make_kg_edge() -> KGEdge:
    return KGEdge(
        subject_id="Q42",
        property_id="P31",
        property_label="instance of",
        object_id="Q5",
        object_label="human",
        value_type=ValueType.ITEM,
    )


def _make_kg_snapshot() -> KGSnapshot:
    return KGSnapshot(
        snapshot_id="snap-001",
        slice="books",
        domain_qid="Q7725634",
        nodes=[_make_kg_node()],
        edges=[_make_kg_edge()],
        meta={"source": "wikidata"},
    )


def _make_grading_reference() -> GradingReference:
    snapshot = _make_kg_snapshot()
    content_label = ContentLabel(
        entity_id="Q42",
        modality=Modality.TEXT,
        fact="Douglas Adams is a British author.",
        source="wikipedia",
    )
    return GradingReference(snapshot=snapshot, content_labels=[content_label])


def _make_grounding_run() -> GroundingRun:
    return GroundingRun(
        run_id="run-001",
        question="Who is Douglas Adams?",
        answer_text="Douglas Adams is a human who attended Cambridge and won the Nobel Prize.",
        slice="books",
        phase="A",
        claims=[_make_claim_retrieved(), _make_claim_reasoned(), _make_claim_fabricated()],
        active_perturbations=["pert-001"],
        grading_reference_id="ref-001",
        error_rates={"text": 0.33, "structure": 0.0, "image": 0.0},
    )


# ---------------------------------------------------------------------------
# (d) Enum value literals
# ---------------------------------------------------------------------------

def test_claim_status_reasoned_supportable_value() -> None:
    """ClaimStatus.REASONED_SUPPORTABLE must have the hyphenated value."""
    assert ClaimStatus.REASONED_SUPPORTABLE.value == "reasoned-supportable"


def test_claim_status_values() -> None:
    assert ClaimStatus.RETRIEVED.value == "retrieved"
    assert ClaimStatus.FABRICATED.value == "fabricated"


def test_support_source_values_are_lowercase_strings() -> None:
    assert SupportSource.DIRECT_TRIPLE.value == "direct_triple"
    assert SupportSource.MULTI_HOP_PATH.value == "multi_hop_path"
    assert SupportSource.TEXT_CONTENT.value == "text_content"
    assert SupportSource.IMAGE_CONTENT.value == "image_content"
    assert SupportSource.NONE.value == "none"


def test_modality_values_are_lowercase_strings() -> None:
    assert Modality.STRUCTURE.value == "structure"
    assert Modality.TEXT.value == "text"
    assert Modality.IMAGE.value == "image"


def test_value_type_values_are_lowercase_strings() -> None:
    assert ValueType.ITEM.value == "item"
    assert ValueType.TIME.value == "time"
    assert ValueType.QUANTITY.value == "quantity"
    assert ValueType.MONOLINGUAL.value == "monolingual"
    assert ValueType.STRING.value == "string"


# ---------------------------------------------------------------------------
# (a) Full JSON round-trip
# ---------------------------------------------------------------------------

def test_grounding_run_json_round_trip() -> None:
    """Serialise to JSON and back; reconstructed object must equal original."""
    run = _make_grounding_run()
    json_str = run.model_dump_json()
    reconstructed = GroundingRun.model_validate_json(json_str)
    assert reconstructed == run


def test_round_trip_preserves_enum_types() -> None:
    """After round-trip, claim statuses must still be ClaimStatus members, not bare strings."""
    run = _make_grounding_run()
    reconstructed = GroundingRun.model_validate_json(run.model_dump_json())
    for claim in reconstructed.claims:
        assert isinstance(claim.status, ClaimStatus), (
            f"Expected ClaimStatus enum, got {type(claim.status)}"
        )
        assert isinstance(claim.support_source, SupportSource), (
            f"Expected SupportSource enum, got {type(claim.support_source)}"
        )


def test_round_trip_preserves_multi_hop_path() -> None:
    """The REASONED_SUPPORTABLE claim's path must survive JSON round-trip intact."""
    run = _make_grounding_run()
    reconstructed = GroundingRun.model_validate_json(run.model_dump_json())
    reasoned = next(c for c in reconstructed.claims if c.status == ClaimStatus.REASONED_SUPPORTABLE)
    assert len(reasoned.grounding_path.edges) == 2
    assert any(not e.traversed_forward for e in reasoned.grounding_path.edges)


def test_round_trip_preserves_nested_enum_in_content_label() -> None:
    """Modality enum inside GradingReference must survive round-trip."""
    ref = _make_grading_reference()
    json_str = ref.model_dump_json()
    reconstructed = GradingReference.model_validate_json(json_str)
    assert reconstructed == ref
    for label in reconstructed.content_labels:
        assert isinstance(label.modality, Modality)


# ---------------------------------------------------------------------------
# (b) status_counts()
# ---------------------------------------------------------------------------

def test_status_counts_all_three_keys_present() -> None:
    """status_counts must include all three ClaimStatus values as keys."""
    run = _make_grounding_run()
    counts = run.status_counts()
    assert set(counts.keys()) == {cs.value for cs in ClaimStatus}


def test_status_counts_correct_values() -> None:
    run = _make_grounding_run()
    counts = run.status_counts()
    assert counts[ClaimStatus.RETRIEVED.value] == 1
    assert counts[ClaimStatus.REASONED_SUPPORTABLE.value] == 1
    assert counts[ClaimStatus.FABRICATED.value] == 1


def test_status_counts_zero_for_missing_status() -> None:
    """When one status is absent, its count must be 0 (not missing)."""
    run = GroundingRun(
        run_id="run-z",
        question="Q?",
        answer_text="A.",
        slice="books",
        phase="A",
        claims=[_make_claim_retrieved(), _make_claim_retrieved()],
    )
    counts = run.status_counts()
    assert counts[ClaimStatus.REASONED_SUPPORTABLE.value] == 0
    assert counts[ClaimStatus.FABRICATED.value] == 0
    assert counts[ClaimStatus.RETRIEVED.value] == 2


# ---------------------------------------------------------------------------
# (c) fabrication_rate()
# ---------------------------------------------------------------------------

def test_fabrication_rate_mixed_run() -> None:
    run = _make_grounding_run()  # 1 retrieved, 1 reasoned, 1 fabricated -> 1/3
    rate = run.fabrication_rate()
    assert abs(rate - 1 / 3) < 1e-9


def test_fabrication_rate_empty_run_is_zero() -> None:
    """fabrication_rate() must return 0.0 (not raise ZeroDivisionError) when claims is empty."""
    run = GroundingRun(
        run_id="run-empty",
        question="Q?",
        answer_text="A.",
        slice="books",
        phase="B",
        claims=[],
    )
    assert run.fabrication_rate() == 0.0


def test_fabrication_rate_all_fabricated() -> None:
    run = GroundingRun(
        run_id="run-all-fab",
        question="Q?",
        answer_text="A.",
        slice="books",
        phase="A",
        claims=[_make_claim_fabricated(), _make_claim_fabricated()],
    )
    assert run.fabrication_rate() == 1.0


def test_fabrication_rate_none_fabricated() -> None:
    run = GroundingRun(
        run_id="run-no-fab",
        question="Q?",
        answer_text="A.",
        slice="books",
        phase="A",
        claims=[_make_claim_retrieved(), _make_claim_reasoned()],
    )
    assert run.fabrication_rate() == 0.0


# ---------------------------------------------------------------------------
# (e) Mutable defaults are independent across instances
# ---------------------------------------------------------------------------

def test_active_perturbations_independent_across_instances() -> None:
    """Two ClaimRecord instances must not share the same active_perturbations list."""
    c1 = ClaimRecord(
        claim_id="x1",
        text="Claim one.",
        status=ClaimStatus.RETRIEVED,
        support_source=SupportSource.DIRECT_TRIPLE,
        linked_entities=[],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
    )
    c2 = ClaimRecord(
        claim_id="x2",
        text="Claim two.",
        status=ClaimStatus.RETRIEVED,
        support_source=SupportSource.DIRECT_TRIPLE,
        linked_entities=[],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
    )
    c1.active_perturbations.append("p1")
    assert c2.active_perturbations == [], "Mutable default must not be shared between instances"


def test_unresolved_entities_independent_across_instances() -> None:
    c1 = ClaimRecord(
        claim_id="y1",
        text="Claim.",
        status=ClaimStatus.FABRICATED,
        support_source=SupportSource.NONE,
        linked_entities=[],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
    )
    c2 = ClaimRecord(
        claim_id="y2",
        text="Claim.",
        status=ClaimStatus.FABRICATED,
        support_source=SupportSource.NONE,
        linked_entities=[],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
    )
    c1.unresolved_entities.append("Q999")
    assert c2.unresolved_entities == []


def test_grounding_run_active_perturbations_independent() -> None:
    r1 = GroundingRun(run_id="r1", question="Q?", answer_text="A.", slice="s", phase="A", claims=[])
    r2 = GroundingRun(run_id="r2", question="Q?", answer_text="A.", slice="s", phase="A", claims=[])
    r1.active_perturbations.append("p")
    assert r2.active_perturbations == []


# ---------------------------------------------------------------------------
# GroundingPath.hops property
# ---------------------------------------------------------------------------

def test_grounding_path_hops_property() -> None:
    """hops must equal len(edges) and must not be a settable field."""
    path = _make_grounding_path_multi_hop()
    assert path.hops == 2
    # hops is a @property — it should NOT appear as a model field
    assert "hops" not in GroundingPath.model_fields


def test_grounding_path_empty_hops_is_zero() -> None:
    path = GroundingPath(edges=[], node_ids=[])
    assert path.hops == 0


# ---------------------------------------------------------------------------
# Defaults (spot-checks)
# ---------------------------------------------------------------------------

def test_kg_node_kind_default() -> None:
    node = KGNode(id="Q1", label="Universe", description=None)
    assert node.kind == "entity"


def test_grounding_config_defaults() -> None:
    cfg = GroundingConfig()
    assert cfg.k_hops == 2
    assert cfg.tau == 0.5
    assert cfg.linker == "label_alias"
    assert cfg.entailment == "minicheck"


def test_claim_record_spurious_path_default_false() -> None:
    c = ClaimRecord(
        claim_id="z1",
        text="X",
        status=ClaimStatus.RETRIEVED,
        support_source=SupportSource.DIRECT_TRIPLE,
        linked_entities=[],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
    )
    assert c.spurious_path is False


# ---------------------------------------------------------------------------
# Optional / nullable fields
# ---------------------------------------------------------------------------

def test_kg_node_optional_fields_none() -> None:
    node = KGNode(id="Q1", label="Minimal", description=None)
    assert node.image_path is None
    assert node.sitelinks is None


def test_kg_edge_object_id_can_be_none() -> None:
    edge = KGEdge(
        subject_id="Q42",
        property_id="P569",
        property_label="date of birth",
        object_id=None,
        object_label="1952-03-11",
        value_type=ValueType.TIME,
    )
    assert edge.object_id is None


def test_linked_entity_optional_fields() -> None:
    entity = LinkedEntity(id="Q1", label="minimal", description=None, link_score=None)
    assert entity.description is None
    assert entity.link_score is None


def test_grounding_run_optional_grading_reference_id() -> None:
    run = GroundingRun(
        run_id="r-opt",
        question="Q?",
        answer_text="A.",
        slice="books",
        phase="A",
        claims=[],
    )
    assert run.grading_reference_id is None


# ---------------------------------------------------------------------------
# TripleRef
# ---------------------------------------------------------------------------

def test_triple_ref_object_id_optional() -> None:
    ref = TripleRef(subject_id="Q42", property_id="P31")
    assert ref.object_id is None


def test_triple_ref_with_object_id() -> None:
    ref = TripleRef(subject_id="Q42", property_id="P31", object_id="Q5")
    assert ref.object_id == "Q5"


# ---------------------------------------------------------------------------
# GenerationContext
# ---------------------------------------------------------------------------

def test_generation_context_round_trip() -> None:
    ctx = GenerationContext(
        entity_id="Q42",
        triples=[_make_kg_edge()],
        description="British author",
        image_path="/path/to/img.jpg",
    )
    reconstructed = GenerationContext.model_validate_json(ctx.model_dump_json())
    assert reconstructed == ctx


def test_generation_context_optional_fields_none() -> None:
    ctx = GenerationContext(entity_id="Q42", triples=[], description=None, image_path=None)
    assert ctx.description is None
    assert ctx.image_path is None


# ---------------------------------------------------------------------------
# ContentLabel with IMAGE modality (enum is part of contract)
# ---------------------------------------------------------------------------

def test_content_label_image_modality() -> None:
    label = ContentLabel(
        entity_id="Q42",
        modality=Modality.IMAGE,
        fact="Douglas Adams photo.",
        source="commons",
    )
    assert label.modality == Modality.IMAGE
    json_str = label.model_dump_json()
    reconstructed = ContentLabel.model_validate_json(json_str)
    assert reconstructed.modality == Modality.IMAGE
    assert isinstance(reconstructed.modality, Modality)
