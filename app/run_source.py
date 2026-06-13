"""Data-source seam for the IVG-KG Dash app (config-flag run-loader shim).

Selects between MOCK mode and REAL mode based on the IVG_KG_RUN_ID env var:

  MOCK mode (default, IVG_KG_RUN_ID unset or empty):
    All four getters delegate to the mock_* fixtures. Behaviour is byte-identical
    to calling mock_grounding_run() / mock_subgraph_elements() / etc. directly.

  REAL mode (IVG_KG_RUN_ID set to a run id):
    Loads data/runs/<IVG_KG_RUN_ID>.json, derives the support subgraph from the
    claim paths (not from a full KG snapshot -- the run does not embed the whole
    KG, but the union of grounded claim paths is the correct, sufficient subgraph),
    and delegates diagnostics to the real diagnostics module.

    If the file is missing, the module fails LOUDLY with a clear error naming the
    expected path -- it NEVER falls back silently to mock (that would mask a broken
    real-run path during verification).

Launch in REAL mode:
    IVG_KG_RUN_ID=slice-01-glass-menagerie uv run python -m app.app

RUNS_DIR is a module-level Path; tests can monkeypatch it to point at a tmp dir.
"""
from __future__ import annotations

import os
from pathlib import Path

from ivg_kg.data.graph_store import nx_to_cyto_elements
from ivg_kg.diagnostics import aggregate_runset, single_run_summary
from ivg_kg.mock.fixtures import (
    mock_answer_diagnostics,
    mock_grounding_run,
    mock_single_run_summary,
    mock_subgraph_elements,
)
from ivg_kg.schema import (
    AnswerDiagnostics,
    GroundingRun,
    KGEdge,
    KGNode,
    KGSnapshot,
    SingleRunStatusSummary,
    ValueType,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Default run output directory -- matches scripts/emit_slice_runs.py convention.
RUNS_DIR: Path = Path(__file__).parent.parent / "data" / "runs"


def _run_id() -> str | None:
    """Return IVG_KG_RUN_ID from the environment, or None if unset/empty."""
    val = os.environ.get("IVG_KG_RUN_ID", "").strip()
    return val if val else None


# ---------------------------------------------------------------------------
# Internal: REAL mode helpers
# ---------------------------------------------------------------------------

def _load_run(run_id: str) -> GroundingRun:
    """Load and validate a GroundingRun from RUNS_DIR/<run_id>.json.

    Raises FileNotFoundError with a clear message if the file is absent --
    the generator (scripts/emit_slice_runs.py) must be run first.
    """
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"REAL mode requested run '{run_id}' but the file does not exist: {path}\n"
            f"Run the generator first:\n"
            f"    uv run python scripts/emit_slice_runs.py"
        )
    return GroundingRun.model_validate_json(path.read_text(encoding="utf-8"))


def _derive_subgraph_snapshot(run: GroundingRun) -> KGSnapshot:
    """Build a KGSnapshot from the union of grounded claim support paths.

    The run does not embed the full KG. The support-graph derived from claim
    paths is the correct and sufficient subgraph for rendering + claim-click
    highlighting. For each grounded claim, the grounding_path carries PathEdges
    with subject/object ids+labels and linked_entities carries additional nodes.

    FABRICATED claims have empty grounding_paths and contribute nothing.
    """
    entity_nodes: dict[str, KGNode] = {}
    edges: list[KGEdge] = []
    seen_edges: set[tuple[str, str, str | None]] = set()

    for claim in run.claims:
        # Collect entity nodes from linked_entities (for all claims -- these
        # are always resolved even when the claim is fabricated, and they anchor
        # the node in the subgraph so it appears when selected).
        for ent in claim.linked_entities:
            if ent.id not in entity_nodes:
                entity_nodes[ent.id] = KGNode(
                    id=ent.id,
                    label=ent.label,
                    description=ent.description,
                    kind="entity",
                )

        # Collect path nodes + edges from grounding_path (only grounded claims
        # have non-empty paths, so this is a no-op for FABRICATED claims).
        for path_node_id in claim.grounding_path.node_ids:
            # node_ids may not have labels; we'll patch them from edges below.
            if path_node_id not in entity_nodes:
                entity_nodes[path_node_id] = KGNode(
                    id=path_node_id,
                    label=path_node_id,  # fallback; patched below from edge data
                    kind="entity",
                )

        for pe in claim.grounding_path.edges:
            # Ensure subject and object nodes exist with proper labels.
            if pe.subject_id not in entity_nodes:
                entity_nodes[pe.subject_id] = KGNode(
                    id=pe.subject_id,
                    label=pe.subject_label,
                    kind="entity",
                )
            else:
                # Patch label if the placeholder was inserted before edge data.
                node = entity_nodes[pe.subject_id]
                if node.label == pe.subject_id:
                    entity_nodes[pe.subject_id] = node.model_copy(
                        update={"label": pe.subject_label}
                    )

            # Determine object: item-valued or literal.
            if pe.object_id is not None:
                obj_id: str | None = pe.object_id
                if obj_id not in entity_nodes:
                    entity_nodes[obj_id] = KGNode(
                        id=obj_id,
                        label=pe.object_label,
                        kind="entity",
                    )
                else:
                    node = entity_nodes[obj_id]
                    if node.label == obj_id:
                        entity_nodes[obj_id] = node.model_copy(
                            update={"label": pe.object_label}
                        )
                value_type = ValueType.ITEM
            else:
                obj_id = None
                value_type = ValueType.STRING  # literal-valued edge

            edge_key = (pe.subject_id, pe.property_id, obj_id)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                # NOTE: literal edges (object_id=None) produce support_frequency key
                # "<subj>|<prop>|None" but a cyto edge id ending in "lit:<type>:<label>",
                # so literal support edges are NOT brushed by the multi-run
                # support_frequency stylesheet; fix belongs in the diagnostics/stylesheet
                # key convention, not here.
                edges.append(
                    KGEdge(
                        subject_id=pe.subject_id,
                        property_id=pe.property_id,
                        property_label=pe.property_label,
                        object_id=obj_id,
                        object_label=pe.object_label,
                        value_type=value_type,
                    )
                )

    # Build a minimal snapshot from the collected nodes + edges.
    sorted_nodes = sorted(entity_nodes.values(), key=lambda n: n.id)
    sorted_edges = sorted(
        edges,
        key=lambda e: (e.subject_id, e.property_id, e.object_id or "", e.object_label),
    )
    return KGSnapshot(
        snapshot_id=f"{run.run_id}-support-subgraph",
        slice=run.slice,
        domain_qid=run.claims[0].linked_entities[0].id if run.claims and run.claims[0].linked_entities else "unknown",
        nodes=sorted_nodes,
        edges=sorted_edges,
        meta={"source": "claim_paths", "run_id": run.run_id},
    )


