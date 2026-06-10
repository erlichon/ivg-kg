"""Subgraph panel (Knowledge pillar) — SPEC-text §4.5.

Renders the KG neighbourhood as dash-cytoscape. Selected claims' support paths
are highlighted by **appending** selectors to BASE_STYLESHEET — the base is
NEVER mutated. Hue on a path edge encodes the claim's STATUS; selected-claim
identity is an ACCENT outline + a numeric badge on the claim's anchor node
(never hue). Literal value nodes are styled distinctly. Tapping a node opens the
entity-detail pane (static placeholder image + label/description) and zooms to
the node + its 1st-degree neighbours (under SUBGRAPH_NODE_CAP).
"""
from __future__ import annotations

import dash_cytoscape
from dash import html

from app import theme
from ivg_kg.config import SUBGRAPH_NODE_CAP
from ivg_kg.schema import ClaimRecord, ClaimStatus

PLACEHOLDER_IMG = "/assets/placeholder_entity.svg"

# --- base stylesheet (module-level; never mutated — append only) -------------
BASE_STYLESHEET: list[dict] = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "background-color": "#21262d",
            "border-color": theme.BORDER,
            "border-width": 1,
            "color": theme.TEXT,
            "font-family": theme.MONO,
            "font-size": "10px",
            "text-valign": "center",
            "text-halign": "center",
            "text-wrap": "wrap",
            "text-max-width": "90px",
            "width": 54,
            "height": 54,
        },
    },
    {
        # literal value nodes — styled distinctly (rectangle, dashed, muted).
        "selector": 'node[kind = "literal"]',
        "style": {
            "shape": "round-rectangle",
            "background-color": "#161b22",
            "border-color": theme.FAINT,
            "border-width": 1,
            "border-style": "dashed",
            "color": theme.MUTED,
            "font-style": "italic",
            "width": 84,
            "height": 38,
        },
    },
    {
        "selector": "edge",
        "style": {
            "label": "data(label)",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": theme.FAINT,
            "line-color": theme.FAINT,
            "font-family": theme.MONO,
            "font-size": "9px",
            # bright label on its own dark pill, so it stays readable over the
            # line (and over a status-hued highlight) — never tinted by the edge.
            "color": "#e6edf3",
            "text-background-color": theme.BG,
            "text-background-opacity": 0.9,
            "text-background-padding": "2px",
            "text-background-shape": "round-rectangle",
            "text-rotation": "autorotate",
            "text-margin-y": -1,
            "width": 1.5,
        },
    },
    {
        # de-emphasised neighbours (1st-degree context, not on a claim path).
        "selector": 'node[faded = "1"]',
        "style": {"opacity": 0.45},
    },
    {
        # injected edges (added by the analyst — CogMG) shown green + dashed.
        "selector": 'edge[injected = "1"]',
        "style": {"line-color": "#3fb950", "line-style": "dashed",
                  "target-arrow-color": "#3fb950", "width": 2.5},
    },
]


def support_edges_and_nodes(claim: ClaimRecord) -> tuple[list[str], list[str], str | None]:
    """Return (support_edge_ids, support_node_ids, anchor_node_id) for a claim.

    Reads the claim's support path (grounding_path) uniformly: every grounded
    claim carries it (a single-edge path for a DIRECT_TRIPLE claim, the full path
    for a multi-hop one). Edge ids follow the "<subj>-<prop>-<obj>" convention.
    """
    anchor = claim.linked_entities[0].id if claim.linked_entities else None
    if claim.grounding_path.edges:
        eids = [
            f"{pe.subject_id}-{pe.property_id}-{pe.object_id}"
            for pe in claim.grounding_path.edges
        ]
        return eids, list(claim.grounding_path.node_ids), anchor
    return [], list(claim.grounding_path.node_ids) or ([anchor] if anchor else []), anchor


