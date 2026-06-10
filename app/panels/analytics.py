"""Analytics panel (Knowledge + Trust pillars) — SPEC-text §4.5 / §4.8.

Variance model (per user steer): the answer is generated ONCE; the **verifier**
then runs N times over its claims (its grading is stochastic). So the
distribution / stability / fabrication-rate spread is VERIFIER variance, not
generation variance. N is selectable. Cross-condition contrasts (absence-leverage,
fabrication-induction) instead require generating one answer per condition and
verifying each — see the info notes.

Surfaces:
  - Full-answer (top): claim-status distribution (mean ± std over N verifier runs)
    + fabrication rate, with an N selector.
  - Per-claim (bottom): one collapsible card per selected claim (closed by
    default); expand for the per-condition stacked bar + stability + leverage +
    spurious chip.
  - Trust strip (persistent): the verifier's measured per-path error.
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
    "Fabrication rate.\n"
    "The answer is generated once; the verifier then grades its claims N times "
    "(its grading is stochastic). For each verifier run we take "
    "(claims graded Fabricated ÷ claims in the answer). The number is the MEAN of "
    "that fraction over the N runs; ± is its standard deviation. "
    "Higher = more of the answer is unsupported by the grading reference."
)
_INFO_DIST = (
    "Claim-status distribution (mean ± std).\n"
    "One generated answer, verified N times. Each verifier run yields a fraction "
    "of claims in each grade (Retrieved / Supportable / Fabricated). The bar is "
    "the MEAN over the N runs; the whisker is ±1 standard deviation. The spread is "
    "VERIFIER variance (the answer is fixed), not generation variance."
)
_INFO_TRUST = (
    "Verifier reliability — measured ONCE on a gold (hand-labelled) set, not "
    "derived from the runs above. Shown before per-claim so those numbers are "
    "interpretable.\n\n"
    "The verifier grades each claim by two paths:\n"
    "• text-NLI — an NLI model (MiniCheck) checks whether the serialized reference "
    "evidence (a triple / a curated content fact) ENTAILS the claim's asserted "
    "value. Drives direct-triple + content grounding; value-sensitive.\n"
    "• structure-path — searches the KG for an undirected multi-hop path "
    "(2..k hops) that entails the claim → 'Supportable'.\n\n"
    "Error per path: take a held-out sample of claims, a human labels each claim's "
    "true status, run the verifier, error = fraction it grades differently from the "
    "human. So text-NLI 6% ⇒ ~6% of text/NLI verdicts are wrong. "
    "(Needs a hand-labelled gold set + the verifier run over it. Mock values here.)"
)
_INFO_STABILITY = (
    "Stability — how reproducible the verifier's verdict for THIS claim is over the "
    "N runs on the fixed full-context answer.\n"
    "• status = the claim's grade in one run (Retrieved / Supportable / Fabricated).\n"
    "• FULL = the full-context condition (nothing withheld).\n"
    "• p_s = fraction of the N runs that gave status s.\n"
    "• H = −Σ_s p_s · ln(p_s)  (Shannon entropy of those fractions).\n"
    "• K = number of distinct statuses the verifier actually returned.\n"
    "stability = 1 − H / ln(K). 1.0 = same grade every run; →0 = evenly split. "
    "Companion: modal status × its share (e.g. 'retrieved 18/20')."
)
_INFO_ABSENCE = (
    "Absence-leverage (per evidence modality m: knowledge / content / image) — how "
    "much the claim relied on that evidence.\n"
    "It compares TWO generation conditions: the answer generated with full context "
    "vs the answer generated with m withheld — each then verified N times. "
    "leverage_m = P(grounded | full) − P(grounded | m withheld), grounded = "
    "Retrieved or Supportable. So yes — it needs running the GENERATOR once per "
    "condition (not just the verifier). High ⇒ relied on m; ~0 ⇒ produced it "
    "regardless (parametric/redundant) or never."
)
_INFO_INDUCTION = (
    "Fabrication-induction (per modality m) = P(fabricated | m withheld) − "
    "P(fabricated | full).\n"
    "Like absence-leverage it compares two generation conditions (full vs "
    "m-withheld), each verified N times. High ⇒ withholding m makes the model "
    "fabricate — the absence-induced-hallucination signal."
)
_INFO_SPURIOUS = (
    "A Supportable claim whose multi-hop path passed the entailment gate but is "
    "not legitimate support — flagged by: relation/value illegitimacy, hub/length "
    "fragility, or route non-robustness. Shown only for Supportable claims."
)


def fab_rate_readout(diag: AnswerDiagnostics) -> html.Div:
    """Big fabrication-rate readout (mean ± std) over the N verifier runs."""
    rate = diag.fabrication_rate
    sd = diag.fabrication_rate_std
    color = theme.STATUS_COLORS[ClaimStatus.FABRICATED.value]
    return html.Div(
        [
            html.Span("fabrication rate ", style={"color": theme.MUTED, "fontSize": "0.8em"}),
            html.Span(f"{rate:.0%}", style={"color": color, "fontWeight": "bold",
                                            "fontSize": "1.4em"}),
            html.Span(f" ± {sd:.0%}", style={"color": theme.MUTED, "fontSize": "0.85em"}),
            html.Span(f"  over N={diag.n_generations} verifier runs",
                      style={"color": theme.FAINT, "fontSize": "0.75em"}),
            theme.info_icon(_INFO_FAB),
        ],
        style={"marginBottom": "8px"},
    )


def trust_strip(error_rates: dict[str, float]) -> html.Div:
    """Always-visible per-path verifier-error strip (Trust pillar)."""
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
            html.Div(["VERIFIER RELIABILITY · error on gold set (per grading path)",
                      theme.info_icon(_INFO_TRUST)],
                     style={"color": theme.FAINT, "fontSize": "0.68em",
                            "letterSpacing": "0.08em", "marginBottom": "6px"}),
            html.Div(chips, style={"display": "flex", "gap": "16px"}),
        ],
        id="trust-strip",
        style={"marginTop": "12px", "paddingTop": "10px",
               "borderTop": f"1px solid {theme.BORDER}"},
    )


def _status_chip(status: str) -> html.Span:
    return html.Span(
        theme.status_label(status).upper(),
        style={"background": theme.status_color(status), "color": theme.BG,
               "fontWeight": "bold", "fontSize": "0.6em", "padding": "2px 6px",
               "borderRadius": "3px", "marginRight": "8px", "whiteSpace": "nowrap"},
    )


def _per_claim_body(diag: ClaimDiagnostics) -> list:
    """The expanded contents of a per-claim card (no header — that's the summary)."""
    modal_count = round(diag.modal_fraction * diag.n_full)
    body: list = [
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
        body.append(
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

    def _readout(label: str, data: dict[str, float], info: str) -> html.Div:
        return html.Div(
            [html.Span(f"{label}  ", style={"color": theme.FAINT, "fontSize": "0.72em"}),
             html.Span("  ".join(f"{m}:{v:+.2f}" for m, v in data.items()),
                       style={"color": theme.MUTED, "fontSize": "0.72em",
                              "fontFamily": theme.MONO}),
             theme.info_icon(info)],
            style={"marginBottom": "4px"},
        )

    if diag.absence_leverage:
        body.append(_readout("absence-leverage ", diag.absence_leverage, _INFO_ABSENCE))
    if diag.fabrication_induction:
        body.append(_readout("fabric-induction", diag.fabrication_induction, _INFO_INDUCTION))
    body.append(dcc.Graph(figure=make_condition_breakdown_figure(diag),
                          config={"displayModeBar": False}))
    return body


def per_claim_card(diag: ClaimDiagnostics, open_: bool = False) -> html.Details:
    """One selected claim as a collapsible card (closed by default; expand for detail)."""
    color = theme.status_color(diag.status.value)
    short = diag.text if len(diag.text) <= 48 else diag.text[:45] + "…"
    summary = html.Summary(
        [_status_chip(diag.status.value), html.Span(short, style={"color": theme.TEXT})],
        style={"cursor": "pointer", "fontSize": "0.82em", "padding": "2px 0"},
    )
    return html.Details(
        [summary, html.Div(_per_claim_body(diag), style={"paddingTop": "8px"})],
        open=open_,
        style={"background": theme.PANEL_ALT, "border": f"1px solid {theme.BORDER}",
               "borderLeft": f"4px solid {color}", "borderRadius": "4px",
               "padding": "7px 10px", "marginBottom": "8px"},
    )


def per_claim_sections(diags: list[ClaimDiagnostics]) -> list:
    """Render one collapsed per-claim card for each selected claim (#7)."""
    if not diags:
        return [html.Div("Select one or more claims to see their per-claim diagnostics.",
                         style={"color": theme.FAINT, "fontStyle": "italic", "fontSize": "0.8em"})]
    return [per_claim_card(d) for d in diags]


def get_analytics_panel(run: GroundingRun, diagnostics: AnswerDiagnostics) -> html.Div:
    """Compose the Analytics panel with the initial N-default diagnostics."""
    return html.Div(
        [
            html.Div("ANALYTICS", style={"color": theme.MUTED, "fontSize": "0.75em",
                                         "letterSpacing": "0.1em", "marginBottom": "10px"}),
            # --- full-answer ---
            html.Div(
                [
                    html.Span("verifier runs (N)  ",
                              style={"color": theme.TEXT, "fontSize": "0.78em"}),
                    dcc.RadioItems(
                        id="n-selector",
                        options=[{"label": f" {n} ", "value": n} for n in N_CHOICES],
                        value=DEFAULT_N,
                        inline=True,
                        labelStyle={"color": theme.TEXT, "marginRight": "12px",
                                    "cursor": "pointer"},
                        inputStyle={"marginRight": "4px"},
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
            # --- trust / gold-set stats (before per-claim, per review) ---
            trust_strip(run.error_rates),
            # --- per-claim ---
            html.Div(
                "PER-CLAIM",
                style={"color": theme.MUTED, "fontSize": "0.72em", "letterSpacing": "0.08em",
                       "marginTop": "12px", "marginBottom": "6px",
                       "borderTop": f"1px solid {theme.BORDER}", "paddingTop": "10px"},
            ),
            html.Div(per_claim_sections([]), id="per-claim-analytics"),
        ],
        id="analytics-panel",
        style=theme.panel_style(height="100%", overflowY="auto"),
    )
