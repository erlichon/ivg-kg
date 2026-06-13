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


class EpistemicLevel(StrEnum):
    """Schema-enforced glyph contract for uncertainty provenance (SPEC-text §4.9d).

    The string values are frozen: they are the glyph selector used by the UI layer.
    Do not change them.
    """

    OBSERVATIONAL = "observational"            # support-frequency (open circle)
    INTERVENTIONAL_AGGREGATE = "interventional"  # offline sweep (filled triangle + interval)
    SINGLE_SAMPLE = "n1"                       # single-run REMOVE/ADD delta (outlined n=1 triangle)


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
    extractor: str = "rule_based"


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

    Claims are NOT aligned across runs (SPEC-text §4.8): ``claim_id`` is a
    WITHIN-RUN identifier only and carries no meaning across runs. The design
    aligns stable KG-item IDs (entities, triplets) for support-frequency, never
    claims, and aggregates claims only as answer-level fractions.

    Fields:
        claim_id: Identifier for this claim WITHIN this run (not cross-run).
        text: The verbatim claim string extracted from answer_text.
        status: Grounding outcome.
        support_source: Modality of the supporting evidence (orthogonal to status).
        linked_entities: QIDs resolved from claim mentions.
        grounding_path: The support path — the KG items this verdict rests on.
            For a grounded claim it carries the supporting triple(s)/node(s): a
            single-edge path for a DIRECT_TRIPLE claim, the node(s) for a
            TEXT_CONTENT claim, the full multi-hop path for a REASONED_SUPPORTABLE
            claim. Empty for FABRICATED claims. This is what support-frequency
            (§4.8) reads to find which KG items were USED to ground a claim.
        active_perturbations: Manifest-entry ids whose withheld triples/content
            touch at least one of this claim's linked entities.
        entailment_score: NLI/visual-probe gate score (MiniCheck or visual probe).
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
    # a perturbed run points at its pre-perturbation baseline run (durable before/after pairing for the REMOVE delta; §4.5)
    baseline_run_id: str | None = None
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
# Diagnostics (§4.8). Two modes. Claims are NOT aligned across runs; only stable
# KG-item IDs (entities, triplets) are. Claims aggregate only as answer-level
# fractions. All across-run spread is GENERATION variance (the verifier is
# deterministic). There is NO absence_leverage / fabrication_induction scalar and
# NO per-claim cross-run alignment — that simplification is the point of §4.8.
# ---------------------------------------------------------------------------


class SingleRunStatusSummary(BaseModel):
    """The single-run analytics view — ONE generated answer (SPEC-text §4.8).

    A single sample, so it carries counts and percentages with NO SE/STD.
    """

    status_counts: dict[str, int]  # {status: count} for THIS one run
    status_percentages: dict[str, float]  # {status: fraction} for THIS one run — no SE
    epistemic_level: EpistemicLevel = EpistemicLevel.SINGLE_SAMPLE  # the n=1 single-sample glyph contract (§4.9d)


class StatusMeanSE(BaseModel):
    """Mean and standard error of a per-run PROPORTION across the N runs (§4.8).

    ``se`` is the SE of a proportion, ``sqrt(p(1-p)/N)`` — NOT the ~0.5 Bernoulli
    per-draw std. N=20 is a floor; small differences are within noise.
    """

    mean: float
    se: float


class AnswerDiagnostics(BaseModel):
    """The multi-run analytics view aggregated over the N runs (SPEC-text §4.8 #5).

    The per-run answer-level fraction of claims in each grade is computed per run
    first, then aggregated to mean +/- SE across the N runs (never pooled).
    ``support_frequency`` is OBSERVATIONAL importance ("how often grounding routes
    through this KG item"), explicitly NOT causal leverage.
    """

    question: str
    n_runs: int
    # status -> mean +/- SE of the per-run answer-level fraction over the N runs
    status_distribution: dict[str, StatusMeanSE]
    # KG-item id (entity_id OR triplet_id "<subject_id>|<property_id>|<object_id>")
    # -> fraction of the N runs it was USED to ground a claim (observational; §4.8)
    support_frequency: dict[str, float] = Field(default_factory=dict)
    epistemic_level: EpistemicLevel = EpistemicLevel.OBSERVATIONAL  # support-frequency is observational glyph contract (§4.9d)


class RepairResult(BaseModel):
    """The gap-repair before/after result (edit-the-KG; SPEC-text §4.6).

    ``repair_leverage`` is a COUNT: the number of claims that flip
    FABRICATED -> grounded when the analyst restores missing evidence to the KG
    and re-runs, aligned by ``claim_id`` within that one answer's before/after
    pair (the ONLY place claims are aligned).
    """

    restored_item: str  # the triple/content restored to the KG
    repair_leverage: int  # count of claims that flipped FABRICATED -> grounded
    repaired_claim_ids: list[str] = Field(default_factory=list)  # which claims flipped
