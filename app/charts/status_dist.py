"""Claim-status distribution column charts (SPEC-text §4.5 / §4.8).

Two figures for the two analytics modes:

- ``make_single_run_figure`` — ONE generated answer: bars are the status
  percentages over that run's claims, with **NO error bars** (a single sample).
- ``make_status_distribution_figure`` — N runs: bars are the **mean** per-run
  answer-level fraction per status, with error bars = the **SE of the proportion**
  ``sqrt(p(1-p)/N)`` (NOT the ~0.5 Bernoulli per-draw std). N=20 is a floor.

Hue encodes status (the one fixed 3-grade palette). Bars start at y=0.
"""
from __future__ import annotations

import plotly.graph_objects as go

from app import theme
from ivg_kg.diagnostics import proportion_se  # single definition; re-exported here
from ivg_kg.schema import SingleRunStatusSummary, StatusMeanSE

__all__ = ["make_single_run_figure", "make_status_distribution_figure", "proportion_se"]


def _layout(fig: go.Figure, title: str) -> None:
    fig.update_layout(
        title={"text": title, "font": {"size": 11}},
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


def make_single_run_figure(summary: SingleRunStatusSummary) -> go.Figure:
    """Single-run status distribution: percentages + counts, NO SE (one sample)."""
    statuses = theme.STATUS_ORDER
    labels = [theme.status_label(s) for s in statuses]
    values = [round(100 * summary.status_percentages.get(s, 0.0), 1) for s in statuses]
    counts = [summary.status_counts.get(s, 0) for s in statuses]
    colors = [theme.status_color(s) for s in statuses]

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[f"{c} ({v:.0f}%)" for c, v in zip(counts, values, strict=False)],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    _layout(fig, "Single run · counts (%) over this answer's claims · no SE (one sample)")
    return fig


def make_status_distribution_figure(
    status_distribution: dict[str, StatusMeanSE],
    n: int,
) -> go.Figure:
    """Multi-run status distribution: mean +/- SE of the per-run fraction over N runs.

    Error bars are the SE of a proportion (sqrt(p(1-p)/N)); N=20 is a floor.
    """
    statuses = theme.STATUS_ORDER
    labels = [theme.status_label(s) for s in statuses]
    means = [status_distribution.get(s) for s in statuses]
    values = [round(100 * (m.mean if m else 0.0), 1) for m in means]
    errors = [round(100 * (m.se if m else 0.0), 1) for m in means]
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
            hovertemplate="%{x}: %{y:.1f}% (SE +/-%{error_y.array:.1f})<extra></extra>",
        )
    )
    _layout(fig, f"N={n} runs · mean +/- SE of the per-run % · SE = sqrt(p(1-p)/N)")
    return fig
