"""Callback registration for the IVG-KG Dash app (SPEC §4.5).

Registers exactly three callbacks:
  CB1 — click → Store("selected-claim"): written ONLY here
  CB2 — Store → Cytoscape stylesheet (highlight support path)
  CB3 — Store → analytics detail area

No circular callbacks: CB2 and CB3 only READ the store, never write it.

Pure helper functions (unit-testable without a running server):
  select_claim_from_trigger(triggered)  -> str | None
  support_elements_for_claim(run, claim_id) -> (edge_ids, node_ids)
  analytics_detail_for_claim(run, claim_id) -> Dash component
"""
from __future__ import annotations

import json

import dash
from dash import ALL, Input, Output, State, html
from dash.exceptions import PreventUpdate

from app.panels.answer import STATUS_COLORS, STATUS_LABELS
from app.panels.subgraph import BASE_STYLESHEET, highlight_stylesheet
from ivg_kg.schema import GroundingRun

# ---------------------------------------------------------------------------
# Pure helpers (unit-testable)
# ---------------------------------------------------------------------------


def select_claim_from_trigger(triggered: list[dict]) -> str | None:
    """Extract the clicked claim_id from a dash ctx.triggered list.

    Returns the claim_id string if exactly one claim button was clicked with
    n_clicks > 0.  Returns None if the list is empty or no click occurred.

    ``triggered`` is a list of dicts with keys "prop_id" and "value",
    matching the structure of dash.ctx.triggered.
    """
    for item in triggered:
        prop_id = item.get("prop_id", "")
        value = item.get("value", 0)
        # Pattern-matching ids are serialised as JSON in prop_id before the dot.
        if ".n_clicks" in prop_id and value:
            # Extract the JSON part before the property name.
            json_part = prop_id.rsplit(".", 1)[0]
            try:
                id_dict = json.loads(json_part)
                if id_dict.get("type") == "claim-btn":
                    return id_dict.get("claim_id")
            except (json.JSONDecodeError, AttributeError):
                continue
    return None


def support_elements_for_claim(
    run: GroundingRun,
    claim_id: str | None,
) -> tuple[list[str], list[str]]:
    """Return (edge_ids, node_ids) for the support path of the given claim.

    Edge ids follow the stored-direction convention: "<subj>-<pid>-<obj>".
    For DIRECT_TRIPLE / TEXT_CONTENT claims that have no grounding_path edges,
    the linked-entity node ids are returned as node_ids (so the nodes are
    highlighted in the subgraph even without path edges).

    Returns ([], []) for unknown/None claim_id.
    """
    if claim_id is None:
        return [], []

    claim = next((c for c in run.claims if c.claim_id == claim_id), None)
    if claim is None:
        return [], []

    path = claim.grounding_path
    if path.edges:
        edge_ids = [
            f"{pe.subject_id}-{pe.property_id}-{pe.object_id}"
            for pe in path.edges
        ]
        node_ids = list(path.node_ids)
        return edge_ids, node_ids

    # No path edges — highlight linked-entity nodes for DIRECT_TRIPLE / TEXT_CONTENT.
    node_ids = [le.id for le in claim.linked_entities]
    return [], node_ids


