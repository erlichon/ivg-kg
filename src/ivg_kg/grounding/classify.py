"""GR8 -- Three-way classifier cascade (VERIFIER correctness core, SPEC-text 4.3(C) + 4.8).

Composes the GR6 linker/canon and the GR7 entailment gate into the deterministic
three-way decision cascade and emits one ClaimRecord per claim:

    RETRIEVED              -- grounded in a single direct triple OR a content fact.
    REASONED_SUPPORTABLE   -- grounded by a multi-hop path through the KG.
    FABRICATED             -- no evidence above the entailment threshold.

This is the proper reimplementation of the simple-but-real cascade in
grounding/slice.py, using the real GR6/GR7 components and adding the real
spurious-path detectors. It is purely ADDITIVE; slice.py keeps working until a
later task rewires the backend.

Decision order (first match wins; SPEC-text 4.3(C)):
    1. Direct triple  -> RETRIEVED / DIRECT_TRIPLE (single-hop path).
    2. Content fact   -> RETRIEVED / TEXT_CONTENT (node-only path).
    3. Multi-hop path -> REASONED_SUPPORTABLE / MULTI_HOP_PATH (full path), then
       run the spurious-path detectors on the chosen path.
    4. else           -> FABRICATED / NONE (empty path; score = best near-miss).

Canonical-orientation rule (GR6 integration, load-bearing for support-frequency):
    Every PathEdge stored on a record has its (subject_id, property_id, object_id)
    canonicalized via PropertyCanon.canonical_triple BEFORE storage, with
    subject_label / object_label / traversed_forward set consistently with the
    canonical orientation. This makes diagnostics.triplet_key over the stored
    edges phrasing- and direction-stable, so support-frequency (sec 4.8)
    aggregates the SAME triplet across runs (e.g. P155 follows / P156 followed by
    collapse to one key).

spurious_path resolution (SPEC-text 4.8 + ClaimRecord docstring):
    spurious_path is set ONLY on a multi-hop REASONED_SUPPORTABLE claim whose path
    passed the value-sensitive gate but is NOT legitimate support. FABRICATED and
    RETRIEVED claims always have spurious_path=False. (SPEC 4.3(C) mentions setting
    it on FABRICATED; that is the slice's simplification and is SUPERSEDED here.)

Determinism (Invariants #8/#14): identical inputs -> identical ClaimRecord. The
gate's determinism is provided. Edge/label/path iteration follows snapshot order;
node pairs are taken in sorted entity-node order. Multi-hop path selection picks
the max-score path with an explicit tuple(node_path) lexicographic tie-break, so
the chosen path is independent of all_simple_paths yield order (which networkx
does not guarantee across versions). No randomness / time / network / pickle.

BOOKS-FIRST: no image-axis code (IMAGE_CONTENT exists in the enum but is never
produced here).
"""

from __future__ import annotations

import networkx as nx

from ivg_kg.data.graph_store import build_networkx
from ivg_kg.grounding.entailment import BaseEntailmentGate, _tokenise
from ivg_kg.grounding.link import PropertyCanon
from ivg_kg.schema import (
    ClaimRecord,
    ClaimStatus,
    ContentLabel,
    GradingReference,
    GroundingConfig,
    GroundingPath,
    KGEdge,
    LinkedEntity,
    PathEdge,
    SupportSource,
)

__all__ = [
    "Classifier",
    "classify_claims",
    "HUB_DEGREE",
    "MARGIN_EPS",
    "REASON_RELATION_ILLEGITIMATE",
    "REASON_VALUE_ABSENT",
    "REASON_HUB_FRAGILITY",
]

# ---------------------------------------------------------------------------
# Spurious-path detector constants (SPEC-text 4.8). Documented module-level
# constants, NOT config fields (the schema/GroundingConfig is frozen for GR8).
# ---------------------------------------------------------------------------

# (2) hub/length fragility: an intermediate node with degree >= HUB_DEGREE is a
# popular "hub" (e.g. a genre or country) that many entities connect through;
# routing a maximal-length path through it on a thin entailment margin is
# fragile, not robust support.
HUB_DEGREE: int = 8