def _load_slice_runs(primary_run: GroundingRun) -> list[GroundingRun]:
    """Load all runs from RUNS_DIR that share the primary run's slice.

    Includes the primary run itself. If fewer runs exist than requested via n in
    get_answer_diagnostics, that is fine -- aggregate_runset accepts any count >= 1.
    """
    runs: list[GroundingRun] = [primary_run]
    try:
        for path in sorted(RUNS_DIR.glob("*.json")):
            if path.stem == primary_run.run_id:
                # Already included as primary_run.
                continue
            try:
                candidate = GroundingRun.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                if candidate.slice == primary_run.slice:
                    runs.append(candidate)
            except Exception:
                # Skip malformed run files; the primary run is already included.
                continue
    except Exception:
        # RUNS_DIR may be inaccessible (e.g. in test environments). Primary run
        # is already included; aggregate over that one.
        pass
    return runs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_grounding_run() -> GroundingRun:
    """Return the GroundingRun for the current mode.

    MOCK mode: returns mock_grounding_run().
    REAL mode: loads RUNS_DIR/<IVG_KG_RUN_ID>.json; fails loudly if absent.
    """
    rid = _run_id()
    if rid is None:
        return mock_grounding_run()
    return _load_run(rid)


def get_subgraph_elements() -> list[dict]:
    """Return dash-cytoscape elements for the current mode.

    MOCK mode: returns mock_subgraph_elements().
    REAL mode: derives the support subgraph from the loaded run's claim paths,
               then converts to cytoscape elements via graph_store.
    """
    rid = _run_id()
    if rid is None:
        return mock_subgraph_elements()
    run = _load_run(rid)
    snapshot = _derive_subgraph_snapshot(run)
    return nx_to_cyto_elements(snapshot)


def get_single_run_summary() -> SingleRunStatusSummary:
    """Return the single-run status summary for the current mode.

    MOCK mode: returns mock_single_run_summary().
    REAL mode: computes diagnostics.single_run_summary(run).
    """
    rid = _run_id()
    if rid is None:
        return mock_single_run_summary()
    run = _load_run(rid)
    return single_run_summary(run)


def get_answer_diagnostics(n: int) -> AnswerDiagnostics:
    """Return multi-run AnswerDiagnostics for the current mode.

    MOCK mode: returns mock_answer_diagnostics(n).
    REAL mode: loads all runs in RUNS_DIR that share the primary run's slice,
               takes up to n of them, then calls diagnostics.aggregate_runset.
               If fewer than n runs exist, aggregates what exists (fine for n>=1).
    """
    rid = _run_id()
    if rid is None:
        return mock_answer_diagnostics(n)
    primary = _load_run(rid)
    all_runs = _load_slice_runs(primary)
    capped = all_runs[:n] if len(all_runs) > n else all_runs
    return aggregate_runset(capped)
