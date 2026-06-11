"""Support-frequency ranked bar (SPEC-text §4.5 / §4.8).

For each KG item (entity or triplet), the fraction of the N runs in which it was
USED to ground a claim -- OBSERVATIONAL importance ("how often grounding routes
through this item"), explicitly NOT causal leverage. The subgraph also encodes
this as node-size / edge-weight; this is the companion ranked list.
"""
from __future__ import annotations

import plotly.graph_objects as go

from app import theme


def make_support_frequency_figure(
    support_frequency: dict[str, float],
    labels: dict[str, str],
    top_k: int = 8,
) -> go.Figure:
    """Horizontal ranked bar of the top-k support-frequency KG items."""
    items = sorted(support_frequency.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    items.reverse()  # plotly draws bottom-up; we want the largest on top
    names = [labels.get(k, k) for k, _ in items]
    values = [round(100 * v, 0) for _, v in items]
    # triplets (edges) vs entities (nodes) get different hues so the two read apart
    colors = [theme.KG_SELECT if "|" in k else "#7d8590" for k, _ in items]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.0f}%" for v in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}: used in %{x:.0f}% of runs<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": "Support-frequency · % of N runs the item grounded a claim "
                       "(observational, not causal)", "font": {"size": 10}},
        plot_bgcolor=theme.PANEL_ALT,
        paper_bgcolor=theme.PANEL,
        font={"color": theme.TEXT, "family": theme.MONO, "size": 9},
        xaxis={"range": [0, 100], "color": theme.MUTED, "gridcolor": theme.BORDER,
               "title": "% of runs"},
        yaxis={"color": theme.TEXT, "automargin": True},
        margin={"l": 8, "r": 24, "t": 36, "b": 28},
        showlegend=False,
        height=240,
    )
    return fig
