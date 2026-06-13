"""Tests for GR5 claim extraction (verifier-side, deterministic, structured h,r,t).

SPEC-text 4.3(A): RuleBasedExtractor is the offline-safe default;
LLMExtractor is the accuracy path (injectable complete= seam for testing).
No model downloads, no network, no generator client usage.
"""

from __future__ import annotations

import sys

import pytest

from ivg_kg.grounding.extract import (
    BaseClaimExtractor,
    ExtractedClaim,
    LLMExtractor,
    RuleBasedExtractor,
    make_extractor,
)
from ivg_kg.schema import GroundingConfig

# ---------------------------------------------------------------------------
# Test 1: RuleBasedExtractor on a multi-sentence books answer
# ---------------------------------------------------------------------------


def test_rule_based_multi_sentence_basic():
    """Two sentences -> two ExtractedClaims with correct (head, relation, tail)."""
    text = "Beloved was written by Toni Morrison. The Glass Menagerie is a play."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 2

    # First claim: "Beloved was written by Toni Morrison."
    # The cue "was written by" matches (longer cue wins over "was" alone).
    c0 = claims[0]
    assert c0.head == "Beloved"
    assert c0.relation == "was written by"
    assert c0.tail == "Toni Morrison"

    # Second claim: "The Glass Menagerie is a play."
    # Leading article is NOT stripped -- canonical title must survive intact for GR6.
    c1 = claims[1]
    assert c1.head == "The Glass Menagerie"
    assert c1.relation == "is a"
    assert c1.tail == "play"


# ---------------------------------------------------------------------------
# Test 2: Longer-phrase wins (relation-cue ordering)
# ---------------------------------------------------------------------------


def test_rule_based_longer_cue_wins():
    """'is the author of' must win over the shorter 'is'."""
    # Use a name without abbreviation periods to avoid triggering the sentence splitter.
    text = "George Orwell is the author of Nineteen Eighty-Four."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.relation == "is the author of"
    assert c.head == "George Orwell"
    assert c.tail == "Nineteen Eighty-Four"


# ---------------------------------------------------------------------------
# Test 3: Graceful degradation when no cue matches
# ---------------------------------------------------------------------------


def test_rule_based_no_cue_degradation():
    """A sentence with no recognised cue yields a triplet with head==text, relation=='', tail==''."""
    text = "Something inscrutable."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.head == text
    assert c.relation == ""
    assert c.tail == ""


# ---------------------------------------------------------------------------
# Test 4: Article stripping and trailing period stripping
# ---------------------------------------------------------------------------


def test_rule_based_article_and_period_strip():
    """'Dracula is a novel.' -> tail=='novel' (period stripped; cue 'is a' already consumed the article)."""
    text = "Dracula is a novel."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.head == "Dracula"
    assert c.relation == "is a"
    assert c.tail == "novel"


def test_rule_based_is_the_cue():
    """'is the' is matched as a cue; the article is consumed by the cue, not stripped."""
    text = "Moby Dick is the novel."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.relation == "is the"
    # 'is the' is a cue; tail is whatever follows -- no article left to strip
    assert c.tail == "novel"


def test_rule_based_is_an_cue():
    """'is an' is matched as a cue; the article is consumed by the cue, not stripped."""
    text = "Hamlet is an epic."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    # 'is an' is a cue; tail follows cue with no article left to strip
    assert c.relation == "is an"
    assert c.tail == "epic"


# ---------------------------------------------------------------------------
# Test 5: Determinism and caching
# ---------------------------------------------------------------------------


def test_rule_based_determinism():
    """Same input -> identical output on repeated calls (value-equal)."""
    text = "Beloved was written by Toni Morrison. The Glass Menagerie is a play."
    extractor = RuleBasedExtractor()
    result1 = extractor.extract(text)
    result2 = extractor.extract(text)

    assert result1 == result2


def test_rule_based_cache_returns_same_object():
    """Second extract() call returns the cached list (same object identity)."""
    text = "Beloved was written by Toni Morrison."
    extractor = RuleBasedExtractor()
    result1 = extractor.extract(text)
    result2 = extractor.extract(text)

    # The second call must be served from cache: same object
    assert result1 is result2


def test_rule_based_extract_calls_inner_only_once(monkeypatch):
    """_extract is called exactly once for repeated extract() calls (cache hit)."""
    extractor = RuleBasedExtractor()
    call_count = 0
    original = extractor._extract

    def counting_extract(answer_text: str):
        nonlocal call_count
        call_count += 1
        return original(answer_text)

    monkeypatch.setattr(extractor, "_extract", counting_extract)

    text = "Beloved was written by Toni Morrison."
    extractor.extract(text)
    extractor.extract(text)
    extractor.extract(text)

    assert call_count == 1


# ---------------------------------------------------------------------------
# Test 6: Sentence splitting and edge cases
# ---------------------------------------------------------------------------


def test_rule_based_empty_input():
    """Empty / whitespace-only input yields empty list."""
    extractor = RuleBasedExtractor()
    assert extractor.extract("") == []
    assert extractor.extract("   ") == []
    assert extractor.extract("\n\t") == []


