"""Graph editor + repair loop (SPEC-text §4.6 / RQ3 + CogMG) — the defining interaction.

A full-width strip that lets the analyst **add / remove evidence** from the graph
and watch the claims re-verify. Flow: edit the graph → the answer is regenerated
from the new generation context → claims are re-verified against the full grading
reference. REMOVE = ablate a triple/description; ADD = the RQ3 repair; INJECT =
add a fact the KG lacked (CogMG — the only edit that changes the reference).
Self-contained + deterministic (mock).
"""
from __future__ import annotations

from dash import html

from app import theme
from ivg_kg.mock.fixtures import (
    ALL_EVIDENCE_IDS,
    CONDITION_PRESENT,
    EVIDENCE_ITEMS,
    INJECT_ITEM,
    claim_text_by_id,
    grounded_count,
    statuses_for_graph,
)
from ivg_kg.schema import ClaimStatus

_INFO_REPAIR = (
    "Graph editor + repair loop.\n"
    "REMOVE an evidence item → it is ablated (the answer is regenerated WITHOUT it). "
    "ADD it back → the RQ3 repair. INJECT adds a fact the KG lacked (CogMG) — the "
    "only edit that changes the grading reference itself.\n\n"
    "After every edit the answer is regenerated from the new context and the claims "
    "are re-verified against the FULL reference. The chips below show the re-verified "
    "statuses; the presets set the standard conditions (full / knowledge-absent / "
    "content-absent). Scripted visual mock — no real generation/injection."
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
        style={"background": theme.PANEL_ALT, "border": f"1px solid {theme.BORDER}",
               "borderLeft": f"4px solid {color}", "borderRadius": "4px",
               "padding": "4px 8px", "fontSize": "0.74em", "whiteSpace": "nowrap"},
    )


def _preset_button(cond: str) -> html.Button:
    return html.Button(
        cond,
        id={"type": "evidence-preset", "cond": cond},
        n_clicks=0,
        style={"background": theme.PANEL, "color": theme.MUTED,
               "border": f"1px solid {theme.BORDER}", "borderRadius": "4px",
               "padding": "2px 9px", "cursor": "pointer", "fontFamily": theme.MONO,
               "fontSize": "0.72em", "marginRight": "6px"},
    )


def _evidence_row(item: dict, present: set[str]) -> html.Div:
    in_graph = item["id"] in present
    return html.Div(
        [
            html.Span("✓ in graph" if in_graph else "✕ withheld",
                      style={"color": "#3fb950" if in_graph else theme.FAINT,
                             "fontSize": "0.7em", "fontWeight": "bold",
                             "width": "78px", "flexShrink": "0"}),
            html.Span(item["label"], style={"color": theme.TEXT, "fontSize": "0.76em",
                                            "flex": "1"}),
            html.Button(
                "remove" if in_graph else "+ add",
                id={"type": "evidence-toggle", "item": item["id"]},
                n_clicks=0,
                style={"background": theme.PANEL,
                       "color": theme.STATUS_COLORS[ClaimStatus.FABRICATED.value]
                       if in_graph else "#3fb950",
                       "border": f"1px solid {theme.BORDER}", "borderRadius": "4px",
                       "padding": "1px 8px", "cursor": "pointer", "fontFamily": theme.MONO,
                       "fontSize": "0.7em", "flexShrink": "0"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "gap": "10px",
               "padding": "3px 0"},
    )


def _inject_row(injected: set[str]) -> html.Div:
    done = INJECT_ITEM["id"] in injected
    return html.Div(
        [
            html.Span("✚ inject", style={"color": "#3fb950", "fontSize": "0.7em",
                                         "fontWeight": "bold", "width": "78px",
                                         "flexShrink": "0"}),
            html.Span([html.Span(INJECT_ITEM["label"],
                                 style={"color": theme.TEXT, "fontSize": "0.76em"}),
                       html.Div(INJECT_ITEM["note"], style={"color": theme.FAINT,
                                                            "fontSize": "0.66em"})],
                      style={"flex": "1"}),
            html.Button(
                "✓ injected" if done else "✚ inject new",
                id={"type": "evidence-inject", "item": INJECT_ITEM["id"]},
                n_clicks=0,
                style={"background": "#10301c" if done else theme.PANEL,
                       "color": "#3fb950", "border": "1px solid #3fb950",
                       "borderRadius": "4px", "padding": "1px 8px", "cursor": "pointer",
                       "fontFamily": theme.MONO, "fontSize": "0.7em", "flexShrink": "0",
                       "opacity": "0.6" if done else "1"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "gap": "10px",
               "padding": "3px 0", "borderTop": f"1px dashed {theme.BORDER}",
               "marginTop": "4px", "paddingTop": "6px"},
    )


def render_repair_body(present: list[str] | None, injected: list[str] | None = None) -> html.Div:
    """Render the editor body: re-verified chips + the add/remove/inject rows."""
    present = list(present if present is not None else ALL_EVIDENCE_IDS)
    injected = injected or []
    statuses = statuses_for_graph(present, injected)
    texts = claim_text_by_id()
    pres = set(present)

    chips = html.Div(
        [_claim_chip(cid, texts[cid], statuses[cid]) for cid in texts],
        style={"display": "flex", "gap": "8px", "flexWrap": "wrap", "marginBottom": "10px"},
    )
    rows = html.Div(
        [_evidence_row(it, pres) for it in EVIDENCE_ITEMS] + [_inject_row(set(injected))],
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
    return html.Div([chips, rows, readout])


def get_repair_panel() -> html.Div:
    """Compose the full-width graph-editor / repair-loop strip."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span("GRAPH EDITOR + REPAIR LOOP",
                              style={"color": theme.MUTED, "fontSize": "0.75em",
                                     "letterSpacing": "0.1em"}),
                    theme.info_icon(_INFO_REPAIR),
                    html.Span("   presets ", style={"color": theme.FAINT, "fontSize": "0.72em",
                                                    "marginLeft": "14px"}),
                    *[_preset_button(c) for c in CONDITION_PRESENT],
                ],
                style={"marginBottom": "10px", "display": "flex", "alignItems": "center",
                       "flexWrap": "wrap"},
            ),
            html.Div(render_repair_body(list(ALL_EVIDENCE_IDS), []), id="repair-body"),
        ],
        id="repair-panel",
        style=theme.panel_style(margin="0 18px 20px 18px"),
    )
