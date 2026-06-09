"""Layout factory for the IVG-KG Dash app (SPEC-text §4.5, §3.3).

get_layout(run, elements) composes the three panels and a dcc.Store.
get_perturbation_controls() renders controls generically from the perturbation
registry (seam #3) — it does NOT hardcode the three types or special-case any
modality.

No side effects on import beyond building Dash component objects.
"""
from __future__ import annotations

from dash import dcc, html

from app.panels.analytics import get_analytics_panel
from app.panels.answer import get_answer_panel
from app.panels.subgraph import get_subgraph_panel
from ivg_kg.mock.fixtures import mock_grounding_run, mock_subgraph_elements
from ivg_kg.perturbation import available_perturbations
from ivg_kg.schema import GroundingRun


def get_perturbation_controls() -> html.Div:
    """Build a controls section driven entirely by the perturbation registry.

    Iterates available_perturbations() and calls control_spec() on each type.
    Renders one labelled checkbox section per entry — completely generic, not
    hardcoded to any specific type_name (seam #3 / Invariant #8).
    """
    registry = available_perturbations()
    control_items: list[html.Div] = []

    for type_name, cls in registry.items():
        spec = cls.control_spec()
        label = spec.get("label", type_name)
        modality = spec.get("modality", "")
        params = spec.get("params", [])

        param_hints = ", ".join(p.get("name", "") for p in params) if params else "no params"

        control_items.append(
            html.Div(
                [
                    dcc.Checklist(
                        id={"type": "perturbation-toggle", "type_name": type_name},
                        options=[
                            {
                                "label": html.Span(
                                    [
                                        html.Span(
                                            label,
                                            style={
                                                "fontWeight": "bold",
                                                "color": "#cdd6f4",
                                            },
                                        ),
                                        html.Span(
                                            f" [{modality}]",
                                            style={
                                                "color": "#585b70",
                                                "fontSize": "0.8em",
                                            },
                                        ),
                                    ]
                                ),
                                "value": type_name,
                            }
                        ],
                        value=[],
                        style={"marginBottom": "4px"},
                    ),
                    html.Div(
                        f"type_name: {type_name} | params: {param_hints}",
                        style={
                            "color": "#585b70",
                            "fontSize": "0.75em",
                            "marginLeft": "20px",
                            "marginBottom": "8px",
                        },
                    ),
                ],
                style={"marginBottom": "6px"},
            )
        )

    return html.Div(
        [
            html.H4(
                "Perturbation Controls",
                style={
                    "color": "#cdd6f4",
                    "marginBottom": "10px",
                    "fontSize": "0.95em",
                    "borderBottom": "1px solid #313244",
                    "paddingBottom": "6px",
                },
            ),
            html.Div(
                "(P0: controls are rendered from registry; not wired to live grounding.)",
                style={"color": "#585b70", "fontSize": "0.75em", "marginBottom": "10px"},
            ),
            html.Div(control_items),
        ],
        id="perturbation-controls",
        style={
            "padding": "12px",
            "background": "#181825",
            "borderRadius": "6px",
            "marginBottom": "16px",
        },
    )


def get_layout(run: GroundingRun | None = None, elements: list[dict] | None = None) -> html.Div:
    """Compose the full three-panel layout with Store and controls.

    Parameters
    ----------
    run:
        GroundingRun to display.  Defaults to mock_grounding_run().
    elements:
        Cytoscape element list.  Defaults to mock_subgraph_elements().
    """
    if run is None:
        run = mock_grounding_run()
    if elements is None:
        elements = mock_subgraph_elements()

    return html.Div(
        [
            # ------------------------------------------------------------------
            # Invisible store — written by CB1, read by CB2 + CB3.
            # ------------------------------------------------------------------
            dcc.Store(id="selected-claim", storage_type="memory"),
            # ------------------------------------------------------------------
            # Header
            # ------------------------------------------------------------------
            html.Div(
                [
                    html.H1(
                        "IVG-KG — Grounding Dashboard",
                        style={
                            "color": "#cdd6f4",
                            "margin": "0",
                            "fontSize": "1.4em",
                            "fontWeight": "600",
                        },
                    ),
                    html.Span(
                        f"Run: {run.run_id}  |  Slice: {run.slice}  |  Phase: {run.phase}",
                        style={"color": "#585b70", "fontSize": "0.85em"},
                    ),
                ],
                style={
                    "padding": "14px 20px",
                    "background": "#181825",
                    "borderBottom": "1px solid #313244",
                    "marginBottom": "16px",
                },
            ),
            # ------------------------------------------------------------------
            # Main content: controls sidebar + three-panel grid
            # ------------------------------------------------------------------
            html.Div(
                [
                    # Sidebar: perturbation controls
                    html.Div(
                        get_perturbation_controls(),
                        style={"width": "220px", "flexShrink": "0"},
                    ),
                    # Three-panel grid
                    html.Div(
                        [
                            # Answer panel
                            html.Div(
                                get_answer_panel(run),
                                style={"flex": "1", "minWidth": "0", "marginRight": "12px"},
                            ),
                            # Subgraph panel
                            html.Div(
                                get_subgraph_panel(elements),
                                style={"flex": "1", "minWidth": "0", "marginRight": "12px"},
                            ),
                            # Analytics panel
                            html.Div(
                                get_analytics_panel(run),
                                style={"flex": "1", "minWidth": "0"},
                            ),
                        ],
                        style={"display": "flex", "flex": "1", "gap": "0", "minWidth": "0"},
                    ),
                ],
                style={
                    "display": "flex",
                    "gap": "16px",
                    "padding": "0 20px 20px 20px",
                    "alignItems": "flex-start",
                },
            ),
        ],
        style={
            "fontFamily": "'Segoe UI', 'Inter', sans-serif",
            "background": "#1e1e2e",
            "minHeight": "100vh",
            "color": "#cdd6f4",
        },
    )
