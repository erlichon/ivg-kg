"""Full-answer claim-status distribution column chart (SPEC-text §4.5 #5).

Hue encodes status (the one fixed 3-grade palette). Bars start at y=0.
"""
from __future__ import annotations

import plotly.graph_objects as go

from app import theme


def make_status_distribution_figure(distribution: dict[str, float], n: int) -> go.Figure:
    """Column chart of the claim-status distribution over the N FULL draws.

    Parameters
    ----------
    distribution:
        ClaimStatus value -> fraction (the three grades), as in
        AnswerDiagnostics.status_distribution.
    n:
        Number of generations the distribution is computed over (for the title).
    """
    statuses = theme.STATUS_ORDER
    labels = [theme.status_label(s) for s in statuses]
    values = [round(100 * distribution.get(s, 0.0), 1) for s in statuses]
    colors = [theme.status_color(s) for s in statuses]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{v:.0f}%" for v in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": f"Claim-status distribution · N={n} draws", "font": {"size": 13}},
        plot_bgcolor=theme.PANEL_ALT,
        paper_bgcolor=theme.PANEL,
        font={"color": theme.TEXT, "family": theme.MONO, "size": 11},
        xaxis={"color": theme.MUTED, "showgrid": False},
        yaxis={
            "title": "% of claims",
            "color": theme.MUTED,
            "gridcolor": theme.BORDER,
            "range": [0, 100],  # bars start at y=0
            "rangemode": "tozero",
        },
        margin={"l": 48, "r": 16, "t": 40, "b": 30},
        showlegend=False,
        height=230,
    )
    return fig
