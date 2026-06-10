"""Per-claim, per-condition stacked-bar small-multiple (SPEC-text §4.5 #6 / §4.8).

One bar per condition {full, knowledge-absent, content-absent}, stacked by
{Retrieved, Supportable, Fabricated, Absent} fractions over the N draws. Reads
off both absence-leverage and fabrication-induction; the vanish-case is the
grey `Absent` segment. Hue encodes status; bars start at y=0.
"""
from __future__ import annotations

import plotly.graph_objects as go

from app import theme
from ivg_kg.schema import ClaimDiagnostics, Condition

# Conditions shown, in order, with short axis labels.
_CONDITIONS = [
    (Condition.FULL.value, "full"),
    (Condition.KNOWLEDGE_ABSENT.value, "know-abs"),
    (Condition.CONTENT_ABSENT.value, "cont-abs"),
]


def make_condition_breakdown_figure(diag: ClaimDiagnostics) -> go.Figure:
    """Stacked-bar small-multiple for one claim's status mix across conditions."""
    cond_values = [c for c, _ in _CONDITIONS]
    cond_labels = [lbl for _, lbl in _CONDITIONS]

    fig = go.Figure()
    for segment in theme.STACK_ORDER:  # retrieved, supportable, fabricated, absent
        ys = [
            round(100 * diag.status_by_condition.get(cv, {}).get(segment, 0.0), 1)
            for cv in cond_values
        ]
        fig.add_bar(
            name=theme.STACK_LABELS[segment],
            x=cond_labels,
            y=ys,
            marker_color=theme.STACK_COLORS[segment],
            hovertemplate="%{x} · " + theme.STACK_LABELS[segment] + ": %{y:.0f}%<extra></extra>",
        )

    fig.update_layout(
        barmode="stack",
        title={"text": "Status by condition (% over N generation draws)", "font": {"size": 12}},
        plot_bgcolor=theme.PANEL_ALT,
        paper_bgcolor=theme.PANEL,
        font={"color": theme.TEXT, "family": theme.MONO, "size": 10},
        xaxis={"color": theme.MUTED, "showgrid": False},
        yaxis={
            "title": "%",
            "color": theme.MUTED,
            "gridcolor": theme.BORDER,
            "range": [0, 100],
            "rangemode": "tozero",
        },
        legend={
            "orientation": "h",
            "y": -0.22,
            "font": {"size": 9},
            "bgcolor": "rgba(0,0,0,0)",
        },
        margin={"l": 36, "r": 12, "t": 36, "b": 36},
        height=240,
    )
    return fig
