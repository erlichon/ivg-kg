"""Mock fixtures for the IVG-KG Dash skeleton (UI1 / SPEC §3.3, §4.5).

Provides a hardcoded, fully deterministic books-slice GroundingRun and the
corresponding dash-cytoscape subgraph elements.  No randomness, no I/O, no
third-party imports beyond ivg_kg.schema.

Book domain (invented Wikidata-style QIDs):
  Q_BOOK       = Q11111  "The Hollow Hours"
  Q_AUTHOR     = Q22222  "Elara Voss"
  Q_TRADITION  = Q33333  "Symbolist movement"
  Q_PUBLISHER  = Q44444  "Meridian Press"

Support path for the REASONED_SUPPORTABLE claim (2-hop, undirected):
  Q_BOOK --(P50: author)--> Q_AUTHOR   [traversed_forward=True]
  Q_TRADITION --(P921: main subject)--> Q_AUTHOR  [traversed_forward=False]
  (i.e. we walk the P921 edge backwards: Q_AUTHOR <- Q_TRADITION)

Edge-id convention (matches UI2 highlighting contract):
  "<subject_id>-<property_id>-<object_id>"
  e.g. "Q11111-P50-Q22222"
"""

from __future__ import annotations

from ivg_kg.schema import (
    ClaimRecord,
    ClaimStatus,
    GroundingPath,
    GroundingRun,
    LinkedEntity,
    PathEdge,
    SupportSource,
)

# ---------------------------------------------------------------------------
# Stable QID / PID constants (books domain, fully invented)
# ---------------------------------------------------------------------------

_BOOK_QID = "Q11111"
_BOOK_LABEL = "The Hollow Hours"
_BOOK_DESC = "A 1923 novel by Elara Voss, associated with the Symbolist movement."

_AUTHOR_QID = "Q22222"
_AUTHOR_LABEL = "Elara Voss"
_AUTHOR_DESC = "German novelist and poet (1891-1956), central figure of Symbolism."

_TRADITION_QID = "Q33333"
_TRADITION_LABEL = "Symbolist movement"
_TRADITION_DESC = "Late 19th/early 20th-century literary and artistic movement."

_PUBLISHER_QID = "Q44444"
_PUBLISHER_LABEL = "Meridian Press"
_PUBLISHER_DESC = "German publishing house, founded 1905."

_P50 = "P50"    # author
_P50_LABEL = "author"
_P577 = "P577"  # publication date
_P577_LABEL = "publication date"
_P123 = "P123"  # publisher
_P123_LABEL = "publisher"
_P921 = "P921"  # main subject
_P921_LABEL = "main subject"

# ---------------------------------------------------------------------------
# Linked-entity helpers
# ---------------------------------------------------------------------------


def _le(qid: str, label: str, desc: str | None = None, score: float = 1.0) -> LinkedEntity:
    return LinkedEntity(id=qid, label=label, description=desc, link_score=score)


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


def _claim_retrieved_direct_triple() -> ClaimRecord:
    """Claim 1: RETRIEVED / DIRECT_TRIPLE — authorship fact."""
    return ClaimRecord(
        claim_id="c1",
        text="The Hollow Hours was written by Elara Voss.",
        status=ClaimStatus.RETRIEVED,
        support_source=SupportSource.DIRECT_TRIPLE,
        linked_entities=[
            _le(_BOOK_QID, _BOOK_LABEL, _BOOK_DESC),
            _le(_AUTHOR_QID, _AUTHOR_LABEL, _AUTHOR_DESC),
        ],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
        entailment_score=0.95,
    )


def _claim_retrieved_text_content() -> ClaimRecord:
    """Claim 2: RETRIEVED / TEXT_CONTENT — genre/tradition from description.

    No direct triple for tradition membership; the grounding is derived from
    the entity description text (SPEC §3.2 content axis, Invariant #2).
    """
    return ClaimRecord(
        claim_id="c2",
        text="The Hollow Hours is associated with the Symbolist literary tradition.",
        status=ClaimStatus.RETRIEVED,
        support_source=SupportSource.TEXT_CONTENT,
        linked_entities=[
            _le(_BOOK_QID, _BOOK_LABEL, _BOOK_DESC),
            _le(_TRADITION_QID, _TRADITION_LABEL, _TRADITION_DESC, score=0.88),
        ],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
        entailment_score=0.91,
    )


