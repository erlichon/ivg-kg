"""Callbacks for the IVG-KG mockup (SPEC-text §4.5 / §4.6).

Selection lives in ``selected-claims``; the editable KG lives in ``present-triples``
+ ``injected``. Each store / output is written by exactly one callback; everything
else reads — no circular callbacks.

  A  claim row/span click        -> selected-claims              (toggle; sole writer)
  B  selected+filter+graph       -> claim-list.children          (re-verified statuses)
  C  selected+mode+N+condition   -> subgraph.stylesheet          (brush OR support-freq)
  E  mode+N+condition            -> analytics-body.children      (single- / multi-run)
  G  ⚙ toggle                    -> settings-panel.style
  Elem present+injected+tap/reset-> subgraph.elements + layout   (edits + zoom)
  Det  tapNode / tapEdge         -> entity-detail.children        (inspect / remove control)
  H  remove-edge / re-add        -> present-triples               (edit-the-KG)
  I  inject / remove-inject      -> injected                      (edit-the-KG)
  L  suggest                     -> inject form fields            (model suggestion)
  J  present + injected          -> repair-body.children          (re-add list + leverage)
  K  present + injected          -> answer-spans.children         (recolour the answer)
"""
from __future__ import annotations

import dash
from dash import ALL, Input, Output, State
from dash.exceptions import PreventUpdate

from app.panels.analytics import multi_run_body, single_run_body
from app.panels.answer import answer_span_children, render_claim_list
from app.panels.repair import render_repair_body
from app.panels.subgraph import (
    BASE_STYLESHEET,
    edge_detail_content,
    ego_elements,
    highlight_stylesheet,
    node_detail_content,
    node_labels_from_elements,
    support_frequency_stylesheet,
)
from ivg_kg.mock.fixtures import (
    ALL_TRIPLE_IDS,
    SUGGESTED_INJECT,
    editable_elements,
    mock_answer_diagnostics,
    mock_condition_diagnostics,
    mock_single_run_summary,
    statuses_for_graph,
)
from ivg_kg.schema import Condition, GroundingRun

_LAYOUT = {"name": "cose", "animate": False, "fit": True, "padding": 24}
_VALID_CONDITIONS = {c.value for c in Condition}


