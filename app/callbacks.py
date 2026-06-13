"""Callbacks for the IVG-KG mockup (SPEC-text §4.4 / §4.5 / §4.6).

Selection lives in ``selected-claims`` (claims) and ``selected-kg-items`` (KG items
in multi-run); the scoped KG edits live in a single ``kg-edits`` log. Each output is
written by exactly one callback; everything else reads — no circular callbacks.

  A  claim row/span click        -> selected-claims              (toggle; sole writer)
  KGS kg-item click (multi-run)  -> selected-kg-items            (toggle; sole writer)
  B  selected+filter+edits       -> claim-list.children          (re-verified statuses)
  C  selected+mode+N+cond+kgsel+edits -> subgraph.stylesheet     (brush / support+select)
  E  mode+N+condition            -> analytics-body.children      (single- / multi-run)
  F  mode                        -> multirun-controls.style
  Elem edits+tap/reset           -> subgraph.elements + layout    (edits + zoom)
  Det  tapNode / tapEdge         -> entity-detail.children        (inspect / remove control)
  G  ⚙ toggle                    -> settings-panel.style
  EDIT remove/add/content/undo   -> kg-edits                     (sole writer; scoped)
  L  suggest                     -> add-triplet form fields
  J  edits                       -> repair-body.children          (edits log + leverage)
  K  edits                       -> answer-spans.children          (recolour the answer)
"""
from __future__ import annotations

import dash
from dash import ALL, Input, Output, State
from dash.exceptions import PreventUpdate

import app.run_source as _run_source
from app.panels.analytics import multi_run_body, single_run_body
from app.panels.answer import answer_span_children, render_claim_list
from app.panels.repair import render_repair_body
from app.panels.subgraph import (
    BASE_STYLESHEET,
    edge_detail_content,
    ego_elements,
    highlight_stylesheet,
    kg_item_highlight_stylesheet,
    node_detail_content,
    node_labels_from_elements,
    support_frequency_stylesheet,
)
from ivg_kg.mock.fixtures import (
    ALL_TRIPLE_IDS,
    SUGGESTED_INJECT,
    editable_elements,
    effective_claims,
    statuses_for_graph,
)
from ivg_kg.schema import GroundingRun

_LAYOUT = {"name": "cose", "animate": False, "fit": True, "padding": 24}