def _claim_reasoned_supportable_multi_hop() -> ClaimRecord:
    """Claim 3: REASONED_SUPPORTABLE / MULTI_HOP_PATH.

    Path: Q_BOOK --(P50)--> Q_AUTHOR <--(P921)-- Q_TRADITION
    Hop 1 is forward (stored direction); hop 2 is backward (traversed_forward=False).
    """
    hop1 = PathEdge(
        subject_id=_BOOK_QID,
        subject_label=_BOOK_LABEL,
        property_id=_P50,
        property_label=_P50_LABEL,
        object_id=_AUTHOR_QID,
        object_label=_AUTHOR_LABEL,
        traversed_forward=True,
    )
    # The stored edge is Q_TRADITION -P921-> Q_AUTHOR.
    # We traverse it backward (from Q_AUTHOR side) to reach Q_TRADITION.
    # subject_id/object_id record the STORED direction; traversed_forward=False
    # signals that the path walked this edge against its stored direction.
    hop2 = PathEdge(
        subject_id=_TRADITION_QID,
        subject_label=_TRADITION_LABEL,
        property_id=_P921,
        property_label=_P921_LABEL,
        object_id=_AUTHOR_QID,
        object_label=_AUTHOR_LABEL,
        traversed_forward=False,
    )
    path = GroundingPath(
        edges=[hop1, hop2],
        node_ids=[_BOOK_QID, _AUTHOR_QID, _TRADITION_QID],
    )
    return ClaimRecord(
        claim_id="c3",
        text=(
            "The Hollow Hours belongs to the Symbolist movement, "
            "inferred via its author Elara Voss."
        ),
        status=ClaimStatus.REASONED_SUPPORTABLE,
        support_source=SupportSource.MULTI_HOP_PATH,
        linked_entities=[
            _le(_BOOK_QID, _BOOK_LABEL, _BOOK_DESC),
            _le(_TRADITION_QID, _TRADITION_LABEL, _TRADITION_DESC, score=0.82),
            _le(_AUTHOR_QID, _AUTHOR_LABEL, _AUTHOR_DESC),
        ],
        grounding_path=path,
        entailment_score=0.70,
    )


def _claim_fabricated_none() -> ClaimRecord:
    """Claim 4: FABRICATED / NONE — invented award, no supporting evidence."""
    return ClaimRecord(
        claim_id="c4",
        text="The Hollow Hours won the International Fiction Prize in 1925.",
        status=ClaimStatus.FABRICATED,
        support_source=SupportSource.NONE,
        linked_entities=[
            _le(_BOOK_QID, _BOOK_LABEL, _BOOK_DESC),
        ],
        grounding_path=GroundingPath(edges=[], node_ids=[]),
        entailment_score=None,
    )


