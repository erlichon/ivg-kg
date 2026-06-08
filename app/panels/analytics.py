"""Analytics panel — P0 skeleton with status-distribution bar chart.

Full analytics (modality coverage, repair history, per-entity breakdown) are
deferred to UI4 / P2.  Here we deliver:
  - A plotly bar chart of run.status_counts() (claim-status distribution).
  - A fabrication-rate readout.
  - A placeholder area updated by CB3 to show selected-claim detail.

STATUS_COLORS mirrors the answer panel colour map so charts are consistent.
"""
from __future__ import annotations

import plotly.graph_objects as go
from dash import dcc, html

from app.panels.answer import STATUS_COLORS, STATUS_LABELS
from ivg_kg.schema import ClaimStatus, GroundingRun

# ---------------------------------------------------------------------------
# Pure figure builder
# ---------------------------------------------------------------------------


def make_status_distribution_figure(status_counts: dict[str, int]) -> go.Figure:
    """Build a bar chart of claim-status counts.

    Uses STATUS_COLORS for consistent colour coding.
    Input keys are ClaimStatus string values (e.g. "retrieved").
    """
    statuses = list(status_counts.keys())
    counts = [status_counts[s] for s in statuses]
    colors = [STATUS_COLORS.get(s, "#555555") for s in statuses]
    labels = [STATUS_LABELS.get(s, s) for s in statuses]

    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=counts,
                marker_color=colors,
                text=counts,
                textposition="auto",
            )
        ]
    )
    fig.update_layout(
        title={"text": "Claim Status Distribution", "font": {"color": "#cdd6f4"}},
        plot_bgcolor="#1e1e2e",
        paper_bgcolor="#181825",
        font={"color": "#cdd6f4"},
        xaxis={"title": "Status", "color": "#a6adc8", "gridcolor": "#313244"},
        yaxis={
            "title": "Count",
            "color": "#a6adc8",
            "gridcolor": "#313244",
            "tickformat": "d",
        },
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Panel factory
# ---------------------------------------------------------------------------


def get_analytics_panel(run: GroundingRun) -> html.Div:
    """Render the analytics panel skeleton.

    Contains:
    - Status-distribution bar chart (from run.status_counts()).
    - Fabrication-rate readout.
    - An area (id="analytics-detail") updated by CB3 for claim-level detail.
    """
    fab_rate = run.fabrication_rate()
    status_counts = run.status_counts()
    fig = make_status_distribution_figure(status_counts)

    fab_color = "#c62828" if fab_rate > 0.3 else "#e65100" if fab_rate > 0.1 else "#2e7d32"

    return html.Div(
        [
            html.H3(
                "Analytics",
                style={"color": "#cdd6f4", "marginBottom": "12px", "fontSize": "1.1em"},
            ),
            html.Div(
                [
                    html.Span("Fabrication rate: ", style={"color": "#a6adc8"}),
                    html.Span(
                        f"{fab_rate:.1%}",
                        style={"color": fab_color, "fontWeight": "bold", "fontSize": "1.1em"},
                    ),
                    html.Span(
                        f"  ({status_counts.get(ClaimStatus.FABRICATED, 0)} / "
                        f"{len(run.claims)} claims)",
                        style={"color": "#585b70", "fontSize": "0.85em"},
                    ),
                ],
                style={"marginBottom": "16px"},
            ),
            dcc.Graph(
                id="status-distribution-chart",
                figure=fig,
                config={"displayModeBar": False},
                style={"height": "260px"},
            ),
            html.Div(
                id="analytics-detail",
                style={
                    "marginTop": "12px",
                    "color": "#a6adc8",
                    "fontSize": "0.9em",
                    "minHeight": "40px",
                    "borderTop": "1px solid #313244",
                    "paddingTop": "12px",
                },
                children="Click a claim in the Answer panel to see details here.",
            ),
        ],
        id="analytics-panel",
        style={
            "padding": "16px",
            "background": "#181825",
            "borderRadius": "6px",
            "height": "100%",
            "overflowY": "auto",
        },
    )
