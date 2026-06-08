"""Tests for mock/fixtures.py (UI1).

Acceptance criteria (from task brief):
(a) mock_grounding_run() contains >=1 claim of each of the three statuses.
(b) Has a REASONED_SUPPORTABLE claim whose grounding_path has >=2 edges
    with >=1 traversed_forward=False.
(c) Includes both a DIRECT_TRIPLE and a TEXT_CONTENT retrieved claim.
(d) status_counts() and fabrication_rate() compute without error;
    status_counts() has all three status keys.
(e) The whole run round-trips through model_dump_json()/model_validate_json().
(f) mock_subgraph_elements() returns elements such that every node id
    referenced by an edge exists as a node, and the multi-hop claim's
    path nodes/edges are all present in the elements.
(g) Calling mock_grounding_run() twice returns independent objects.
No image_path / taxa content anywhere (assert none of the nodes carry an
image_path and no claim uses IMAGE_CONTENT).
"""
from ivg_kg.mock.fixtures import mock_grounding_run, mock_subgraph_elements
from ivg_kg.schema import ClaimStatus, GroundingRun, SupportSource

# ---------------------------------------------------------------------------
# (a) All three statuses present
# ---------------------------------------------------------------------------


def test_all_three_statuses_present():
    run = mock_grounding_run()
    statuses = {c.status for c in run.claims}
    assert ClaimStatus.RETRIEVED in statuses, "No RETRIEVED claim"
    assert ClaimStatus.REASONED_SUPPORTABLE in statuses, "No REASONED_SUPPORTABLE claim"
    assert ClaimStatus.FABRICATED in statuses, "No FABRICATED claim"


# ---------------------------------------------------------------------------
# (b) REASONED_SUPPORTABLE claim with >=2 edges and >=1 traversed_forward=False
# ---------------------------------------------------------------------------


def test_reasoned_supportable_path():
    run = mock_grounding_run()
    rs_claims = [c for c in run.claims if c.status == ClaimStatus.REASONED_SUPPORTABLE]
    assert rs_claims, "No REASONED_SUPPORTABLE claim found"
    claim = rs_claims[0]
    path = claim.grounding_path
    assert len(path.edges) >= 2, (
        f"Expected >=2 path edges, got {len(path.edges)}"
    )
    backward_edges = [e for e in path.edges if not e.traversed_forward]
    assert backward_edges, "No edge with traversed_forward=False in REASONED_SUPPORTABLE path"


# ---------------------------------------------------------------------------
# (c) Both DIRECT_TRIPLE and TEXT_CONTENT retrieved claims present
# ---------------------------------------------------------------------------


def test_direct_triple_and_text_content_retrieved():
    run = mock_grounding_run()
    retrieved = [c for c in run.claims if c.status == ClaimStatus.RETRIEVED]
    sources = {c.support_source for c in retrieved}
    assert SupportSource.DIRECT_TRIPLE in sources, "No DIRECT_TRIPLE retrieved claim"
    assert SupportSource.TEXT_CONTENT in sources, "No TEXT_CONTENT retrieved claim"


# ---------------------------------------------------------------------------
# (d) status_counts() and fabrication_rate() work; status_counts() has all keys
# ---------------------------------------------------------------------------


def test_status_counts_and_fabrication_rate():
    run = mock_grounding_run()
    counts = run.status_counts()
    # All three keys must exist
    assert "retrieved" in counts
    assert "reasoned-supportable" in counts
    assert "fabricated" in counts
    # Values must be non-negative integers
    assert all(isinstance(v, int) and v >= 0 for v in counts.values())
    # fabrication_rate must be a float in [0, 1]
    rate = run.fabrication_rate()
    assert isinstance(rate, float)
    assert 0.0 <= rate <= 1.0


# ---------------------------------------------------------------------------
# (e) JSON round-trip
# ---------------------------------------------------------------------------


def test_json_round_trip():
    run = mock_grounding_run()
    serialised = run.model_dump_json()
    restored = GroundingRun.model_validate_json(serialised)
    # Re-serialise to compare as canonical JSON
    assert restored.model_dump_json() == serialised


# ---------------------------------------------------------------------------
# (f) Subgraph elements: edge node ids exist; path elements present
# ---------------------------------------------------------------------------


def test_subgraph_elements_referential_integrity():
    elements = mock_subgraph_elements()
    node_ids = {e["data"]["id"] for e in elements if "source" not in e["data"]}
    edges = [e for e in elements if "source" in e["data"]]
    for edge in edges:
        src = edge["data"]["source"]
        tgt = edge["data"]["target"]
        assert src in node_ids, f"Edge source '{src}' not in node ids"
        assert tgt in node_ids, f"Edge target '{tgt}' not in node ids"


def test_path_nodes_and_edges_in_subgraph():
    run = mock_grounding_run()
    elements = mock_subgraph_elements()
    rs_claims = [c for c in run.claims if c.status == ClaimStatus.REASONED_SUPPORTABLE]
    assert rs_claims, "No REASONED_SUPPORTABLE claim"
    claim = rs_claims[0]
    path = claim.grounding_path

    node_ids = {e["data"]["id"] for e in elements if "source" not in e["data"]}
    edge_ids = {e["data"]["id"] for e in elements if "source" in e["data"]}

    for nid in path.node_ids:
        assert nid in node_ids, f"Path node '{nid}' not found in subgraph elements"

    for pedge in path.edges:
        expected_edge_id = f"{pedge.subject_id}-{pedge.property_id}-{pedge.object_id}"
        assert expected_edge_id in edge_ids, (
            f"Path edge '{expected_edge_id}' not found in subgraph elements"
        )


# ---------------------------------------------------------------------------
# (g) Independent objects on successive calls
# ---------------------------------------------------------------------------


def test_independent_objects_on_successive_calls():
    run1 = mock_grounding_run()
    run2 = mock_grounding_run()
    # Mutate run1's claims list
    run1.claims.clear()
    # run2 must still have claims
    assert run2.claims, "Mutating run1 affected run2 — shared mutable state detected"


# ---------------------------------------------------------------------------
# No image_path or IMAGE_CONTENT anywhere
# ---------------------------------------------------------------------------


def test_no_image_path_or_image_content():
    run = mock_grounding_run()
    for claim in run.claims:
        assert claim.support_source != SupportSource.IMAGE_CONTENT, (
            f"Claim {claim.claim_id} uses IMAGE_CONTENT — forbidden in books fixture"
        )

    elements = mock_subgraph_elements()
    for element in elements:
        data = element["data"]
        assert "image_path" not in data or data.get("image_path") is None, (
            f"Element {data.get('id')} has image_path — forbidden in books fixture"
        )


# ---------------------------------------------------------------------------
# Type check: mock_grounding_run() returns a GroundingRun
# ---------------------------------------------------------------------------


def test_returns_correct_types():
    run = mock_grounding_run()
    assert isinstance(run, GroundingRun)
    elements = mock_subgraph_elements()
    assert isinstance(elements, list)
    assert all(isinstance(e, dict) for e in elements)


# ---------------------------------------------------------------------------
# Slice and phase sanity
# ---------------------------------------------------------------------------


def test_slice_and_phase():
    run = mock_grounding_run()
    assert run.slice == "books"
    assert run.phase == "A"
    assert run.active_perturbations == []
