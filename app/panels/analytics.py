"""Analytics panel (Knowledge + Trust pillars) — SPEC-text §4.5 / §4.8.

Variance model: the VERIFIER is a deterministic instrument (it always grades
against the full KG), so it is NOT the source of any spread. The GENERATOR is the
stochastic system under test. Every per-draw difference is therefore GENERATION
variance: we draw the generator **N times per condition** {full, knowledge-absent,
content-absent} and grade each draw once. N is selectable.

A fact SLOT (head + relation) can be filled by different VARIANTS (values) across
draws; a variant has exactly one fixed status (deterministic verifier), so a slot's
mixed status distribution reflects WHICH variant the generator emitted (or none),
never a per-claim status flip. The per-claim panel is anchored on the slot and
shows the variant breakdown.

Surfaces:
  - Full-answer (top): claim-status distribution (fraction ± SE over N generation
    draws) + fabrication rate, with an N selector + a prominent small-N caveat.
  - Per-claim (bottom): one collapsible card per selected slot (closed by default);
    expand for the per-condition stacked bar + variant breakdown + stability +
    leverage + spurious chip.
  - Trust strip (persistent): the verifier's measured per-path error.
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from app.charts.condition_breakdown import make_condition_breakdown_figure
from app.charts.status_dist import make_status_distribution_figure, proportion_se
from ivg_kg.mock.fixtures import N_CHOICES
from ivg_kg.schema import AnswerDiagnostics, ClaimDiagnostics, ClaimStatus, GroundingRun

DEFAULT_N = 20

# Back-compat re-export.
STATUS_COLORS = theme.STATUS_COLORS

_INFO_FAB = (
    "Fabrication rate.\n"
    "The GENERATOR is drawn N times under the full-context condition; the verifier "
    "grades each draw once (deterministically, against the full KG). For each draw "
    "we take (claims graded Fabricated ÷ claims in that draw); the number is the "
    "fraction over the N draws. ± is the standard error of that proportion, "
    "SE = sqrt(p(1-p)/N) — the uncertainty at N draws, not a per-draw std. "
    "Higher = more of the answer is unsupported by the grading reference."
)
_INFO_DIST = (
    "Claim-status distribution (fraction ± SE).\n"
    "Over the N generation draws under the FULL condition, the share of claims in "
    "each grade (Retrieved / Supportable / Fabricated). The spread is GENERATION "
    "variance — the verifier is deterministic, so it is not repeated grading. The "
    "whisker is the SE of the proportion sqrt(p(1-p)/N), NOT the Bernoulli "
    "per-draw std (~0.5). At N=20 an SE near 0.11 is typical, so small differences "
    "are within noise."
)
_INFO_TRUST = (
    "Verifier reliability — measured ONCE on the curated QA gold set (calibrated on "
    "the curated QA set, hand-labelled), not derived from the runs above. Shown "
    "before per-claim so those numbers are interpretable.\n\n"
    "The verifier grades each claim by two paths:\n"
    "• text-NLI — an NLI model (MiniCheck) checks whether the serialized reference "
    "evidence (a triple / a curated content fact) ENTAILS the claim's asserted "
    "value. Drives direct-triple + content grounding; value-sensitive.\n"
    "• structure-path — searches the KG for an undirected multi-hop path "
    "(2..k hops) that entails the claim → 'Supportable'.\n\n"
    "Error per path: take a held-out sample of claims, a human labels each claim's "
    "true status, run the verifier, error = fraction it grades differently from the "
    "human. So text-NLI 6% ⇒ ~6% of text/NLI verdicts are wrong. "
    "(Needs the curated QA gold set + the verifier run over it. Mock values here.)"
)
_INFO_STABILITY = (
    "Stability — how reproducible the SLOT's per-draw outcome is over the N FULL "
    "generation draws (the confidence companion).\n"
    "• outcome = the status of whichever VARIANT filled the slot in a draw "
    "(Retrieved / Supportable / Fabricated), or 'absent' if the slot was unfilled.\n"
    "• FULL = the full-context generation condition (nothing withheld).\n"
    "• p_s = fraction of the N draws with outcome s.\n"
    "• H = −Σ_s p_s · ln(p_s)  (Shannon entropy of those fractions).\n"
    "• K = number of distinct outcomes observed.\n"
    "stability = 1 − H / ln(K). 1.0 = same outcome every draw; →0 = evenly split. "
    "It moves because the generator picks different variants — not because grading "
    "changes (a variant's status is fixed). Companion: modal outcome × its share."
)
_INFO_PRESENCE = (
    "Presence rate — the fraction of the N FULL generation draws in which the slot "
    "is filled at all (1 − P[absent]). Low presence means the generator often omits "
    "this fact; the remaining bar splits across the variant statuses below."
)
_INFO_VARIANTS = (
    "Variant breakdown — every value the generator emitted for this slot, with its "
    "ONE fixed status (the deterministic verifier grades a fixed value identically "
    "every time) and how often it was drawn (count over the N FULL draws).\n"
    "This is what explains a mixed slot distribution: the per-variant status meter "
    "never moves — only which variant appears does. A 'fabricated' variant is the "
    "generator asserting a WRONG VALUE in the SAME slot (e.g. the wrong birth date)."
)
_INFO_ABSENCE = (
    "Absence-leverage (per evidence modality m: knowledge / content / image) — how "
    "much the slot relied on that evidence (SLOT-level).\n"
    "It compares two GENERATION conditions, each drawn N times: full context vs m "
    "withheld from the generator. leverage_m = P(grounded | full) − "
    "P(grounded | m withheld); grounded = the filling variant is Retrieved or "
    "Supportable. High ⇒ relied on m; ~0 ⇒ produced it regardless "
    "(parametric/redundant) or never.\n"
    "Small-N: it is a difference of two proportions, SE ≈ sqrt(2p(1-p)/N) ≈ 0.16 at "
    "N=20 — only |leverage| ≳ 0.3 is distinguishable from noise."
)
_INFO_INDUCTION = (
    "Fabrication-induction (per modality m, SLOT-level) = P(fabricated | m "
    "withheld) − P(fabricated | full).\n"
    "Like absence-leverage it compares two generation conditions (full vs "
    "m-withheld), each drawn N times. High ⇒ withholding m makes the generator "
    "emit a wrong-value variant — the absence-induced-hallucination signal. Same "
    "small-N caveat (SE ≈ 0.16 at N=20)."
)
_INFO_SPURIOUS = (
    "A Supportable claim whose multi-hop path passed the entailment gate but is "
    "not legitimate support — flagged by: relation/value illegitimacy, hub/length "
    "fragility, or route non-robustness. Shown only for Supportable claims."
)
_INFO_TWO_VIEWS = (
    "Two distinct per-claim views (do not blur):\n"
    "(1) THIS card — the generation-variance distribution over N draws: how the "
    "stochastic generator behaves for this slot (the RQ2 experiment).\n"
    "(2) The graph editor below — a deterministic re-verification of a FIXED claim "
    "against the edited KG (remove/inject a triple → re-grade the same claim, "
    "instant, NO regeneration). It answers 'what does this verdict rest on', a "
    "different question."
)


def fab_rate_readout(diag: AnswerDiagnostics) -> html.Div:
    """Big fabrication-rate readout (fraction ± SE) over the N FULL generation draws."""
    rate = diag.fabrication_rate
    se = proportion_se(rate, diag.n_generations)
    color = theme.STATUS_COLORS[ClaimStatus.FABRICATED.value]
    return html.Div(
        [
            html.Span("fabrication rate ", style={"color": theme.MUTED, "fontSize": "0.8em"}),
            html.Span(f"{rate:.0%}", style={"color": color, "fontWeight": "bold",
                                            "fontSize": "1.4em"}),
            html.Span(f" ± {se:.0%} SE", style={"color": theme.MUTED, "fontSize": "0.85em"}),
            html.Span(f"  over N={diag.n_generations} generation draws (FULL)",
                      style={"color": theme.FAINT, "fontSize": "0.75em"}),
            theme.info_icon(_INFO_FAB),
        ],
        style={"marginBottom": "8px"},
    )


def small_n_caveat() -> html.Div:
    """Prominent small-N honesty banner (SPEC-text §4.8 statistical-honesty)."""
    return html.Div(
        [
            html.Span("⚠ small-N ", style={"color": theme.STATUS_COLORS[
                ClaimStatus.REASONED_SUPPORTABLE.value], "fontWeight": "bold",
                "fontSize": "0.72em"}),
            html.Span(
                "N=20 is a FLOOR, not a target. Error bars are the SE of the "
                "proportion (sqrt(p(1-p)/N)); absence-leverage is a difference of "
                "proportions (SE ≈ 0.16 at N=20), so leverages below ~0.3 are within "
                "noise. All spread is generation variance — the verifier is deterministic.",
                style={"color": theme.MUTED, "fontSize": "0.7em", "lineHeight": "1.4"},
            ),
        ],
        style={"background": theme.PANEL_ALT, "border": f"1px dashed {theme.BORDER}",
               "borderRadius": "4px", "padding": "6px 9px", "marginBottom": "8px"},
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
            html.Div(["VERIFIER RELIABILITY · error on curated QA gold set (per grading path)",
                      theme.info_icon(_INFO_TRUST)],
                     style={"color": theme.FAINT, "fontSize": "0.68em",
                            "letterSpacing": "0.08em", "marginBottom": "6px"}),
            html.Div(chips, style={"display": "flex", "gap": "16px"}),
            html.Div("calibrated on the curated QA set (hand-labelled); not derived "
                     "from the draws above",
                     style={"color": theme.FAINT, "fontSize": "0.66em",
                            "fontStyle": "italic", "marginTop": "5px"}),
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


def _variant_breakdown(diag: ClaimDiagnostics) -> html.Div:
    """The REQUIRED per-slot variant breakdown: value · fixed status · draw freq."""
    rows: list = []
    for v in diag.variants:
        full_count = v.draw_frequency.get("full", 0)
        short = v.text if len(v.text) <= 46 else v.text[:43] + "…"
        rows.append(
            html.Div(
                [
                    html.Span(short or v.normalized_value,
                              style={"color": theme.TEXT, "fontSize": "0.72em"}),
                    html.Span("  ·  ", style={"color": theme.FAINT, "fontSize": "0.72em"}),
                    html.Span(theme.status_label(v.status.value),
                              style={"color": theme.status_color(v.status.value),
                                     "fontWeight": "bold", "fontSize": "0.72em"}),
                    html.Span(f"  ·  {full_count}/{diag.n_full}",
                              style={"color": theme.MUTED, "fontSize": "0.72em"}),
                ],
                style={"borderLeft": f"3px solid {theme.status_color(v.status.value)}",
                       "paddingLeft": "7px", "marginBottom": "3px"},
            )
        )
    return html.Div(
        [
            html.Div(["variants filling this slot (each a FIXED status · draws over N)",
                      theme.info_icon(_INFO_VARIANTS)],
                     style={"color": theme.FAINT, "fontSize": "0.7em", "marginBottom": "4px"}),
            *rows,
        ],
        style={"marginBottom": "8px"},
    )


def _per_claim_body(diag: ClaimDiagnostics) -> list:
    """The expanded contents of a per-slot card (no header — that's the summary)."""
    modal_count = round(diag.modal_fraction * diag.n_full)
    present_count = round(diag.presence_rate * diag.n_full)
    body: list = [
        html.Div(
            [
                html.Span("presence ", style={"color": theme.MUTED, "fontSize": "0.78em"}),
                html.Span(f"{present_count}/{diag.n_full}",
                          style={"color": theme.TEXT, "fontWeight": "bold"}),
                html.Span(f"  ({diag.presence_rate:.0%} of draws fill this slot)",
                          style={"color": theme.FAINT, "fontSize": "0.72em"}),
                theme.info_icon(_INFO_PRESENCE),
            ],
            style={"marginBottom": "6px"},
        ),
        _variant_breakdown(diag),
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
    if diag.intra_answer_contradiction:
        body.append(
            html.Div(
                "⚠ intra-answer contradiction: a single draw asserted two variants "
                "of this slot.",
                style={"color": theme.STATUS_COLORS[ClaimStatus.FABRICATED.value],
                       "fontSize": "0.72em", "marginBottom": "6px"},
            )
        )
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
    body.append(
        html.Div(
            ["this is the generation-variance distribution over N draws (the "
             "experiment); the graph editor below re-verifies a FIXED claim against "
             "the edited KG — instant, no regeneration",
             theme.info_icon(_INFO_TWO_VIEWS)],
            style={"color": theme.FAINT, "fontSize": "0.68em", "fontStyle": "italic",
                   "marginTop": "6px", "lineHeight": "1.4"},
        )
    )
    return body


def per_claim_card(diag: ClaimDiagnostics, open_: bool = False) -> html.Details:
    """One selected slot as a collapsible card (closed by default; expand for detail)."""
    color = theme.status_color(diag.modal_status.value)
    short = diag.text if len(diag.text) <= 48 else diag.text[:45] + "…"
    summary = html.Summary(
        [_status_chip(diag.modal_status.value), html.Span(short, style={"color": theme.TEXT})],
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
    """Render one collapsed per-slot card for each selected claim (#7)."""
    if not diags:
        return [html.Div("Select one or more claims to see their per-slot diagnostics.",
                         style={"color": theme.FAINT, "fontStyle": "italic", "fontSize": "0.8em"})]
    return [per_claim_card(d) for d in diags]


def unaligned_readout(run: GroundingRun) -> html.Div:
    """Count of claims mapping to no slice slot (aligned=False) — a pipeline metric."""
    total = len(run.claims)
    unaligned = sum(1 for c in run.claims if not c.aligned)
    return html.Div(
        [
            html.Span("unaligned claims ", style={"color": theme.FAINT, "fontSize": "0.7em"}),
            html.Span(f"{unaligned}/{total}",
                      style={"color": theme.MUTED, "fontWeight": "bold", "fontSize": "0.72em"}),
            html.Span("  (mapped to no slice slot; never force-aligned — coverage, "
                      "not gate error)",
                      style={"color": theme.FAINT, "fontSize": "0.68em"}),
        ],
        style={"marginBottom": "6px"},
    )


def get_analytics_panel(run: GroundingRun, diagnostics: AnswerDiagnostics) -> html.Div:
    """Compose the Analytics panel with the initial N-default diagnostics."""
    return html.Div(
        [
            html.Div("ANALYTICS", style={"color": theme.MUTED, "fontSize": "0.75em",
                                         "letterSpacing": "0.1em", "marginBottom": "10px"}),
            # --- full-answer ---
            html.Div(
                [
                    html.Span("generation draws / condition (N)  ",
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
            small_n_caveat(),
            html.Div(fab_rate_readout(diagnostics), id="fab-rate"),
            unaligned_readout(run),
            html.Div(["distribution over N generation draws (±SE)", theme.info_icon(_INFO_DIST)],
                     style={"color": theme.FAINT, "fontSize": "0.7em", "marginBottom": "2px"}),
            dcc.Graph(
                id="status-dist-graph",
                figure=make_status_distribution_figure(
                    diagnostics.status_distribution,
                    diagnostics.n_generations,
                ),
                config={"displayModeBar": False},
            ),
            # --- trust / gold-set stats (before per-claim, per review) ---
            trust_strip(run.error_rates),
            # --- per-claim ---
            html.Div(
                "PER-CLAIM (per fact slot)",
                style={"color": theme.MUTED, "fontSize": "0.72em", "letterSpacing": "0.08em",
                       "marginTop": "12px", "marginBottom": "6px",
                       "borderTop": f"1px solid {theme.BORDER}", "paddingTop": "10px"},
            ),
            html.Div(per_claim_sections([]), id="per-claim-analytics"),
        ],
        id="analytics-panel",
        style=theme.panel_style(height="100%", overflowY="auto"),
    )
