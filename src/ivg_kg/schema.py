"""
Central pydantic v2 schema contract for IVG-KG (SPEC-text §4.2).

All models are JSON-serialisable for use with Dash dcc.Store.
No third-party imports beyond pydantic and stdlib enum/typing.

Invariants (from SPEC):
- GenerationContext (ablatable) and GradingReference (immutable full reference)
  are intentionally separate types; do not merge them.
- RETRIEVED means grounded in a single evidence item — a triple OR a content
  fact (description / curated image label); support_source records which.
- spurious_path=True means evidence existed but failed the entailment gate,
  resulting in FABRICATED status despite a candidate path being found.
- PathEdge.traversed_forward records the stored-edge direction on undirected
  path search; it is mandatory and must not be removed.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ClaimStatus(StrEnum):
    """Grounding outcome for a single claim.

    Values are given verbatim in SPEC-text §4.2; the hyphen in REASONED_SUPPORTABLE
    is intentional and must not be changed.
    """

    RETRIEVED = "retrieved"
    REASONED_SUPPORTABLE = "reasoned-supportable"
    FABRICATED = "fabricated"


class SupportSource(StrEnum):
    """Modality of the evidence that supported (or failed to support) a claim.

    Orthogonal to ClaimStatus: a RETRIEVED claim may be supported by a direct
    triple, a text content fact, or an image content label.
    """

    DIRECT_TRIPLE = "direct_triple"
    MULTI_HOP_PATH = "multi_hop_path"
    TEXT_CONTENT = "text_content"
    IMAGE_CONTENT = "image_content"
    NONE = "none"


class Modality(StrEnum):
    STRUCTURE = "structure"
    TEXT = "text"
    IMAGE = "image"


class ValueType(StrEnum):
    ITEM = "item"
    TIME = "time"
    QUANTITY = "quantity"
    MONOLINGUAL = "monolingual"
    STRING = "string"


class Condition(StrEnum):
    """Generation-context condition a run was produced under (SPEC-text §4.2).

    Each run's answer is generated from the (possibly ablated) context for this
    condition; the diagnostics aggregate the N draws across conditions (§4.8).
    """

    FULL = "full"
    KNOWLEDGE_ABSENT = "knowledge-absent"
    CONTENT_ABSENT = "content-absent"
    IMAGE_ABSENT = "image-absent"  # image axis only; unused in the books spine


# ---------------------------------------------------------------------------
# Utility reference selector
# ---------------------------------------------------------------------------


class TripleRef(BaseModel):
    """Selects a specific triple in the KG (used to identify what to withhold)."""

    subject_id: str
    property_id: str
    object_id: str | None = None


# ---------------------------------------------------------------------------
# KG shape
# ---------------------------------------------------------------------------


class KGNode(BaseModel):
    """A Wikidata entity node in the knowledge graph snapshot."""

    id: str
    label: str
    description: str | None = None
    sitelinks: int | None = None
    image_path: str | None = None  # image-axis slices (artwork/taxa, post-M-BOOKS) + entity-image display (P18); not grounding evidence in the books spine
    kind: str = "entity"


class KGEdge(BaseModel):
    """A single directional Wikidata triple (subject, property, object)."""

    subject_id: str
    property_id: str
    property_label: str
    object_id: str | None = None  # None for non-item values (time, quantity, etc.)
    object_label: str
    value_type: ValueType


class KGSnapshot(BaseModel):
    """A frozen sub-graph around a domain entity at a specific slice."""

    snapshot_id: str
    slice: str
    domain_qid: str
    nodes: list[KGNode]
    edges: list[KGEdge]
    meta: dict[str, Any] = Field(default_factory=dict)


class ContentLabel(BaseModel):
    """A curated textual or image-derived fact about an entity.

    Image content labels (modality=IMAGE) store a natural-language description
    of the image; grading is done by text NLI against this string, not the
    raster image.
    """

    entity_id: str
    modality: Modality
    fact: str
    source: str


class GradingReference(BaseModel):
    """The immutable full reference used for grounding classification.

    This is the ground-truth; it is never ablated.  The generation-side
    evidence (possibly ablated) lives in GenerationContext.
    """

    snapshot: KGSnapshot
    content_labels: list[ContentLabel]


# ---------------------------------------------------------------------------
# Pipeline I/O
# ---------------------------------------------------------------------------


class GenerationContext(BaseModel):
    """The (possibly ablated) evidence shown to the generator.

    Perturbations withhold evidence here only; the GradingReference is never
    modified.  Keeping these two types separate is a load-bearing invariant
    (SPEC-text §3.2).
    """

    entity_id: str
    triples: list[KGEdge]
    description: str | None = None
    image_path: str | None = None


class GroundingConfig(BaseModel):
    """Tunable parameters for the grounding pipeline."""

    k_hops: int = 2
    tau: float = 0.5
    linker: str = "label_alias"
    entailment: str = "minicheck"


# ---------------------------------------------------------------------------
# Per-claim log
# ---------------------------------------------------------------------------


class LinkedEntity(BaseModel):
    """An entity mention resolved to a Wikidata QID."""

    id: str
    label: str
    description: str | None = None
    link_score: float | None = None


class PathEdge(BaseModel):
    """A single hop in a multi-hop grounding path.

    traversed_forward records whether the path followed the stored edge
    direction (True) or reversed it (False).  Path search is UNDIRECTED but
    edge directionality is preserved here for interpretability.
    """

    subject_id: str
    subject_label: str
    property_id: str
    property_label: str
    object_id: str | None = None
    object_label: str
    traversed_forward: bool


class GroundingPath(BaseModel):
    """A multi-hop path through the KG that (putatively) grounds a claim.

    hops is a derived read-only property equal to len(edges); it is NOT stored
    as a separate field to prevent desync on round-trips.
    """

    edges: list[PathEdge]
    node_ids: list[str]

    @property
    def hops(self) -> int:
        """Number of hops in the path; equal to len(edges)."""
        return len(self.edges)


class ClaimRecord(BaseModel):
    """Log entry for a single claim extracted from the model answer.

    Fields:
        claim_id: Unique identifier for this claim within the run.
        text: The verbatim claim string extracted from answer_text.
        status: Grounding outcome.
        support_source: Modality of the supporting evidence (orthogonal to status).
        linked_entities: QIDs resolved from claim mentions.
        grounding_path: Non-empty only for MULTI_HOP_PATH claims.
        active_perturbations: Manifest-entry ids whose withheld triples/content
            touch at least one of this claim's linked entities.
        entailment_score: NLI/visual-probe gate score (MiniCheck or visual probe).
        slot_key: Canonical (head_entity, relation) key — the fact SLOT (§4.8).
            Canonicalized via the §4.3(B) property-alias / inverse-orientation
            table so the same slot is keyed identically regardless of surface
            phrasing or relation direction.
        claim_key: slot_key + normalized_value — the VARIANT.  Aligns "the same
            claim" (same slot AND same asserted value) across draws of a RunSet.
            A variant has exactly one status (deterministic verifier, full-KG
            grading); the slot's mixed distribution reflects WHICH variant the
            generator emitted, not a per-claim status flip (§4.8).
        aligned: False when the claim maps to no slice slot (unmappable
            subject/predicate); such claims are never force-aligned (§4.3(B)/§4.8).
        unaligned_reason: Reason code when aligned is False.
        spurious_path: True when a multi-hop path passed the value-sensitive
            entailment gate but is not legitimate support (Supportable claims).
        spurious_reason: Reason code/text when spurious_path is True (§4.8).
        unresolved_entities: Mention strings that could not be linked to any
            entity in the domain slice.  Distinct from FABRICATED status.
    """

    claim_id: str
    text: str
    status: ClaimStatus
    support_source: SupportSource
    slot_key: str | None = None
    claim_key: str | None = None
    aligned: bool = True
    unaligned_reason: str | None = None
    linked_entities: list[LinkedEntity]
    grounding_path: GroundingPath
    active_perturbations: list[str] = Field(default_factory=list)
    entailment_score: float | None = None
    spurious_path: bool = False
    spurious_reason: str | None = None
    unresolved_entities: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Grounding run
# ---------------------------------------------------------------------------


class GroundingRun(BaseModel):
    """Top-level record for one question-answer grounding pass.

    Fields:
        run_id: Unique run identifier.
        question: The question posed to the generative model.
        answer_text: The model's raw answer.
        slice: Dataset slice name (e.g. "books").
        phase: Experiment phase identifier ("A" or "B").
        claims: Per-claim grounding records.
        active_perturbations: Manifest-entry ids active in this run.
        grading_reference_id: Foreign key to the GradingReference (if stored).
        error_rates: Per-modality fabrication rates keyed by modality path string
            (e.g. {"text": .., "structure": .., "image": ..}).
    """

    run_id: str
    question: str
    answer_text: str
    slice: str
    phase: str
    condition: Condition = Condition.FULL
    sample_index: int = 0
    claims: list[ClaimRecord]
    active_perturbations: list[str] = Field(default_factory=list)
    grading_reference_id: str | None = None
    error_rates: dict[str, float] = Field(default_factory=dict)

    def status_counts(self) -> dict[str, int]:
        """Return a count mapping for each ClaimStatus value.

        All three statuses are always present as keys (with count 0 when
        absent) so that downstream chart code can depend on stable keys.
        """
        counts: dict[str, int] = {cs.value: 0 for cs in ClaimStatus}
        for claim in self.claims:
            counts[claim.status.value] += 1
        return counts

    def fabrication_rate(self) -> float:
        """Fraction of claims whose status is FABRICATED.

        Returns 0.0 when claims is empty (no division by zero).
        """
        if not self.claims:
            return 0.0
        fabricated = sum(1 for c in self.claims if c.status == ClaimStatus.FABRICATED)
        return fabricated / len(self.claims)


# ---------------------------------------------------------------------------
# Diagnostics aggregated over a RunSet (the N draws x conditions) — SPEC-text §4.8
# ---------------------------------------------------------------------------

# Pseudo-status used in per-draw / stacked-bar accounting when a SLOT is not
# filled by a given draw (distinct from FABRICATED). Not a ClaimStatus.
ABSENT = "absent"


class VariantStat(BaseModel):
    """One VARIANT filling a slot: its single fixed status + how often it appeared.

    The verifier is deterministic and grades against the full KG, so a variant's
    ``status`` is INVARIANT across draws and conditions (SPEC-text §4.8). The only
    thing that varies is ``draw_frequency`` — how often the generator emitted this
    particular value for the slot. This is what explains a mixed slot distribution:
    the per-variant status meter never moves; only which variant appears does.
    """

    normalized_value: str
    status: ClaimStatus  # invariant per variant
    text: str = ""  # a representative surface form of this variant
    draw_frequency: dict[str, int] = Field(default_factory=dict)  # condition -> count of draws


class ClaimDiagnostics(BaseModel):
    """One fact SLOT, aggregated across the RunSet (SPEC-text §4.8).

    SLOT-anchored (``slot_key``), NOT variant-anchored: because the verifier is
    deterministic and grades against the full KG, a variant has exactly one
    status, so stability / absence_leverage / fabrication_induction are degenerate
    at the variant level and only well-defined at the slot level. Per draw the
    outcome is the status of whichever variant filled the slot (or ``absent``).

    Drives the per-claim Analytics view (#6): the per-condition stacked-bar
    small-multiple + the variant breakdown + the stability scalar + the
    spurious-path chip.
    """

    slot_key: str  # canonical head + relation
    text: str  # a representative surface form for the slot
    presence_rate: float  # fraction of the N FULL draws the slot is filled (1 - P[absent])
    variants: list[VariantStat] = Field(default_factory=list)  # REQUIRED breakdown
    intra_answer_contradiction: bool = False  # a single draw asserting two variants of the slot
    stability: float  # SLOT-level: 1 - H(outcome|FULL)/log K over the N FULL draws
    modal_status: ClaimStatus  # most common per-draw outcome under FULL
    modal_fraction: float  # e.g. 0.9 -> "retrieved 9/10"
    n_full: int  # number of FULL draws the fractions/frequencies are over
    # condition -> {status_or_"absent": fraction over N} (stacked-bar input)
    status_by_condition: dict[str, dict[str, float]]
    absence_leverage: dict[str, float] = Field(default_factory=dict)
    fabrication_induction: dict[str, float] = Field(default_factory=dict)
    spurious_path: bool = False
    spurious_reason: str | None = None


class AnswerDiagnostics(BaseModel):
    """The full-answer analytics view aggregated over the RunSet (#5).

    All variance here is GENERATION variance: the verifier is deterministic, so
    the spread across the N draws reflects the stochastic generator under test,
    not repeated grading. Error bars on the distribution are the SE of the
    proportion (sqrt(p(1-p)/N)), derived in the chart from the fraction + N — not
    a per-draw std (SPEC-text §4.8 statistical-honesty).
    """

    question: str
    n_generations: int  # N generation draws per condition
    # fraction of claims in each grade over the N FULL draws (column chart heights)
    status_distribution: dict[str, float]
    fabrication_rate: float  # fabricated fraction over the N FULL draws
    claim_diagnostics: list[ClaimDiagnostics]
