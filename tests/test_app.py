"""Tests for UI2 — Dash three-panel skeleton.

Covers (offline, no running server):
- backend.ground_response raises NotImplementedError
- make_app() / get_layout() builds without error; layout contains dcc.Store(id='selected-claim')
- get_perturbation_controls() renders one control per available_perturbations() entry
- Invariant #12: highlight_stylesheet purity (no mutation of BASE_STYLESHEET)
- CB2 mapping: support_elements_for_claim for REASONED_SUPPORTABLE / unknown claims
- CB1 logic: select_claim_from_trigger returns correct claim_id / None
- No circular callbacks: selected-claim store is Output of exactly one callback
- Naming: no bare 'reasoned' label without '-supportable'
"""
from __future__ import annotations

import json

import pytest

from ivg_kg.mock.fixtures import mock_grounding_run, mock_subgraph_elements
from ivg_kg.perturbation import available_perturbations
from ivg_kg.schema import ClaimStatus, GradingReference, GroundingConfig, KGSnapshot

# ---------------------------------------------------------------------------
# backend.ground_response raises NotImplementedError
# ---------------------------------------------------------------------------


def test_ground_response_raises_not_implemented():
    from ivg_kg.grounding.backend import ground_response

    snapshot = KGSnapshot(
        snapshot_id="mock", slice="books", domain_qid="Q11111", nodes=[], edges=[]
    )
    reference = GradingReference(snapshot=snapshot, content_labels=[])
    config = GroundingConfig()

    with pytest.raises(NotImplementedError):
        ground_response(
            question="What?",
            answer_text="Answer.",
            reference=reference,
            active_perturbations=[],
            config=config,
        )


# ---------------------------------------------------------------------------
# make_app() / get_layout() builds without error; store present
# ---------------------------------------------------------------------------


def test_make_app_builds_without_error():
    from app.app import make_app
    app = make_app()
    assert app is not None


def test_layout_contains_selected_claim_store():
    from app.app import make_app
    from dash import dcc

    app = make_app()
    layout = app.layout

    def find_store(component, store_id):
        if isinstance(component, dcc.Store) and component.id == store_id:
            return True
        children = getattr(component, "children", None)
        if children is None:
            return False
        if isinstance(children, list):
            return any(find_store(c, store_id) for c in children)
        return find_store(children, store_id)

    assert find_store(layout, "selected-claim"), (
        "Layout must contain dcc.Store(id='selected-claim')"
    )


def test_import_app_layout():
    """Verify that 'import app.layout' works under pytest."""
    import app.layout  # noqa: F401


# ---------------------------------------------------------------------------
# Controls from registry
# ---------------------------------------------------------------------------


def test_perturbation_controls_one_per_registry_entry():
    """get_perturbation_controls() must produce one control per registered perturbation."""
    from app.layout import get_perturbation_controls

    registry = available_perturbations()
    control_div = get_perturbation_controls()

    # Render to string representation and check each type_name appears
    div_str = str(control_div)
    for type_name in registry:
        assert type_name in div_str, (
            f"Perturbation type_name '{type_name}' not found in controls output"
        )


def test_perturbation_controls_all_three_type_names():
    """All three registered type_names must appear in the controls."""
    from app.layout import get_perturbation_controls

    registry = available_perturbations()
    assert len(registry) == 3, f"Expected 3 perturbation types, got {len(registry)}"

    expected = {"text_content_absence", "knowledge_absence", "image_content_absence"}
    assert set(registry.keys()) == expected

    control_div = get_perturbation_controls()
    div_str = str(control_div)
    for type_name in expected:
        assert type_name in div_str, f"'{type_name}' missing from perturbation controls"


# ---------------------------------------------------------------------------
# Invariant #12: highlight_stylesheet purity
# ---------------------------------------------------------------------------


def test_highlight_stylesheet_returns_new_list():
    from app.panels.subgraph import BASE_STYLESHEET, highlight_stylesheet

    saved = list(BASE_STYLESHEET)
    edge_ids = ["Q11111-P50-Q22222"]
    node_ids = ["Q11111", "Q22222"]

    result = highlight_stylesheet(BASE_STYLESHEET, edge_ids, node_ids)

    # Result is a NEW list
    assert result is not BASE_STYLESHEET
    # Result is longer (appended selectors)
    assert len(result) > len(BASE_STYLESHEET)
    # BASE_STYLESHEET is UNCHANGED
    assert BASE_STYLESHEET == saved, "highlight_stylesheet mutated BASE_STYLESHEET"


