"""Subgraph panel — dash_cytoscape graph with path-highlighting support.

BASE_STYLESHEET is the module-level default stylesheet; it must NEVER be
mutated (Invariant #12).

highlight_stylesheet(base, path_edge_ids, path_node_ids) returns a NEW list
equal to base + appended highlight selectors — it never modifies base.
"""
from __future__ import annotations

import dash_cytoscape
from dash import html

# ---------------------------------------------------------------------------
# Base stylesheet (module-level; must not be mutated anywhere — Invariant #12)
# ---------------------------------------------------------------------------

BASE_STYLESHEET: list[dict] = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "background-color": "#313244",
            "border-color": "#585b70",
            "border-width": 1,
            "color": "#cdd6f4",
            "font-size": "11px",
            "text-valign": "center",
            "text-halign": "center",
            "width": 60,
            "height": 60,
        },
    },
    {
        "selector": "edge",
        "style": {
            "label": "data(label)",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#585b70",
            "line-color": "#585b70",
            "font-size": "9px",
            "color": "#a6adc8",
            "text-rotation": "autorotate",
            "width": 1.5,
        },
    },
]


def highlight_stylesheet(
    base: list[dict],
    path_edge_ids: list[str],
    path_node_ids: list[str],
) -> list[dict]:
    """Return base + appended highlight selectors for the given path elements.

    PURE function — never mutates ``base``.  Returns a NEW list.
    (Invariant #12: appending, never editing the global stylesheet.)

    Parameters
    ----------
    base:
        The current base stylesheet (must not be modified).
    path_edge_ids:
        Edge element ids to highlight (format: "<subj>-<pid>-<obj>").
    path_node_ids:
        Node element ids to highlight.

    Returns
    -------
    list[dict]
        A new list equal to ``base`` followed by the highlight selector dicts.
    """
    appended: list[dict] = []

    for nid in path_node_ids:
        appended.append(
            {
                "selector": f'node[id = "{nid}"]',
                "style": {
                    "background-color": "#89b4fa",
                    "border-color": "#74c7ec",
                    "border-width": 3,
                    "color": "#1e1e2e",
                    "font-weight": "bold",
                },
            }
        )

    for eid in path_edge_ids:
        appended.append(
            {
                "selector": f'edge[id = "{eid}"]',
                "style": {
                    "line-color": "#f38ba8",
                    "target-arrow-color": "#f38ba8",
                    "width": 3,
                    "color": "#f38ba8",
                    "font-weight": "bold",
                },
            }
        )

    # Return a brand-new list — do NOT do base += appended (would mutate base).
    return list(base) + appended


def get_subgraph_panel(elements: list[dict]) -> html.Div:
    """Render the subgraph panel containing a Cytoscape graph.

    The Cytoscape component carries id="subgraph" and the BASE_STYLESHEET.
    CB2 will swap the stylesheet (via Output) to base + highlight selectors
    for the selected claim path.
    """
    return html.Div(
        [
            html.H3(
                "Knowledge Subgraph",
                style={"color": "#cdd6f4", "marginBottom": "12px", "fontSize": "1.1em"},
            ),
            html.Div(
                "Click a claim to highlight its support path.",
                style={"color": "#a6adc8", "fontSize": "0.85em", "marginBottom": "10px"},
            ),
            dash_cytoscape.Cytoscape(
                id="subgraph",
                elements=elements,
                stylesheet=BASE_STYLESHEET,
                layout={"name": "cose"},
                style={"width": "100%", "height": "420px", "background": "#1e1e2e"},
                responsive=True,
            ),
            html.Div(
                id="node-detail",
                style={
                    "marginTop": "10px",
                    "color": "#a6adc8",
                    "fontSize": "0.85em",
                    "minHeight": "24px",
                },
            ),
        ],
        id="subgraph-panel",
        style={
            "padding": "16px",
            "background": "#181825",
            "borderRadius": "6px",
            "height": "100%",
        },
    )