def _claim_fabricated_spurious() -> ClaimRecord:
    """Claim 5: FABRICATED with spurious_path=True.

    A candidate multi-hop path was found (Book->Author->Publisher) but the
    entailment gate rejected it.  Illustrates the 'evidence existed but failed'
    case (SPEC spurious_path flag).
    """
    # Candidate path that was found but rejected
    hop1 = PathEdge(
        subject_id=_BOOK_QID,
        subject_label=_BOOK_LABEL,
        property_id=_P50,
        property_label=_P50_LABEL,
        object_id=_AUTHOR_QID,
        object_label=_AUTHOR_LABEL,
        traversed_forward=True,
    )
    hop2 = PathEdge(
        subject_id=_AUTHOR_QID,
        subject_label=_AUTHOR_LABEL,
        property_id=_P123,
        property_label=_P123_LABEL,
        object_id=_PUBLISHER_QID,
        object_label=_PUBLISHER_LABEL,
        traversed_forward=True,
    )
    spurious_path = GroundingPath(
        edges=[hop1, hop2],
        node_ids=[_BOOK_QID, _AUTHOR_QID, _PUBLISHER_QID],
    )
    return ClaimRecord(
        claim_id="c5",
        text="Elara Voss was exclusively published by Meridian Press throughout her career.",
        status=ClaimStatus.FABRICATED,
        support_source=SupportSource.MULTI_HOP_PATH,
        linked_entities=[
            _le(_AUTHOR_QID, _AUTHOR_LABEL, _AUTHOR_DESC),
            _le(_PUBLISHER_QID, _PUBLISHER_LABEL, _PUBLISHER_DESC, score=0.79),
        ],
        grounding_path=spurious_path,
        entailment_score=0.31,
        spurious_path=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def mock_grounding_run() -> GroundingRun:
    """Return a fresh hardcoded GroundingRun for the books slice.

    Constructs a new object on every call — no shared mutable state.
    Covers all three ClaimStatus values, both DIRECT_TRIPLE and TEXT_CONTENT
    retrieved sources, and a MULTI_HOP_PATH with an undirected traversal.
    """
    return GroundingRun(
        run_id="mock-run-books-001",
        question="Tell me about the novel 'The Hollow Hours' and its literary context.",
        answer_text=(
            "The Hollow Hours was written by Elara Voss. "
            "The Hollow Hours is associated with the Symbolist literary tradition. "
            "The Hollow Hours belongs to the Symbolist movement, "
            "inferred via its author Elara Voss. "
            "The Hollow Hours won the International Fiction Prize in 1925. "
            "Elara Voss was exclusively published by Meridian Press throughout her career."
        ),
        slice="books",
        phase="A",
        claims=[
            _claim_retrieved_direct_triple(),
            _claim_retrieved_text_content(),
            _claim_reasoned_supportable_multi_hop(),
            _claim_fabricated_none(),
            _claim_fabricated_spurious(),
        ],
        active_perturbations=[],
    )


def mock_subgraph_elements() -> list[dict]:
    """Return dash-cytoscape elements for the books mock subgraph.

    Includes a node per entity and edges for all triples referenced by the
    mock run.  Edge ids use the stable convention '<subject_id>-<pid>-<object_id>'
    so that UI2 callbacks can map a claim's GroundingPath to specific elements
    for stylesheet-based highlighting without mutating the global stylesheet.

    No image_path fields; no taxa/image content (books-only hard gate).
    """
    nodes: list[dict] = [
        {"data": {"id": _BOOK_QID, "label": _BOOK_LABEL, "description": _BOOK_DESC}},
        {"data": {"id": _AUTHOR_QID, "label": _AUTHOR_LABEL, "description": _AUTHOR_DESC}},
        {
            "data": {
                "id": _TRADITION_QID,
                "label": _TRADITION_LABEL,
                "description": _TRADITION_DESC,
            }
        },
        {
            "data": {
                "id": _PUBLISHER_QID,
                "label": _PUBLISHER_LABEL,
                "description": _PUBLISHER_DESC,
            }
        },
    ]

    def _edge(subj: str, pid: str, obj: str, label: str) -> dict:
        return {
            "data": {
                "id": f"{subj}-{pid}-{obj}",
                "source": subj,
                "target": obj,
                "label": label,
                "property_id": pid,
            }
        }

    edges: list[dict] = [
        # Claim 1: DIRECT_TRIPLE — book authored by
        _edge(_BOOK_QID, _P50, _AUTHOR_QID, _P50_LABEL),
        # Multi-hop path edges (also used by claim 3 and spurious claim 5)
        _edge(_TRADITION_QID, _P921, _AUTHOR_QID, _P921_LABEL),
        _edge(_AUTHOR_QID, _P123, _PUBLISHER_QID, _P123_LABEL),
        # Book publication date (structural triple, adds subgraph richness)
        # object_id is None for date values — use a placeholder node-less edge
        # represented as a string target; we instead encode it as a data attr
        # to avoid referential-integrity issues (no date node in the graph).
        # Omitted here to keep the elements set clean and self-consistent.
    ]

    return nodes + edges
