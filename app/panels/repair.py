"""Graph edits — inject panel + re-add list (SPEC-text §4.6 / RQ3 + CogMG).

Ablation is per specific triple and happens ON the graph (tap an edge in the
Subgraph panel → remove it). This bottom strip hosts the parts that don't live on
the graph: an **editable inject form** (a model suggestion pre-fills it, but the
analyst edits subject / relation / value) and a **re-add list** of any removed
triples. Every edit re-verifies the claims (the answer + chips update). No global
condition presets — there is no single "knowledge-absent" mode; you remove the
specific evidence you want. Scripted visual mock.
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from ivg_kg.mock.fixtures import (
    ENTITY_OPTIONS,
    SUGGESTED_INJECT,
    grounded_count,
    removed_triples,
)

_INFO_REPAIR = (
    "Graph edits — a DETERMINISTIC re-verification (NOT a regeneration).\n"
    "The claim text is held FIXED; removing/injecting a triple re-grades the SAME "
    "claims against the edited KG (instant, bit-stable). This is a different view "
    "from the Analytics per-claim card, which is the N-draw GENERATION-variance "
    "distribution — here nothing is re-sampled.\n\n"
    "REMOVE a triple by tapping its edge in the Subgraph panel → it leaves the KG "
    "and the fixed claims re-grade; removed triples appear here with '+ re-add' "
    "(the RQ3 repair-leverage counterfactual).\n\n"
    "INJECT adds a NEW triple the KG lacked (CogMG) — a model suggestion pre-fills the "
    "form, but you edit subject / relation / value before inserting. After every edit "
    "the claims are re-verified against the full reference (the answer + chips update). "
    "Scripted visual mock — no real generation/injection."
)


def _inject_form() -> html.Div:
    return html.Div(
        [
            html.Div("inject a new triple (editable — pre-filled with a model suggestion)",
                     style={"color": theme.MUTED, "fontSize": "0.72em", "marginBottom": "4px"}),
            html.Div(
                [
                    dcc.Dropdown(id="inject-subject", options=ENTITY_OPTIONS,
                                 value=SUGGESTED_INJECT["subject"], clearable=False,
                                 style={"width": "190px", "color": "#111", "fontSize": "0.78em"}),
                    dcc.Input(id="inject-relation", value=SUGGESTED_INJECT["relation"],
                              placeholder="relation", debounce=True,
                              style={"width": "150px", "fontSize": "0.8em", "padding": "3px 6px"}),
                    dcc.Input(id="inject-value", value=SUGGESTED_INJECT["value"],
                              placeholder="value", debounce=True,
                              style={"width": "170px", "fontSize": "0.8em", "padding": "3px 6px"}),
                    html.Button("↻ suggest", id="inject-suggest", n_clicks=0,
                                style=_btn(theme.MUTED)),
                    html.Button("✚ inject", id="inject-apply", n_clicks=0,
                                style=_btn("#3fb950")),
                ],
                style={"display": "flex", "gap": "8px", "alignItems": "center",
                       "flexWrap": "wrap"},
            ),
        ],
        style={"marginBottom": "10px"},
    )


def _btn(color: str) -> dict:
    return {"background": theme.PANEL, "color": color, "border": f"1px solid {color}",
            "borderRadius": "4px", "padding": "3px 10px", "cursor": "pointer",
            "fontFamily": theme.MONO, "fontSize": "0.74em", "flexShrink": "0"}


def render_repair_body(present: list[str] | None, injected: list[dict] | None = None) -> html.Div:
    """Re-add list (removed triples) + injected list + grounded readout."""
    injected = injected or []
    removed = removed_triples(present)

    removed_block = html.Div(
        [
            html.Span("removed (tap an edge to remove; click to re-add): ",
                      style={"color": theme.FAINT, "fontSize": "0.72em"}),
            *([html.Span("none", style={"color": theme.FAINT, "fontSize": "0.72em",
                                        "fontStyle": "italic"})] if not removed else [
                html.Button(
                    f"+ re-add  {t['prop_label']} ({t['id']})",
                    id={"type": "readd", "item": t["id"]}, n_clicks=0,
                    style={**_btn("#3fb950"), "marginRight": "6px", "marginBottom": "4px"},
                ) for t in removed
            ]),
        ],
        style={"marginBottom": "8px"},
    )

    injected_block = html.Div(
        [html.Span("injected: ", style={"color": theme.FAINT, "fontSize": "0.72em"})]
        + ([html.Span("none yet", style={"color": theme.FAINT, "fontSize": "0.72em",
                                         "fontStyle": "italic"})] if not injected else [
            html.Button(
                f"✕ {inj.get('relation', '?')} = {inj.get('value', '?')}",
                id={"type": "remove-inject", "idx": i}, n_clicks=0,
                style={**_btn("#3fb950"), "marginRight": "6px", "marginBottom": "4px"},
            ) for i, inj in enumerate(injected)
        ]),
        style={"marginBottom": "8px"},
    )

    n = grounded_count(present, injected)
    readout = html.Div(
        [
            html.Span("grounded ", style={"color": theme.MUTED, "fontSize": "0.8em"}),
            html.Span(f"{n}/6", style={"color": "#3fb950" if n else theme.MUTED,
                                       "fontWeight": "bold", "fontSize": "1.1em"}),
            html.Span("  claims (re-verified after the edit)  ·  scripted visual mock",
                      style={"color": theme.FAINT, "fontSize": "0.72em"}),
        ]
    )
    return html.Div([removed_block, injected_block, readout])


def get_repair_panel() -> html.Div:
    """Compose the full-width graph-edits / inject strip."""
    return html.Div(
        [
            html.Div(
                [html.Span("GRAPH EDITS + INJECT",
                           style={"color": theme.MUTED, "fontSize": "0.75em",
                                  "letterSpacing": "0.1em"}),
                 theme.info_icon(_INFO_REPAIR)],
                style={"marginBottom": "4px"},
            ),
            html.Div(
                "Deterministic re-verification — the claim text is FIXED; an edit "
                "re-grades the SAME claims against the edited KG (instant, no "
                "regeneration). Distinct from the N-draw generation-variance view in "
                "Analytics.",
                style={"color": theme.FAINT, "fontSize": "0.7em", "fontStyle": "italic",
                       "marginBottom": "10px", "lineHeight": "1.4"},
            ),
            _inject_form(),
            html.Div(render_repair_body(None, []), id="repair-body"),
        ],
        id="repair-panel",
        style=theme.panel_style(margin="0 18px 20px 18px"),
    )
