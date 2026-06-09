"""Callbacks for the IVG-KG mockup — the eight interactions (SPEC-text §4.5).

Selection state lives in one store, ``selected-claims`` (an ordered list of
claim_ids; order = badge order). It is written by exactly one callback (claim
row / span clicks); every other callback only READS it — no circular callbacks.

Callbacks:
  A  claim row/span click  -> selected-claims.data            (toggle; sole writer)
  B  selected + status-filter -> claim-list.children          (#1 filter, #2 multi-select)
  C  selected             -> subgraph.stylesheet              (#2 brush; append-only)
  D  selected + N         -> per-claim-analytics.children     (#4/#6 per-claim view)
  E  N                    -> status-dist-graph.figure + fab-rate.children  (#5)
  F  node tap / reset     -> subgraph.elements + entity-detail.children     (#7/#8 zoom)
"""
from __future__ import annotations

import dash
from dash import ALL, Input, Output, State
from dash.exceptions import PreventUpdate

from app.charts.status_dist import make_status_distribution_figure
from app.panels.analytics import fab_rate_readout, per_claim_view
from app.panels.answer import render_claim_list
from app.panels.subgraph import (
    BASE_STYLESHEET,
    ego_elements,
    highlight_stylesheet,
    node_detail_content,
    node_labels_from_elements,
)
from ivg_kg.schema import AnswerDiagnostics, GroundingRun


def register_callbacks(
    app: dash.Dash,
    run: GroundingRun,
    elements: list[dict],
    diagnostics_by_n: dict[int, AnswerDiagnostics],
) -> None:
    """Register the eight-interaction callbacks (closures over the mock data)."""
    claims_by_id = {c.claim_id: c for c in run.claims}
    id_to_key = {c.claim_id: c.claim_key for c in run.claims}
    node_labels = node_labels_from_elements(elements)
    overview_elements = list(elements)

    # ---- A: claim click -> selected-claims (toggle; the only writer) --------
    @app.callback(
        Output("selected-claims", "data"),
        Input({"type": "claim-row", "claim_id": ALL}, "n_clicks"),
        Input({"type": "claim-span", "claim_id": ALL}, "n_clicks"),
        State("selected-claims", "data"),
        prevent_initial_call=True,
    )
    def toggle_selection(_rows, _spans, current):  # noqa: ANN001
        trig = dash.ctx.triggered
        trigger_id = dash.ctx.triggered_id
        if not trigger_id or not isinstance(trigger_id, dict):
            raise PreventUpdate
        # ignore spurious fires from dynamic re-render (n_clicks falsy)
        if not trig or not trig[0].get("value"):
            raise PreventUpdate
        cid = trigger_id.get("claim_id")
        if cid not in claims_by_id:
            raise PreventUpdate
        selected = list(current or [])
        if cid in selected:
            selected.remove(cid)
        else:
            selected.append(cid)
        return selected

    # ---- B: selected + filter -> claim list (filter + outline/badge) --------
    @app.callback(
        Output("claim-list", "children"),
        Input("selected-claims", "data"),
        Input("status-filter", "value"),
    )
    def render_list(selected, grades):  # noqa: ANN001
        return render_claim_list(run, selected or [], grades or [])

    # ---- C: selected -> subgraph stylesheet (append-only highlight) ---------
    @app.callback(
        Output("subgraph", "stylesheet"),
        Input("selected-claims", "data"),
        State("selected-claims", "modified_timestamp"),
    )
    def brush_subgraph(selected, _ts):  # noqa: ANN001
        selected = selected or []
        if not selected:
            return BASE_STYLESHEET
        ordered = [claims_by_id[cid] for cid in selected if cid in claims_by_id]
        return highlight_stylesheet(BASE_STYLESHEET, ordered, node_labels)

    # ---- D: selected + N -> per-claim analytics -----------------------------
    @app.callback(
        Output("per-claim-analytics", "children"),
        Input("selected-claims", "data"),
        Input("n-selector", "value"),
    )
    def render_per_claim(selected, n):  # noqa: ANN001
        selected = selected or []
        if not selected:
            return per_claim_view(None)
        focused = selected[-1]
        key = id_to_key.get(focused)
        diag = diagnostics_by_n.get(int(n)) if n is not None else None
        if diag is None or key is None:
            return per_claim_view(None)
        cd = next((c for c in diag.claim_diagnostics if c.claim_key == key), None)
        return per_claim_view(cd)

    # ---- E: N -> full-answer distribution + fabrication rate ----------------
    @app.callback(
        Output("status-dist-graph", "figure"),
        Output("fab-rate", "children"),
        Input("n-selector", "value"),
    )
    def update_full_answer(n):  # noqa: ANN001
        diag = diagnostics_by_n.get(int(n)) if n is not None else None
        if diag is None:
            raise PreventUpdate
        fig = make_status_distribution_figure(diag.status_distribution, diag.n_generations)
        return fig, fab_rate_readout(diag)

    # ---- F: node tap / reset -> zoom elements + entity-detail (#7/#8) -------
    @app.callback(
        Output("subgraph", "elements"),
        Output("entity-detail", "children"),
        Input("subgraph", "tapNodeData"),
        Input("reset-view", "n_clicks"),
        prevent_initial_call=True,
    )
    def node_zoom_and_detail(node_data, _reset):  # noqa: ANN001
        trigger_id = dash.ctx.triggered_id
        if trigger_id == "reset-view":
            return overview_elements, node_detail_content(None)
        # tapNodeData fired
        if not node_data:
            raise PreventUpdate
        return (
            ego_elements(overview_elements, node_data["id"]),
            node_detail_content(node_data),
        )
