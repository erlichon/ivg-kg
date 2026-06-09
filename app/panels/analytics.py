"""Analytics panel (Knowledge + Trust pillars) — SPEC-text §4.5 / §4.8.

Three surfaces:
  - Full-answer (top): claim-status distribution column chart + fabrication rate
    over N generations, with an N selector (#5).
  - Per-claim (bottom): the per-condition stacked-bar small-multiple + the
    stability scalar + the spurious-path warning chip (#4/#6).
  - Trust strip (persistent): per-modality classifier error (error_rates).
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from app.charts.condition_breakdown import make_condition_breakdown_figure
from app.charts.status_dist import make_status_distribution_figure
from ivg_kg.mock.fixtures import N_CHOICES
from ivg_kg.schema import AnswerDiagnostics, ClaimDiagnostics, ClaimStatus, GroundingRun

DEFAULT_N = 20

# Back-compat re-export.
STATUS_COLORS = theme.STATUS_COLORS


_INFO_FAB = (
    "Fabrication rate = mean over the N generations of "
    "(fabricated claims ÷ claims in that draw). The ± is the standard deviation "
    "of that fraction across the N draws. Higher = more claims unsupported by the "
    "grading reference."
)
_INFO_DIST = (
    "Claim-status distribution: for each of the N full-context generations we "
    "compute the fraction of its claims in each grade, then plot the MEAN (bar) "
    "± 1 standard deviation (error bar) across the N draws."
)
_INFO_TRUST = (
    "Classifier error per modality path — the held-out error rate of each grader "
    "(text-NLI gate; structure path-search), reported so the analytic numbers are "
    "interpretable (the Trust pillar). Lower = more reliable grading. (Mock values.)"
)
_INFO_STABILITY = (
    "Stability = 1 − H(status | FULL) ÷ log K over the N full-context draws: how "
    "reproducible the claim's status is across generations (1.0 = identical every "
    "draw). The companion 'modal status × share' is the legible version."
)
_INFO_ABSENCE = (
    "Absence-leverage per modality = P(grounded | full) − P(grounded | modality "
    "withheld), over the N draws. High ⇒ the claim relied on that evidence."
)
_INFO_INDUCTION = (
    "Fabrication-induction per modality = P(fabricated | modality withheld) − "
    "P(fabricated | full). The absence-induced-hallucination signal: high ⇒ "
    "withholding that evidence makes the model fabricate."
)
_INFO_SPURIOUS = (
    "A Supportable claim whose multi-hop path passed the entailment gate but is "
    "not legitimate support (relation/value illegitimacy, hub/length fragility, or "
    "route non-robustness). Shown only for Supportable claims."
)


def fab_rate_readout(diag: AnswerDiagnostics) -> html.Div:
    """Big fabrication-rate readout (mean ± std) over the N FULL draws."""
    rate = diag.fabrication_rate
    sd = diag.fabrication_rate_std
    color = theme.STATUS_COLORS[ClaimStatus.FABRICATED.value]
    return html.Div(
        [
            html.Span("fabrication rate ", style={"color": theme.MUTED, "fontSize": "0.8em"}),
            html.Span(f"{rate:.0%}", style={"color": color, "fontWeight": "bold",
                                            "fontSize": "1.4em"}),
            html.Span(f" ± {sd:.0%}", style={"color": theme.MUTED, "fontSize": "0.85em"}),
            html.Span(f"  over N={diag.n_generations} draws",
                      style={"color": theme.FAINT, "fontSize": "0.75em"}),
            theme.info_icon(_INFO_FAB),
        ],
        style={"marginBottom": "8px"},
    )


def trust_strip(error_rates: dict[str, float]) -> html.Div:
    """Always-visible per-modality classifier-error strip (Trust pillar)."""
    chips: list = []
    for path, err in error_rates.items():
        chips.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.Span(path, style={"color": theme.MUTED, "fontSize": "0.72em"}),
                            html.Span(f" {err:.0%}", style={"color": theme.TEXT,
                                                            "fontWeight": "bold",
                                                            "fontSize": "0.72em"}),
                        ]
                    ),
                    # mini bar, starts at 0
                    html.Div(
                        html.Div(style={"width": f"{min(100, err * 100 * 4):.0f}%",
                                        "height": "5px", "background": theme.ACCENT,
                                        "borderRadius": "3px"}),
                        style={"background": theme.BORDER, "borderRadius": "3px",
                               "height": "5px", "marginTop": "3px"},
                    ),
                ],
                style={"flex": "1"},
            )
        )
    return html.Div(
        [
            html.Div(["TRUST · classifier error (per modality path)",
                      theme.info_icon(_INFO_TRUST)],
                     style={"color": theme.FAINT, "fontSize": "0.68em",
                            "letterSpacing": "0.08em", "marginBottom": "6px"}),
            html.Div(chips, style={"display": "flex", "gap": "16px"}),
        ],
        id="trust-strip",
        style={
            "marginTop": "12px", "paddingTop": "10px",
            "borderTop": f"1px solid {theme.BORDER}",
        },
    )


def per_claim_view(diag: ClaimDiagnostics | None) -> list:
    """Render the per-claim analytics children (stacked-bar + stability + chip)."""
    if diag is None:
        return [html.Div("Click a claim to see its per-condition diagnostics.",
                         style={"color": theme.FAINT, "fontStyle": "italic",
                                "fontSize": "0.8em"})]

    color = theme.status_color(diag.status.value)
    modal_count = round(diag.modal_fraction * diag.n_full)
    children: list = [
        html.Div(
            [
                html.Span(theme.status_label(diag.status.value).upper(),
                          style={"background": color, "color": theme.BG, "fontWeight": "bold",
                                 "fontSize": "0.62em", "padding": "2px 6px",
                                 "borderRadius": "3px", "marginRight": "8px"}),
                html.Span(diag.text, style={"color": theme.TEXT, "fontSize": "0.85em"}),
            ],
            style={"marginBottom": "8px"},
        ),
        html.Div(
            [
                html.Span("stability ", style={"color": theme.MUTED, "fontSize": "0.78em"}),
                html.Span(f"{diag.stability:.2f}", style={"color": theme.TEXT,
                                                          "fontWeight": "bold"}),
                html.Span(
                    f"   ·   {theme.status_label(diag.modal_status.value)} "
                    f"{modal_count}/{diag.n_full}",
                    style={"color": theme.MUTED, "fontSize": "0.78em"},
                ),
                theme.info_icon(_INFO_STABILITY),
            ],
            style={"marginBottom": "8px"},
        ),
    ]

    if diag.spurious_path:
        children.append(
            html.Div(
                [
                    html.Span(
                        "⚠ Supportable — path suspect",
                        style={"color": theme.BG,
                               "background": theme.STATUS_COLORS[ClaimStatus.FABRICATED.value],
                               "fontWeight": "bold", "fontSize": "0.72em",
                               "padding": "2px 8px", "borderRadius": "3px",
                               "display": "inline-block", "marginBottom": "4px"},
                    ),
                    theme.info_icon(_INFO_SPURIOUS),
                    html.Div(diag.spurious_reason or "spurious supporting path",
                             style={"color": theme.MUTED, "fontSize": "0.74em",
                                    "lineHeight": "1.4"}),
                ],
                style={"marginBottom": "8px"},
            )
        )

    # RQ2 readouts (legible companions to the stacked bar): absence-leverage
    # (drop in P(grounded) when a modality is withheld) and fabrication-induction
    # (rise in P(fabricated)) — the absence-hallucination signal proper.
    def _readout(label: str, data: dict[str, float], info: str) -> html.Div:
        body = "  ".join(f"{m}:{v:+.2f}" for m, v in data.items())
        return html.Div(
            [html.Span(f"{label}  ", style={"color": theme.FAINT, "fontSize": "0.72em"}),
             html.Span(body, style={"color": theme.MUTED, "fontSize": "0.72em",
                                    "fontFamily": theme.MONO}),
             theme.info_icon(info)],
            style={"marginBottom": "4px"},
        )

    if diag.absence_leverage:
        children.append(_readout("absence-leverage ", diag.absence_leverage, _INFO_ABSENCE))
    if diag.fabrication_induction:
        children.append(_readout("fabric-induction", diag.fabrication_induction, _INFO_INDUCTION))

    children.append(
        dcc.Graph(figure=make_condition_breakdown_figure(diag),
                  config={"displayModeBar": False})
    )
    return children


def get_analytics_panel(run: GroundingRun, diagnostics: AnswerDiagnostics) -> html.Div:
    """Compose the Analytics panel with the initial N-default diagnostics."""
    return html.Div(
        [
            html.Div("ANALYTICS", style={"color": theme.MUTED, "fontSize": "0.75em",
                                         "letterSpacing": "0.1em", "marginBottom": "10px"}),
            # --- full-answer ---
            html.Div(
                [
                    html.Span("generations  ", style={"color": theme.MUTED,
                                                      "fontSize": "0.78em"}),
                    dcc.RadioItems(
                        id="n-selector",
                        options=[{"label": f" {n} ", "value": n} for n in N_CHOICES],
                        value=DEFAULT_N,
                        inline=True,
                        style={"display": "inline-block"},
                    ),
                ],
                style={"marginBottom": "8px"},
            ),
            html.Div(fab_rate_readout(diagnostics), id="fab-rate"),
            html.Div(["distribution (mean ± std)", theme.info_icon(_INFO_DIST)],
                     style={"color": theme.FAINT, "fontSize": "0.7em", "marginBottom": "2px"}),
            dcc.Graph(
                id="status-dist-graph",
                figure=make_status_distribution_figure(
                    diagnostics.status_distribution,
                    diagnostics.n_generations,
                    diagnostics.status_distribution_std,
                ),
                config={"displayModeBar": False},
            ),
            # --- per-claim ---
            html.Div(
                "PER-CLAIM",
                style={"color": theme.MUTED, "fontSize": "0.72em", "letterSpacing": "0.08em",
                       "marginTop": "10px", "marginBottom": "6px",
                       "borderTop": f"1px solid {theme.BORDER}", "paddingTop": "10px"},
            ),
            html.Div(per_claim_view(None), id="per-claim-analytics"),
            # --- trust ---
            trust_strip(run.error_rates),
        ],
        id="analytics-panel",
        style=theme.panel_style(height="100%", overflowY="auto"),
    )
