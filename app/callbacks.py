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
  G  ⚙ toggle             -> settings-panel.style
  H  preset / add-remove  -> present-evidence.data   (graph editor)
  I  preset / inject      -> injected-evidence.data
  J  present + injected   -> repair-body.children     (re-verify after each edit)
"""
from __future__ import annotations

import dash
from dash import ALL, Input, Output, State
from dash.exceptions import PreventUpdate

from app.charts.status_dist import make_status_distribution_figure
from app.panels.analytics import fab_rate_readout, per_claim_sections
from app.panels.answer import render_claim_list
from app.panels.repair import render_repair_body
from app.panels.subgraph import (
    BASE_STYLESHEET,
    ego_elements,
    highlight_stylesheet,
    node_detail_content,
    node_labels_from_elements,
)
from ivg_kg.mock.fixtures import ALL_EVIDENCE_IDS, CONDITION_PRESENT
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
        diag = diagnostics_by_n.get(int(n)) if n is not None else None
        if not selected or diag is None:
            return per_claim_sections([])
        by_key = {c.claim_key: c for c in diag.claim_diagnostics}
        # one card per selected claim, in selection order (all closed by default)
        diags = [
            by_key[id_to_key[cid]]
            for cid in selected
            if cid in id_to_key and id_to_key.get(cid) in by_key
        ]
        return per_claim_sections(diags)

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
        fig = make_status_distribution_figure(
            diag.status_distribution, diag.n_generations, diag.status_distribution_std
        )
        return fig, fab_rate_readout(diag)

    # ---- F: node tap / reset -> zoom elements + entity-detail (#7/#8) -------
    @app.callback(
        Output("subgraph", "elements"),
        Output("subgraph", "layout"),
        Output("entity-detail", "children"),
        Input("subgraph", "tapNodeData"),
        Input("reset-view", "n_clicks"),
        prevent_initial_call=True,
    )
    def node_zoom_and_detail(node_data, _reset):  # noqa: ANN001
        # A fresh layout dict each call forces cytoscape to re-run cose + re-fit
        # the viewport (otherwise the pan/zoom can stay stuck after an elements
        # swap, which made "reset view" look like it did nothing).
        layout = {"name": "cose", "animate": False, "fit": True, "padding": 24}
        trigger_id = dash.ctx.triggered_id
        if trigger_id == "reset-view":
            return overview_elements, layout, node_detail_content(None)
        # tapNodeData fired
        if not node_data:
            raise PreventUpdate
        return (
            ego_elements(overview_elements, node_data["id"]),
            layout,
            node_detail_content(node_data),
        )

    # ---- G: ⚙ toggle the generation-settings panel (#6) ---------------------
    @app.callback(
        Output("settings-panel", "style"),
        Input("settings-toggle", "n_clicks"),
        State("settings-panel", "style"),
        prevent_initial_call=True,
    )
    def toggle_settings(n, style):  # noqa: ANN001
        style = dict(style or {})
        style["display"] = "block" if (n or 0) % 2 == 1 else "none"
        return style

    # ---- H: graph editor — preset or add/remove -> present-evidence ---------
    @app.callback(
        Output("present-evidence", "data"),
        Input({"type": "evidence-preset", "cond": ALL}, "n_clicks"),
        Input({"type": "evidence-toggle", "item": ALL}, "n_clicks"),
        State("present-evidence", "data"),
        prevent_initial_call=True,
    )
    def update_present(_presets, _toggles, current):  # noqa: ANN001
        trig = dash.ctx.triggered_id
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        if isinstance(trig, dict) and trig.get("type") == "evidence-preset":
            return list(CONDITION_PRESENT.get(trig.get("cond"), ALL_EVIDENCE_IDS))
        if isinstance(trig, dict) and trig.get("type") == "evidence-toggle":
            present = list(current if current is not None else ALL_EVIDENCE_IDS)
            item = trig.get("item")
            if item in present:
                present.remove(item)  # remove = ablate
            else:
                present.append(item)  # add back = restore
            return present
        raise PreventUpdate

    # ---- I: preset (reset) or inject -> injected-evidence -------------------
    @app.callback(
        Output("injected-evidence", "data"),
        Input({"type": "evidence-preset", "cond": ALL}, "n_clicks"),
        Input({"type": "evidence-inject", "item": ALL}, "n_clicks"),
        State("injected-evidence", "data"),
        prevent_initial_call=True,
    )
    def update_injected(_presets, _inject, current):  # noqa: ANN001
        trig = dash.ctx.triggered_id
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        if isinstance(trig, dict) and trig.get("type") == "evidence-preset":
            return []  # presets reset injections
        if isinstance(trig, dict) and trig.get("type") == "evidence-inject":
            inj = list(current or [])
            item = trig.get("item")
            if item not in inj:
                inj.append(item)
            return inj
        raise PreventUpdate

    # ---- J: present + injected -> re-verified editor body (#2/#3) -----------
    @app.callback(
        Output("repair-body", "children"),
        Input("present-evidence", "data"),
        Input("injected-evidence", "data"),
    )
    def render_repair(present, injected):  # noqa: ANN001
        return render_repair_body(present, injected or [])
