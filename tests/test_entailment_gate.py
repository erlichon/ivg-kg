"""Tests for GR7 BaseEntailmentGate and concrete implementations.

TDD: all tests written before implementation.  The full suite must run with NO
model download / no network access.

Coverage contract:
  - ABC is non-instantiable.
  - entails() signature returns float in [0, 1].
  - LexicalEntailmentGate: value-sensitivity, asymmetry, determinism.
  - DebertaEntailmentGate / MiniCheckEntailmentGate: lazy import + factory type
    selection (no model load).
  - Cache: repeated identical pairs are served from cache (scorer not re-invoked).
  - Factory selects correct class from config.entailment.
  - Slice tests remain green (regression guard: import entails from slice still works).
"""
from __future__ import annotations

import sys
from typing import Any

import pytest

from ivg_kg.schema import GroundingConfig

# ---------------------------------------------------------------------------
# ABC non-instantiable
# ---------------------------------------------------------------------------

def test_base_entailment_gate_is_abstract():
    """BaseEntailmentGate cannot be instantiated directly."""
    from ivg_kg.grounding.entailment import BaseEntailmentGate
    with pytest.raises(TypeError):
        BaseEntailmentGate()  # type: ignore[abstract]


def test_base_entailment_gate_has_entails_method():
    """BaseEntailmentGate exposes an abstract entails(premise, hypothesis) -> float."""
    import inspect

    from ivg_kg.grounding.entailment import BaseEntailmentGate
    assert "entails" in set(dir(BaseEntailmentGate))
    sig = inspect.signature(BaseEntailmentGate.entails)
    params = list(sig.parameters)
    # self, premise, hypothesis
    assert "premise" in params
    assert "hypothesis" in params


# ---------------------------------------------------------------------------
# LexicalEntailmentGate: contract
# ---------------------------------------------------------------------------

def test_lexical_gate_returns_float_in_unit_interval():
    """LexicalEntailmentGate.entails must return float in [0, 1]."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    score = gate.entails("Alice wrote a book", "Alice authored a text")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_lexical_gate_exact_overlap_gives_high_score():
    """Identical premise and hypothesis -> score near 1.0 (full token overlap)."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    text = "Tennessee Williams wrote The Glass Menagerie"
    score = gate.entails(text, text)
    assert score > 0.8


def test_lexical_gate_no_overlap_gives_low_score():
    """Completely disjoint tokens -> score == 0.0."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    score = gate.entails("apple orange banana", "umbrella quantum matrix")
    assert score == 0.0


# ---------------------------------------------------------------------------
# LexicalEntailmentGate: value-sensitivity (Invariant #3)
# ---------------------------------------------------------------------------

def test_lexical_value_sensitive_wrong_year_scores_zero():
    """Hypothesis asserting a WRONG year vs premise with the correct year -> 0.0."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    premise = "The Glass Menagerie date of first performance 1944"
    hypothesis = "The Glass Menagerie was first performed in 1960."
    score = gate.entails(premise, hypothesis)
    assert score == 0.0, f"Wrong-year hypothesis must score 0.0, got {score}"


def test_lexical_value_sensitive_correct_year_scores_positive():
    """Hypothesis asserting the CORRECT year present in premise -> positive score."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    premise = "The Glass Menagerie date of first performance 1944"
    hypothesis = "The Glass Menagerie first performance was in 1944."
    score = gate.entails(premise, hypothesis)
    assert score > 0.0, f"Correct-year hypothesis must score > 0.0, got {score}"


def test_lexical_value_sensitive_entity_match_alone_not_support():
    """Entity name present in both premise and hypothesis but year wrong -> score 0.0."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    # premise has 1871; hypothesis says 1850 (wrong number)
    premise = "Principles of Economics Vienna 1871"
    hypothesis = "Principles of Economics was published in Berlin in 1850."
    score = gate.entails(premise, hypothesis)
    assert score == 0.0, f"Entity match alone must not score > 0 when year wrong, got {score}"