# (2) hub/length fragility: the path's entailment margin above tau must be
# <= MARGIN_EPS for the hub-fragility detector to fire (a barely-passing path).
MARGIN_EPS: float = 0.05

# ---------------------------------------------------------------------------
# Spurious-reason vocabulary (SPEC-text 4.8).
# These string values are stable contract identifiers used in ClaimRecord and
# tests. Use these constants throughout code to avoid typo-drift.
# ---------------------------------------------------------------------------

REASON_RELATION_ILLEGITIMATE: str = "relation_illegitimate"
REASON_VALUE_ABSENT: str = "value_absent"
REASON_HUB_FRAGILITY: str = "hub_fragility"


# ---------------------------------------------------------------------------
# Serialisation helpers (mirror slice.py semantics)
# ---------------------------------------------------------------------------


def _serialise_edge(edge: KGEdge, node_labels: dict[str, str]) -> str:
    """Serialise a KGEdge to a human-readable premise string.

    Uses the node-label map so the subject appears as a readable string rather
    than a bare QID. Mirrors slice._serialise_edge.
    """
    subj_label = node_labels.get(edge.subject_id, edge.subject_id)
    return f"{subj_label} {edge.property_label} {edge.object_label}"


def _serialise_path(path_edges: list[PathEdge]) -> str:
    """Serialise a list of PathEdge to a single premise string."""
    return " ".join(
        f"{pe.subject_label} {pe.property_label} {pe.object_label}" for pe in path_edges
    )


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class Classifier:
    """Deterministic three-way claim classifier (GR8).

    Precomputes fixed state once (node-label map, entity-label set, directed and
    undirected NetworkX views, node degrees) so classify() does NOT rebuild the
    graph per claim (the slice does; this must not).
    """

    def __init__(
        self,
        reference: GradingReference,
        *,
        gate: BaseEntailmentGate,
        canon: PropertyCanon,
        config: GroundingConfig,
    ) -> None:
        self._reference = reference
        self._gate = gate
        self._canon = canon
        self._config = config

        snapshot = reference.snapshot
        self._node_labels: dict[str, str] = {n.id: n.label for n in snapshot.nodes}

        # Built once. Directed view drives edge-direction recovery; undirected
        # view drives path search.
        self._graph: nx.MultiDiGraph = build_networkx(snapshot)
        self._undirected = self._graph.to_undirected()

        # Node kind + degree maps (degree from the undirected view for the hub
        # detector; counts all incident edges regardless of direction).
        self._node_kind: dict[str, str] = {
            n: d.get("kind", "entity") for n, d in self._graph.nodes(data=True)
        }
        self._degree: dict[str, int] = dict(self._undirected.degree())

        # Entity nodes only (literals excluded as endpoints AND waypoints),
        # sorted for deterministic pair enumeration.
        self._entity_nodes: list[str] = sorted(
            n for n, k in self._node_kind.items() if k == "entity"
        )

    # -- node-label lookup ------------------------------------------------

    def _node_label(self, node_id: str) -> str:
        return self._node_labels.get(node_id, node_id)

    # -- canonical PathEdge construction ----------------------------------

    def _make_path_edge(
        self,
        subject_id: str,
        property_id: str,
        property_label: str,
        object_id: str | None,
        object_label: str,
        *,
        traversed_forward: bool,
    ) -> PathEdge:
        """Build a PathEdge with its triple canonicalized via GR6 PropertyCanon.

        The stored (subject_id, property_id, object_id) is canonical so
        diagnostics.triplet_key over it is direction-stable. When the canon flips
        an inverse-pair triple (e.g. P156 -> P155), subject and object swap; the
        labels follow the swap and traversed_forward is inverted to stay
        consistent with the new orientation.
        """
        canon_s, canon_p, canon_o = self._canon.canonical_triple(subject_id, property_id, object_id)
        flipped = canon_s != subject_id or canon_o != object_id

        if flipped:
            # Subject/object swapped by the canon. Labels follow; the canonical
            # property keeps its original surface label (we only have one label
            # string available, the pre-flip property_label -- acceptable since
            # the canonical property is the same relation in the inverse phrasing).
            new_subject_label = object_label
            new_object_label = self._node_label(subject_id)
            new_traversed = not traversed_forward
        else:
            new_subject_label = self._node_label(subject_id)
            new_object_label = object_label
            new_traversed = traversed_forward

        return PathEdge(
            subject_id=canon_s,
            subject_label=new_subject_label,
            property_id=canon_p,
            property_label=property_label,
            object_id=canon_o,
            object_label=new_object_label,
            traversed_forward=new_traversed,
        )

    def _path_from_edge(self, edge: KGEdge) -> GroundingPath:
        """Single-hop GroundingPath for a direct triple (canonical-oriented)."""
        if edge.object_id is not None:
            object_node_id = edge.object_id
        else:
            object_node_id = f"lit:{edge.value_type.value}:{edge.object_label}"
        path_edge = self._make_path_edge(
            edge.subject_id,
            edge.property_id,
            edge.property_label,
            edge.object_id,
            edge.object_label,
            traversed_forward=True,
        )
        # node_ids reflect the canonical orientation of the stored edge.
        if path_edge.object_id is not None:
            node_ids = [path_edge.subject_id, path_edge.object_id]
        else:
            # Literal object: the canon never flips when object_id is None, so
            # subject is unchanged and the literal node id is stable.
            node_ids = [edge.subject_id, object_node_id]
        return GroundingPath(edges=[path_edge], node_ids=node_ids)

    # -- cascade stages ---------------------------------------------------

    def _best_direct_triple(self, claim_text: str) -> tuple[float, KGEdge | None]:
        """Max gate score over all snapshot edges; ties keep the first in order."""
        best_score = 0.0
        best_edge: KGEdge | None = None
        for edge in self._reference.snapshot.edges:
            premise = _serialise_edge(edge, self._node_labels)
            score = self._gate.entails(premise, claim_text)
            if score > best_score:
                best_score = score
                best_edge = edge
        return best_score, best_edge

    def _best_content_label(self, claim_text: str) -> tuple[float, ContentLabel | None]:
        """Max gate score over all content labels; ties keep the first in order."""
        best_score = 0.0
        best_label: ContentLabel | None = None
        for cl in self._reference.content_labels:
            score = self._gate.entails(cl.fact, claim_text)
            if score > best_score:
                best_score = score
                best_label = cl
        return best_score, best_label

    def _path_to_edges(self, node_path: list[str]) -> list[PathEdge] | None:
        """Convert a node path to canonical PathEdges; None if any hop has no edge."""
        path_edges: list[PathEdge] = []
        for u, v in zip(node_path[:-1], node_path[1:], strict=False):
            if self._graph.has_edge(u, v):
                edge_data = next(iter(self._graph[u][v].values()))
                forward = True
            elif self._graph.has_edge(v, u):
                edge_data = next(iter(self._graph[v][u].values()))
                forward = False
            else:
                return None

            src_id = u if forward else v
            tgt_id = v if forward else u
            tgt_is_entity = self._node_kind.get(tgt_id, "entity") == "entity"
            path_edges.append(
                self._make_path_edge(
                    src_id,
                    edge_data.get("property_id", ""),
                    edge_data.get("property_label", ""),
                    tgt_id if tgt_is_entity else None,
                    edge_data.get("object_label", ""),
                    traversed_forward=forward,
                )
            )
        return path_edges

    def _best_multi_hop(
        self, claim_text: str
    ) -> tuple[float, GroundingPath | None, list[str] | None]:
        """Max-entailment 2..k-hop path over entity-node pairs (literals excluded).

        Returns (best_score, best_path, best_node_path). Endpoints and waypoints
        are entity nodes only. Enumeration order is deterministic: entity nodes
        are pre-sorted and pairs are taken in sorted order.

        Tie-breaking is EXPLICIT and version-independent: when two paths yield
        the same entailment score, the winner is determined by comparing
        tuple(node_path) lexicographically. This makes the chosen path
        independent of all_simple_paths yield order (which networkx does not
        guarantee to be stable across versions).
        """
        k_hops = self._config.k_hops
        best_score = 0.0
        best_path: GroundingPath | None = None
        best_node_path: list[str] | None = None

        nodes = self._entity_nodes
        for i, src in enumerate(nodes):
            for tgt in nodes[i + 1 :]:
                try:
                    candidate_paths = nx.all_simple_paths(self._undirected, src, tgt, cutoff=k_hops)
                except (nx.NetworkXError, nx.exception.NodeNotFound):
                    continue

                for node_path in candidate_paths:
                    if len(node_path) < 3:  # need >= 2 hops (>= 3 nodes)
                        continue
                    # Intermediate waypoints must be entity nodes (no literals).
                    intermediates = node_path[1:-1]
                    if any(self._node_kind.get(n, "entity") == "literal" for n in intermediates):
                        continue

                    path_edges = self._path_to_edges(node_path)
                    if path_edges is None:
                        continue
                    premise = _serialise_path(path_edges)
                    score = self._gate.entails(premise, claim_text)
                    # Explicit tie-break: prefer the tuple(node_path)-lexicographically
                    # smaller path so the result is independent of yield order.
                    node_path_key = tuple(node_path)
                    best_node_path_key = (
                        tuple(best_node_path) if best_node_path is not None else None
                    )
                    if score > best_score or (
                        score == best_score
                        and best_node_path_key is not None
                        and node_path_key < best_node_path_key
                    ):
                        best_score = score
                        best_path = GroundingPath(edges=path_edges, node_ids=list(node_path))
                        best_node_path = list(node_path)

        return best_score, best_path, best_node_path

    # -- spurious-path detectors (only on multi-hop Supportable) ----------

    def _detect_spurious(
        self,
        path: GroundingPath,
        node_path: list[str],
        best_score: float,
        relation_surface: str | None,
        object_surface: str | None,
    ) -> tuple[bool, str | None]:
        """Run the spurious-path detectors in priority order on a chosen path.

        Returns (spurious_path, spurious_reason). Detector (3) route-non-robustness
        reuses edit-the-KG re-runs and is DEFERRED (out of scope for GR8).
        """
        premise = _serialise_path(path.edges)

        # (1a) relation-allowlist illegitimacy.
        if relation_surface is not None:
            target_pid = self._canon.canonical_property(relation_surface)
            if target_pid is not None:
                edge_pids = {
                    self._canon.canonical_property(pe.property_id) or pe.property_id
                    for pe in path.edges
                }
                if target_pid not in edge_pids:
                    return True, REASON_RELATION_ILLEGITIMATE

        # (1b) value-absent: asserted object value missing from the path premise.
        # Slice-grade lexical heuristic: can over/under-fire on multi-token or
        # punctuated object surfaces; superseded by the model gate downstream.
        if object_surface is not None and object_surface.strip():
            obj_tokens = _tokenise(object_surface)
            premise_tokens = _tokenise(premise)
            if obj_tokens and not obj_tokens.issubset(premise_tokens):
                return True, REASON_VALUE_ABSENT

        # (2) hub/length fragility.
        hops = len(path.edges)
        if hops == self._config.k_hops:
            intermediates = node_path[1:-1]
            through_hub = any(self._degree.get(n, 0) >= HUB_DEGREE for n in intermediates)
            margin = best_score - self._config.tau
            if through_hub and margin <= MARGIN_EPS:
                return True, REASON_HUB_FRAGILITY

        return False, None

    # -- public surface ---------------------------------------------------

    def classify(
        self,
        claim_text: str,
        linked_entities: list[LinkedEntity],
        *,
        claim_id: str,
        relation_surface: str | None = None,
        object_surface: str | None = None,
        active_perturbations: list[str] | None = None,
        unresolved_entities: list[str] | None = None,
    ) -> ClaimRecord:
        """Classify one claim against the FULL grading reference.

        active_perturbations is recorded for attribution only and MUST NOT alter
        any decision (Invariant #1): grading is always against the full reference.
        """
        perts = list(active_perturbations) if active_perturbations else []
        unresolved = list(unresolved_entities) if unresolved_entities else []
        tau = self._config.tau

        def _record(
            status: ClaimStatus,
            support_source: SupportSource,
            grounding_path: GroundingPath,
            entailment_score: float | None,
            *,
            spurious_path: bool = False,
            spurious_reason: str | None = None,
        ) -> ClaimRecord:
            return ClaimRecord(
                claim_id=claim_id,
                text=claim_text,
                status=status,
                support_source=support_source,
                linked_entities=list(linked_entities),
                grounding_path=grounding_path,
                active_perturbations=perts,
                entailment_score=entailment_score,
                spurious_path=spurious_path,
                spurious_reason=spurious_reason,
                unresolved_entities=unresolved,
            )

        # --- (1) Direct triple ---
        dt_score, dt_edge = self._best_direct_triple(claim_text)
        if dt_score > tau and dt_edge is not None:
            return _record(
                ClaimStatus.RETRIEVED,
                SupportSource.DIRECT_TRIPLE,
                self._path_from_edge(dt_edge),
                dt_score,
            )

        # --- (2) Content fact ---
        cl_score, cl_label = self._best_content_label(claim_text)
        if cl_score > tau and cl_label is not None:
            return _record(
                ClaimStatus.RETRIEVED,
                SupportSource.TEXT_CONTENT,
                GroundingPath(edges=[], node_ids=[cl_label.entity_id]),
                cl_score,
            )

        # --- (3) Multi-hop path ---
        mh_score, mh_path, mh_node_path = self._best_multi_hop(claim_text)
        if mh_score > tau and mh_path is not None and mh_node_path is not None:
            spurious, reason = self._detect_spurious(
                mh_path, mh_node_path, mh_score, relation_surface, object_surface
            )
            return _record(
                ClaimStatus.REASONED_SUPPORTABLE,
                SupportSource.MULTI_HOP_PATH,
                mh_path,
                mh_score,
                spurious_path=spurious,
                spurious_reason=reason,
            )

        # --- (4) FABRICATED ---
        best_near_miss = max(dt_score, cl_score, mh_score)
        return _record(
            ClaimStatus.FABRICATED,
            SupportSource.NONE,
            GroundingPath(edges=[], node_ids=[]),
            best_near_miss if best_near_miss > 0.0 else None,
        )


