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


def _header(run: GroundingRun) -> html.Div:
    return html.Div(
        [
            html.Span("ivg-kg", style={"color": theme.ACCENT, "fontWeight": "bold",
                                       "fontSize": "1.2em", "fontFamily": theme.MONO}),
            html.Span("  grounding dashboard · mockup (offline mock data)",
                      style={"color": theme.MUTED, "fontSize": "0.85em"}),
            html.Span(
                f"slice: {run.slice}   phase: {run.phase}   run: {run.run_id}",
                style={"color": theme.FAINT, "fontSize": "0.78em", "float": "right",
                       "fontFamily": theme.MONO},
            ),
        ],
        style={
            "padding": "12px 20px", "background": theme.PANEL,
            "borderBottom": f"1px solid {theme.BORDER}", "marginBottom": "14px",
            "overflow": "hidden",
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