def highlight_stylesheet(
    base: list[dict],
    selected_claims: list[ClaimRecord],
    node_labels: dict[str, str],
) -> list[dict]:
    """Return base + appended highlight selectors (PURE; base never mutated).

    Path edges take the claim's STATUS hue; support nodes get a status-hue ring;
    each selected claim's anchor node gets the ACCENT outline + a numeric badge
    (identity != hue). Multiple claims sharing an anchor combine their badges.
    """
    appended: list[dict] = []
    anchor_badges: dict[str, list[str]] = {}
    path_node_hue: dict[str, str] = {}

    for badge, claim in enumerate(selected_claims, start=1):
        hue = theme.status_color(claim.status.value)
        edge_ids, node_ids, anchor = support_edges_and_nodes(claim)
        for eid in edge_ids:
            appended.append({
                "selector": f'edge[id = "{eid}"]',
                "style": {
                    "line-color": hue,
                    "target-arrow-color": hue,
                    "width": 4,
                    "z-index": 20,
                    "opacity": 1,
                },
            })
        for nid in node_ids:
            path_node_hue[nid] = hue
        if anchor:
            anchor_badges.setdefault(anchor, []).append(str(badge))

    # status-hue ring on support nodes (shows the path; hue == status)
    for nid, hue in path_node_hue.items():
        appended.append({
            "selector": f'node[id = "{nid}"]',
            "style": {"border-color": hue, "border-width": 3, "opacity": 1},
        })
    # accent outline + numeric badge on anchors (identity; wins over hue ring)
    for nid, badges in anchor_badges.items():
        label = node_labels.get(nid, nid)
        appended.append({
            "selector": f'node[id = "{nid}"]',
            "style": {
                "border-color": theme.ACCENT,
                "border-width": 5,
                "opacity": 1,
                "label": f"{label}  [{','.join(badges)}]",
                "font-weight": "bold",
            },
        })
    return list(base) + appended


def support_frequency_stylesheet(
    base: list[dict], support_frequency: dict[str, float]
) -> list[dict]:
    """Return base + appended selectors sizing nodes/edges by support-frequency.

    OBSERVATIONAL importance (§4.8): node size and edge width scale with the
    fraction of the N runs in which that KG item was used to ground a claim.
    Entity keys size NODES; triplet keys "<subj>|<prop>|<obj>" size the matching
    EDGE (id "<subj>-<prop>-<obj>"). PURE — base is never mutated.
    """
    appended: list[dict] = []
    for item, freq in support_frequency.items():
        f = max(0.0, min(1.0, freq))
        if "|" in item:  # triplet -> edge width
            edge_id = item.replace("|", "-")
            appended.append({
                "selector": f'edge[id = "{edge_id}"]',
                "style": {"width": 1.5 + 7.0 * f, "opacity": 0.35 + 0.6 * f},
            })
        else:  # entity -> node area (width == height)
            size = 40 + 56 * f
            appended.append({
                "selector": f'node[id = "{item}"]',
                "style": {"width": size, "height": size, "opacity": 0.45 + 0.55 * f},
            })
    return list(base) + appended


def node_labels_from_elements(elements: list[dict]) -> dict[str, str]:
    """Map node id -> label from a cytoscape element list."""
    return {
        e["data"]["id"]: e["data"].get("label", e["data"]["id"])
        for e in elements
        if "source" not in e["data"]
    }


def ego_elements(elements: list[dict], node_id: str, cap: int = SUBGRAPH_NODE_CAP) -> list[dict]:
    """Return the tapped node + its 1st-degree neighbours (edges between them).

    Neighbours beyond the cap are dropped (node-cap; SPEC-text §4.5 #3).
    """
    edges = [e for e in elements if "source" in e["data"]]
    nodes = {e["data"]["id"]: e for e in elements if "source" not in e["data"]}
    keep = {node_id}
    for e in edges:
        s, t = e["data"]["source"], e["data"]["target"]
        if s == node_id:
            keep.add(t)
        elif t == node_id:
            keep.add(s)
    if len(keep) > cap:
        keep = set(list(keep)[:cap])
    out: list[dict] = []
    for nid in keep:
        if nid in nodes:
            node = {"data": dict(nodes[nid]["data"])}
            if nid != node_id:
                node["data"]["faded"] = "1"  # neighbours de-emphasised
            out.append(node)
    for e in edges:
        if e["data"]["source"] in keep and e["data"]["target"] in keep:
            out.append(e)
    return out