def test_highlight_stylesheet_appended_selectors_target_given_ids():
    from app.panels.subgraph import BASE_STYLESHEET, highlight_stylesheet

    edge_ids = ["Q11111-P50-Q22222", "Q33333-P921-Q22222"]
    node_ids = ["Q11111", "Q22222", "Q33333"]

    result = highlight_stylesheet(BASE_STYLESHEET, edge_ids, node_ids)
    result_str = str(result)

    for eid in edge_ids:
        assert eid in result_str, f"Edge id '{eid}' not in appended selectors"
    for nid in node_ids:
        assert nid in result_str, f"Node id '{nid}' not in appended selectors"


def test_highlight_stylesheet_base_unchanged_after_call():
    from app.panels.subgraph import BASE_STYLESHEET, highlight_stylesheet

    # Save deep copy of content
    saved_content = [dict(entry) for entry in BASE_STYLESHEET]
    saved_len = len(BASE_STYLESHEET)

    highlight_stylesheet(BASE_STYLESHEET, ["e1"], ["n1"])

    assert len(BASE_STYLESHEET) == saved_len, "BASE_STYLESHEET length changed"
    for i, entry in enumerate(BASE_STYLESHEET):
        assert entry == saved_content[i], f"BASE_STYLESHEET[{i}] was mutated"


# ---------------------------------------------------------------------------
# CB2 mapping: support_elements_for_claim
# ---------------------------------------------------------------------------


def test_support_elements_reasoned_supportable():
    """REASONED_SUPPORTABLE claim yields correct path edge_ids and node_ids."""
    from app.callbacks import support_elements_for_claim

    run = mock_grounding_run()
    rs_claim = next(c for c in run.claims if c.status == ClaimStatus.REASONED_SUPPORTABLE)

    edge_ids, node_ids = support_elements_for_claim(run, rs_claim.claim_id)

    # edge_ids must match <subj>-<prop>-<obj> for each PathEdge
    expected_edge_ids = [
        f"{pe.subject_id}-{pe.property_id}-{pe.object_id}"
        for pe in rs_claim.grounding_path.edges
    ]
    assert sorted(edge_ids) == sorted(expected_edge_ids), (
        f"Expected edge ids {expected_edge_ids}, got {edge_ids}"
    )

    # node_ids must match grounding_path.node_ids
    expected_node_ids = rs_claim.grounding_path.node_ids
    assert sorted(node_ids) == sorted(expected_node_ids), (
        f"Expected node ids {expected_node_ids}, got {node_ids}"
    )


def test_support_elements_unknown_claim_returns_empty():
    from app.callbacks import support_elements_for_claim

    run = mock_grounding_run()
    edge_ids, node_ids = support_elements_for_claim(run, "nonexistent-claim-id")
    assert edge_ids == []
    assert node_ids == []


def test_support_elements_none_claim_returns_empty():
    from app.callbacks import support_elements_for_claim

    run = mock_grounding_run()
    edge_ids, node_ids = support_elements_for_claim(run, None)
    assert edge_ids == []
    assert node_ids == []


def test_cb2_no_selection_returns_base_stylesheet():
    """When no claim is selected, CB2 logic returns BASE_STYLESHEET unchanged."""
    from app.callbacks import support_elements_for_claim
    from app.panels.subgraph import BASE_STYLESHEET, highlight_stylesheet

    run = mock_grounding_run()
    edge_ids, node_ids = support_elements_for_claim(run, None)
    assert edge_ids == [] and node_ids == []

    # When both are empty, highlight_stylesheet still returns a list but
    # no extra selectors for nonexistent ids; the important thing is BASE_STYLESHEET
    # is not mutated. We test the CB2 shortcut path separately.
    result = highlight_stylesheet(BASE_STYLESHEET, edge_ids, node_ids)
    # Still a new list (even with empty ids, function returns base + [])
    assert result is not BASE_STYLESHEET


# ---------------------------------------------------------------------------
# CB1 logic: select_claim_from_trigger
# ---------------------------------------------------------------------------


def test_select_claim_from_trigger_returns_claim_id():
    from app.callbacks import select_claim_from_trigger

    # Simulate a pattern-matching trigger: triggered_id contains claim_id
    triggered = [{"prop_id": '{"claim_id":"c3","type":"claim-btn"}.n_clicks', "value": 1}]
    result = select_claim_from_trigger(triggered)
    assert result == "c3", f"Expected 'c3', got {result!r}"


def test_select_claim_from_trigger_returns_none_when_empty():
    from app.callbacks import select_claim_from_trigger

    result = select_claim_from_trigger([])
    assert result is None


def test_select_claim_from_trigger_returns_none_when_no_clicks():
    from app.callbacks import select_claim_from_trigger

    triggered = [{"prop_id": '{"claim_id":"c1","type":"claim-btn"}.n_clicks', "value": 0}]
    result = select_claim_from_trigger(triggered)
    # value=0 means no actual click — should return None
    assert result is None


# ---------------------------------------------------------------------------
# No circular callbacks: selected-claim store is Output of exactly one callback
# ---------------------------------------------------------------------------


