"""Answer panel (Outputs + Process pillars) — SPEC-text §4.5.

Chat-style: question bubble + answer with status-coloured claim spans + the
`>>PROPOSED → >>VERIFY → status` verification trace (Process pillar). Below:
the three-grade status filter (#1) and the multi-select claim list (#2) — each
claim coloured by status (hue == status), selected claims marked by an ACCENT
outline + numeric badge (identity != hue).

Back-compat: STATUS_COLORS / STATUS_LABELS are re-exported from app.theme so
existing imports keep working; the long enum term lives only in code.
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from ivg_kg.mock.fixtures import CLAIM_SPANS
from ivg_kg.schema import ClaimStatus, GroundingRun

# Re-exported for back-compat; hue == status (the long enum term in code only).
STATUS_COLORS = theme.STATUS_COLORS
STATUS_LABELS = {
    ClaimStatus.RETRIEVED.value: "retrieved",
    ClaimStatus.REASONED_SUPPORTABLE.value: "reasoned-supportable",
    ClaimStatus.FABRICATED.value: "fabricated",
}

_GRADE_ORDER = theme.STATUS_ORDER


def _status_chip(status: str) -> html.Span:
    color = theme.status_color(status)
    return html.Span(
        theme.status_label(status).upper(),
        style={
            "background": color,
            "color": theme.BG,
            "fontWeight": "bold",
            "fontSize": "0.62em",
            "padding": "2px 6px",
            "borderRadius": "3px",
            "letterSpacing": "0.05em",
            "marginRight": "8px",
            "whiteSpace": "nowrap",
        },
    )


def _question_bubble(question: str) -> html.Div:
    return html.Div(
        [
            html.Span("user", style={"color": theme.FAINT, "fontSize": "0.7em"}),
            html.Div(
                question,
                style={
                    "background": "#1f6feb22",
                    "border": f"1px solid {theme.ACCENT}55",
                    "borderRadius": "8px 8px 8px 2px",
                    "padding": "8px 12px",
                    "marginTop": "2px",
                    "color": theme.TEXT,
                },
            ),
        ],
        style={"marginBottom": "12px"},
    )


def _answer_with_spans(run: GroundingRun) -> html.Div:
    """Render answer_text with clickable status-coloured spans for claims."""
    text = run.answer_text
    status_by_id = {c.claim_id: c.status.value for c in run.claims}

    # Locate each claim's span substring; keep only found, non-overlapping, sorted.
    spans: list[tuple[int, int, str]] = []
    for cid, sub in CLAIM_SPANS.items():
        idx = text.find(sub)
        if idx >= 0:
            spans.append((idx, idx + len(sub), cid))
    spans.sort()
    pruned: list[tuple[int, int, str]] = []
    last_end = 0
    for start, end, cid in spans:
        if start >= last_end:
            pruned.append((start, end, cid))
            last_end = end

    children: list = []
    cursor = 0
    for start, end, cid in pruned:
        if start > cursor:
            children.append(html.Span(text[cursor:start]))
        color = theme.status_color(status_by_id.get(cid, ""))
        children.append(
            html.Span(
                text[start:end],
                id={"type": "claim-span", "claim_id": cid},
                n_clicks=0,
                title=f"{theme.status_label(status_by_id.get(cid, ''))} — click to select",
                style={
                    "background": f"{color}33",
                    "borderBottom": f"2px solid {color}",
                    "color": theme.TEXT,
                    "cursor": "pointer",
                    "padding": "0 1px",
                },
            )
        )
        cursor = end
    if cursor < len(text):
        children.append(html.Span(text[cursor:]))

    return html.Div(
        [
            html.Span("assistant", style={"color": theme.FAINT, "fontSize": "0.7em"}),
            html.Div(
                children,
                style={
                    "background": theme.PANEL_ALT,
                    "border": f"1px solid {theme.BORDER}",
                    "borderRadius": "8px 8px 2px 8px",
                    "padding": "10px 12px",
                    "marginTop": "2px",
                    "lineHeight": "1.6",
                },
            ),
        ],
        style={"marginBottom": "14px"},
    )


def _status_filter() -> html.Div:
    return html.Div(
        [
            html.Div(
                "filter by grade (clear = show all)",
                style={"color": theme.FAINT, "fontSize": "0.7em", "marginBottom": "4px"},
            ),
            dcc.Checklist(
                id="status-filter",
                options=[
                    {"label": html.Span(
                        theme.status_label(s),
                        style={"color": theme.status_color(s), "marginRight": "12px",
                               "fontWeight": "bold", "fontSize": "0.8em"},
                    ), "value": s}
                    for s in _GRADE_ORDER
                ],
                value=list(_GRADE_ORDER),
                inline=True,
            ),
        ],
        style={"marginBottom": "10px"},
    )


def render_claim_list(
    run: GroundingRun,
    selected_ids: list[str] | None = None,
    active_grades: list[str] | None = None,
) -> list[html.Div]:
    """Render the claim rows (filtered by grade; selected rows outlined + badged).

    Used by both the initial panel and the reactive callback. Empty/None
    active_grades means "show all" (clearing the filter shows everything).
    """
    selected_ids = selected_ids or []
    grades = active_grades if active_grades else list(_GRADE_ORDER)
    badge_for = {cid: i + 1 for i, cid in enumerate(selected_ids)}

    rows: list[html.Div] = []
    for c in run.claims:
        if c.status.value not in grades:
            continue
        color = theme.status_color(c.status.value)
        is_sel = c.claim_id in badge_for
        grounded = c.status != ClaimStatus.FABRICATED
        # Process pillar, merged into the row: proposed → verified ✓/✗.
        verify_mark = html.Span(
            "✓" if grounded else "✗",
            title="proposed → verified against the grading reference",
            style={"color": theme.TEXT if grounded else color, "fontWeight": "bold",
                   "marginRight": "6px", "fontFamily": theme.MONO},
        )
        children = [verify_mark, _status_chip(c.status.value), html.Span(c.text)]
        if is_sel:
            children.insert(
                0,
                html.Span(
                    f"{badge_for[c.claim_id]}",
                    style={
                        "display": "inline-block",
                        "minWidth": "16px",
                        "height": "16px",
                        "lineHeight": "16px",
                        "textAlign": "center",
                        "background": theme.ACCENT,
                        "color": theme.BG,
                        "borderRadius": "50%",
                        "fontSize": "0.7em",
                        "fontWeight": "bold",
                        "marginRight": "6px",
                    },
                ),
            )
        if c.spurious_path:
            children.append(
                html.Span(
                    "⚠ path suspect",
                    style={"color": theme.STATUS_COLORS[ClaimStatus.FABRICATED.value],
                           "fontSize": "0.7em", "marginLeft": "8px"},
                )
            )
        rows.append(
            html.Div(
                children,
                id={"type": "claim-row", "claim_id": c.claim_id},
                n_clicks=0,
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "flexWrap": "wrap",
                    "gap": "2px",
                    "background": theme.PANEL_ALT,
                    "border": f"{'2px' if is_sel else '1px'} solid "
                              f"{theme.ACCENT if is_sel else theme.BORDER}",
                    "borderLeft": f"4px solid {color}",
                    "borderRadius": "4px",
                    "padding": "7px 10px",
                    "marginBottom": "6px",
                    "cursor": "pointer",
                    "fontSize": "0.85em",
                },
            )
        )
    if not rows:
        rows.append(
            html.Div("(no claims match the filter)",
                     style={"color": theme.FAINT, "fontStyle": "italic", "fontSize": "0.8em"})
        )
    return rows


def get_answer_panel(run: GroundingRun) -> html.Div:
    """Compose the Answer panel."""
    return html.Div(
        [
            html.Div("ANSWER", style={"color": theme.MUTED, "fontSize": "0.75em",
                                      "letterSpacing": "0.1em", "marginBottom": "10px"}),
            _question_bubble(run.question),
            _answer_with_spans(run),
            _status_filter(),
            html.Div(
                [
                    ">> claims · proposed → verified against the grading reference ",
                    html.Span("(✓ grounded · ✗ fabricated)", style={"color": theme.FAINT}),
                ],
                style={"color": theme.MUTED, "fontSize": "0.72em", "marginBottom": "6px",
                       "fontFamily": theme.MONO},
            ),
            html.Div(
                render_claim_list(run, [], list(_GRADE_ORDER)),
                id="claim-list",
            ),
        ],
        id="answer-panel",
        style=theme.panel_style(height="100%", overflowY="auto"),
    )
