"""Full-answer claim-status distribution column chart (SPEC-text §4.5 #5 / §4.8).

Hue encodes status (the one fixed 3-grade palette). Bars start at y=0. Error bars
are the **standard error of the proportion** SE = sqrt(p(1-p)/N) over the N
GENERATION draws — NOT a per-draw std. All spread is generation variance (the
verifier is deterministic).
"""
from __future__ import annotations

import math

import plotly.graph_objects as go

from app import theme


def proportion_se(p: float, n: int) -> float:
    """Standard error of a proportion p over N draws: sqrt(p(1-p)/N) (§4.8)."""
    if n <= 0:
        return 0.0
    p = min(max(p, 0.0), 1.0)
    return math.sqrt(p * (1.0 - p) / n)


def make_status_distribution_figure(
    distribution: dict[str, float],
    n: int,
) -> go.Figure:
    """Column chart of the claim-status distribution over the N FULL generation draws.

    Bars are the fraction of claims in each grade; error bars are the SE of the
    proportion (sqrt(p(1-p)/N)) — the uncertainty on that fraction at N draws,
    not the Bernoulli per-draw std (SPEC-text §4.8).

    Parameters
    ----------
    distribution:
        ClaimStatus value -> fraction of claims in that grade (the three grades).
    n:
        Number of generation draws the distribution is computed over.
    """
    statuses = theme.STATUS_ORDER
    labels = [theme.status_label(s) for s in statuses]
    props = [distribution.get(s, 0.0) for s in statuses]
    values = [round(100 * p, 1) for p in props]
    errors = [round(100 * proportion_se(p, n), 1) for p in props]
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
            hovertemplate="%{x}: %{y:.1f}% (SE ±%{error_y.array:.1f})<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": f"Claim-status distribution · N={n} generation draws (FULL) · ±SE",
               "font": {"size": 11}},
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