# ---------------------------------------------------------------------------
# Convenience wrapper (optional GR9 wiring helper)
# ---------------------------------------------------------------------------


def classify_claims(
    claims: list[tuple[str, list[LinkedEntity]]],
    reference: GradingReference,
    *,
    gate: BaseEntailmentGate,
    canon: PropertyCanon,
    config: GroundingConfig,
    active_perturbations: list[str] | None = None,
) -> list[ClaimRecord]:
    """Classify a batch of (claim_text, linked_entities) pairs with one Classifier.

    A thin convenience over Classifier for GR9 wiring; claim_id is assigned as
    c1, c2, ... within the batch (a WITHIN-RUN identifier only, per the schema).

    Note: this builds a fresh Classifier (and thus a fresh NetworkX graph) once
    per call. A long-lived caller running multiple batches or ablation conditions
    against the SAME reference should construct and reuse one Classifier directly
    so that the graph and the gate's score cache stay warm across calls.
    """
    classifier = Classifier(reference, gate=gate, canon=canon, config=config)
    records: list[ClaimRecord] = []
    for i, (claim_text, linked) in enumerate(claims):
        records.append(
            classifier.classify(
                claim_text,
                linked,
                claim_id=f"c{i + 1}",
                active_perturbations=active_perturbations,
            )
        )
    return records
