"""KG editing layer with per-edit scope (SPEC-text §4.4 / §4.6 / RQ3 + CogMG).

Every edit carries a SCOPE chosen by the toggle:
  - generation only        -> change the model's context; grade vs the FULL reference.
  - generation + verification -> change the real KG; grade vs the EDITED reference.

You can add/remove triplets, add an entity (with an optional description), and
remove an entity's content (description/image, via the entity-detail pane). The
edits log shows each op + its scope with an undo; the readout shows repair-leverage
(claims flipped FABRICATED -> grounded) and the current grounded count. Scripted,
deterministic, offline.
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from ivg_kg.mock.fixtures import (
    ENTITY_OPTIONS,
    SCOPE_LABELS,
    SUGGESTED_INJECT,
    grounded_count,
    removed_triples,
    repair_result,
)

_INFO_REPAIR = (
    "KG editing with per-edit SCOPE (SPEC-text §4.4).\n"
    "Each edit applies to either:\n"
    "- generation only: changes ONLY the model's generation context; grading still "
    "uses the FULL reference. Removing induces absence-hallucination the verifier "
    "still CATCHES; adding lets the model state a fact the verifier still cannot "
    "confirm (so it does NOT repair the verdict).\n"
    "- generation + verification: changes the real KG, so grading uses the EDITED "
    "reference. Adding the missing date grounds c3 (gap-repair); removing blinds the "
    "verifier.\n\n"
    "Add/remove triplets here; add an entity (optional description); remove an "
    "entity's content from its detail pane (tap a node). Scripted visual mock."
)
_SCOPE_INFO = (
    "Scope of the next edit. 'generation only' = withhold-from-context (the grading "
    "reference stays full). 'generation + verification' = edit-the-KG (grading uses "
    "the edited reference). Watch the repair-leverage differ: adding the date "
    "generation-only does NOT repair c3 (still unverifiable); generation+verification "
    "does."
)


def _btn(color: str) -> dict:
    return {"background": theme.PANEL, "color": color, "border": f"1px solid {color}",
            "borderRadius": "4px", "padding": "3px 10px", "cursor": "pointer",
            "fontFamily": theme.MONO, "fontSize": "0.74em", "flexShrink": "0"}


def _scope_toggle() -> html.Div:
    return html.Div(
        [
            html.Span("edit scope ", style={"color": theme.TEXT, "fontSize": "0.78em"}),
            dcc.RadioItems(
                id="edit-scope",
                options=[{"label": f" {SCOPE_LABELS['gen']} ", "value": "gen"},
                         {"label": f" {SCOPE_LABELS['both']} ", "value": "both"}],
                value="both", inline=True,
                labelStyle={"color": theme.TEXT, "marginRight": "14px", "cursor": "pointer"},
                inputStyle={"marginRight": "4px"},
                style={"display": "inline-block"},
            ),
            theme.info_icon(_SCOPE_INFO),
        ],
        style={"marginBottom": "8px"},
    )


def _add_triplet_form() -> html.Div:
    return html.Div(
        [
            html.Div("add a triplet (editable — pre-filled with a model suggestion: the missing date)",
                     style={"color": theme.MUTED, "fontSize": "0.72em", "marginBottom": "4px"}),
            html.Div(
                [
                    dcc.Dropdown(id="inject-subject", options=ENTITY_OPTIONS,
                                 value=SUGGESTED_INJECT["subject"], clearable=False,
                                 style={"width": "180px", "color": "#111", "fontSize": "0.78em"}),
                    dcc.Input(id="inject-relation", value=SUGGESTED_INJECT["relation"],
                              placeholder="relation", debounce=True,
                              style={"width": "140px", "fontSize": "0.8em", "padding": "3px 6px"}),
                    dcc.Input(id="inject-value", value=SUGGESTED_INJECT["value"],
                              placeholder="value", debounce=True,
                              style={"width": "150px", "fontSize": "0.8em", "padding": "3px 6px"}),
                    html.Button("↻ suggest", id="inject-suggest", n_clicks=0,
                                style=_btn(theme.MUTED)),
                    html.Button("✚ add triplet", id="inject-apply", n_clicks=0,
                                style=_btn("#3fb950")),
                ],
                style={"display": "flex", "gap": "8px", "alignItems": "center",
                       "flexWrap": "wrap"},
            ),
        ],
        style={"marginBottom": "8px"},
    )


def _add_entity_form() -> html.Div:
    return html.Div(
        [
            html.Div("add an entity (label + optional description)",
                     style={"color": theme.MUTED, "fontSize": "0.72em", "marginBottom": "4px"}),
            html.Div(
                [
                    dcc.Input(id="entity-label", placeholder="entity label", debounce=True,
                              style={"width": "180px", "fontSize": "0.8em", "padding": "3px 6px"}),
                    dcc.Input(id="entity-desc", placeholder="description (optional)", debounce=True,
                              style={"width": "260px", "fontSize": "0.8em", "padding": "3px 6px"}),
                    html.Button("✚ add entity", id="entity-apply", n_clicks=0,
                                style=_btn("#3fb950")),
                ],
                style={"display": "flex", "gap": "8px", "alignItems": "center",
                       "flexWrap": "wrap"},
            ),
        ],
        style={"marginBottom": "10px"},
    )


def _edit_label(e: dict) -> str:
    if e.get("kind") == "triplet":
        body = f"{e.get('relation') or e.get('id', 'triplet')}"
        if e.get("value"):
            body += f" = {e['value']}"
    elif e.get("kind") == "entity":
        body = f"entity {e.get('label', '?')}"
    else:  # content
        body = f"content of {e.get('id', '?')}"
    return f"{e.get('op', '?')} {body}"


def render_repair_body(edits: list[dict] | None = None) -> html.Div:
    """Edits log (with undo) + re-add list + repair-leverage / grounded readout."""
    edits = edits or []
    removed = removed_triples(edits)

    removed_block = html.Div(
        [
            html.Span("withheld base triples (tap an edge to remove; click to re-add): ",
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

    edits_block = html.Div(
        [html.Span("edits applied: ", style={"color": theme.FAINT, "fontSize": "0.72em"})]
        + ([html.Span("none yet", style={"color": theme.FAINT, "fontSize": "0.72em",
                                         "fontStyle": "italic"})] if not edits else [
            html.Button(
                f"✕ {_edit_label(e)} [{SCOPE_LABELS.get(e.get('scope', 'both'), '?')}]",
                id={"type": "remove-edit", "idx": i}, n_clicks=0,
                style={**_btn(theme.MUTED), "marginRight": "6px", "marginBottom": "4px"},
            ) for i, e in enumerate(edits)
        ]),
        style={"marginBottom": "8px"},
    )

    rr = repair_result(edits)
    n = grounded_count(edits)
    flipped = (
        f"+{rr.repair_leverage} repaired: {', '.join(rr.repaired_claim_ids)}"
        if rr.repair_leverage else "+0 repaired (no fabricated claim restored yet)"
    )
    readout = html.Div(
        [
            html.Span("repair-leverage ", style={"color": theme.MUTED, "fontSize": "0.8em"}),
            html.Span(flipped, style={"color": "#3fb950" if rr.repair_leverage else theme.MUTED,
                                      "fontWeight": "bold", "fontSize": "0.95em"}),
            html.Span("  (claims FABRICATED -> grounded vs the original answer, on "
                      "restore + re-run)",
                      style={"color": theme.FAINT, "fontSize": "0.72em"}),
            html.Div(
                [
                    html.Span("grounded ", style={"color": theme.MUTED, "fontSize": "0.78em"}),
                    html.Span(f"{n}/6", style={"color": theme.TEXT, "fontWeight": "bold"}),
                    html.Span("  claims now (graded against the CURRENT reference)  ·  "
                              "scripted visual mock",
                              style={"color": theme.FAINT, "fontSize": "0.72em"}),
                ],
                style={"marginTop": "3px"},
            ),
        ]
    )
    return html.Div([removed_block, edits_block, readout])


def get_repair_panel() -> html.Div:
    """Compose the full-width KG-editing strip."""
    return html.Div(
        [
            html.Div(
                [html.Span("KG EDITS (scoped)",
                           style={"color": theme.MUTED, "fontSize": "0.75em",
                                  "letterSpacing": "0.1em"}),
                 theme.info_icon(_INFO_REPAIR)],
                style={"marginBottom": "4px"},
            ),
            html.Div(
                "Choose the scope per edit: generation-only (withhold-from-context; "
                "the grading reference stays full) vs generation+verification "
                "(edit-the-KG; grading uses the edited reference).",
                style={"color": theme.FAINT, "fontSize": "0.7em", "fontStyle": "italic",
                       "marginBottom": "10px", "lineHeight": "1.4"},
            ),
            _scope_toggle(),
            _add_triplet_form(),
            _add_entity_form(),
            html.Div(render_repair_body(None), id="repair-body"),
        ],
        id="repair-panel",
        style=theme.panel_style(margin="0 18px 20px 18px"),
    )
