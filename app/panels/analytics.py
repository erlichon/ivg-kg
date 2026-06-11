"""Analytics panel (Knowledge pillar) — SPEC-text §4.5 / §4.8.

Two MODES via a toggle (the verifier is a deterministic instrument; all across-run
spread is GENERATION variance):

- **SINGLE-RUN** — one generated answer. Status counts + percentages over that run's
  claims, with **NO SE** (a single sample). The per-claim support-path highlight
  ("what this verdict rests on") and per-claim status live in the Answer + Subgraph
  panels (select a claim to brush its path).
- **MULTI-RUN** — re-run the query N times (N selectable, default 20). Shows
  **(a)** the status distribution as **mean +/- SE** of the per-run answer-level
  fraction, and **(b)** **support-frequency** (observational, NOT causal) over KG
  items, encoded as node-size / edge-weight on the subgraph plus a ranked list. The
  **withhold-from-context** selector {full, content-withheld, knowledge-withheld}
  shows the distribution SHIFT; withholding never changes the grading reference.
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from app.charts.status_dist import (
    make_single_run_figure,
    make_status_distribution_figure,
)
from app.charts.support_frequency import make_support_frequency_figure
from ivg_kg.mock.fixtures import N_CHOICES, kg_item_label
from ivg_kg.schema import (
    AnswerDiagnostics,
    ClaimStatus,
    Condition,
    GroundingRun,
    SingleRunStatusSummary,
)

DEFAULT_N = 20

# Back-compat re-export.
STATUS_COLORS = theme.STATUS_COLORS

# Withhold-from-context conditions (the multi-run distribution-shift selector).
_WITHHOLD_OPTIONS = [
    {"label": " full ", "value": Condition.FULL.value},
    {"label": " content-withheld ", "value": Condition.CONTENT_ABSENT.value},
    {"label": " knowledge-withheld ", "value": Condition.KNOWLEDGE_ABSENT.value},
]
_WITHHOLD_LABEL = {o["value"]: o["label"].strip() for o in _WITHHOLD_OPTIONS}

_INFO_SINGLE = (
    "Single-run mode — ONE generated answer.\n"
    "Bars are the status percentages over this answer's claims (counts shown too). "
    "It is a SINGLE sample, so there is NO SE/error bar. Select a claim (left) to "
    "highlight its support path on the subgraph -- 'what this verdict rests on'."
)
_INFO_MULTI = (
    "Multi-run mode — re-run the query N times (default 20).\n"
    "For each run we take the answer-level fraction of claims in each grade, then "
    "report the MEAN and SE across the N runs. The error bar is the SE of a "
    "PROPORTION, sqrt(p(1-p)/N) -- NOT the ~0.5 Bernoulli per-draw std. The verifier "
    "is deterministic; the spread is GENERATION variance. N=20 is a FLOOR."
)
_INFO_SUPPORTFREQ = (
    "Support-frequency (observational importance, NOT causal).\n"
    "For each KG item (entity or triplet), the fraction of the N runs in which it "
    "was USED to ground a claim -- 'used' = it lies on the support path of >= 1 "
    "grounded claim that run. It says 'how often grounding routes through this "
    "item', NOT 'how much it causes grounding'. Encoded as node-size / edge-weight "
    "on the subgraph; the ranked list is the companion."
)
_INFO_WITHHOLD = (
    "Withhold-from-context (RQ2 absence experiment) — layer 1 of 2.\n"
    "Hide a description (content) or a triplet (structure) from the GENERATION "
    "context only. The item STAYS in the grading reference; grading is always "
    "against the FULL reference. So withholding shifts the multi-run status "
    "distribution toward fabrication WITHOUT relabelling true claims. Its result is "
    "the SHIFT across {full, content-withheld, knowledge-withheld}. "
    "It NEVER changes the grading reference (contrast: edit-the-KG, below, does)."
)
_INFO_SMALLN = (
    "Small-N honesty: error bars are the SE of a proportion, sqrt(p(1-p)/N), not the "
    "~0.5 Bernoulli per-draw std. N=20 is a FLOOR, not a target -- small differences "
    "between bars/conditions are within noise."
)


def small_n_caveat() -> html.Div:
    """Prominent small-N honesty banner (SPEC-text §4.8 statistical-honesty)."""
    return html.Div(
        [
            html.Span("⚠ small-N ", style={"color": theme.STATUS_COLORS[
                ClaimStatus.REASONED_SUPPORTABLE.value], "fontWeight": "bold",
                "fontSize": "0.72em"}),
            html.Span(
                "N=20 is a FLOOR, not a target. Error bars are the SE of a proportion "
                "(sqrt(p(1-p)/N)), not the ~0.5 per-draw std; small differences are "
                "within noise. All spread is generation variance (the verifier is "
                "deterministic).",
                style={"color": theme.MUTED, "fontSize": "0.7em", "lineHeight": "1.4"},
            ),
            theme.info_icon(_INFO_SMALLN),
        ],
        style={"background": theme.PANEL_ALT, "border": f"1px dashed {theme.BORDER}",
               "borderRadius": "4px", "padding": "6px 9px", "marginBottom": "8px"},
    )


# ---------------------------------------------------------------------------
# Mode bodies (rendered into #analytics-body by the mode/N/condition callback)
# ---------------------------------------------------------------------------
def single_run_body(summary: SingleRunStatusSummary) -> list:
    """SINGLE-RUN: status counts + percentages, NO SE (one sample)."""
    total = sum(summary.status_counts.values())
    return [
        html.Div(
            ["one generated answer · status % over its claims · NO SE (single sample)",
             theme.info_icon(_INFO_SINGLE)],
            style={"color": theme.FAINT, "fontSize": "0.72em", "marginBottom": "4px"},
        ),
        dcc.Graph(figure=make_single_run_figure(summary), config={"displayModeBar": False}),
        html.Div(
            f"{total} claims this run. Select a claim (left) to highlight its "
            "support path on the subgraph -- 'what this verdict rests on'.",
            style={"color": theme.MUTED, "fontSize": "0.72em", "marginTop": "2px"},
        ),
    ]


def _shift_row(condition_diags: dict[str, AnswerDiagnostics], selected: str) -> html.Div:
    """Compact fabrication-rate-by-condition readout — the withhold-from-context shift."""
    rows: list = []
    fab = ClaimStatus.FABRICATED.value
    for cond_value, label in _WITHHOLD_LABEL.items():
        d = condition_diags.get(cond_value)
        if d is None:
            continue
        m = d.status_distribution.get(fab)
        mean = m.mean if m else 0.0
        se = m.se if m else 0.0
        is_sel = cond_value == selected
        rows.append(
            html.Div(
                [
                    html.Span(("▶ " if is_sel else "  ") + label,
                              style={"color": theme.TEXT if is_sel else theme.MUTED,
                                     "fontWeight": "bold" if is_sel else "normal",
                                     "fontSize": "0.72em"}),
                    html.Span(f"  fab {mean:.0%} ± {se:.0%}",
                              style={"color": theme.STATUS_COLORS[fab], "fontSize": "0.72em"}),
                ],
                style={"marginBottom": "2px"},
            )
        )
    return html.Div(
        [
            html.Div(["distribution SHIFT across conditions (fabrication rate)",
                      theme.info_icon(_INFO_WITHHOLD)],
                     style={"color": theme.FAINT, "fontSize": "0.7em", "marginBottom": "3px"}),
            *rows,
            html.Div("withhold-from-context hides evidence from the GENERATOR only; "
                     "grading stays against the FULL reference (it never changes the "
                     "reference).",
                     style={"color": theme.FAINT, "fontSize": "0.66em",
                            "fontStyle": "italic", "marginTop": "3px"}),
        ],
        style={"marginTop": "8px", "marginBottom": "6px"},
    )


def _support_frequency_list(support_frequency: dict[str, float], labels: dict[str, str]) -> html.Div:
    """Clickable ranked list of KG items; clicking highlights the item on the subgraph."""
    items = sorted(support_frequency.items(), key=lambda kv: kv[1], reverse=True)
    rows = [
        html.Button(
            [
                html.Span("◆ " if "|" in item else "● ",
                          style={"color": theme.KG_SELECT if "|" in item else theme.MUTED}),
                html.Span(labels.get(item, item), style={"color": theme.TEXT}),
                html.Span(f"  {freq:.0%}", style={"color": theme.MUTED}),
            ],
            id={"type": "kg-item", "item": item}, n_clicks=0,
            style={"display": "block", "width": "100%", "textAlign": "left",
                   "background": theme.PANEL_ALT, "border": f"1px solid {theme.BORDER}",
                   "borderRadius": "4px", "padding": "3px 8px", "marginBottom": "3px",
                   "cursor": "pointer", "fontFamily": theme.MONO, "fontSize": "0.72em"},
        )
        for item, freq in items
    ]
    return html.Div(rows)


def multi_run_body(
    diag: AnswerDiagnostics,
    condition_diags: dict[str, AnswerDiagnostics],
    condition: str,
    n: int,
) -> list:
    """MULTI-RUN: mean+/-SE distribution (selected condition) + support-frequency + shift."""
    labels = {item: kg_item_label(item) for item in diag.support_frequency}
    return [
        small_n_caveat(),
        html.Div(
            [f"status distribution · N={n} runs · {_WITHHOLD_LABEL.get(condition, condition)} "
             "· mean ±SE", theme.info_icon(_INFO_MULTI)],
            style={"color": theme.FAINT, "fontSize": "0.7em", "marginBottom": "2px"},
        ),
        dcc.Graph(
            figure=make_status_distribution_figure(diag.status_distribution, diag.n_runs),
            config={"displayModeBar": False},
        ),
        _shift_row(condition_diags, condition),
        html.Div(
            ["support-frequency — click an item to highlight it on the subgraph; "
             "node-size / edge-weight encode it too (observational, not causal)",
             theme.info_icon(_INFO_SUPPORTFREQ)],
            style={"color": theme.FAINT, "fontSize": "0.7em", "marginTop": "6px",
                   "marginBottom": "2px"},
        ),
        _support_frequency_list(diag.support_frequency, labels),
        dcc.Graph(
            figure=make_support_frequency_figure(diag.support_frequency, labels),
            config={"displayModeBar": False},
        ),
    ]


def _controls() -> html.Div:
    """Mode toggle + (multi-run) N selector + withhold-from-context selector."""
    radio_label = {"color": theme.TEXT, "marginRight": "12px", "cursor": "pointer"}
    return html.Div(
        [
            html.Div(
                [
                    html.Span("mode  ", style={"color": theme.TEXT, "fontSize": "0.78em"}),
                    dcc.RadioItems(
                        id="analytics-mode",
                        options=[{"label": " single-run ", "value": "single"},
                                 {"label": " multi-run ", "value": "multi"}],
                        value="single", inline=True,
                        labelStyle=radio_label, inputStyle={"marginRight": "4px"},
                        style={"display": "inline-block"},
                    ),
                ],
                style={"marginBottom": "6px"},
            ),
            html.Div(
                [
                    html.Span("multi-run  N ", style={"color": theme.MUTED, "fontSize": "0.74em"}),
                    dcc.RadioItems(
                        id="n-selector",
                        options=[{"label": f" {n} ", "value": n} for n in N_CHOICES],
                        value=DEFAULT_N, inline=True,
                        labelStyle={"color": theme.MUTED, "marginRight": "10px",
                                    "cursor": "pointer"},
                        inputStyle={"marginRight": "4px"},
                        style={"display": "inline-block"},
                    ),
                    html.Span("   withhold ", style={"color": theme.MUTED, "fontSize": "0.74em"}),
                    dcc.RadioItems(
                        id="withhold-condition",
                        options=_WITHHOLD_OPTIONS,
                        value=Condition.FULL.value, inline=True,
                        labelStyle={"color": theme.MUTED, "marginRight": "8px",
                                    "cursor": "pointer", "fontSize": "0.92em"},
                        inputStyle={"marginRight": "4px"},
                        style={"display": "inline-block"},
                    ),
                ],
                # only shown in multi-run mode (toggled by the mode callback); the
                # controls stay in the DOM so they remain valid callback inputs.
                id="multirun-controls",
                style={"marginBottom": "8px", "display": "none"},
            ),
        ],
    )


def get_analytics_panel(run: GroundingRun, single_summary: SingleRunStatusSummary) -> html.Div:
    """Compose the Analytics panel; the body starts in single-run mode."""
    return html.Div(
        [
            html.Div("ANALYTICS", style={"color": theme.MUTED, "fontSize": "0.75em",
                                         "letterSpacing": "0.1em", "marginBottom": "10px"}),
            _controls(),
            html.Div(single_run_body(single_summary), id="analytics-body"),
        ],
        id="analytics-panel",
        style=theme.panel_style(height="100%", overflowY="auto"),
    )
