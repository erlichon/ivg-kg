"""KG editing layer — two operations (SPEC-text §4.4 / §4.6 / RQ3 + CogMG).

There is no scope toggle. Scope is fixed by the operation:
  - REMOVE (a triplet or an entity's description) -> from the GENERATION CONTEXT only;
    the verifier / grading reference is ALWAYS full and is NEVER ablated. REMOVE tests
    whether the model NEEDS that evidence (qualitative RQ2).
  - ADD (a true missing fact: a triplet or an entity) -> to the KG (both the generation
    context and the grading reference). ADD repairs / gap-repairs.

The edits log shows each op + what it touched with an undo; the readout shows
repair-leverage (claims flipped FABRICATED -> grounded) and the grounded count.
Scripted, deterministic, offline.
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from app.run_source import _run_id as _current_run_id
from ivg_kg.mock.fixtures import (
    ENTITY_OPTIONS,
    SCOPE_LABELS,
    SUGGESTED_INJECT,
    grounded_count,
    removed_triples,
    repair_result,
)

_INFO_REPAIR = (
    "KG editing — two operations (SPEC-text §4.4). Scope is fixed by the operation; "
    "there is no toggle.\n"
    "- REMOVE a triplet (tap its edge) or an entity's description (its detail pane) "
    "-> withholds it from the model's GENERATION CONTEXT only. The grading reference "
    "stays FULL (never ablated), so the claim fabricates only if the model actually "
    "couldn't recover it -- the qualitative RQ2 demo (does the model NEED it?).\n"
    "- ADD a triplet or an entity (optional description) -> adds it to the KG (both "
    "the generation context and the grading reference). This repairs: a claim "
    "fabricated only because the KG lacked a true fact flips to grounded.\n"
    "We never remove from the verifier; there is no generation-only add. Scripted mock."
)
_INFO_LEVERAGE = (
    "Repair-leverage (RQ3).\n"
    "WHAT: the COUNT of the answer's claims whose verdict flips FABRICATED -> grounded.\n"
    "WHEN: after you ADD a true missing fact to the KG and the answer is RE-RUN.\n"
    "HOW: compared to the ORIGINAL answer (no edits), aligned by claim_id within this "
    "one before/after pair; regeneration-based (not a deterministic re-grounding).\n"
    "Here the only originally-fabricated claim is the father's birth date (c3) -- the "
    "KG has a gap -- so adding the date repairs +1 (c3)."
)


def _btn(color: str) -> dict:
    return {"background": theme.PANEL, "color": color, "border": f"1px solid {color}",
            "borderRadius": "4px", "padding": "3px 10px", "cursor": "pointer",
            "fontFamily": theme.MONO, "fontSize": "0.74em", "flexShrink": "0"}


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
    """Edits log (with undo) + re-add list + repair-leverage / grounded readout.

    In REAL mode the repair demo is disabled: the interactive KG-edit / repair loop
    is built for the bundled mock scenario only. A real live re-grounding loop lands
    with UI5/EX3 (GR9). An honest note is shown instead of Chopin-specific content.
    """
    if _current_run_id() is not None:
        return html.Div(
            "Interactive KG-edit / repair demo runs on the bundled mock scenario; "
            "live repair on loaded runs lands with the repair loop (UI5/EX3).",
            style={"color": theme.FAINT, "fontSize": "0.78em", "fontStyle": "italic",
                   "padding": "6px 0"},
        )

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
    before = grounded_count(None)
    now = grounded_count(edits)
    lev_txt = (
        f"+{rr.repair_leverage}  ({', '.join(rr.repaired_claim_ids)})"
        if rr.repair_leverage else "+0"
    )
    readout = html.Div(
        [
            html.Span("repair-leverage  ", style={"color": theme.MUTED, "fontSize": "0.8em"}),
            html.Span(lev_txt, style={"color": "#3fb950" if rr.repair_leverage else theme.MUTED,
                                      "fontWeight": "bold", "fontSize": "1.0em"}),
            html.Span("  claims flipped FABRICATED -> grounded by these edits",
                      style={"color": theme.FAINT, "fontSize": "0.72em"}),
            theme.info_icon(_INFO_LEVERAGE),
            html.Div(
                [
                    html.Span("grounded ", style={"color": theme.MUTED, "fontSize": "0.78em"}),
                    html.Span(f"{before}/6 → {now}/6",
                              style={"color": theme.TEXT, "fontWeight": "bold"}),
                    html.Span("   (original answer → after the edits, graded vs the "
                              "CURRENT reference)  ·  scripted visual mock",
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
                [html.Span("KG EDITS",
                           style={"color": theme.MUTED, "fontSize": "0.75em",
                                  "letterSpacing": "0.1em"}),
                 theme.info_icon(_INFO_REPAIR)],
                style={"marginBottom": "4px"},
            ),
            html.Div(
                "Two operations: REMOVE (tap a triplet's edge, or remove an entity's "
                "description in its detail pane) withholds it from the model's "
                "generation context (the verifier keeps the full reference); ADD (below) "
                "adds a true fact to the KG and repairs.",
                style={"color": theme.FAINT, "fontSize": "0.7em", "fontStyle": "italic",
                       "marginBottom": "10px", "lineHeight": "1.4"},
            ),
            _add_triplet_form(),
            _add_entity_form(),
            html.Div(render_repair_body(None), id="repair-body"),
        ],
        id="repair-panel",
        style=theme.panel_style(margin="0 18px 20px 18px"),
    )
