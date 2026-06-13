"""GR5 -- Claim extraction (VERIFIER core, SPEC-text 4.3(A)).

Extracts structured (head, relation, tail) triplets from LLM answer text.
This is a VERIFIER-SIDE stage:

    - DETERMINISTIC: identical answer_text -> identical triplet list.
    - STRUCTURED OUTPUT: produces ExtractedClaim(h, r, t), NOT free text.
    - NO GENERATOR CLIENT: this module MUST NOT import or use
      ivg_kg.grounding.clients.BaseAIClient or any concrete generator client
      (LocalModelClient, OllamaClient, CloudAIClient).  Those are generator-only
      and their docstring forbids using them for verification/grading.
    - CACHED: per-instance dict cache keyed by answer_text hash.

Three implementations are provided:

    RuleBasedExtractor  -- model-free, always available offline.
                           Used as the default in tests, fixtures, and the
                           offline pipeline.

    LLMExtractor        -- RefChecker/KGR-style seq2seq extractor.
                           The completion function is INJECTABLE (complete=)
                           so it is testable without any model download.
                           Lazy-loads a HF model only when complete= is None
                           and the extractor is first called.

Factory:
    make_extractor(name="rule_based", **kwargs) returns the configured extractor.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

__all__ = [
    "ExtractedClaim",
    "BaseClaimExtractor",
    "RuleBasedExtractor",
    "LLMExtractor",
    "make_extractor",
]

# ---------------------------------------------------------------------------
# Verifier-internal output type
# ---------------------------------------------------------------------------


class ExtractedClaim(BaseModel):
    """A single (head, relation, tail) triplet extracted from one claim sentence.

    This type is VERIFIER-INTERNAL and is not part of the backend<->UI schema
    contract (schema.py).  Linking head/tail to QIDs is done in GR6, not here.
    """

    text: str  # the verbatim claim sentence this triplet came from
    head: str  # subject surface string (NOT yet linked to a QID; GR6 links it)
    relation: str  # relation/predicate surface string ("" if none could be parsed)
    tail: str  # object surface string ("" if none could be parsed)


# ---------------------------------------------------------------------------
# Sentence-boundary splitter (mirrors slice.split_claims rule exactly)
# ---------------------------------------------------------------------------

# Sentence-ending .!? followed by whitespace, OR semicolon (with optional ws).
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=;)\s*")


def _split_sentences(answer_text: str) -> list[str]:
    """Split answer_text into claim-sized sentence units.

    Uses the SAME deterministic boundary rule as slice.split_claims:
    sentence-ending .!? followed by whitespace, or semicolons.
    Strips whitespace; drops empties.
    """
    stripped = answer_text.strip()
    if not stripped:
        return []
    parts = _SPLIT_RE.split(stripped)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Relation cue lexicon
# ---------------------------------------------------------------------------
# Match order: earliest start position wins; on a start-position tie, the
# longer match wins.  Longer phrases are listed before their prefixes so
# the tie-break fires correctly when both start at the same offset.
# All entries are lowercase; matching is case-insensitive on word boundaries.

_RELATION_CUES: list[str] = [
    "was written by",
    "were written by",
    "is written by",
    "written by",
    "was authored by",
    "authored by",
    "is the author of",
    "author of",
    "wrote",
    "is a",
    "is an",
    "is the",
    "was a",
    "was an",
    "was the",
    "is",
    "was",
    "are",
    "were",
    "belongs to",
    "is part of",
    "was published in",
    "published in",
    "was published by",
    "published by",
]

# Pre-compiled regex patterns for each cue (case-insensitive, word boundaries).
# Stored as (cue_string, compiled_pattern) in the same order as _RELATION_CUES.
_CUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = []
for _cue in _RELATION_CUES:
    # Use word boundary on the left; allow end of string or non-word on the right.
    # re.escape handles multi-word cues correctly (spaces are literal).
    _pattern = re.compile(
        r"(?<!\w)" + re.escape(_cue) + r"(?!\w)",
        re.IGNORECASE,
    )
    _CUE_PATTERNS.append((_cue, _pattern))

_TRAILING_PERIOD_RE = re.compile(r"[.]+$")


def _parse_triplet(sentence: str) -> tuple[str, str, str]:
    """Parse a single sentence into (head, relation, tail).

    Selects the cue with the earliest start position in the sentence; on a
    start-position tie, the longer match wins.  Returns (sentence, "", "") when
    no cue matches, preserving recall for downstream handling.

    Article stripping is intentionally NOT done here -- canonical book/work
    titles carry leading articles (e.g. "A Tale of Two Cities", "The Glass
    Menagerie") and stripping them would break GR6 Wikidata label matching.
    Article normalisation is delegated to the GR6 linker.
    """
    # Find the cue with the earliest match position; among ties, longest first
    # (the lexicon is already ordered longest-first so we iterate in order and
    # keep the earliest-start match across all cues).
    best_match: re.Match[str] | None = None
    best_cue: str = ""

    for cue, pattern in _CUE_PATTERNS:
        m = pattern.search(sentence)
        if m is None:
            continue
        # Select the match that starts EARLIEST in the sentence.
        # Among ties (same start position), prefer the LONGER cue (longer end).
        # This ensures "was published in" wins over "was" at the same position.
        if best_match is None:
            best_match = m
            best_cue = cue
        elif m.start() < best_match.start():
            best_match = m
            best_cue = cue
        elif m.start() == best_match.start() and m.end() > best_match.end():
            best_match = m
            best_cue = cue

    if best_match is None:
        # No cue found - degrade gracefully
        return sentence, "", ""

    head = sentence[: best_match.start()].strip()
    tail_raw = sentence[best_match.end() :].strip()

    # Strip trailing period only (e.g. "novel." -> "novel").
    # Leading articles are preserved so the GR6 linker can match canonical labels.
    tail = _TRAILING_PERIOD_RE.sub("", tail_raw).strip()

    return head, best_cue, tail


# ---------------------------------------------------------------------------
# Base ABC
# ---------------------------------------------------------------------------


class BaseClaimExtractor(ABC):
    """Abstract claim extractor.

    Subclasses implement _extract(answer_text) -> list[ExtractedClaim].
    extract() wraps _extract with an in-process per-instance cache keyed by
    answer_text.

    Contract:
        - extract(answer_text) -> list[ExtractedClaim]; deterministic; cached.
        - VERIFIER-SIDE: MUST NOT use ivg_kg.grounding.clients.BaseAIClient or
          any concrete generator client.
        - Identical answer_text -> identical list (bit-stable, cache-consistent).
    """

    def __init__(self) -> None:
        # Per-instance cache: answer_text -> list[ExtractedClaim].
        # Unbounded by design (one extractor instance per pipeline sweep is fine).
        # Not thread-safe -- the pipeline is single-threaded and deterministic.
        self._cache: dict[str, list[ExtractedClaim]] = {}

    def extract(self, answer_text: str) -> list[ExtractedClaim]:
        """Return structured ExtractedClaim list for answer_text.

        Cached by answer_text: repeated calls with the same text return the
        same list object (identity, not just equality).

        IMPORTANT: the returned list is the shared cached object.  Callers
        must treat it as read-only and must not mutate it (append, remove,
        or reassign elements); doing so would corrupt the cache for all
        subsequent callers.
        """
        if answer_text in self._cache:
            return self._cache[answer_text]
        result = self._extract(answer_text)
        self._cache[answer_text] = result
        return result

    @abstractmethod
    def _extract(self, answer_text: str) -> list[ExtractedClaim]:
        """Compute structured ExtractedClaim list without caching.

        Subclasses implement this.  The caching wrapper lives in extract().
        """
        ...


# ---------------------------------------------------------------------------
# RuleBasedExtractor -- model-free, always available offline
# ---------------------------------------------------------------------------


class RuleBasedExtractor(BaseClaimExtractor):
    """Model-free deterministic claim extractor using a fixed relation-cue lexicon.

    Suitable for offline use, CI, and tests (no model download required).

    Algorithm:
        1. Split answer_text into sentences using the same regex as slice.split_claims.
        2. For each sentence, find the relation cue with the earliest start position;
           on a start-position tie, the longer match wins.
        3. head = text before the cue (surface string preserved, no article stripping).
        4. relation = the matched cue (canonical lowercase as stored in lexicon).
        5. tail = text after the cue (trailing period stripped; articles preserved).
        6. If no cue matches: degrade to (sentence, "", "") to preserve recall.

    Determinism: pure regex over ASCII-normalised text; no randomness, no I/O,
    no model.  Identical input -> identical output every time.
    """

    def _extract(self, answer_text: str) -> list[ExtractedClaim]:
        """Parse answer_text into a list of ExtractedClaims.

        One sentence -> one ExtractedClaim (one triplet per sentence in the
        rule-based path).  Sentences are split by _split_sentences().
        """
        sentences = _split_sentences(answer_text)
        claims: list[ExtractedClaim] = []
        for sentence in sentences:
            head, relation, tail = _parse_triplet(sentence)
            claims.append(
                ExtractedClaim(
                    text=sentence,
                    head=head,
                    relation=relation,
                    tail=tail,
                )
            )
        return claims


# ---------------------------------------------------------------------------
# LLM extraction prompt template (vendored KGR/VeGraph fallback prompt)
# ---------------------------------------------------------------------------

_LLM_EXTRACTION_PROMPT: str = (
    "Decompose the following answer into atomic (subject; relation; object) triplets, "
    "one per line. Use semicolons to separate the three parts. "
    "Output ONLY the triplets, no explanation.\n\n"
    "Answer: {answer_text}\n\n"
    "Triplets:"
)

# ---------------------------------------------------------------------------
# LLMExtractor -- RefChecker-style seq2seq extractor (optional, lazy-loaded)
# ---------------------------------------------------------------------------


class LLMExtractor(BaseClaimExtractor):
    """RefChecker/KGR-style LLM-based claim extractor (verifier-side, optional).

    The completion function is INJECTABLE (complete= parameter) so the class
    is fully testable without any model download.

    Determinism contract: pinned greedy decoding (temperature=0, do_sample=False,
    num_beams=1), fixed input format, fixed batch order.

    Generator-client isolation: this class MUST NOT import or use
    ivg_kg.grounding.clients.BaseAIClient or any concrete generator client.
    It has its own lazy-load path using HF transformers directly.

    Args:
        complete: Optional callable (str) -> str.  If provided, used as the
            deterministic completion function (test/seam path).  If None, a HF
            seq2seq model is lazy-loaded on the first _extract() call.
        model_id: Optional HF model ID for the lazy-load path.  Ignored when
            complete is provided.
    """

    def __init__(
        self,
        *,
        complete: Callable[[str], str] | None = None,
        model_id: str | None = None,
    ) -> None:
        super().__init__()
        self._complete = complete
        self._model_id = model_id
        self._tokenizer: Any = None  # lazy-loaded
        self._model: Any = None  # lazy-loaded

    def _load(self) -> None:  # pragma: no cover
        """Lazy-load HF seq2seq model for the live path.

        Only called when complete= is None and _extract() is first invoked.
        Imports are deferred so the module is importable with no model present.
        Pinned to float32 for bit-stable determinism (SPEC ss4.3, Invariants #8/#14).
        """
        import torch  # noqa: PLC0415 -- intentionally lazy
        from transformers import (  # noqa: PLC0415 -- intentionally lazy
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
        )

        model_id = self._model_id or "google/flan-t5-base"
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(
            model_id,
            torch_dtype=torch.float32,
        )
        self._model.eval()

    def _complete_with_model(self, prompt: str) -> str:  # pragma: no cover
        """Run greedy inference with the lazy-loaded model.

        Pinned greedy: do_sample=False, num_beams=1, temperature not set
        (greedy decoding is deterministic given a fixed model state).
        """
        import torch  # noqa: PLC0415 -- intentionally lazy

        if self._tokenizer is None or self._model is None:
            self._load()

        inputs = self._tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                num_beams=1,
            )
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    @staticmethod
    def _parse_model_output(raw_output: str, answer_text: str) -> list[ExtractedClaim]:
        """Deterministically parse model output into ExtractedClaim list.

        Expected format: one triplet per non-empty line as
            head ; relation ; tail
        Lines with fewer than 2 semicolons are silently skipped.
        Trailing periods on any part are stripped.
        text is set to the full answer_text since line-to-sentence alignment
        is not available without a second pass.
        """
        claims: list[ExtractedClaim] = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(";")]
            if len(parts) < 3:
                # Malformed: skip (tolerate gracefully)
                continue
            head = _TRAILING_PERIOD_RE.sub("", parts[0]).strip()
            relation = _TRAILING_PERIOD_RE.sub("", parts[1]).strip()
            tail = _TRAILING_PERIOD_RE.sub("", parts[2]).strip()
            if not head and not relation and not tail:
                continue
            claims.append(
                ExtractedClaim(
                    text=answer_text,
                    head=head,
                    relation=relation,
                    tail=tail,
                )
            )
        return claims

    def _extract(self, answer_text: str) -> list[ExtractedClaim]:
        """Build prompt, call completion, parse output deterministically."""
        prompt = _LLM_EXTRACTION_PROMPT.format(answer_text=answer_text)

        if self._complete is not None:
            raw_output = self._complete(prompt)
        else:  # pragma: no cover
            raw_output = self._complete_with_model(prompt)

        return self._parse_model_output(raw_output, answer_text)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_extractor(name: str = "rule_based", **kwargs: Any) -> BaseClaimExtractor:
    """Return the claim extractor selected by name.

    Valid selectors:
        "rule_based" -> RuleBasedExtractor (model-free, always available)
        "llm"        -> LLMExtractor(**kwargs) (injectable complete= or lazy HF)

    Raises ValueError for unknown selectors.
    """
    if name == "rule_based":
        return RuleBasedExtractor()
    if name == "llm":
        return LLMExtractor(**kwargs)
    raise ValueError(f"Unknown extractor selector: {name!r}. Valid options: 'rule_based', 'llm'.")
