"""
Gold QA set format for IVG-KG (SPEC-text §4.7 / GR10).

PURPOSE: double duty
  1. Calibration fold -- calibrate the grounding verifier; tau/k frozen here.
     Only the "calibration" fold items are used for this.
  2. RQ2 anchor -- anchor the ablation sweep evaluation.

ADVERSARIAL VALUE-SWAPPED NEGATIVES (§6 false-claim control)
  Items where adversarial_negative=True carry a WRONG VALUE for an in-reference
  entity: the claim is factually wrong but plausible-sounding.  The grading
  oracle MUST assign FABRICATED.  An entity-match-only grader is caught because
  the entity is present in the reference but the value is wrong.

FOLD PARTITIONING
  fold="calibration"  -- used to calibrate tau/k; grading on this fold freezes
                          those hyperparameters.  DISJOINT from the sweep fold.
  fold="sweep"        -- used as the RQ2 evaluation anchor; tau/k are read-only.

MODALITY COVERAGE
  fact_type encodes which verifier axis the item exercises:
    "structure"  -- relies on a KG triple (direct or multi-hop)
    "text"       -- relies on a text content description
  (image axis reserved for post-books slices; stubs here use structure/text only)

JSON I/O
  GoldQASet.to_json() / GoldQASet.from_json() are the canonical wire form.
  load_gold_qa_set(path) reads a UTF-8 JSON file and returns a validated set.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from ivg_kg.schema import ClaimStatus, Modality

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GoldFold(StrEnum):
    """Partition of the gold QA set.

    calibration -- tau/k are frozen on this fold; use ONLY for verifier
                   calibration, never for downstream sweep evaluation.
    sweep       -- RQ2 evaluation anchor; reads frozen tau/k, never re-fits.
    """

    CALIBRATION = "calibration"
    SWEEP = "sweep"


# ---------------------------------------------------------------------------
# Per-item expected outcome
# ---------------------------------------------------------------------------


class ExpectedClaimOutcome(BaseModel):
    """Expected grounding outcome for a single claim within a GoldQAItem.

    Used to compute classifier error (confusion matrix entry) per claim.

    Fields:
        claim_text      -- verbatim claim string as it would appear in the answer.
        expected_status -- the oracle ClaimStatus the verifier must produce.
        modality        -- which evidence axis this claim exercises (structure / text).
                           Allows per-modality error breakdown.
    """

    claim_text: str
    expected_status: ClaimStatus
    modality: Modality


# ---------------------------------------------------------------------------
# Core item
# ---------------------------------------------------------------------------


class GoldQAItem(BaseModel):
    """One item in the curated gold QA set (SPEC-text §4.7 / GR10).

    Fields:
        item_id             -- stable identifier within this gold set; must be
                               unique within a GoldQASet.
        question            -- the question posed to the generative model.
        entity_id           -- primary Wikidata QID this question targets.
        slice_id            -- the frozen slice the question belongs to
                               (e.g. "books-p0-v1").
        expected_outcomes   -- ordered list of (claim, expected_status, modality)
                               triples.  The verifier is graded by comparing its
                               output against these.
        adversarial_negative -- True when this item is a value-swapped negative:
                               a wrong-value claim about an in-reference entity
                               that MUST grade FABRICATED.  This is the §6
                               false-claim control; an entity-match-only grader
                               passes the entity check but fails the value check.
        fold                -- CALIBRATION or SWEEP; items in the calibration fold
                               are used to freeze tau/k; DISJOINT from sweep.
        notes               -- optional free-text authoring note (not used in
                               grading logic).
    """

    item_id: str
    question: str
    entity_id: str
    slice_id: str
    expected_outcomes: Annotated[list[ExpectedClaimOutcome], Field(min_length=1)]
    adversarial_negative: bool = False
    fold: GoldFold
    notes: str | None = None


# ---------------------------------------------------------------------------
# Set container
# ---------------------------------------------------------------------------


class GoldQASet(BaseModel):
    """A validated, versioned collection of GoldQAItems.

    Invariants:
    - item_ids are unique within the set.
    - At least one adversarial_negative item must be present (the §6 control
      is load-bearing; a set with zero adversarial negatives is incomplete).
    - Both folds must be represented (calibration + sweep; disjoint design).

    These invariants are NOT validated at construction time (the format is a
    seam for human authoring; partial stubs are allowed).  The
    assert_complete() helper checks them when required by the verifier.

    Fields:
        set_id      -- stable identifier for this gold set version.
        slice_id    -- the frozen slice this set covers.
        items       -- the gold items.
        schema_version -- version tag for forward-compatibility.
    """

    set_id: str
    slice_id: str
    items: list[GoldQAItem] = Field(default_factory=list)
    schema_version: str = "1.0"

    # ------------------------------------------------------------------
    # Convenience selectors
    # ------------------------------------------------------------------

    def calibration_items(self) -> list[GoldQAItem]:
        """Items belonging to the calibration fold."""
        return [it for it in self.items if it.fold == GoldFold.CALIBRATION]

    def sweep_items(self) -> list[GoldQAItem]:
        """Items belonging to the sweep/RQ2 anchor fold."""
        return [it for it in self.items if it.fold == GoldFold.SWEEP]

    def adversarial_items(self) -> list[GoldQAItem]:
        """Items that are value-swapped adversarial negatives (§6 control)."""
        return [it for it in self.items if it.adversarial_negative]

    def items_by_modality(self, modality: Modality) -> list[GoldQAItem]:
        """Items that exercise the given modality in at least one expected outcome."""
        return [
            it
            for it in self.items
            if any(oc.modality == modality for oc in it.expected_outcomes)
        ]

    # ------------------------------------------------------------------
    # Validation helper
    # ------------------------------------------------------------------

    def assert_complete(self) -> None:
        """Raise ValueError if the set fails completeness invariants.

        Call this before using the set for calibration or sweep evaluation.
        Not called automatically so partial stubs remain loadable.
        """
        seen_ids: set[str] = set()
        for it in self.items:
            if it.item_id in seen_ids:
                raise ValueError(f"duplicate item_id: {it.item_id!r}")
            seen_ids.add(it.item_id)

        folds = {it.fold for it in self.items}
        if GoldFold.CALIBRATION not in folds:
            raise ValueError("gold set has no calibration-fold items")
        if GoldFold.SWEEP not in folds:
            raise ValueError("gold set has no sweep-fold items")

        if not any(it.adversarial_negative for it in self.items):
            raise ValueError(
                "gold set has no adversarial value-swapped negatives (section-6 control)"
            )

        for it in self.items:
            if it.adversarial_negative and not any(
                oc.expected_status == ClaimStatus.FABRICATED for oc in it.expected_outcomes
            ):
                raise ValueError(
                    f"adversarial item {it.item_id!r} has no FABRICATED expected outcome"
                )

    # ------------------------------------------------------------------
    # JSON I/O
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize to a UTF-8 JSON string (compact, sorted keys)."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, s: str) -> GoldQASet:
        """Reconstruct a GoldQASet from a JSON string."""
        return cls.model_validate_json(s)


# ---------------------------------------------------------------------------
# File loader
# ---------------------------------------------------------------------------


def load_gold_qa_set(path: str | Path) -> GoldQASet:
    """Load and validate a GoldQASet from a UTF-8 JSON file.

    Parameters
    ----------
    path:
        Path to the .json file (absolute or relative to cwd).

    Returns
    -------
    GoldQASet
        Validated set.  Raises pydantic.ValidationError on schema mismatch,
        FileNotFoundError / json.JSONDecodeError on I/O / parse errors.
    """
    text = Path(path).read_text(encoding="utf-8")
    return GoldQASet.from_json(text)
