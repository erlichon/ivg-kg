"""Answer panel — claim list colour-coded by status, each clickable.

Each claim is rendered as an html.Button with a pattern-matching id
{"type": "claim-btn", "claim_id": <id>} so that CB1 can identify which claim
was clicked via dash.callback_context.triggered.

STATUS_COLORS maps ClaimStatus string values to CSS colour strings.
The key "reasoned-supportable" is used verbatim (Invariant #5 — NEVER "reasoned").
"""
from __future__ import annotations

from dash import html

from ivg_kg.schema import ClaimStatus, GroundingRun

# Deterministic colour map keyed by ClaimStatus string values (Invariant #5).
STATUS_COLORS: dict[str, str] = {
    ClaimStatus.RETRIEVED: "#2e7d32",           # green
    ClaimStatus.REASONED_SUPPORTABLE: "#e65100",  # amber/orange
    ClaimStatus.FABRICATED: "#c62828",           # red
}

# Human-readable labels (Invariant #5: always use the hyphenated form).
STATUS_LABELS: dict[str, str] = {
    ClaimStatus.RETRIEVED: "retrieved",
    ClaimStatus.REASONED_SUPPORTABLE: "reasoned-supportable",
    ClaimStatus.FABRICATED: "fabricated",
}


def _claim_button(claim_id: str, text: str, status: str) -> html.Button:
    """Render a single claim as a clickable button colour-coded by status."""
    color = STATUS_COLORS.get(status, "#555555")
    label = STATUS_LABELS.get(status, status)
    return html.Button(
        children=[
            html.Span(
                f"[{label}]",
                style={
                    "fontWeight": "bold",
                    "color": color,
                    "marginRight": "8px",
                    "fontSize": "0.85em",
                    "textTransform": "uppercase",
                    "letterSpacing": "0.04em",
                },
            ),
            html.Span(text),
        ],
        id={"type": "claim-btn", "claim_id": claim_id},
        n_clicks=0,
        style={
            "display": "block",
            "width": "100%",
            "textAlign": "left",
            "background": "#1e1e2e",
            "border": f"1px solid {color}",
            "borderLeft": f"4px solid {color}",
            "color": "#cdd6f4",
            "padding": "10px 14px",
            "marginBottom": "8px",
            "cursor": "pointer",
            "borderRadius": "4px",
            "fontSize": "0.95em",
            "lineHeight": "1.5",
            "transition": "background 0.15s",
        },
    )


def _legend() -> html.Div:
    """Render a compact status legend."""
    items = [
        html.Span(
            STATUS_LABELS[status],
            style={
                "color": color,
                "fontWeight": "bold",
                "marginRight": "16px",
                "fontSize": "0.85em",
                "textTransform": "uppercase",
            },
        )
        for status, color in STATUS_COLORS.items()
    ]
    return html.Div(
        [html.Span("Legend: ")] + items,
        style={"marginBottom": "12px", "color": "#a6adc8", "fontSize": "0.85em"},
    )


def get_answer_panel(run: GroundingRun) -> html.Div:
    """Render the answer panel with all claims colour-coded and clickable.

    Each claim is rendered as an html.Button with a pattern-matching id so
    CB1 can determine which claim was clicked.  Labels use the full hyphenated
    status strings (Invariant #5).
    """
    claim_buttons = [
        _claim_button(claim.claim_id, claim.text, claim.status)
        for claim in run.claims
    ]

    return html.Div(
        [
            html.H3(
                "Answer Claims",
                style={"color": "#cdd6f4", "marginBottom": "12px", "fontSize": "1.1em"},
            ),
            html.Div(
                run.question,
                style={
                    "color": "#a6adc8",
                    "fontStyle": "italic",
                    "marginBottom": "16px",
                    "fontSize": "0.9em",
                    "borderLeft": "3px solid #313244",
                    "paddingLeft": "10px",
                },
            ),
            _legend(),
            html.Div(claim_buttons, id="claim-list"),
        ],
        id="answer-panel",
        style={
            "padding": "16px",
            "background": "#181825",
            "borderRadius": "6px",
            "height": "100%",
            "overflowY": "auto",
        },
    )