def test_no_circular_callbacks_store_written_by_one_callback():
    """selected-claim Store must be Output of exactly one callback (CB1)."""
    from app.app import make_app

    app = make_app()
    store_output_key = "selected-claim.data"
    # Check how many callbacks write to selected-claim.data
    output_callbacks = [
        k for k, v in app.callback_map.items() if k == store_output_key
    ]
    assert len(output_callbacks) == 1, (
        f"selected-claim.data should be Output of exactly 1 callback, "
        f"found {len(output_callbacks)}: {output_callbacks}"
    )


def test_no_circular_callbacks_store_not_written_by_cb2_cb3():
    """CB2 (stylesheet) and CB3 (analytics) must not write to selected-claim.data."""
    from app.app import make_app

    app = make_app()
    # selected-claim.data must appear as Output at most once
    output_count = sum(
        1 for k in app.callback_map if "selected-claim" in k and "data" in k
    )
    assert output_count <= 1, (
        f"selected-claim.data appears as Output in {output_count} callbacks (expected 1)"
    )


# ---------------------------------------------------------------------------
# Naming: no bare 'reasoned' without '-supportable' in STATUS labels
# ---------------------------------------------------------------------------


def test_status_colors_uses_reasoned_supportable_key():
    """STATUS_COLORS dict must use 'reasoned-supportable', never bare 'reasoned'."""
    from app.panels.answer import STATUS_COLORS

    assert "reasoned-supportable" in STATUS_COLORS, (
        "STATUS_COLORS must have 'reasoned-supportable' key"
    )
    assert "reasoned" not in STATUS_COLORS or STATUS_COLORS.get("reasoned") is None, (
        "STATUS_COLORS must not have a bare 'reasoned' key"
    )


def test_answer_panel_no_bare_reasoned_label():
    """Answer panel HTML must not display bare 'reasoned' as a label."""
    from app.panels.answer import get_answer_panel

    run = mock_grounding_run()
    panel = get_answer_panel(run)
    panel_str = str(panel)

    # The word 'reasoned-supportable' is allowed; bare 'reasoned' alone is not
    # Strip all occurrences of 'reasoned-supportable' and check none remain
    stripped = panel_str.replace("reasoned-supportable", "")
    # After removing 'reasoned-supportable', the bare word 'reasoned' must not appear
    assert "reasoned" not in stripped, (
        "Answer panel contains bare 'reasoned' label — must use 'reasoned-supportable'"
    )


def test_analytics_panel_no_bare_reasoned_label():
    """Analytics panel must use 'reasoned-supportable', never bare 'reasoned'."""
    from app.panels.analytics import get_analytics_panel

    run = mock_grounding_run()
    panel = get_analytics_panel(run)
    panel_str = str(panel)

    stripped = panel_str.replace("reasoned-supportable", "")
    assert "reasoned" not in stripped, (
        "Analytics panel contains bare 'reasoned' — must use 'reasoned-supportable'"
    )


# ---------------------------------------------------------------------------
# Additional structural smoke tests
# ---------------------------------------------------------------------------


def test_get_answer_panel_returns_component():
    from app.panels.answer import get_answer_panel
    from dash import html

    run = mock_grounding_run()
    panel = get_answer_panel(run)
    assert isinstance(panel, html.Div)


def test_get_subgraph_panel_returns_component():
    from app.panels.subgraph import get_subgraph_panel
    from dash import html

    elements = mock_subgraph_elements()
    panel = get_subgraph_panel(elements)
    assert isinstance(panel, html.Div)


def test_get_analytics_panel_returns_component():
    from app.panels.analytics import get_analytics_panel
    from dash import html

    run = mock_grounding_run()
    panel = get_analytics_panel(run)
    assert isinstance(panel, html.Div)


def test_subgraph_panel_contains_cytoscape():
    from app.panels.subgraph import get_subgraph_panel

    elements = mock_subgraph_elements()
    panel = get_subgraph_panel(elements)
    panel_str = str(panel)
    # Cytoscape component must be present (check repr or children)
    assert "subgraph" in panel_str, "Cytoscape id='subgraph' not found in subgraph panel"


def test_analytics_detail_for_claim():
    from app.callbacks import analytics_detail_for_claim

    run = mock_grounding_run()
    # For a known claim
    result = analytics_detail_for_claim(run, "c3")
    assert result is not None

    # For None
    result_none = analytics_detail_for_claim(run, None)
    assert result_none is not None  # should return some placeholder, not crash


def test_store_data_is_json_serializable():
    """claim_id string (what gets stored) is JSON-serializable."""
    run = mock_grounding_run()
    for claim in run.claims:
        # The store would hold the claim_id string
        json.dumps(claim.claim_id)  # must not raise