def test_rule_based_semicolon_split():
    """Semicolons also act as sentence boundaries."""
    text = "Beloved was written by Toni Morrison; 1984 was written by George Orwell."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 2
    assert claims[0].head == "Beloved"
    assert claims[1].head == "1984"


def test_rule_based_split_on_question_and_exclamation():
    """! and ? also act as sentence boundaries."""
    text = "Was Hamlet written by Shakespeare? Yes, it was written by Shakespeare!"
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    # Two sentences split on ? + whitespace
    assert len(claims) == 2


# ---------------------------------------------------------------------------
# Test 7: LLMExtractor with injected complete stub
# ---------------------------------------------------------------------------


def _make_stub_complete(output: str):
    """Return a deterministic completion stub that ignores input."""

    def complete(prompt: str) -> str:
        return output

    return complete


def test_llm_extractor_basic_parse():
    """LLMExtractor with a stub complete -> parses two triplets correctly."""
    stub_output = "Beloved ; written by ; Toni Morrison\nThe Glass Menagerie ; is a ; play"
    extractor = LLMExtractor(complete=_make_stub_complete(stub_output))
    claims = extractor.extract(
        "Beloved was written by Toni Morrison. The Glass Menagerie is a play."
    )

    assert len(claims) == 2

    c0 = claims[0]
    assert c0.head == "Beloved"
    assert c0.relation == "written by"
    assert c0.tail == "Toni Morrison"

    c1 = claims[1]
    assert c1.head == "The Glass Menagerie"
    assert c1.relation == "is a"
    assert c1.tail == "play"


def test_llm_extractor_malformed_line_tolerance():
    """Malformed lines (no semicolons / wrong format) are skipped gracefully."""
    stub_output = (
        "Beloved ; written by ; Toni Morrison\n"
        "this line has no semicolons and should be skipped\n"
        "also bad\n"
        "The Glass Menagerie ; is a ; play"
    )
    extractor = LLMExtractor(complete=_make_stub_complete(stub_output))
    claims = extractor.extract("any text")

    # Only the two well-formed lines should produce claims
    assert len(claims) == 2
    assert claims[0].head == "Beloved"
    assert claims[1].head == "The Glass Menagerie"


def test_llm_extractor_empty_output():
    """Empty model output -> empty claims list."""
    extractor = LLMExtractor(complete=_make_stub_complete(""))
    claims = extractor.extract("some answer text")
    assert claims == []


def test_llm_extractor_caching():
    """LLMExtractor also caches by answer_text (same object on repeat call)."""
    stub_output = "Beloved ; written by ; Toni Morrison"
    extractor = LLMExtractor(complete=_make_stub_complete(stub_output))
    text = "Beloved was written by Toni Morrison."
    r1 = extractor.extract(text)
    r2 = extractor.extract(text)
    assert r1 is r2


def test_llm_extractor_does_not_use_generator_client():
    """LLMExtractor must not import or reference generator clients."""
    # If the module imports cleanly with a stub complete=, the invariant holds.
    # We additionally verify no generator-client attribute is set on the instance.
    extractor = LLMExtractor(complete=_make_stub_complete("a ; b ; c"))
    assert not hasattr(extractor, "_ai_client")
    assert not hasattr(extractor, "_generator")
    # Verify the extract module does not export or reference generator client names.
    # (clients may be loaded by other tests; we check the extract module object itself)
    import ivg_kg.grounding.extract as extract_mod

    assert not hasattr(extract_mod, "BaseAIClient")
    assert not hasattr(extract_mod, "LocalModelClient")
    assert not hasattr(extract_mod, "OllamaClient")
    assert not hasattr(extract_mod, "CloudAIClient")
    # sys is available at module scope via the top-level import
    _ = sys.modules  # verify sys is accessible (imported at top of test file)


# ---------------------------------------------------------------------------
# Test 8: make_extractor factory
# ---------------------------------------------------------------------------


def test_make_extractor_rule_based():
    """make_extractor('rule_based') returns a RuleBasedExtractor."""
    e = make_extractor("rule_based")
    assert isinstance(e, RuleBasedExtractor)


def test_make_extractor_default():
    """make_extractor() with no args returns a RuleBasedExtractor."""
    e = make_extractor()
    assert isinstance(e, RuleBasedExtractor)


def test_make_extractor_llm_with_complete():
    """make_extractor('llm', complete=stub) returns an LLMExtractor."""
    stub = _make_stub_complete("a ; b ; c")
    e = make_extractor("llm", complete=stub)
    assert isinstance(e, LLMExtractor)


def test_make_extractor_unknown_raises():
    """make_extractor with an unknown name raises ValueError naming the bad value."""
    with pytest.raises(ValueError, match="nope"):
        make_extractor("nope")


# ---------------------------------------------------------------------------
# Test 9: GroundingConfig extractor field
# ---------------------------------------------------------------------------


def test_grounding_config_extractor_default():
    """GroundingConfig().extractor == 'rule_based' (default value)."""
    cfg = GroundingConfig()
    assert cfg.extractor == "rule_based"