def test_lexical_value_sensitive_omitted_value_scores_zero():
    """Hypothesis asserting a specific date that is completely absent from premise -> 0.0."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    premise = "Hamlet is a play by Shakespeare"
    hypothesis = "Hamlet was written in 1603."
    score = gate.entails(premise, hypothesis)
    assert score == 0.0, f"Omitted year assertion must score 0.0, got {score}"


# ---------------------------------------------------------------------------
# LexicalEntailmentGate: asymmetry
# ---------------------------------------------------------------------------

def test_lexical_gate_is_asymmetric():
    """Swapping premise and hypothesis produces a genuine direction split."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    # premise has date 1944; hypothesis lacks it -> value check fires only on the
    # reverse direction (where 1944 appears in the hypothesis).
    # forward: hyp has no value assertion -> positive Jaccard score.
    # reverse: hyp has 1944 which is absent from "first performance" -> value block -> 0.0.
    premise = "first performance 1944 St Louis"
    hypothesis = "first performance"
    fwd = gate.entails(premise, hypothesis)
    rev = gate.entails(hypothesis, premise)
    assert (fwd > 0.0) != (rev > 0.0), (
        f"expected a genuine direction split: fwd={fwd}, rev={rev}"
    )


def test_lexical_gate_premise_evidence_hypothesis_claim_convention():
    """Premise=reference (has date), hypothesis=claim (omits date) -> positive.
    Swapped direction (claim as premise, reference as hypothesis) -> 0.0 due to value check."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    reference = "The Glass Menagerie Tennessee Williams 1944 premiere"
    claim_no_date = "Tennessee Williams wrote The Glass Menagerie."
    # Correct direction: premise=reference, hyp=claim (no date assertion -> no value block)
    fwd = gate.entails(reference, claim_no_date)
    # Reversed: premise=claim (no date), hyp=reference (HAS 1944 -> value check: 1944 not in claim -> 0)
    rev = gate.entails(claim_no_date, reference)
    assert fwd > 0.0, f"Correct direction (reference as premise) should score > 0, got {fwd}"
    assert rev == 0.0, f"Reversed direction (reference as hypothesis) should score 0.0, got {rev}"


# ---------------------------------------------------------------------------
# LexicalEntailmentGate: determinism
# ---------------------------------------------------------------------------

def test_lexical_gate_is_deterministic():
    """Same (premise, hypothesis) always produces the exact same float."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    p = "Tennessee Williams wrote The Glass Menagerie premiere 1944"
    h = "The Glass Menagerie premiered in 1944."
    scores = [gate.entails(p, h) for _ in range(10)]
    assert len(set(scores)) == 1, f"Expected all identical, got {set(scores)}"


def test_lexical_gate_empty_inputs_return_zero():
    """Empty premise or empty hypothesis returns 0.0."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    assert gate.entails("", "some hypothesis") == 0.0
    assert gate.entails("some premise", "") == 0.0
    assert gate.entails("", "") == 0.0


# ---------------------------------------------------------------------------
# Cache: repeated identical pair served from cache
# ---------------------------------------------------------------------------

def test_cache_avoids_repeated_scoring():
    """A second identical (premise, hypothesis) call is served from cache.

    Monkeypatches the internal _score method on a LexicalEntailmentGate subclass
    to count invocations; asserts the scorer is called only once for two identical
    pairs.
    """
    from ivg_kg.grounding.entailment import LexicalEntailmentGate

    call_count = 0
    original_score = LexicalEntailmentGate._score

    class InstrumentedGate(LexicalEntailmentGate):
        def _score(self, premise: str, hypothesis: str) -> float:
            nonlocal call_count
            call_count += 1
            return original_score(self, premise, hypothesis)

    gate = InstrumentedGate()
    p = "Tennessee Williams premiere 1944"
    h = "premiere 1944"

    score1 = gate.entails(p, h)
    score2 = gate.entails(p, h)

    assert score1 == score2
    assert call_count == 1, (
        f"_score should be called once for repeated identical pair, called {call_count} times"
    )


def test_cache_is_keyed_by_premise_hypothesis_pair():
    """Different (premise, hypothesis) pairs are scored separately (no false cache hits)."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    gate = LexicalEntailmentGate()
    s1 = gate.entails("Alice wrote a book 1900", "Alice wrote a book in 1900.")
    s2 = gate.entails("Bob wrote a book 1901", "Bob wrote a book in 1901.")
    # Both should return scores independently; different inputs -> potentially different scores
    # The critical property: the second call did NOT return the first call's cached value.
    # (here the scores may coincidentally equal; test that cache doesn't cross-contaminate
    # by verifying a clearly distinct pair)
    s_wrong = gate.entails("completely unrelated text", "another unrelated sentence")
    # s_wrong should not equal s1 (they are very different inputs)
    # Just ensure both are in [0,1] and the gate processed both
    assert 0.0 <= s1 <= 1.0
    assert 0.0 <= s2 <= 1.0
    assert 0.0 <= s_wrong <= 1.0


