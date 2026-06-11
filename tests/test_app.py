"""Light tests for the mockup UI (panels, callbacks, charts).

No running server / no network. Asserts the app builds, the encoding/selection
helpers behave, the stylesheet stays append-only, the callback graph is acyclic
(single store writer), and the figure factories return Plotly figures.
"""
from __future__ import annotations

import copy

import plotly.graph_objects as go
from app.app import make_app
from app.charts.status_dist import (
    make_single_run_figure,
    make_status_distribution_figure,
)
from app.charts.support_frequency import make_support_frequency_figure
from app.layout import get_layout, get_perturbation_controls
from app.panels.answer import render_claim_list
from app.panels.subgraph import (
    BASE_STYLESHEET,
    ego_elements,
    highlight_stylesheet,
    node_detail_content,
    node_labels_from_elements,
)
from dash import html

from ivg_kg.mock import fixtures as fx
from ivg_kg.schema import ClaimStatus


# --- helper ----------------------------------------------------------------
def _find(component, pred):
    """Recursively collect Dash components matching pred."""
    found = []
    if pred(component):
        found.append(component)
    children = getattr(component, "children", None)
    if children is None:
        return found
    if not isinstance(children, (list, tuple)):
        children = [children]
    for ch in children:
        found.extend(_find(ch, pred))
    return found


# --- build -----------------------------------------------------------------
def test_app_and_layout_build():
    app = make_app()
    assert app.layout is not None
    layout = get_layout()
    stores = _find(layout, lambda c: getattr(c, "id", None) == "selected-claims")
    assert stores, "layout must contain dcc.Store(id='selected-claims')"


def test_perturbation_controls_mentions_registry_entries():
    from ivg_kg.perturbation import available_perturbations

    text = str(get_perturbation_controls())
    for type_name in available_perturbations():
        assert type_name.replace("_", " ").title() in text or type_name in text


# --- status filter + multi-select (#1, #2) ---------------------------------
def test_claim_list_filter():
    run = fx.mock_grounding_run()
    only_retrieved = render_claim_list(run, [], [ClaimStatus.RETRIEVED.value])
    assert sum(1 for r in only_retrieved if getattr(r, "id", None)) == 3
    all_rows = render_claim_list(run, [], [])  # empty grades = show all
    assert sum(1 for r in all_rows if getattr(r, "id", None)) == 6


def test_claim_list_selection_keeps_rows():
    run = fx.mock_grounding_run()
    grades = list({c.status.value for c in run.claims})
    rows = render_claim_list(run, ["c1", "c4"], grades)
    assert sum(1 for r in rows if getattr(r, "id", None)) == 6


# --- subgraph highlight: append-only purity (#2, encoding) -----------------
def test_highlight_stylesheet_is_append_only_and_pure():
    run = fx.mock_grounding_run()
    labels = node_labels_from_elements(fx.mock_subgraph_elements())
    base_before = copy.deepcopy(BASE_STYLESHEET)
    c4 = next(c for c in run.claims if c.claim_id == "c4")
    result = highlight_stylesheet(BASE_STYLESHEET, [c4], labels)
    assert result is not BASE_STYLESHEET
    assert len(result) > len(BASE_STYLESHEET)
    assert BASE_STYLESHEET == base_before, "BASE_STYLESHEET must never be mutated"
    sels = " ".join(s["selector"] for s in result)
    assert "Q260763-P19-Q1392501" in sels  # c4's genuine path edge highlighted


# --- entity-detail pane (#7) ------------------------------------------------
def test_node_detail_entity_shows_placeholder_image():
    detail = node_detail_content(
        {"id": "Q1268", "label": "Frédéric Chopin", "kind": "entity", "description": "composer"}
    )
    imgs = _find(detail, lambda c: isinstance(c, html.Img))
    assert len(imgs) == 1
    assert imgs[0].src.endswith("placeholder_entity.svg")


def test_node_detail_literal_has_no_image():
    detail = node_detail_content({"id": "lit:time:x", "label": "15 April 1771", "kind": "literal"})
    assert _find(detail, lambda c: isinstance(c, html.Img)) == []


def test_node_detail_none_is_placeholder():
    assert node_detail_content(None) is not None


# --- ego zoom (#7/#8) -------------------------------------------------------
def test_ego_elements_node_plus_neighbours():
    els = fx.mock_subgraph_elements()
    ego = ego_elements(els, "Q260763")  # Nicolas Chopin
    node_ids = {e["data"]["id"] for e in ego if "source" not in e["data"]}
    assert {"Q260763", "Q1392501", "Q1268"} <= node_ids
    faded = {
        e["data"]["id"]
        for e in ego
        if "source" not in e["data"] and e["data"].get("faded") == "1"
    }
    assert "Q260763" not in faded and faded