def register_callbacks(app: dash.Dash, run: GroundingRun, elements: list[dict]) -> None:
    """Register all callbacks (closures over the mock data)."""
    claims_by_id = {c.claim_id: c for c in run.claims}
    node_labels = node_labels_from_elements(elements)
    base_triple_ids = set(ALL_TRIPLE_IDS)

    def _condition(value: str | None) -> Condition:
        return Condition(value) if value in _VALID_CONDITIONS else Condition.FULL

    # ---- A: claim click -> selected-claims (toggle; sole writer) ------------
    @app.callback(
        Output("selected-claims", "data"),
        Input({"type": "claim-row", "claim_id": ALL}, "n_clicks"),
        Input({"type": "claim-span", "claim_id": ALL}, "n_clicks"),
        State("selected-claims", "data"),
        prevent_initial_call=True,
    )
    def toggle_selection(_rows, _spans, current):  # noqa: ANN001
        trig = dash.ctx.triggered_id
        if not trig or not isinstance(trig, dict):
            raise PreventUpdate
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        cid = trig.get("claim_id")
        if cid not in claims_by_id:
            raise PreventUpdate
        selected = list(current or [])
        selected.remove(cid) if cid in selected else selected.append(cid)
        return selected

    # ---- B: selected + filter + graph edits -> claim list -------------------
    @app.callback(
        Output("claim-list", "children"),
        Input("selected-claims", "data"),
        Input("status-filter", "value"),
        Input("present-triples", "data"),
        Input("injected", "data"),
    )
    def render_list(selected, grades, present, injected):  # noqa: ANN001
        override = statuses_for_graph(present, injected or [])
        return render_claim_list(run, selected or [], grades or [], status_override=override)

    # ---- C: selected + mode + N + condition -> subgraph stylesheet ----------
    # single-run -> brush selected claims' support paths (append-only highlight);
    # multi-run  -> size nodes/edges by support-frequency for the chosen condition.
    @app.callback(
        Output("subgraph", "stylesheet"),
        Input("selected-claims", "data"),
        Input("analytics-mode", "value"),
        Input("n-selector", "value"),
        Input("withhold-condition", "value"),
    )
    def style_subgraph(selected, mode, n, condition):  # noqa: ANN001
        if mode == "multi":
            diag = mock_answer_diagnostics(int(n or 20), _condition(condition))
            return support_frequency_stylesheet(BASE_STYLESHEET, diag.support_frequency)
        selected = selected or []
        if not selected:
            return BASE_STYLESHEET
        ordered = [claims_by_id[cid] for cid in selected if cid in claims_by_id]
        return highlight_stylesheet(BASE_STYLESHEET, ordered, node_labels)

    # ---- E: mode + N + condition -> analytics body --------------------------
    @app.callback(
        Output("analytics-body", "children"),
        Input("analytics-mode", "value"),
        Input("n-selector", "value"),
        Input("withhold-condition", "value"),
    )
    def render_analytics_body(mode, n, condition):  # noqa: ANN001
        if mode == "multi":
            n = int(n or 20)
            cond = _condition(condition)
            condition_diags = mock_condition_diagnostics(n)
            diag = condition_diags[cond.value]
            return multi_run_body(diag, condition_diags, cond.value, n)
        return single_run_body(mock_single_run_summary())

    # ---- F: mode -> show the multi-run controls only in multi-run mode ------
    @app.callback(
        Output("multirun-controls", "style"),
        Input("analytics-mode", "value"),
    )
    def toggle_multirun_controls(mode):  # noqa: ANN001
        return {"marginBottom": "8px", "display": "block" if mode == "multi" else "none"}

    # ---- Elem: graph edits + node zoom -> subgraph elements -----------------
    @app.callback(
        Output("subgraph", "elements"),
        Output("subgraph", "layout"),
        Input("present-triples", "data"),
        Input("injected", "data"),
        Input("subgraph", "tapNodeData"),
        Input("reset-view", "n_clicks"),
        prevent_initial_call=True,
    )
    def update_elements(present, injected, node_data, _reset):  # noqa: ANN001
        full = editable_elements(present, injected or [])
        prop = dash.ctx.triggered[0]["prop_id"] if dash.ctx.triggered else ""
        if prop.endswith("tapNodeData") and node_data:
            return ego_elements(full, node_data["id"]), _LAYOUT  # zoom to node
        return full, _LAYOUT  # full edited graph (edit / reset / deselect)

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

    # ---- H: remove-edge / re-add -> present-triples (edit-the-KG) -----------
    @app.callback(
        Output("present-triples", "data"),
        Input({"type": "remove-edge", "triple": ALL}, "n_clicks"),
        Input({"type": "readd", "item": ALL}, "n_clicks"),
        State("present-triples", "data"),
        prevent_initial_call=True,
    )
    def update_present(_rm, _add, current):  # noqa: ANN001
        trig = dash.ctx.triggered_id
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        present = list(current if current is not None else ALL_TRIPLE_IDS)
        if isinstance(trig, dict) and trig.get("type") == "remove-edge":
            t = trig.get("triple")
            if t in present:
                present.remove(t)
        elif isinstance(trig, dict) and trig.get("type") == "readd":
            t = trig.get("item")
            if t not in present:
                present.append(t)
        return present

    # ---- I: inject (editable) / remove-inject -> injected -------------------
    @app.callback(
        Output("injected", "data"),
        Input("inject-apply", "n_clicks"),
        Input({"type": "remove-inject", "idx": ALL}, "n_clicks"),
        State("inject-subject", "value"),
        State("inject-relation", "value"),
        State("inject-value", "value"),
        State("injected", "data"),
        prevent_initial_call=True,
    )
    def update_injected(_apply, _rm, subject, relation, value, current):  # noqa: ANN001
        trig = dash.ctx.triggered_id
        if not dash.ctx.triggered or not dash.ctx.triggered[0].get("value"):
            raise PreventUpdate
        inj = list(current or [])
        if trig == "inject-apply":
            if not (relation and value):
                raise PreventUpdate
            inj.append({"subject": subject, "relation": relation, "value": value})
            return inj
        if isinstance(trig, dict) and trig.get("type") == "remove-inject":
            i = trig.get("idx")
            if isinstance(i, int) and 0 <= i < len(inj):
                inj.pop(i)
            return inj
        raise PreventUpdate

    # ---- L: suggest -> pre-fill the (editable) inject form ------------------
    @app.callback(
        Output("inject-subject", "value"),
        Output("inject-relation", "value"),
        Output("inject-value", "value"),
        Input("inject-suggest", "n_clicks"),
        prevent_initial_call=True,
    )
    def suggest(_n):  # noqa: ANN001
        return SUGGESTED_INJECT["subject"], SUGGESTED_INJECT["relation"], SUGGESTED_INJECT["value"]

    # ---- J: graph -> re-add list + grounded + repair-leverage ---------------
    @app.callback(
        Output("repair-body", "children"),
        Input("present-triples", "data"),
        Input("injected", "data"),
    )
    def render_repair(present, injected):  # noqa: ANN001
        return render_repair_body(present, injected or [])

    # ---- K: graph -> recolour the answer text spans -------------------------
    @app.callback(
        Output("answer-spans", "children"),
        Input("present-triples", "data"),
        Input("injected", "data"),
    )
    def recolour_answer(present, injected):  # noqa: ANN001
        return answer_span_children(run, statuses_for_graph(present, injected or []))