def analytics_detail_for_claim(
    run: GroundingRun,
    claim_id: str | None,
) -> html.Div:
    """Build a small detail component for the selected claim.

    Returns a placeholder Div when claim_id is None or not found.
    """
    if claim_id is None:
        return html.Div(
            "Click a claim in the Answer panel to see details here.",
            style={"color": "#585b70", "fontStyle": "italic"},
        )

    claim = next((c for c in run.claims if c.claim_id == claim_id), None)
    if claim is None:
        return html.Div(
            f"Claim '{claim_id}' not found.",
            style={"color": "#f38ba8"},
        )

    status_color = STATUS_COLORS.get(claim.status, "#555555")
    status_label = STATUS_LABELS.get(claim.status, claim.status)

    entity_labels = ", ".join(
        f"{le.label} ({le.id})" for le in claim.linked_entities
    ) or "none"

    rows: list[html.Tr] = [
        html.Tr([html.Td("Claim ID", style={"color": "#a6adc8"}), html.Td(claim.claim_id)]),
        html.Tr([
            html.Td("Status", style={"color": "#a6adc8"}),
            html.Td(
                status_label,
                style={"color": status_color, "fontWeight": "bold"},
            ),
        ]),
        html.Tr([
            html.Td("Support source", style={"color": "#a6adc8"}),
            html.Td(claim.support_source),
        ]),
        html.Tr([
            html.Td("Entailment score", style={"color": "#a6adc8"}),
            html.Td(
                f"{claim.entailment_score:.3f}" if claim.entailment_score is not None else "n/a"
            ),
        ]),
        html.Tr([
            html.Td("Spurious path", style={"color": "#a6adc8"}),
            html.Td("yes" if claim.spurious_path else "no"),
        ]),
        html.Tr([
            html.Td("Linked entities", style={"color": "#a6adc8"}),
            html.Td(entity_labels, style={"fontSize": "0.85em"}),
        ]),
    ]

    if claim.grounding_path.edges:
        hop_texts = []
        for pe in claim.grounding_path.edges:
            direction = "→" if pe.traversed_forward else "←"
            hop_texts.append(
                f"{pe.subject_label} {direction}[{pe.property_label}]→ {pe.object_label}"
            )
        rows.append(
            html.Tr([
                html.Td("Path", style={"color": "#a6adc8", "verticalAlign": "top"}),
                html.Td(
                    [html.Div(h, style={"fontSize": "0.8em"}) for h in hop_texts]
                ),
            ])
        )

    return html.Div(
        [
            html.Div(
                f'"{claim.text}"',
                style={
                    "color": "#cdd6f4",
                    "fontStyle": "italic",
                    "marginBottom": "10px",
                    "borderLeft": f"3px solid {status_color}",
                    "paddingLeft": "8px",
                    "fontSize": "0.9em",
                },
            ),
            html.Table(
                rows,
                style={
                    "width": "100%",
                    "fontSize": "0.85em",
                    "borderCollapse": "collapse",
                    "color": "#cdd6f4",
                },
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------


def register_callbacks(app: dash.Dash, run: GroundingRun) -> None:
    """Register CB1, CB2, CB3 on the given Dash app.

    Parameters
    ----------
    app:
        The Dash application instance.
    run:
        The GroundingRun whose claims drive CB2 (path lookup) and CB3 (detail).
        Captured in the callback closures.
    """

    # ------------------------------------------------------------------
    # CB1 — click → Store("selected-claim")
    # Written ONLY here (no circular callbacks).
    # ------------------------------------------------------------------
    @app.callback(
        Output("selected-claim", "data"),
        Input({"type": "claim-btn", "claim_id": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def cb1_click_to_store(n_clicks_list: list[int | None]) -> str | None:
        triggered = dash.ctx.triggered
        claim_id = select_claim_from_trigger(triggered)
        if claim_id is None:
            raise PreventUpdate
        return claim_id

    # ------------------------------------------------------------------
    # CB2 — Store → Cytoscape stylesheet
    # Reads store independently (no circular dependency with CB1/CB3).
    # modified_timestamp used per §4.5 for initial-load read.
    # ------------------------------------------------------------------
    @app.callback(
        Output("subgraph", "stylesheet"),
        Input("selected-claim", "data"),
        State("selected-claim", "modified_timestamp"),
    )
    def cb2_store_to_stylesheet(
        claim_id: str | None,
        _modified_ts: int | None,
    ) -> list[dict]:
        edge_ids, node_ids = support_elements_for_claim(run, claim_id)
        if not edge_ids and not node_ids:
            return BASE_STYLESHEET
        return highlight_stylesheet(BASE_STYLESHEET, edge_ids, node_ids)

    # ------------------------------------------------------------------
    # CB3 — Store → analytics detail
    # Reads store independently (no circular dependency).
    # ------------------------------------------------------------------
    @app.callback(
        Output("analytics-detail", "children"),
        Input("selected-claim", "data"),
    )
    def cb3_store_to_analytics(claim_id: str | None) -> html.Div:
        return analytics_detail_for_claim(run, claim_id)