def register_callbacks(app: dash.Dash, run: GroundingRun, elements: list[dict]) -> None:
    """Register all callbacks (closures over the mock data)."""
    claims_by_id = {c.claim_id: c for c in run.claims}
    node_labels = node_labels_from_elements(elements)
    base_triple_ids = set(ALL_TRIPLE_IDS)

    # ---- A: claim click -> selected-claims (toggle; sole writer) ------------
    @app.callback(
        Output("selected-claims", "data"),
        Input({"type": "claim-row", "claim_id": ALL}, "n_clicks"),
        Input({"type": "claim-span", "claim_id": ALL}, "n_clicks"),
        Input("reset-view", "n_clicks"),
        State("selected-claims", "data"),
        prevent_initial_call=True,
    )
    def toggle_selection(_rows, _spans, _reset, current):  # noqa: ANN001
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        trig = dash.ctx.triggered_id
        if trig == "reset-view":
            return []
        if not isinstance(trig, dict):
            raise PreventUpdate
        cid = trig.get("claim_id")
        if cid not in claims_by_id:
            raise PreventUpdate
        selected = list(current or [])
        selected.remove(cid) if cid in selected else selected.append(cid)
        return selected

    # ---- KGS: kg-item click -> selected-kg-items (toggle; sole writer) ------
    @app.callback(
        Output("selected-kg-items", "data"),
        Input({"type": "kg-item", "item": ALL}, "n_clicks"),
        Input("reset-view", "n_clicks"),
        State("selected-kg-items", "data"),
        prevent_initial_call=True,
    )
    def toggle_kg_item(_n, _reset, current):  # noqa: ANN001
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        trig = dash.ctx.triggered_id
        if trig == "reset-view":
            return []
        if not isinstance(trig, dict):
            raise PreventUpdate
        item = trig.get("item")
        sel = list(current or [])
        sel.remove(item) if item in sel else sel.append(item)
        return sel

    # ---- B: selected + filter + edits -> claim list -------------------------
    @app.callback(
        Output("claim-list", "children"),
        Input("selected-claims", "data"),
        Input("status-filter", "value"),
        Input("kg-edits", "data"),
    )
    def render_list(selected, grades, edits):  # noqa: ANN001
        override = statuses_for_graph(edits)
        return render_claim_list(run, selected or [], grades or [], status_override=override)

    # ---- C: selected/mode/N/kg-selection/edits -> subgraph stylesheet -------
    @app.callback(
        Output("subgraph", "stylesheet"),
        Input("selected-claims", "data"),
        Input("analytics-mode", "value"),
        Input("n-selector", "value"),
        Input("selected-kg-items", "data"),
        Input("kg-edits", "data"),
    )
    def style_subgraph(selected, mode, n, kg_selected, edits):  # noqa: ANN001
        if mode == "multi":
            diag = _run_source.get_answer_diagnostics(int(n or 20))
            sized = support_frequency_stylesheet(BASE_STYLESHEET, diag.support_frequency)
            return kg_item_highlight_stylesheet(sized, kg_selected or [])
        selected = selected or []
        if not selected:
            return BASE_STYLESHEET
        # effective claims reflect the current edits: the brush hue matches the
        # re-verified status and a repaired c3 highlights the full date triple.
        eff = {c.claim_id: c for c in effective_claims(edits)}
        ordered = [eff[cid] for cid in selected if cid in eff]
        return highlight_stylesheet(BASE_STYLESHEET, ordered, node_labels)

    # ---- E: mode + N -> analytics body --------------------------------------
    @app.callback(
        Output("analytics-body", "children"),
        Input("analytics-mode", "value"),
        Input("n-selector", "value"),
    )
    def render_analytics_body(mode, n):  # noqa: ANN001
        if mode == "multi":
            n = int(n or 20)
            return multi_run_body(_run_source.get_answer_diagnostics(n), n)
        return single_run_body(_run_source.get_single_run_summary())

    # ---- F: mode -> show the multi-run controls only in multi-run mode ------
    @app.callback(
        Output("multirun-controls", "style"),
        Input("analytics-mode", "value"),
    )
    def toggle_multirun_controls(mode):  # noqa: ANN001
        return {"marginBottom": "8px", "display": "block" if mode == "multi" else "none"}

    # ---- Elem: edits + node zoom -> subgraph elements -----------------------
    @app.callback(
        Output("subgraph", "elements"),
        Output("subgraph", "layout"),
        Input("kg-edits", "data"),
        Input("subgraph", "tapNodeData"),
        Input("reset-view", "n_clicks"),
        prevent_initial_call=True,
    )
    def update_elements(edits, node_data, _reset):  # noqa: ANN001
        prop = dash.ctx.triggered[0]["prop_id"] if dash.ctx.triggered else ""
        if prop.startswith("reset-view"):
            return editable_elements(None), _LAYOUT  # reset clears edits -> base overview
        full = editable_elements(edits)
        if prop.endswith("tapNodeData") and node_data:
            return ego_elements(full, node_data["id"]), _LAYOUT  # zoom to node
        return full, _LAYOUT  # full edited graph (edit / deselect)

    # ---- Det: tap node / edge -> entity-or-edge detail ----------------------
    @app.callback(
        Output("entity-detail", "children"),
        Input("subgraph", "tapNodeData"),
        Input("subgraph", "tapEdgeData"),
        prevent_initial_call=True,
    )
    def show_detail(node_data, edge_data):  # noqa: ANN001
        prop = dash.ctx.triggered[0]["prop_id"] if dash.ctx.triggered else ""
        if prop.endswith("tapEdgeData") and edge_data:
            return edge_detail_content(edge_data, base_triple_ids)
        if prop.endswith("tapNodeData") and node_data:
            return node_detail_content(node_data)
        return node_detail_content(None)

    # ---- G: ⚙ toggle the generation-settings panel --------------------------
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

    # ---- EDIT: two operations -> kg-edits (sole writer) ---------------------
    # Scope is fixed by the operation (no toggle): REMOVE -> "gen" (generation
    # context only; reference never ablated); ADD -> "both" (to the KG).
    @app.callback(
        Output("kg-edits", "data"),
        Input({"type": "remove-edge", "triple": ALL}, "n_clicks"),
        Input({"type": "readd", "item": ALL}, "n_clicks"),
        Input("inject-apply", "n_clicks"),
        Input("entity-apply", "n_clicks"),
        Input({"type": "remove-content", "entity": ALL}, "n_clicks"),
        Input({"type": "remove-edit", "idx": ALL}, "n_clicks"),
        Input("reset-view", "n_clicks"),
        State("inject-subject", "value"),
        State("inject-relation", "value"),
        State("inject-value", "value"),
        State("entity-label", "value"),
        State("entity-desc", "value"),
        State("kg-edits", "data"),
        prevent_initial_call=True,
    )
    def apply_edit(  # noqa: ANN001, PLR0913
        _rm, _add, _inj, _ent, _rc, _re, _reset, subject, relation, value, label, desc, current,
    ):
        trig = dash.ctx.triggered_id
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        if trig == "reset-view":
            return []  # reset clears all KG edits
        edits = list(current or [])
        if trig == "inject-apply":  # ADD a triplet -> to the KG (both)
            if not (relation and value):
                raise PreventUpdate
            edits.append({"op": "add", "kind": "triplet", "scope": "both",
                          "subject": subject, "relation": relation, "value": value})
        elif trig == "entity-apply":  # ADD an entity -> to the KG (both)
            if not label:
                raise PreventUpdate
            edits.append({"op": "add", "kind": "entity", "scope": "both",
                          "id": f"new:{label}", "label": label, "description": desc or None})
        elif isinstance(trig, dict):
            kind = trig.get("type")
            if kind == "remove-edge":  # REMOVE a triplet -> from generation context (gen)
                edits.append({"op": "remove", "kind": "triplet", "scope": "gen",
                              "id": trig.get("triple")})
            elif kind == "readd":  # restore a withheld triplet to generation
                edits.append({"op": "add", "kind": "triplet", "scope": "gen",
                              "id": trig.get("item")})
            elif kind == "remove-content":  # REMOVE a description -> from generation context (gen)
                edits.append({"op": "remove", "kind": "content", "scope": "gen",
                              "id": trig.get("entity")})
            elif kind == "remove-edit":
                i = trig.get("idx")
                if isinstance(i, int) and 0 <= i < len(edits):
                    edits.pop(i)
        return edits

    # ---- L: suggest -> pre-fill the (editable) add-triplet form -------------
    @app.callback(
        Output("inject-subject", "value"),
        Output("inject-relation", "value"),
        Output("inject-value", "value"),
        Input("inject-suggest", "n_clicks"),
        prevent_initial_call=True,
    )
    def suggest(_n):  # noqa: ANN001
        return SUGGESTED_INJECT["subject"], SUGGESTED_INJECT["relation"], SUGGESTED_INJECT["value"]

    # ---- J: edits -> edits log + leverage readout ---------------------------
    @app.callback(
        Output("repair-body", "children"),
        Input("kg-edits", "data"),
    )
    def render_repair(edits):  # noqa: ANN001
        return render_repair_body(edits)

    # ---- K: edits -> recolour the answer text spans -------------------------
    @app.callback(
        Output("answer-spans", "children"),
        Input("kg-edits", "data"),
    )
    def recolour_answer(edits):  # noqa: ANN001
        return answer_span_children(run, statuses_for_graph(edits))
