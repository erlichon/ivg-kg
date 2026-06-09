"""Layout factory for the IVG-KG mockup (SPEC-text §4.5, §3.3).

Three columns — Answer (left) · Subgraph (middle, the focus) · Analytics (right)
— over a shared dcc.Store(selected-claims). Panels read the store independently
(no circular callbacks); see app/callbacks.py.

get_perturbation_controls() is retained (controls-from-registry seam #3) but is
not part of this 8-interaction mockup grid.
"""
from __future__ import annotations

from dash import dcc, html

from app import theme
from app.panels.analytics import DEFAULT_N, get_analytics_panel
from app.panels.answer import get_answer_panel
from app.panels.subgraph import get_subgraph_panel
from ivg_kg.mock.fixtures import (
    mock_answer_diagnostics,
    mock_grounding_run,
    mock_subgraph_elements,
)
from ivg_kg.perturbation import available_perturbations
from ivg_kg.schema import AnswerDiagnostics, GroundingRun


def get_perturbation_controls() -> html.Div:
    """Controls rendered generically from the perturbation registry (seam #3)."""
    registry = available_perturbations()
    items: list[html.Div] = []
    for type_name, cls in registry.items():
        spec = cls.control_spec()
        items.append(
            html.Div(
                f"{spec.get('label', type_name)} [{spec.get('modality', '')}]",
                style={"color": theme.MUTED, "fontSize": "0.8em", "marginBottom": "4px"},
            )
        )
    return html.Div(
        [html.H4("Perturbation Controls", style={"color": theme.TEXT}), *items],
        id="perturbation-controls",
    )


def _slice_selector() -> html.Div:
    """Header data-slice selector (#5). Mock: one books scenario; the gated image
    slices are shown disabled to signal the design (built post-M-BOOKS)."""
    return html.Div(
        [
            html.Span("slice ", style={"color": theme.FAINT, "fontSize": "0.75em"}),
            dcc.Dropdown(
                id="slice-selector",
                options=[
                    {"label": "books · Chopin (Q1268)", "value": "books"},
                    {"label": "taxa · range maps — gated (post-M-BOOKS)",
                     "value": "taxa", "disabled": True},
                    {"label": "artwork · depicts — gated (post-M-BOOKS)",
                     "value": "artwork", "disabled": True},
                ],
                value="books",
                clearable=False,
                style={"width": "300px", "color": "#111", "fontSize": "0.8em"},
            ),
        ],
        style={"display": "flex", "alignItems": "center", "gap": "6px"},
    )


def _header(run: GroundingRun) -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Span("ivg-kg", style={"color": theme.ACCENT, "fontWeight": "bold",
                                               "fontSize": "1.2em", "fontFamily": theme.MONO}),
                    html.Span("  grounding dashboard · mockup (offline mock data)",
                              style={"color": theme.MUTED, "fontSize": "0.85em"}),
                ],
            ),
            html.Div(
                [
                    _slice_selector(),
                    html.Button(
                        "⚙ generation",
                        id="settings-toggle",
                        n_clicks=0,
                        title="Configure generation parameters (temperature, etc.)",
                        style={"background": theme.PANEL_ALT, "color": theme.TEXT,
                               "border": f"1px solid {theme.BORDER}", "borderRadius": "4px",
                               "padding": "4px 10px", "cursor": "pointer",
                               "fontFamily": theme.MONO, "fontSize": "0.8em"},
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "14px"},
            ),
        ],
        style={
            "padding": "10px 20px", "background": theme.PANEL,
            "borderBottom": f"1px solid {theme.BORDER}", "marginBottom": "0",
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        },
    )