# --- callback graph: single store writer, no cycle -------------------------
def test_callback_graph_single_writer():
    app = make_app()

    def count(prop_substr):
        return sum(1 for k in app.callback_map if prop_substr in k)

    assert count("selected-claims.data") == 1  # sole writer (toggle)
    assert count("subgraph.stylesheet") == 1
    assert count("subgraph.elements") == 1
    assert count("claim-list.children") == 1
    assert count("analytics-body.children") == 1  # single writer for the mode body


# --- mode toggle + multi-run controls --------------------------------------
def test_analytics_has_mode_and_n_selector_no_condition_selector():
    s = str(get_layout())
    assert "analytics-mode" in s and "n-selector" in s
    assert "withhold-condition" not in s  # condition selector removed (RQ2 is offline)


def test_mode_bodies_render():
    from app.panels.analytics import multi_run_body, single_run_body

    single = str(single_run_body(fx.mock_single_run_summary())).lower()
    assert "no se" in single and "single sample" in single
    multi = str(multi_run_body(fx.mock_answer_diagnostics(20), 20)).lower()
    assert "support-frequency" in multi and "se" in multi
    assert "shift" not in multi and "withheld" not in multi  # no condition-shift panel


# --- figure factories return Plotly figures --------------------------------
def test_single_run_figure():
    assert isinstance(make_single_run_figure(fx.mock_single_run_summary()), go.Figure)


def test_status_distribution_figure_multirun():
    d = fx.mock_answer_diagnostics(20)
    assert isinstance(
        make_status_distribution_figure(d.status_distribution, d.n_runs), go.Figure
    )


def test_support_frequency_figure():
    d = fx.mock_answer_diagnostics(20)
    labels = {k: fx.kg_item_label(k) for k in d.support_frequency}
    assert isinstance(make_support_frequency_figure(d.support_frequency, labels), go.Figure)


# --- naming: UI shows "Supportable", never a bare "reasoned" ---------------
def test_ui_uses_supportable_not_reasoned():
    from app.panels.analytics import get_analytics_panel
    from app.panels.answer import get_answer_panel

    run = fx.mock_grounding_run()
    summary = fx.mock_single_run_summary()
    rendered = (str(get_answer_panel(run)) + str(get_analytics_panel(run, summary))).lower()
    assert "supportable" in rendered
    # The long enum value may appear in code/option values, but never as a bare
    # "reasoned" UI label (constraint #4): strip the enum value, then assert.
    assert "reasoned" not in rendered.replace("reasoned-supportable", "")


def test_layout_has_slice_and_settings_controls():
    s = str(get_layout())
    assert "slice-selector" in s and "settings-toggle" in s and "settings-panel" in s


def test_settings_toggle_callback_registered():
    app = make_app()
    assert sum(1 for k in app.callback_map if "settings-panel.style" in k) == 1


def test_status_distribution_error_bars_are_proportion_se():
    from app.charts.status_dist import proportion_se

    # SE of a proportion = sqrt(p(1-p)/N), NOT the Bernoulli per-draw std (~0.5).
    assert proportion_se(0.0, 20) == 0.0
    assert proportion_se(1.0, 20) == 0.0
    assert abs(proportion_se(0.5, 20) - (0.25 / 20) ** 0.5) < 1e-12
    d = fx.mock_answer_diagnostics(20)
    fig = make_status_distribution_figure(d.status_distribution, d.n_runs)
    assert isinstance(fig, go.Figure)


def test_graph_editor_panel_and_callbacks():
    from app.panels.repair import get_repair_panel, render_repair_body

    panel = str(get_repair_panel())
    # add-triplet + add-entity forms exist; the per-edit scope toggle is gone
    assert "inject-apply" in panel and "entity-apply" in panel
    assert "edit-scope" not in panel
    # body renders for a REMOVE edit (P22 from generation) -> re-add + repair-leverage
    body = str(render_repair_body([{"op": "remove", "kind": "triplet", "scope": "gen",
                                    "id": "P22"}]))
    assert "re-add" in body and "repair-leverage" in body
    app = make_app()
    # the single KG-edits log + KG-item selection are each written by one callback
    assert sum(1 for k in app.callback_map if "kg-edits.data" in k) == 1
    assert sum(1 for k in app.callback_map if "selected-kg-items.data" in k) == 1
    assert sum(1 for k in app.callback_map if "repair-body.children" in k) == 1
    assert sum(1 for k in app.callback_map if "answer-spans.children" in k) == 1
