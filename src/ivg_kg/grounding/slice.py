"""SLICE component (#1a) -- deepened/replaced by GR5/GR6/GR7/GR8.

Simple-but-real grounding cascade for the vertical slice:

  claim_split   -- sentence/clause split (stand-in for GR5 extraction)
  link_claims   -- case-insensitive label/alias substring linker (stand-in for GR6)
  entails       -- token-overlap + value-sensitive gate (stand-in for GR7 NLI)
  cascade       -- decision-order classifier (stand-in for GR8)

No network calls, no model downloads, no provider SDKs.  Pure deterministic Python.

All helpers accept and return schema types from ivg_kg.schema.  The public entry
point is run_cascade(), called by backend.ground_response().
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

import networkx as nx

from ivg_kg.data.graph_store import build_networkx
from ivg_kg.schema import (
    ClaimRecord,
    ClaimStatus,
    ContentLabel,
    GradingReference,
    GroundingConfig,
    GroundingPath,
    KGEdge,
    KGSnapshot,
    LinkedEntity,
    PathEdge,
    SupportSource,
)

# ---------------------------------------------------------------------------
# Step 1: claim splitting (SLICE stand-in for GR5 extraction)
# ---------------------------------------------------------------------------
# Splits answer_text on sentence-ending punctuation followed by whitespace, or
# on semicolons.  Each non-empty unit becomes one claim.  Deterministic.

_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=;)\s*")


def split_claims(answer_text: str) -> list[str]:
    """Split answer_text into claim-sized units.

    SLICE stand-in for GR5 claim extraction.  Uses sentence-boundary split
    (`.!?` followed by whitespace, or `;`).  Strips whitespace; drops empties.
    Deterministic.
    """
    parts = _SPLIT_RE.split(answer_text.strip())
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Step 2: entity linking (SLICE stand-in for GR6)
# ---------------------------------------------------------------------------
# Case-insensitive substring match: a mention matches a node when the node's
# label appears as a substring of the mention (or the mention in the label).
# Uses only nodes from the snapshot (no external lookup).


def _normalise_text(s: str) -> str:
    """Lowercase, strip, NFC-normalise."""
    return unicodedata.normalize("NFC", s.strip().lower())


def link_entities(
    claim_text: str,
    snapshot: KGSnapshot,
) -> tuple[list[LinkedEntity], list[str]]:
    """Resolve entity mentions in claim_text to KGNode ids.

    SLICE stand-in for GR6 entity linking.  Uses case-insensitive label
    substring match: a node matches when its label is a substring of the
    claim (or vice versa).  Each matching node yields one LinkedEntity with
    link_score=1.0 (exact substring).

    Words in the claim that match NO node label go into unresolved_entities
    as individual tokens (best-effort; not the same as FABRICATED status).

    Returns
    -------
    (linked, unresolved)
        linked: list[LinkedEntity] for resolved nodes
        unresolved: list[str] mention strings that had no match
    """
    norm_claim = _normalise_text(claim_text)
    linked: list[LinkedEntity] = []
    matched_labels: set[str] = set()

    for node in snapshot.nodes:
        norm_label = _normalise_text(node.label)
        if not norm_label:
            continue
        # match: node label appears in claim OR claim fragment appears in label
        if norm_label in norm_claim or norm_claim in norm_label:
            linked.append(
                LinkedEntity(
                    id=node.id,
                    label=node.label,
                    description=node.description,
                    link_score=1.0,
                )
            )
            matched_labels.add(norm_label)

    # Collect unresolved: words in the claim not covered by any matched label.
    # Simple token-level check for brief unresolved tracking.
    tokens = re.findall(r"[A-Za-z]+", norm_claim)
    stop_words = {
        "a", "an", "the", "is", "was", "were", "are", "be", "been", "being",
        "has", "have", "had", "of", "in", "on", "at", "to", "for", "and",
        "or", "but", "with", "by", "from", "it", "its", "this", "that",
        "which", "who", "whom", "what", "when", "where", "how", "not",
        "no", "as", "also", "both",
    }
    covered: set[str] = set()
    for lbl in matched_labels:
        for tok in re.findall(r"[A-Za-z]+", lbl):
            covered.add(tok)
    unresolved = sorted(
        {t for t in tokens if t not in covered and t not in stop_words},
    )

    return linked, unresolved


# ---------------------------------------------------------------------------
# Step 3: entailment gate (SLICE stand-in for GR7 NLI)
# ---------------------------------------------------------------------------
# Deterministic token-overlap score: Jaccard over lowercase letter-tokens.
# PLUS a value-sensitive check: if the claim asserts a date, number, or named
# object that the premise contradicts or omits -> score forced below tau.
# Asymmetric: premise = serialised evidence; hypothesis = claim.

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenise(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


# Patterns that detect a concrete value assertion in the hypothesis.
_DATE_RE = re.compile(r"\b\d{4}\b|\b(?:january|february|march|april|may|june|july|august|"
                      r"september|october|november|december)\b", re.I)
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
# Named-object: a capitalised multi-word phrase (heuristic)
_NAMED_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+")


def _extract_values(text: str) -> set[str]:
    """Extract concrete value tokens (dates, numbers, named objects) from text."""
    vals: set[str] = set()
    for m in _DATE_RE.finditer(text):
        vals.add(m.group(0).lower())
    for m in _NUMBER_RE.finditer(text):
        vals.add(m.group(0))
    for m in _NAMED_RE.finditer(text):
        vals.add(m.group(0).lower())
    return vals


def entails(premise: str, hypothesis: str) -> float:
    """Compute a deterministic entailment score for (premise, hypothesis).

    SLICE stand-in for GR7 NLI gate.  Asymmetric: premise is the serialised
    evidence string; hypothesis is the claim text.

    Score = Jaccard(tokens(premise), tokens(hypothesis)).
    Value-sensitive override: if the hypothesis asserts a concrete value
    (date, number, named object) that is absent from or contradicted by the
    premise, the value-check hard-fail forces the score to 0.0.

    Returns a raw entailment score in [0, 1].  Thresholding against config.tau
    happens in the cascade (run_cascade), not here.
    """
    jaccard, _ = _entails_detailed(premise, hypothesis)
    return jaccard


def _entails_detailed(
    premise: str,
    hypothesis: str,
    entity_labels: frozenset[str] | None = None,
) -> tuple[float, bool]:
    """Return (score, value_blocked).

    score:         Jaccard when value check passes; 0.0 when value check fails.
    value_blocked: True when the value-sensitive check killed a non-zero jaccard.

    Used internally so the cascade can distinguish 'no lexical overlap' from
    'lexical overlap but wrong value' (the latter yields spurious_path=True).

    entity_labels: optional set of lowercased entity names from the KG snapshot.
    Named objects that match an entity label are treated as entity mentions
    (not concrete value assertions) and do not trigger value-blocking.  Without
    this set, named objects are treated as concrete value assertions.
    """
    if not premise or not hypothesis:
        return 0.0, False

    p_toks = _tokenise(premise)
    h_toks = _tokenise(hypothesis)
    union = p_toks | h_toks
    if not union:
        return 0.0, False

    jaccard = len(p_toks & h_toks) / len(union)

    # Value-sensitive check: extract concrete values asserted in the hypothesis.
    h_vals = _extract_values(hypothesis)
    if h_vals:
        # Filter out entity mentions -- they are linking anchors, not value claims.
        # A named value is filtered if it exactly matches an entity label OR
        # if any entity label is a substring of it (handles prepended articles/prepositions).
        if entity_labels is not None:
            h_vals = {
                v for v in h_vals
                if v not in entity_labels
                and not any(el in v for el in entity_labels if len(el) > 3)  # known slice heuristic; GR7 will replace
            }
        if h_vals:
            p_vals = _extract_values(premise)
            premise_lower = premise.lower()
            for v in h_vals:
                if v not in premise_lower and v not in p_vals:
                    # Value assertion fails -- premise omits/contradicts it.
                    return 0.0, (jaccard > 0.0)

    return jaccard, False


# ---------------------------------------------------------------------------
# Serialise evidence to a premise string
# ---------------------------------------------------------------------------


def _build_node_label_map(snapshot: KGSnapshot) -> dict[str, str]:
    """Build a QID -> label lookup from snapshot nodes."""
    return {n.id: n.label for n in snapshot.nodes}


def _build_entity_label_set(snapshot: KGSnapshot) -> frozenset[str]:
    """Build a frozenset of lowercased entity labels for value-check filtering."""
    return frozenset(_normalise_text(n.label) for n in snapshot.nodes)


def _serialise_edge(edge: KGEdge, node_labels: dict[str, str]) -> str:
    """Serialise a KGEdge to a human-readable premise string.

    Uses the node label map so subject names appear as readable strings
    rather than bare QIDs.
    """
    subj_label = node_labels.get(edge.subject_id, edge.subject_id)
    return f"{subj_label} {edge.property_label} {edge.object_label}"


# ---------------------------------------------------------------------------
# Step 4: classification cascade
# ---------------------------------------------------------------------------
# Decision order (SPEC-text §4.3(C)):
#   1. Direct triple entails claim  -> RETRIEVED / DIRECT_TRIPLE
#   2. Content label entails claim  -> RETRIEVED / TEXT_CONTENT
#   3. Multi-hop path entails claim -> REASONED_SUPPORTABLE / MULTI_HOP_PATH
#   4. else                         -> FABRICATED / NONE


def _best_direct_triple(
    claim: str,
    reference: GradingReference,
    node_labels: dict[str, str],
    entity_labels: frozenset[str],
) -> tuple[float, KGEdge | None, bool]:
    """Return (best_score, best_edge, value_blocked) over all edges.

    value_blocked is True when the best-lexical-overlap edge was killed by the
    value-sensitive check -- used to set spurious_path=True on FABRICATED claims.
    """
    best_score = 0.0
    best_edge: KGEdge | None = None
    any_value_blocked = False
    for edge in reference.snapshot.edges:
        premise = _serialise_edge(edge, node_labels)
        score, blocked = _entails_detailed(premise, claim, entity_labels)
        if blocked:
            any_value_blocked = True
        if score > best_score:
            best_score = score
            best_edge = edge
    return best_score, best_edge, any_value_blocked


def _best_content_label(
    claim: str,
    reference: GradingReference,
    entity_labels: frozenset[str],
) -> tuple[float, ContentLabel | None, bool]:
    """Return (best_score, best_label, value_blocked) over all content labels."""
    best_score = 0.0
    best_label: ContentLabel | None = None
    any_value_blocked = False
    for cl in reference.content_labels:
        score, blocked = _entails_detailed(cl.fact, claim, entity_labels)
        if blocked:
            any_value_blocked = True
        if score > best_score:
            best_score = score
            best_label = cl
    return best_score, best_label, any_value_blocked


def _make_path_from_edge(edge: KGEdge, snapshot: KGSnapshot) -> GroundingPath:
    """Wrap a single KGEdge in a single-hop GroundingPath."""
    object_node_id = edge.object_id if edge.object_id else f"lit:{edge.value_type.value}:{edge.object_label}"
    return GroundingPath(
        edges=[
            PathEdge(
                subject_id=edge.subject_id,
                subject_label=_node_label(snapshot, edge.subject_id),
                property_id=edge.property_id,
                property_label=edge.property_label,
                object_id=edge.object_id,
                object_label=edge.object_label,
                traversed_forward=True,
            )
        ],
        node_ids=[edge.subject_id, object_node_id],
    )


def _node_label(snapshot: KGSnapshot, node_id: str) -> str:
    """Look up the label for a node id in the snapshot."""
    for node in snapshot.nodes:
        if node.id == node_id:
            return node.label
    return node_id


def _multi_hop_search(
    claim: str,
    reference: GradingReference,
    k_hops: int,
    entity_labels: frozenset[str],
) -> tuple[float, GroundingPath | None, bool]:
    """Search for a multi-hop undirected path (2..k hops) entailing the claim.

    SLICE stand-in for GR8 path search.  Uses NetworkX all_simple_paths on
    the undirected view of the snapshot graph.  Excludes literal nodes as
    intermediate waypoints.  Picks the highest-entailment path (not shortest).
    Retains stored edge direction in PathEdge.traversed_forward.

    Returns (best_score, best_path, value_blocked).
    """
    g_directed = build_networkx(reference.snapshot)
    g_undirected = g_directed.to_undirected()

    snapshot = reference.snapshot
    node_map: dict[str, dict[str, Any]] = dict(g_directed.nodes(data=True))

    # entity nodes only (not literals) as endpoints and intermediates
    entity_nodes = [n for n, d in g_directed.nodes(data=True) if d.get("kind", "entity") == "entity"]

    best_score = 0.0
    best_path_obj: GroundingPath | None = None
    any_value_blocked = False

    # try all pairs of entity nodes as (source, target)
    for src in entity_nodes:
        for tgt in entity_nodes:
            if src >= tgt:
                continue  # avoid duplicate pairs
            try:
                paths = nx.all_simple_paths(g_undirected, src, tgt, cutoff=k_hops)
            except (nx.NetworkXError, nx.exception.NodeNotFound):
                continue

            for node_path in paths:
                if len(node_path) < 3:
                    # minimum 2 hops = 3 nodes
                    continue

                # all intermediate nodes must be entity nodes (not literal)
                intermediates = node_path[1:-1]
                if any(node_map.get(n, {}).get("kind", "entity") == "literal" for n in intermediates):
                    continue

                path_edges = _path_to_edges(node_path, g_directed, snapshot)
                if path_edges is None:
                    continue
                premise = " ".join(
                    f"{pe.subject_label} {pe.property_label} {pe.object_label}"
                    for pe in path_edges
                )
                score, blocked = _entails_detailed(premise, claim, entity_labels)
                if blocked:
                    any_value_blocked = True
                if score > best_score:
                    best_score = score
                    best_path_obj = GroundingPath(
                        edges=path_edges,
                        node_ids=list(node_path),
                    )

    return best_score, best_path_obj, any_value_blocked


def _path_to_edges(
    node_path: list[str],
    g: nx.MultiDiGraph,
    snapshot: KGSnapshot,
) -> list[PathEdge] | None:
    """Convert a node path to a list of PathEdge objects.

    For each consecutive (u, v) pair, look up the edge data from the directed
    graph (try forward u->v, then reverse v->u).  Returns None if any hop has
    no edge data.
    """
    path_edges: list[PathEdge] = []
    for u, v in zip(node_path[:-1], node_path[1:], strict=False):
        if g.has_edge(u, v):
            edge_data = next(iter(g[u][v].values()))
            forward = True
        elif g.has_edge(v, u):
            edge_data = next(iter(g[v][u].values()))
            forward = False
        else:
            return None  # no edge in either direction -- path is invalid

        src_id = u if forward else v
        tgt_id = v if forward else u
        path_edges.append(
            PathEdge(
                subject_id=src_id,
                subject_label=_node_label(snapshot, src_id),
                property_id=edge_data.get("property_id", ""),
                property_label=edge_data.get("property_label", ""),
                object_id=tgt_id if g.nodes[tgt_id].get("kind", "entity") == "entity" else None,
                object_label=edge_data.get("object_label", ""),
                traversed_forward=forward,
            )
        )
    return path_edges


# ---------------------------------------------------------------------------
# Public: run_cascade
# ---------------------------------------------------------------------------


def run_cascade(
    question: str,
    answer_text: str,
    reference: GradingReference,
    *,
    active_perturbations: list[str],
    config: GroundingConfig,
) -> list[ClaimRecord]:
    """Run the full grounding cascade on answer_text against reference.

    Returns a list of ClaimRecord objects (one per claim) with status,
    support_source, linked_entities, grounding_path, and entailment_score
    populated.  active_perturbations is recorded for attribution only; it
    does NOT change grading (Invariant #1).
    """
    claims_text = split_claims(answer_text)
    records: list[ClaimRecord] = []
    node_labels = _build_node_label_map(reference.snapshot)
    entity_labels = _build_entity_label_set(reference.snapshot)

    for i, claim_text in enumerate(claims_text):
        claim_id = f"c{i + 1}"
        linked, unresolved = link_entities(claim_text, reference.snapshot)

        # --- (1) Direct triple ---
        dt_score, best_edge, dt_blocked = _best_direct_triple(
            claim_text, reference, node_labels, entity_labels
        )
        if dt_score > config.tau and best_edge is not None:
            records.append(ClaimRecord(
                claim_id=claim_id,
                text=claim_text,
                status=ClaimStatus.RETRIEVED,
                support_source=SupportSource.DIRECT_TRIPLE,
                linked_entities=linked,
                grounding_path=_make_path_from_edge(best_edge, reference.snapshot),
                active_perturbations=list(active_perturbations),
                entailment_score=dt_score,
                unresolved_entities=unresolved,
            ))
            continue

        # --- (2) Content label ---
        cl_score, best_cl, cl_blocked = _best_content_label(claim_text, reference, entity_labels)
        if cl_score > config.tau and best_cl is not None:
            records.append(ClaimRecord(
                claim_id=claim_id,
                text=claim_text,
                status=ClaimStatus.RETRIEVED,
                support_source=SupportSource.TEXT_CONTENT,
                linked_entities=linked,
                grounding_path=GroundingPath(
                    edges=[],
                    node_ids=[best_cl.entity_id],
                ),
                active_perturbations=list(active_perturbations),
                entailment_score=cl_score,
                unresolved_entities=unresolved,
            ))
            continue

        # --- (3) Multi-hop path ---
        mh_score, mh_path, mh_blocked = _multi_hop_search(
            claim_text, reference, config.k_hops, entity_labels
        )
        if mh_score > config.tau and mh_path is not None:
            records.append(ClaimRecord(
                claim_id=claim_id,
                text=claim_text,
                status=ClaimStatus.REASONED_SUPPORTABLE,
                support_source=SupportSource.MULTI_HOP_PATH,
                linked_entities=linked,
                grounding_path=mh_path,
                active_perturbations=list(active_perturbations),
                entailment_score=mh_score,
                unresolved_entities=unresolved,
            ))
            continue

        # --- (4) FABRICATED ---
        # spurious_path=True when a candidate path/triple existed but was killed
        # by the value-sensitive gate (dt_blocked or cl_blocked or mh_blocked),
        # OR when a candidate had non-zero score below tau.
        any_blocked = dt_blocked or cl_blocked or mh_blocked
        any_candidate = dt_score > 0.0 or cl_score > 0.0 or mh_score > 0.0
        spurious = any_blocked or any_candidate
        spurious_reason: str | None = None
        if spurious:
            if any_blocked:
                spurious_reason = "value-sensitive gate rejected a candidate (wrong value)"
            elif dt_score >= cl_score and dt_score >= mh_score:
                spurious_reason = f"best direct triple score {dt_score:.3f} below tau {config.tau}"
            elif cl_score >= mh_score:
                spurious_reason = f"best content label score {cl_score:.3f} below tau {config.tau}"
            else:
                spurious_reason = f"best path score {mh_score:.3f} below tau {config.tau}"

        best_cand_score = max(dt_score, cl_score, mh_score)
        records.append(ClaimRecord(
            claim_id=claim_id,
            text=claim_text,
            status=ClaimStatus.FABRICATED,
            support_source=SupportSource.NONE,
            linked_entities=linked,
            grounding_path=GroundingPath(edges=[], node_ids=[]),
            active_perturbations=list(active_perturbations),
            entailment_score=best_cand_score if best_cand_score > 0.0 else None,
            spurious_path=spurious,
            spurious_reason=spurious_reason,
            unresolved_entities=unresolved,
        ))

    return records