def _settings_panel() -> html.Div:
    """Collapsible generation-settings view (#6). Presentational mock — the
    on-stage figures run off precomputed/offline run-sets (SPEC-text §4.6/§10)."""
    def _slider(label: str, sid: str, lo: float, hi: float, step: float, val: float) -> html.Div:
        return html.Div(
            [
                html.Div(label, style={"color": theme.MUTED, "fontSize": "0.75em"}),
                dcc.Slider(min=lo, max=hi, step=step, value=val, id=sid,
                           marks={lo: str(lo), hi: str(hi)},
                           tooltip={"placement": "bottom", "always_visible": False}),
            ],
            style={"flex": "1", "minWidth": "150px"},
        )

    return html.Div(
        [
            html.Div(
                [
                    html.Span("generation settings", style={"color": theme.TEXT,
                                                            "fontWeight": "bold"}),
                    theme.info_icon(
                        "Controls for the live N-generation path (per condition, N draws). "
                        "Mock & presentational here: the on-stage demo and reported figures "
                        "run off precomputed offline run-sets (SPEC-text §4.6 / §10)."
                    ),
                ],
                style={"marginBottom": "8px", "fontSize": "0.85em"},
            ),
            html.Div(
                [
                    _slider("temperature", "gen-temperature", 0.0, 1.5, 0.05, 0.0),
                    _slider("top-p", "gen-top-p", 0.0, 1.0, 0.05, 1.0),
                    html.Div(
                        [
                            html.Div("max new tokens", style={"color": theme.MUTED,
                                                              "fontSize": "0.75em"}),
                            dcc.Input(id="gen-max-tokens", type="number", value=256,
                                      style={"width": "90px"}),
                        ],
                        style={"flex": "0 0 auto"},
                    ),
                    html.Div(
                        [
                            html.Div("model", style={"color": theme.MUTED, "fontSize": "0.75em"}),
                            dcc.Dropdown(
                                id="gen-model",
                                options=[
                                    {"label": "Llama-3.2-3B-Instruct (local)", "value": "local"},
                                    {"label": "cloud · BaseAIClient adapter", "value": "cloud"},
                                ],
                                value="local", clearable=False,
                                style={"width": "240px", "color": "#111", "fontSize": "0.8em"},
                            ),
                        ],
                        style={"flex": "0 0 auto"},
                    ),
                ],
                style={"display": "flex", "gap": "20px", "alignItems": "flex-start",
                       "flexWrap": "wrap"},
            ),
            html.Div(
                "Mock: parameters are presentational; the displayed answer is FULL draw #0 "
                "of a precomputed, offline run-set. N (draws/condition) is set in Analytics.",
                style={"color": theme.FAINT, "fontSize": "0.72em", "marginTop": "10px"},
            ),
        ],
        id="settings-panel",
        style={
            "display": "none",  # toggled by the ⚙ button (see callbacks)
            "padding": "12px 20px", "background": theme.PANEL_ALT,
            "borderBottom": f"1px solid {theme.BORDER}", "marginBottom": "14px",
        },
    )


def get_layout(
    run: GroundingRun | None = None,
    elements: list[dict] | None = None,
    diagnostics: AnswerDiagnostics | None = None,
) -> html.Div:
    """Compose the three-panel mockup layout with the shared store."""
    if run is None:
        run = mock_grounding_run()
    if elements is None:
        elements = mock_subgraph_elements()
    if diagnostics is None:
        diagnostics = mock_answer_diagnostics(DEFAULT_N)

    return html.Div(
        [
            dcc.Store(id="selected-claims", data=[]),
            _header(run),
            _settings_panel(),
            html.Div(
                [
                    html.Div(get_answer_panel(run),
                             style={"flex": "1.05", "minWidth": "0"}),
                    html.Div(get_subgraph_panel(elements),
                             style={"flex": "1.5", "minWidth": "0"}),
                    html.Div(get_analytics_panel(run, diagnostics),
                             style={"flex": "1.1", "minWidth": "0"}),
                ],
                style={"display": "flex", "gap": "14px", "padding": "0 18px 20px 18px",
                       "alignItems": "stretch"},
            ),
        ],
        style={
            "fontFamily": theme.MONO,
            "background": theme.BG,
            "minHeight": "100vh",
            "color": theme.TEXT,
        },
    )