def test_grounding_config_extractor_round_trip():
    """GroundingConfig round-trips through JSON without losing the extractor field."""
    cfg = GroundingConfig(extractor="llm")
    json_str = cfg.model_dump_json()
    cfg2 = GroundingConfig.model_validate_json(json_str)
    assert cfg2.extractor == "llm"


def test_grounding_config_default_round_trip():
    """Default GroundingConfig round-trips correctly."""
    cfg = GroundingConfig()
    cfg2 = GroundingConfig.model_validate_json(cfg.model_dump_json())
    assert cfg2.extractor == "rule_based"
    assert cfg2.k_hops == 2
    assert cfg2.tau == 0.5
    assert cfg2.linker == "label_alias"
    assert cfg2.entailment == "minicheck"


# ---------------------------------------------------------------------------
# Test 10: ExtractedClaim is a proper pydantic v2 model
# ---------------------------------------------------------------------------


def test_extracted_claim_model():
    """ExtractedClaim is constructible and serialisable as pydantic v2."""
    c = ExtractedClaim(
        text="Beloved was written by Toni Morrison.",
        head="Beloved",
        relation="written by",
        tail="Toni Morrison",
    )
    assert c.text == "Beloved was written by Toni Morrison."
    d = c.model_dump()
    assert d["head"] == "Beloved"
    assert d["relation"] == "written by"
    assert d["tail"] == "Toni Morrison"


def test_extracted_claim_empty_relation():
    """ExtractedClaim allows empty relation and tail (degradation triplet)."""
    c = ExtractedClaim(
        text="Something inscrutable.",
        head="Something inscrutable.",
        relation="",
        tail="",
    )
    assert c.relation == ""
    assert c.tail == ""


# ---------------------------------------------------------------------------
# Test 11: BaseClaimExtractor ABC contract
# ---------------------------------------------------------------------------


def test_base_claim_extractor_is_abstract():
    """BaseClaimExtractor cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseClaimExtractor()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Test 12: extract method is the public cached wrapper (not _extract directly)
# ---------------------------------------------------------------------------


def test_extract_text_field_is_source_sentence():
    """Each ExtractedClaim.text is the source sentence for that triplet."""
    text = "Beloved was written by Toni Morrison. 1984 was written by George Orwell."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 2
    assert claims[0].text == "Beloved was written by Toni Morrison."
    assert claims[1].text == "1984 was written by George Orwell."


# ---------------------------------------------------------------------------
# Test 13: published_in and published_by cues
# ---------------------------------------------------------------------------


def test_rule_based_published_in_cue():
    """'published in' cue parses correctly."""
    text = "Beloved was published in 1987."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    # 'was published in' is the longer cue and should match
    assert "published in" in claims[0].relation
    assert claims[0].head == "Beloved"
    assert "1987" in claims[0].tail


def test_rule_based_authored_by_cue():
    """'authored by' cue parses correctly."""
    text = "Moby Dick was authored by Herman Melville."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    assert "authored by" in claims[0].relation
    assert claims[0].head == "Moby Dick"
    assert claims[0].tail == "Herman Melville"


# ---------------------------------------------------------------------------
# Test 14: Leading-article titles survive intact (GR6 linker regression guard)
# ---------------------------------------------------------------------------


def test_title_with_leading_article_a_in_head():
    """'A Tale of Two Cities was written by Charles Dickens.' -- 'A' is part of the title."""
    text = "A Tale of Two Cities was written by Charles Dickens."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.head == "A Tale of Two Cities"
    assert c.relation == "was written by"
    assert c.tail == "Charles Dickens"


def test_title_with_leading_article_a_in_tail():
    """'Charles Dickens wrote A Tale of Two Cities.' -- 'A' is part of the title in tail."""
    text = "Charles Dickens wrote A Tale of Two Cities."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.head == "Charles Dickens"
    assert c.relation == "wrote"
    # Trailing period stripped; leading article in title preserved
    assert c.tail == "A Tale of Two Cities"


def test_title_with_leading_article_the_in_head():
    """'The Glass Menagerie is a play.' -- 'The' is part of the canonical title."""
    text = "The Glass Menagerie is a play."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.head == "The Glass Menagerie"
    assert c.relation == "is a"
    assert c.tail == "play"


def test_common_noun_tail_period_stripped():
    """'Dracula is a novel.' -- period stripped from tail; cue 'is a' consumes the article."""
    text = "Dracula is a novel."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    assert c.head == "Dracula"
    assert c.relation == "is a"
    assert c.tail == "novel"


def test_cue_at_sentence_start_empty_head():
    """A sentence starting with a cue produces head=='' (degenerate but deterministic)."""
    text = "is a novel."
    extractor = RuleBasedExtractor()
    claims = extractor.extract(text)

    assert len(claims) == 1
    c = claims[0]
    # The cue fires at position 0; head is the empty string before it.
    assert c.head == ""
    assert c.relation == "is a"
    assert c.tail == "novel"