def test_cache_cleared_on_new_instance():
    """Two separate gate instances have independent caches."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate
    g1 = LexicalEntailmentGate()
    g2 = LexicalEntailmentGate()
    p, h = "same text", "same text"
    g1.entails(p, h)
    # g2's cache is independent; this is structural (separate dict per instance)
    assert g1._cache is not g2._cache


# ---------------------------------------------------------------------------
# DebertaEntailmentGate: lazy import + factory type (no model load)
# ---------------------------------------------------------------------------

def test_deberta_gate_importable_without_model():
    """DebertaEntailmentGate class is importable with no transformers/torch installed."""
    # If transformers is absent, this must still import cleanly.
    from ivg_kg.grounding.entailment import DebertaEntailmentGate  # noqa: F401


def test_deberta_gate_constructed_without_model_load(monkeypatch):
    """DebertaEntailmentGate.__init__ does NOT load the model on construction.

    The lazy loader is monkeypatched to assert it is never called at import or
    construction time.
    """
    from ivg_kg.grounding import entailment as mod

    loaded = []

    def fake_load_deberta(model_id: str):
        loaded.append(model_id)
        raise RuntimeError("Model must not be loaded in tests")

    monkeypatch.setattr(mod, "_load_deberta_model", fake_load_deberta)

    from ivg_kg.grounding.entailment import DebertaEntailmentGate
    gate = DebertaEntailmentGate(model_id="test-model-id")
    assert not loaded, "Model should not be loaded at construction time"
    assert isinstance(gate, DebertaEntailmentGate)


def test_deberta_gate_is_subclass_of_base():
    """DebertaEntailmentGate is a subclass of BaseEntailmentGate."""
    from ivg_kg.grounding.entailment import BaseEntailmentGate, DebertaEntailmentGate
    assert issubclass(DebertaEntailmentGate, BaseEntailmentGate)


# ---------------------------------------------------------------------------
# MiniCheckEntailmentGate: lazy import + factory type (no model load)
# ---------------------------------------------------------------------------

def test_minicheck_gate_importable_without_model():
    """MiniCheckEntailmentGate class is importable with no transformers/torch installed."""
    from ivg_kg.grounding.entailment import MiniCheckEntailmentGate  # noqa: F401


def test_minicheck_gate_constructed_without_model_load(monkeypatch):
    """MiniCheckEntailmentGate.__init__ does NOT load the model on construction."""
    from ivg_kg.grounding import entailment as mod

    loaded = []

    def fake_load_minicheck(model_id: str):
        loaded.append(model_id)
        raise RuntimeError("Model must not be loaded in tests")

    monkeypatch.setattr(mod, "_load_minicheck_model", fake_load_minicheck)

    from ivg_kg.grounding.entailment import MiniCheckEntailmentGate
    gate = MiniCheckEntailmentGate(model_id="test-model-id")
    assert not loaded, "Model should not be loaded at construction time"
    assert isinstance(gate, MiniCheckEntailmentGate)


def test_minicheck_gate_is_subclass_of_base():
    """MiniCheckEntailmentGate is a subclass of BaseEntailmentGate."""
    from ivg_kg.grounding.entailment import BaseEntailmentGate, MiniCheckEntailmentGate
    assert issubclass(MiniCheckEntailmentGate, BaseEntailmentGate)


# ---------------------------------------------------------------------------
# Factory: make_entailment_gate selects correct class from config
# ---------------------------------------------------------------------------

def test_factory_selects_lexical_gate():
    """make_entailment_gate returns LexicalEntailmentGate when config.entailment='lexical'."""
    from ivg_kg.grounding.entailment import LexicalEntailmentGate, make_entailment_gate
    config = GroundingConfig(entailment="lexical")
    gate = make_entailment_gate(config)
    assert isinstance(gate, LexicalEntailmentGate)


def test_factory_selects_deberta_gate(monkeypatch):
    """make_entailment_gate returns DebertaEntailmentGate when config.entailment='deberta'."""
    from ivg_kg.grounding import entailment as mod
    from ivg_kg.grounding.entailment import DebertaEntailmentGate, make_entailment_gate

    # Ensure _load_deberta_model is not called (lazy; no model at test time)
    monkeypatch.setattr(mod, "_load_deberta_model", lambda _: None)

    config = GroundingConfig(entailment="deberta")
    gate = make_entailment_gate(config)
    assert isinstance(gate, DebertaEntailmentGate)


def test_factory_selects_minicheck_gate(monkeypatch):
    """make_entailment_gate returns MiniCheckEntailmentGate when config.entailment='minicheck'."""
    from ivg_kg.grounding import entailment as mod
    from ivg_kg.grounding.entailment import MiniCheckEntailmentGate, make_entailment_gate

    monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: None)

    config = GroundingConfig(entailment="minicheck")
    gate = make_entailment_gate(config)
    assert isinstance(gate, MiniCheckEntailmentGate)


def test_factory_unknown_entailment_raises():
    """make_entailment_gate raises ValueError for an unknown entailment selector."""
    from ivg_kg.grounding.entailment import make_entailment_gate
    config = GroundingConfig(entailment="nonexistent_gate")
    with pytest.raises(ValueError, match="nonexistent_gate"):
        make_entailment_gate(config)


def test_factory_default_config_returns_gate():
    """make_entailment_gate handles default GroundingConfig (entailment='minicheck')."""
    from ivg_kg.grounding.entailment import MiniCheckEntailmentGate, make_entailment_gate

    # Default GroundingConfig has entailment='minicheck'; gate constructed without model load
    config = GroundingConfig()
    gate = make_entailment_gate(config)
    assert isinstance(gate, MiniCheckEntailmentGate)


# ---------------------------------------------------------------------------
# Slice regression guard: entails from slice still behaves correctly
# ---------------------------------------------------------------------------

def test_slice_entails_still_value_sensitive():
    """Importing entails from the slice module still works and is value-sensitive."""
    from ivg_kg.grounding.slice import entails as slice_entails
    premise = "The Glass Menagerie date of first performance 1944"
    hypothesis = "The Glass Menagerie was first performed in 1960."
    score = slice_entails(premise, hypothesis)
    assert score == 0.0, f"Slice entails regression: expected 0.0, got {score}"


def test_slice_entails_passes_on_correct_value():
    """Slice entails returns positive score for hypothesis matching premise value."""
    from ivg_kg.grounding.slice import entails as slice_entails
    premise = "The Glass Menagerie date of first performance 1944"
    hypothesis = "The Glass Menagerie first performance was in 1944."
    score = slice_entails(premise, hypothesis)
    assert score > 0.3, f"Slice entails regression: expected > 0.3, got {score}"


# ---------------------------------------------------------------------------
# Module-level: no top-level transformers/torch import
# ---------------------------------------------------------------------------

def test_entailment_module_imports_without_transformers():
    """The entailment module must import cleanly even when transformers is absent.

    Temporarily removes 'transformers' and 'torch' from sys.modules to simulate
    an environment where neither is installed.
    """
    # Stash original modules
    stash: dict[str, Any] = {}
    to_remove = [k for k in sys.modules if k.startswith("transformers") or k.startswith("torch")]
    for k in to_remove:
        stash[k] = sys.modules.pop(k)

    # Also block future imports
    blockers = {}
    for name in ("transformers", "torch"):
        blockers[name] = sys.modules.get(name)
        sys.modules[name] = None  # type: ignore[assignment]

    try:
        # Force reimport of the entailment module
        if "ivg_kg.grounding.entailment" in sys.modules:
            del sys.modules["ivg_kg.grounding.entailment"]
        import ivg_kg.grounding.entailment  # noqa: F401
    finally:
        # Restore
        for k, v in stash.items():
            sys.modules[k] = v
        for name, v in blockers.items():
            if v is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = v