def node_detail_content(node_data: dict | None) -> html.Div:
    """Entity-detail pane: static placeholder image + label/description.

    The image is a STATIC LOCAL placeholder asset (no image axis / no network).
    Literal value nodes show their value chip instead of an image.
    """
    if not node_data:
        return html.Div(
            "Tap a node to inspect the entity.",
            style={"color": theme.FAINT, "fontStyle": "italic", "fontSize": "0.8em"},
        )
    label = node_data.get("label") or node_data.get("id", "?")
    kind = node_data.get("kind", "entity")
    desc = node_data.get("description")

    if kind == "literal":
        media: html.Div = html.Div(
            label,
            style={
                "fontFamily": theme.MONO, "color": theme.MUTED, "fontStyle": "italic",
                "border": f"1px dashed {theme.FAINT}", "borderRadius": "6px",
                "padding": "10px", "textAlign": "center",
            },
        )
        title = "literal value"
    else:
        media = html.Img(
            src=PLACEHOLDER_IMG,
            alt=f"{label} (placeholder)",
            style={"width": "108px", "height": "120px", "borderRadius": "6px",
                   "flexShrink": "0"},
        )
        title = label

    body: list = [
        html.Div(title, style={"color": theme.TEXT, "fontWeight": "bold",
                               "marginBottom": "4px"}),
    ]
    if desc:
        body.append(html.Div(desc, style={"color": theme.MUTED, "fontSize": "0.8em",
                                           "lineHeight": "1.4"}))
    return html.Div(
        [media, html.Div(body, style={"marginLeft": "12px"})],
        style={"display": "flex", "alignItems": "flex-start"},
    )


def edge_detail_content(edge_data: dict, base_triple_ids: set[str]) -> html.Div:
    """Edge-detail pane: show the triple + a remove control (base triples only)."""
    label = edge_data.get("label", "")
    pid = edge_data.get("property_id", "")
    injected = edge_data.get("injected") == "1"
    rows: list = [
        html.Div(
            [html.Span("triple ", style={"color": theme.FAINT, "fontSize": "0.72em"}),
             html.Span(f"{edge_data.get('source', '?')} —[{label}]→ {edge_data.get('target', '?')}",
                       style={"color": theme.TEXT, "fontSize": "0.82em", "fontFamily": theme.MONO})],
            style={"marginBottom": "8px"},
        ),
    ]
    if injected:
        rows.append(html.Div("injected (CogMG) — remove it from the inject panel below.",
                             style={"color": "#3fb950", "fontSize": "0.74em"}))
    elif pid in base_triple_ids:
        rows.append(html.Button(
            "✕ remove this triple from the graph",
            id={"type": "remove-edge", "triple": pid},
            n_clicks=0,
            style={"background": theme.PANEL_ALT,
                   "color": theme.STATUS_COLORS[ClaimStatus.FABRICATED.value],
                   "border": f"1px solid {theme.STATUS_COLORS[ClaimStatus.FABRICATED.value]}",
                   "borderRadius": "4px", "padding": "3px 10px", "cursor": "pointer",
                   "fontFamily": theme.MONO, "fontSize": "0.74em"},
        ))
    return html.Div(rows)


def get_subgraph_panel(elements: list[dict]) -> html.Div:
    """Compose the Subgraph panel (overview state = all claim nodes + neighbours)."""
    return html.Div(
        [
            html.Div(
                [
                    html.Span("SUBGRAPH", style={"color": theme.MUTED, "fontSize": "0.75em",
                                                 "letterSpacing": "0.1em"}),
                    html.Button(
                        "⟲ reset view",
                        id="reset-view",
                        n_clicks=0,
                        style={
                            "float": "right", "background": theme.PANEL_ALT,
                            "color": theme.MUTED, "border": f"1px solid {theme.BORDER}",
                            "borderRadius": "4px", "fontSize": "0.72em",
                            "padding": "2px 8px", "cursor": "pointer",
                            "fontFamily": theme.MONO,
                        },
                    ),
                ],
                style={"marginBottom": "8px", "overflow": "hidden"},
            ),
            html.Div(
                "Brush claims (left) onto paths · tap a NODE to inspect/zoom · "
                "tap an EDGE to remove that triple from the graph.",
                style={"color": theme.FAINT, "fontSize": "0.72em", "marginBottom": "8px"},
            ),
            dash_cytoscape.Cytoscape(
                id="subgraph",
                elements=elements,
                stylesheet=BASE_STYLESHEET,
                layout={"name": "cose", "animate": False, "padding": 20},
                style={"width": "100%", "height": "430px", "background": theme.PANEL_ALT,
                       "border": f"1px solid {theme.BORDER}", "borderRadius": "6px"},
                responsive=True,
            ),
            html.Div(
                node_detail_content(None),
                id="entity-detail",
                style={
                    "marginTop": "10px", "minHeight": "70px",
                    "background": theme.PANEL_ALT, "border": f"1px solid {theme.BORDER}",
                    "borderRadius": "6px", "padding": "10px",
                },
            ),
        ],
        id="subgraph-panel",
        style=theme.panel_style(height="100%"),
    )
