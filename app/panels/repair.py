"""Repair-loop strip (SPEC-text §4.6 / RQ3 + CogMG) — the defining interaction.

Overview → Inspection → **Repair** → Overview. Pick an ablation condition; under
knowledge-absence the dependent claims fabricate. The analyst then either
**restores** a withheld triple (RQ3: re-add to the generation context, regenerate,
re-ground) or **injects** a genuinely-missing one (CogMG: add to the KG-full
reference). Either re-grounds the dependent claims; **repair-leverage** = the
number that flip fabricated → grounded. Self-contained + deterministic (mock).
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from ivg_kg.mock.fixtures import (
    REPAIR_ITEMS,
    claim_text_by_id,
    effective_statuses,
    repair_leverage,
)
from ivg_kg.schema import ClaimStatus

_INFO_REPAIR = (
    "The controlled repair loop (RQ3). Under an ablation condition the dependent "
    "claims fabricate; RESTORE re-adds a withheld triple to the generation context "
    "(regenerate → re-ground), INJECT adds a genuinely-missing triple to the KG-full "
    "reference (CogMG). repair-leverage = the number of claims that flip fabricated → "
    "grounded per repair. Mock: scripted + deterministic."
)


def _claim_chip(cid: str, text: str, status: ClaimStatus) -> html.Div:
    color = theme.status_color(status.value)
    grounded = status != ClaimStatus.FABRICATED
    short = text if len(text) <= 30 else text[:27] + "…"
    return html.Div(
        [
            html.Span("✓" if grounded else "✗",
                      style={"color": theme.TEXT if grounded else color, "marginRight": "5px",
                             "fontWeight": "bold"}),
            html.Span(short, style={"color": theme.TEXT}),
        ],
        style={
            "background": theme.PANEL_ALT, "border": f"1px solid {theme.BORDER}",
            "borderLeft": f"4px solid {color}", "borderRadius": "4px",
            "padding": "4px 8px", "fontSize": "0.74em", "whiteSpace": "nowrap",
        },
    )


def _repair_card(item: dict, done: bool) -> html.Div:
    is_inject = item["kind"] == "inject"
    tag = "✚ inject (new KG triple)" if is_inject else "↺ restore (withheld)"
    tag_color = "#3fb950" if is_inject else theme.ACCENT
    return html.Div(
        [
            html.Div(tag, style={"color": tag_color, "fontSize": "0.68em",
                                 "fontWeight": "bold", "marginBottom": "3px"}),
            html.Div(item["label"], style={"color": theme.TEXT, "fontSize": "0.76em"}),
            html.Div("✓ applied" if done else "click to apply",
                     style={"color": theme.MUTED if done else theme.FAINT,
                            "fontSize": "0.68em", "marginTop": "3px"}),
        ],
        id={"type": "repair-item", "item": item["id"]},
        n_clicks=0,
        style={
            "background": theme.PANEL if not done else "#10301c",
            "border": f"1px solid {tag_color if not done else '#3fb950'}",
            "borderRadius": "6px", "padding": "8px 10px", "cursor": "pointer",
            "opacity": "0.6" if done else "1", "minWidth": "210px", "flex": "0 0 auto",
        },
    )


def render_repair_body(condition: str, repaired: list[str] | None = None) -> html.Div:
    """Render the repair-strip body for the given condition + applied repairs."""
    repaired = repaired or []
    statuses = effective_statuses(condition, repaired)
    texts = claim_text_by_id()

    chips = html.Div(
        [_claim_chip(cid, texts[cid], statuses[cid]) for cid in texts],
        style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginBottom": "10px"},
    )

    if condition != "knowledge-absent":
        note = (
            "Full context — no evidence is withheld; switch to "
            "knowledge-absent to restore/inject."
            if condition == "full"
            else "Content-absent — the description is withheld; the structural "
                 "claims here are unaffected (manipulation check)."
        )
        return html.Div([chips, html.Div(note, style={"color": theme.FAINT,
                                                      "fontSize": "0.76em"})])

    lev = repair_leverage(condition, repaired)
    cards = html.Div(
        [_repair_card(it, it["id"] in repaired) for it in REPAIR_ITEMS],
        style={"display": "flex", "gap": "10px", "flexWrap": "wrap", "marginBottom": "10px"},
    )
    leverage_color = "#3fb950" if lev else theme.MUTED
    leverage = html.Div(
        [
            html.Span("repair-leverage ", style={"color": theme.MUTED, "fontSize": "0.8em"}),
            html.Span(f"+{lev}", style={"color": leverage_color, "fontWeight": "bold",
                                        "fontSize": "1.2em"}),
            html.Span(" claims re-grounded", style={"color": theme.FAINT, "fontSize": "0.75em"}),
        ]
    )
    return html.Div([chips, cards, leverage])


def get_repair_panel() -> html.Div:
    """Compose the full-width Repair-loop strip."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span("REPAIR LOOP", style={"color": theme.MUTED, "fontSize": "0.75em",
                                                    "letterSpacing": "0.1em"}),
                    theme.info_icon(_INFO_REPAIR),
                    html.Span("  condition ", style={"color": theme.FAINT, "fontSize": "0.78em",
                                                     "marginLeft": "16px"}),
                    dcc.RadioItems(
                        id="condition-selector",
                        options=[
                            {"label": " full ", "value": "full"},
                            {"label": " knowledge-absent ", "value": "knowledge-absent"},
                            {"label": " content-absent ", "value": "content-absent"},
                        ],
                        value="full",
                        inline=True,
                        style={"display": "inline-block"},
                    ),
                ],
                style={"marginBottom": "10px", "display": "flex", "alignItems": "center"},
            ),
            html.Div(render_repair_body("full", []), id="repair-body"),
        ],
        id="repair-panel",
        style=theme.panel_style(margin="0 18px 20px 18px"),
    )
