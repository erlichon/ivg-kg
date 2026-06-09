"""DA2 — In-memory graph store: build, freeze, load, and render a KGSnapshot.

Row contract for build_snapshot (DA3 must conform to this):
===========================================================
Each row is a dict representing ONE triple of a domain entity.  The following
keys are recognised:

Required keys:
  subject_id      str  Wikidata QID (bare, e.g. "Q571") or full URI
                       (e.g. "http://www.wikidata.org/entity/Q571") — normalised
                       to the bare QID internally.
  subject_label   str  Human-readable label for the subject entity.
  property_id     str  Wikidata PID (bare, e.g. "P50") or full URI
                       (e.g. "http://www.wikidata.org/prop/direct/P50") — normalised.
  property_label  str  Human-readable label for the property.
  object_label    str  Display value: label for item-valued objects; the literal
                       string itself for time/quantity/monolingual/string values.
  value_type      str  One of "item", "time", "quantity", "monolingual", "string".
                       Any other value raises ValueError.

Optional keys (treated as None when absent or when the value is the empty string):
  subject_description  str|None  Free-text description of the subject entity.
  subject_sitelinks    str|None  Wikipedia sitelink count as a string; parsed to int.
  object_id            str|None  Wikidata QID (or URI) for item-valued objects.
                                 Must be absent or None for non-item value types.

Normalisation:
  QIDs and PIDs that arrive as full Wikidata entity/property URIs are stripped
  to their bare identifier (e.g. "Q571" or "P50").  Bare identifiers are
  accepted unchanged.  See _normalise_id() for details.

Literal-node convention (GR8 depends on this):
===============================================
For each KGEdge whose object_id is None (non-item value), build_networkx()
creates a synthetic "literal node" with:
  id     = f"lit:{value_type}:{object_label}"  (stable, derived from value only)
  kind   = "literal"                             (GR8 filters on this attribute)
  label  = object_label                         (display value)

Two subjects that share the same value_type + object_label produce the SAME
literal node id and therefore connect to a SINGLE shared node.  This shared-
literal structure is required by the §6 "spurious shared-literal path" test
(TS2).

KGSnapshot.nodes stores ONLY entity nodes (subject entities + item-valued
object entities).  Literal nodes are derived at NetworkX-build time and are
NOT stored in the frozen JSON snapshot (Invariant #10).

No pickle is used anywhere in this module (Invariant #10).
No provider SDKs, no network calls (Invariants #7, #9).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx

from ivg_kg.schema import KGEdge, KGNode, KGSnapshot, ValueType

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ENTITY_URI_PREFIX = "http://www.wikidata.org/entity/"
_PROP_URI_PREFIXES = (
    "http://www.wikidata.org/prop/direct/",
    "http://www.wikidata.org/prop/",
)


def _normalise_id(raw: str | None) -> str | None:
    """Strip a full Wikidata URI to a bare QID or PID.

    Accepts:
      "http://www.wikidata.org/entity/Q571"          -> "Q571"
      "http://www.wikidata.org/prop/direct/P50"       -> "P50"
      "http://www.wikidata.org/prop/P50"              -> "P50"
      "Q571"                                          -> "Q571"  (unchanged)
      None                                            -> None    (unchanged)
    """
    if raw is None:
        return None
    if raw.startswith(_ENTITY_URI_PREFIX):
        return raw[len(_ENTITY_URI_PREFIX):]
    for prefix in _PROP_URI_PREFIXES:
        if raw.startswith(prefix):
            return raw[len(prefix):]
    return raw


def _parse_sitelinks(value: str | None) -> int | None:
    """Parse a sitelink count string to int, or return None if absent/empty."""
    if value is None or value == "":
        return None
    return int(value)


def _literal_node_id(value_type: str, object_label: str) -> str:
    """Derive a stable, deterministic id for a literal node.

    Convention: "lit:<value_type>:<object_label>"
    Equal value_type + object_label always yield the same id, so two subjects
    with the same literal value share a single node (Invariant #4).
    """
    return f"lit:{value_type}:{object_label}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_snapshot(
    rows: list[dict[str, Any]],
    *,
    snapshot_id: str,
    slice: str,  # noqa: A002  — matches KGSnapshot field name
    domain_qid: str,
    meta: dict[str, Any] | None = None,
) -> KGSnapshot:
    """Build a KGSnapshot from a list of triple rows.

    See module docstring for the full row-key contract.

    Parameters
    ----------
    rows:
        List of dicts, each describing one triple.  See module docstring.
    snapshot_id:
        Unique identifier for this snapshot.
    slice:
        Dataset slice name (e.g. "books").
    domain_qid:
        QID of the focal entity for this snapshot.
    meta:
        Optional metadata dict (defaults to empty dict).

    Returns
    -------
    KGSnapshot with:
    - One KGEdge per row, deterministically ordered by (subject_id, property_id,
      object_id or object_label).
    - Deduplicated KGNodes for every subject entity and every item-valued object
      entity, deterministically ordered by id.  Subject-entity attributes
      (description, sitelinks) are taken from the first row that provides them.
    - NO literal nodes in KGSnapshot.nodes (literals live in the NetworkX graph).
    """
    entity_nodes: dict[str, KGNode] = {}
    edges: list[KGEdge] = []

    for row in rows:
        # --- normalise ids ---
        subject_id = _normalise_id(row["subject_id"])
        property_id = _normalise_id(row["property_id"])
        raw_object_id = row.get("object_id")
        object_id = _normalise_id(raw_object_id) if raw_object_id else None

        # --- subject node (first occurrence wins for description/sitelinks) ---
        if subject_id not in entity_nodes:
            entity_nodes[subject_id] = KGNode(
                id=subject_id,
                label=row["subject_label"],
                description=row.get("subject_description") or None,
                sitelinks=_parse_sitelinks(row.get("subject_sitelinks")),
                kind="entity",
            )

        # --- value_type: raise clearly on unknown values ---
        raw_vt = row["value_type"]
        try:
            value_type = ValueType(raw_vt)
        except ValueError:
            raise ValueError(
                f"Unknown value_type {raw_vt!r}. "
                f"Expected one of: {[v.value for v in ValueType]}"
            ) from None

        # --- item-valued object node ---
        if object_id and object_id not in entity_nodes:
            entity_nodes[object_id] = KGNode(
                id=object_id,
                label=row["object_label"],
                description=None,
                sitelinks=None,
                kind="entity",
            )

        # --- edge ---
        edges.append(
            KGEdge(
                subject_id=subject_id,
                property_id=property_id,
                property_label=row["property_label"],
                object_id=object_id,
                object_label=row["object_label"],
                value_type=value_type,
            )
        )

    # --- deterministic ordering (Invariant #9) ---
    sorted_nodes = sorted(entity_nodes.values(), key=lambda n: n.id)
    sorted_edges = sorted(
        edges,
        key=lambda e: (e.subject_id, e.property_id, e.object_id or "", e.object_label),
    )

    return KGSnapshot(
        snapshot_id=snapshot_id,
        slice=slice,
        domain_qid=domain_qid,
        nodes=sorted_nodes,
        edges=sorted_edges,
        meta=meta if meta is not None else {},
    )


def freeze_snapshot(snapshot: KGSnapshot, dir_path: Path | str) -> Path:
    """Write a KGSnapshot to canonical JSON at <dir_path>/snapshot.json.

    The directory is created if it does not exist.  The JSON is produced by
    Pydantic's model_dump_json() which guarantees stable key order.  No pickle
    is written (Invariant #10).

    Parameters
    ----------
    snapshot:
        The KGSnapshot to freeze.
    dir_path:
        Target directory.  Created (with parents) if absent.

    Returns
    -------
    Path to the directory that was written (same as dir_path, as a Path object).
    """
    target = Path(dir_path)
    target.mkdir(parents=True, exist_ok=True)
    json_path = target / "snapshot.json"
    json_path.write_text(snapshot.model_dump_json(), encoding="utf-8")
    return target


def load_snapshot(dir_path: Path | str) -> KGSnapshot:
    """Load a KGSnapshot from <dir_path>/snapshot.json.

    Uses Pydantic model_validate_json() for full schema validation.
    No pickle is used (Invariant #10).

    Parameters
    ----------
    dir_path:
        Directory containing snapshot.json (as written by freeze_snapshot).

    Returns
    -------
    Validated KGSnapshot instance.
    """
    json_path = Path(dir_path) / "snapshot.json"
    return KGSnapshot.model_validate_json(json_path.read_text(encoding="utf-8"))


def build_networkx(snapshot: KGSnapshot) -> nx.MultiDiGraph:
    """Build a directed multigraph from a KGSnapshot.

    Node conventions:
      - Entity nodes: one per KGNode in snapshot.nodes, attributes include
        id, label, description, sitelinks, kind (always "entity" for KGNodes).
      - Literal nodes: one per unique (value_type, object_label) pair from
        literal-valued edges (object_id is None).  id = "lit:<vt>:<label>",
        kind = "literal".  Equal literal values share a SINGLE node so that
        two subjects that share a literal are connected through it (Invariant #4).

    Edge conventions:
      - Every KGEdge becomes a directed edge subject_id -> object_id (item)
        or subject_id -> literal_node_id (literal).
      - Edge attributes: property_id, property_label, value_type (str), object_label.

    GR8 note: use g.to_undirected() for path search; exclude nodes with
    kind == "literal" as intermediate waypoints (Invariant #4).

    No pickle (Invariant #10).  Build is deterministic and reproducible purely
    from the JSON snapshot.

    Parameters
    ----------
    snapshot:
        A KGSnapshot as produced by build_snapshot() or load_snapshot().

    Returns
    -------
    nx.MultiDiGraph with entity + literal nodes and directed triple edges.
    """
    g: nx.MultiDiGraph = nx.MultiDiGraph()

    # --- add entity nodes ---
    for node in snapshot.nodes:
        g.add_node(
            node.id,
            label=node.label,
            kind=node.kind,
            description=node.description,
            sitelinks=node.sitelinks,
            image_path=node.image_path,
        )

    # --- add edges (and literal nodes as needed) ---
    for edge in snapshot.edges:
        if edge.object_id is not None:
            # item-valued edge
            target = edge.object_id
            # ensure the target node exists even if the snapshot omitted it
            # (defensive: should not happen if build_snapshot is correct)
            if target not in g:
                g.add_node(target, label=edge.object_label, kind="entity")
        else:
            # literal-valued edge: create/reuse shared literal node
            lit_id = _literal_node_id(edge.value_type.value, edge.object_label)
            if lit_id not in g:
                g.add_node(
                    lit_id,
                    label=edge.object_label,
                    kind="literal",
                    value_type=edge.value_type.value,
                    object_label=edge.object_label,
                )
            target = lit_id

        g.add_edge(
            edge.subject_id,
            target,
            property_id=edge.property_id,
            property_label=edge.property_label,
            value_type=edge.value_type.value,
            object_label=edge.object_label,
        )

    return g


def nx_to_cyto_elements(snapshot: KGSnapshot) -> list[dict[str, Any]]:
    """Convert a KGSnapshot to dash-cytoscape elements.

    Builds the NetworkX graph internally, then emits:
      - Node elements: {"data": {"id": <id>, "label": <label>, "kind": <kind>}}
      - Edge elements: {"data": {"id": "<subj>-<prop>-<obj_or_lit_id>",
                                 "source": <subj>, "target": <obj_or_lit_id>,
                                 "label": <property_label>}}

    Edge-id convention matches the established mock fixture contract:
      "<subject_id>-<property_id>-<object_or_literal_node_id>"

    Referential integrity is guaranteed: every edge's source and target exist as
    node elements (literal nodes are included as cyto nodes).

    Output is deterministic (nodes sorted by id, edges sorted by id).

    Parameters
    ----------
    snapshot:
        A KGSnapshot as produced by build_snapshot() or load_snapshot().

    Returns
    -------
    List of cytoscape element dicts (nodes first, then edges, both sorted by id).
    """
    g = build_networkx(snapshot)

    # nodes — sorted by id for determinism
    node_elements: list[dict[str, Any]] = []
    for node_id in sorted(g.nodes()):
        data = g.nodes[node_id]
        node_data: dict[str, Any] = {
            "id": node_id,
            "label": data.get("label", node_id),
            "kind": data.get("kind", "entity"),
        }
        # Surface description + image_path when present so the UI entity-detail
        # pane can show them (SPEC-text §4.5: show the entity image when present).
        # image_path is a demo-visual (P18), not grounding evidence in the books spine.
        if data.get("description") is not None:
            node_data["description"] = data["description"]
        if data.get("image_path") is not None:
            node_data["image_path"] = data["image_path"]
        node_elements.append({"data": node_data})

    # edges — sorted by id for determinism
    edge_elements: list[dict[str, Any]] = []
    seen_edge_ids: set[str] = set()
    raw_edges: list[tuple[str, str, str, dict]] = []

    for subj, tgt, edge_data in g.edges(data=True):
        prop_id = edge_data.get("property_id", "")
        edge_id = f"{subj}-{prop_id}-{tgt}"
        raw_edges.append((edge_id, subj, tgt, edge_data))

    for edge_id, subj, tgt, edge_data in sorted(raw_edges, key=lambda t: t[0]):
        if edge_id in seen_edge_ids:
            continue
        seen_edge_ids.add(edge_id)
        edge_elements.append(
            {
                "data": {
                    "id": edge_id,
                    "source": subj,
                    "target": tgt,
                    "label": edge_data.get("property_label", ""),
                }
            }
        )

    return node_elements + edge_elements


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------
# Freeze/load go exclusively through JSON (model_dump_json / model_validate_json).
# No serialisation via the pickle protocol is used or permitted in this module.
__all__ = [
    "build_snapshot",
    "freeze_snapshot",
    "load_snapshot",
    "build_networkx",
    "nx_to_cyto_elements",
]
