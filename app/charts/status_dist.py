"""Full-answer claim-status distribution column chart (SPEC-text §4.5 #5).

Hue encodes status (the one fixed 3-grade palette). Bars start at y=0.
"""
from __future__ import annotations

import plotly.graph_objects as go

from app import theme


def make_status_distribution_figure(
    distribution: dict[str, float],
    n: int,
    std: dict[str, float] | None = None,
) -> go.Figure:
    """Column chart of the claim-status distribution over the N FULL draws.

    Bars are the MEAN per-draw fraction; error bars are +/- 1 std over the N
    draws (SPEC-text §4.5 #5).

    Parameters
    ----------
    distribution:
        ClaimStatus value -> mean per-draw fraction (the three grades).
    n:
        Number of generations the distribution is computed over.
    std:
        ClaimStatus value -> population std of the per-draw fraction (error bars).
    """
    std = std or {}
    statuses = theme.STATUS_ORDER
    labels = [theme.status_label(s) for s in statuses]
    values = [round(100 * distribution.get(s, 0.0), 1) for s in statuses]
    errors = [round(100 * std.get(s, 0.0), 1) for s in statuses]
    colors = [theme.status_color(s) for s in statuses]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            error_y={
                "type": "data",
                "array": errors,
                "visible": True,
                "color": theme.TEXT,
                "thickness": 1.2,
                "width": 5,
            },
            text=[f"{v:.0f}±{e:.0f}%" for v, e in zip(values, errors, strict=False)],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}: %{y:.1f}% ± %{error_y.array:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": f"Claim-status distribution · mean±std over N={n}", "font": {"size": 12}},
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
