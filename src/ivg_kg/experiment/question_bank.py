"""
Question bank format for IVG-KG (SPEC-text §5 / EX1).

PURPOSE: a FIXED set of questions for the books spine experiment.
The bank is authored once and version-locked alongside the frozen slice.
Questions are stratified across KGR tiers so the sweep covers retrieval,
reasoning, and ablation-boundary behaviour uniformly.

TIER TAXONOMY (books spine)
  one_hop_retrieval   -- single-hop retrieval; grounding via direct triple.
                         These are the "easy" structure-grounded questions.
  multi_hop_reasoning -- multi-hop reasoning; grounding via a path across
                         2+ triples.  Tests the reasoned-supportable path.
  ablated_entity      -- question specifically probes an entity whose
                         description / triples may be withheld under an
                         ablation.  Designed to measure content-absence effect.

FACT TYPE (books content axis)
  genre_form          -- genre or form of the work (e.g. "memory play", "novel")
  tradition_affiliation -- literary tradition or school the work/author belongs to
  scope               -- descriptive scope (e.g. "Southern Gothic", "economic
                          treatise")
  descriptive_role    -- author/character/role descriptors from text content
  knowledge_structure -- purely KG-structural facts (triples, not descriptions)
  None                -- not applicable (multi-hop; no single content type)

UNRESOLVED ENTITIES
  out_of_slice_expected=True signals that the question is expected to produce
  unresolved entity mentions (entities that appear in the model answer but
  have no QID in the slice).  This lets test harnesses distinguish expected
  unresolved mentions from unexpected ones.

JSON I/O
  QuestionBank.to_json() / QuestionBank.from_json() are the canonical wire form.
  load_question_bank(path) reads a UTF-8 JSON file and returns a validated bank.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class QuestionTier(StrEnum):
    """KGR-style difficulty tier for a question.

    ONE_HOP_RETRIEVAL   -- answer grounded in a single direct triple.
    MULTI_HOP_REASONING -- answer requires traversing 2+ triples.
    ABLATED_ENTITY      -- question targets an entity subject to ablation;
                           measures content-absence sensitivity.
    """

    ONE_HOP_RETRIEVAL = "one_hop_retrieval"
    MULTI_HOP_REASONING = "multi_hop_reasoning"
    ABLATED_ENTITY = "ablated_entity"


class FactType(StrEnum):
    """Books-spine content fact type the question targets.

    genre_form              -- genre / literary form of the work.
    tradition_affiliation   -- literary tradition or school.
    scope                   -- thematic or descriptive scope.
    descriptive_role        -- author/character role from text description.
    knowledge_structure     -- purely structural KG facts (triples).
    """

    GENRE_FORM = "genre_form"
    TRADITION_AFFILIATION = "tradition_affiliation"
    SCOPE = "scope"
    DESCRIPTIVE_ROLE = "descriptive_role"
    KNOWLEDGE_STRUCTURE = "knowledge_structure"


# ---------------------------------------------------------------------------
# Core item
# ---------------------------------------------------------------------------


class QuestionBankItem(BaseModel):
    """One question in the fixed books question bank (SPEC-text §5 / EX1).

    Fields:
        item_id             -- stable identifier within this bank; unique within
                               a QuestionBank.
        question            -- verbatim question text posed to the generator.
        tier                -- KGR-style tier (one_hop_retrieval / multi_hop_reasoning
                               / ablated_entity).
        entity_id           -- primary Wikidata QID the question targets.
        slice_id            -- the frozen slice this question belongs to.
        fact_type           -- books-spine content fact type targeted; None when
                               the question spans multiple types (multi-hop).
        out_of_slice_expected -- True when the expected model answer is known to
                               mention entities not present in the frozen slice
                               (helps distinguish expected vs unexpected unresolved
                               mentions in the grounding output).
        notes               -- optional authoring note; not used in grading logic.
    """

    item_id: str
    question: str
    tier: QuestionTier
    entity_id: str
    slice_id: str
    fact_type: FactType | None = None
    out_of_slice_expected: bool = False
    notes: str | None = None


# ---------------------------------------------------------------------------
# Bank container
# ---------------------------------------------------------------------------


class QuestionBank(BaseModel):
    """A validated, versioned collection of QuestionBankItems.

    The bank is fixed for a given slice version; items are not modified
    after authoring.

    Fields:
        bank_id         -- stable identifier for this bank version.
        slice_id        -- the frozen slice this bank covers.
        items           -- the questions.
        schema_version  -- version tag for forward-compatibility.
    """

    bank_id: str
    slice_id: str
    items: Annotated[list[QuestionBankItem], Field(default_factory=list)]
    schema_version: str = "1.0"

    # ------------------------------------------------------------------
    # Convenience selectors
    # ------------------------------------------------------------------

    def items_by_tier(self, tier: QuestionTier) -> list[QuestionBankItem]:
        """Return items matching the given tier."""
        return [it for it in self.items if it.tier == tier]

    def tiers_present(self) -> set[QuestionTier]:
        """Return the set of tiers represented in this bank."""
        return {it.tier for it in self.items}

    # ------------------------------------------------------------------
    # JSON I/O
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize to a UTF-8 JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, s: str) -> QuestionBank:
        """Reconstruct a QuestionBank from a JSON string."""
        return cls.model_validate_json(s)


# ---------------------------------------------------------------------------
# File loader
# ---------------------------------------------------------------------------


def load_question_bank(path: str | Path) -> QuestionBank:
    """Load and validate a QuestionBank from a UTF-8 JSON file.

    Parameters
    ----------
    path:
        Path to the .json file.

    Returns
    -------
    QuestionBank
        Validated bank.  Raises pydantic.ValidationError on schema mismatch.
    """
    text = Path(path).read_text(encoding="utf-8")
    return QuestionBank.from_json(text)
