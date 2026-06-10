"""Central visual theme for the IVG-KG mockup (SPEC-text §4.5 encoding rules).

Single source of truth for the **status palette**: hue encodes claim STATUS —
one fixed 3-grade palette used IDENTICALLY in every panel (Answer / Subgraph /
Analytics). Multiple selected claims are distinguished by an OUTLINE + NUMERIC
BADGE (a fixed accent colour + a number), NEVER by re-using hue for identity.

UI labels are the short forms: Retrieved / Supportable / Fabricated. The long
term ``reasoned-supportable`` stays only in code/enum values.

Terminal / monospace aesthetic on a dark ground.
"""
from __future__ import annotations

from dash import html

from ivg_kg.schema import ClaimStatus

# --- ground / chrome ---------------------------------------------------------
BG = "#0d1117"  # page background
PANEL = "#161b22"  # panel background
PANEL_ALT = "#0d1117"  # inset background (chat bubbles, traces)
BORDER = "#30363d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
FAINT = "#6e7681"
ACCENT = "#58a6ff"  # the single selection-outline colour (identity != hue)

MONO = "'JetBrains Mono', 'SF Mono', 'Menlo', 'Consolas', 'Roboto Mono', monospace"

# --- the load-bearing status palette (hue == status) -------------------------
# Keyed by ClaimStatus *value* strings so every panel imports the same map.
# Pastel 3-grade palette (light on the dark ground; chip text uses BG for contrast).
STATUS_COLORS: dict[str, str] = {
    ClaimStatus.RETRIEVED.value: "#8fd9a8",            # pastel green
    ClaimStatus.REASONED_SUPPORTABLE.value: "#f2d08a",  # pastel amber / gold
    ClaimStatus.FABRICATED.value: "#f4a6c0",           # pastel rose / magenta
}

# Short UI labels (the long term stays in the enum / prose).
STATUS_UI_LABELS: dict[str, str] = {
    ClaimStatus.RETRIEVED.value: "Retrieved",
    ClaimStatus.REASONED_SUPPORTABLE.value: "Supportable",
    ClaimStatus.FABRICATED.value: "Fabricated",
}

# Ordered grades for filters / charts (the THREE real grades; "proposed" is the
# input universe, not a fourth grade).
STATUS_ORDER: list[str] = [
    ClaimStatus.RETRIEVED.value,
    ClaimStatus.REASONED_SUPPORTABLE.value,
    ClaimStatus.FABRICATED.value,
]


def status_color(status: str) -> str:
    """Hue for a claim status value (falls back to muted grey)."""
    return STATUS_COLORS.get(str(status), FAINT)


def status_label(status: str) -> str:
    """Short UI label for a claim status value."""
    return STATUS_UI_LABELS.get(str(status), str(status))


def info_icon(explanation: str) -> html.Details:
    """A click-to-toggle 'ⓘ' indicator (what + how computed).

    Uses a native <details>/<summary> disclosure: click the ⓘ to reveal a
    persistent, fully-wrapping note (it stays until clicked again — no flaky
    hover). Offline, no callback. The summary marker is hidden via info.css.
    """
    return html.Details(
        [
            html.Summary(
                "ⓘ",
                style={"color": ACCENT, "cursor": "pointer", "fontSize": "0.85em",
                       "display": "inline"},
            ),
            html.Div(
                explanation,
                style={
                    "marginTop": "4px", "maxWidth": "320px", "whiteSpace": "pre-wrap",
                    "background": "#0b1020", "border": f"1px solid {ACCENT}",
                    "borderRadius": "6px", "padding": "8px 10px",
                    "color": TEXT, "fontSize": "0.74em", "lineHeight": "1.45",
                    "fontFamily": MONO, "fontWeight": "normal",
                },
            ),
        ],
        className="ivg-info",
        style={"display": "inline-block", "verticalAlign": "middle", "marginLeft": "5px"},
    )


def panel_style(**extra: object) -> dict:
    """Base style for a panel container."""
    base = {
        "padding": "14px 16px",
        "background": PANEL,
        "border": f"1px solid {BORDER}",
        "borderRadius": "8px",
    }
    base.update(extra)  # type: ignore[arg-type]
    return base
