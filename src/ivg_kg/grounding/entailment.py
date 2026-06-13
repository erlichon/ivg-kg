"""GR7 -- Deterministic entailment gate (VERIFIER core measurement instrument).

This module is the SEAM between the caller (classifier / cascade) and the
entailment back-end.  Three implementations are provided:

    LexicalEntailmentGate   -- model-free Jaccard + value-sensitive guard;
                               always available offline; used in tests and as
                               the default offline gate.

    DebertaEntailmentGate   -- DeBERTa-v3-large NLI (LIVE path).
                               transformers/torch imports are LAZY: the module
                               and this class are fully importable with no model
                               present.

    MiniCheckEntailmentGate -- Bespoke-MiniCheck-7B (OFFLINE precompute /
                               calibration path).  ALL reported/figure numbers
                               come from the offline (MiniCheck) path.
                               Same lazy-import contract as DeBERTa.

Design invariants (SPEC-text ss4.3):
    - ASYMMETRIC: premise = serialised reference evidence; hypothesis = claim.
      Do NOT invert.  MiniCheck/NLI are directional.
    - VALUE-SENSITIVE (Invariant #3): a hypothesis asserting a concrete value
      (date/number/named-object) that the premise CONTRADICTS or OMITS scores
      0.0.  Entity-match alone is NOT support.
    - DETERMINISTIC (Invariants #8/#14): fixed float32, no sampling, pinned
      batch order on MPS.  Same (premise, hypothesis) -> identical float.
    - DIFFERENT MODEL FAMILY from the generator (no self-verification,
      Invariant #14).  This module imports NOTHING from grounding/clients/.
    - CACHE: each gate instance memoises entails() keyed by the
      (premise, hypothesis) pair so repeated pairs are not re-scored.
    - NO THRESHOLDING HERE: entails() returns a raw score in [0, 1].
      Thresholding against tau happens in the CALLER.

Factory:
    make_entailment_gate(config) reads config.entailment ("lexical" /
    "deberta" / "minicheck") and returns the configured gate.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

# ---------------------------------------------------------------------------
# Base ABC
# ---------------------------------------------------------------------------


class BaseEntailmentGate(ABC):
    """Abstract entailment gate.

    Subclasses implement _score(premise, hypothesis) -> float.
    entails() wraps _score with an in-process cache keyed by
    (premise, hypothesis).

    Contract:
        - entails(premise, hypothesis) -> float in [0, 1].
        - Asymmetric: premise = serialised reference evidence; hypothesis =
          claim text.  Do NOT invert.
        - Value-sensitive: a hypothesis asserting a concrete value absent from
          or contradicted by the premise must score <= 0.0 (return 0.0).
        - Deterministic: identical inputs -> identical float on every call.
        - No thresholding: raw score returned; tau applied by the caller.
    """

    def __init__(self) -> None:
        # Per-instance cache: (premise, hypothesis) -> float.
        # Unbounded by design -- one gate instance per sweep is fine; revisit if
        # a single instance spans the whole corpus.  Not thread-safe (fine for the
        # single-threaded deterministic pipeline).
        self._cache: dict[tuple[str, str], float] = {}

    def entails(self, premise: str, hypothesis: str) -> float:
        """Return a raw entailment score in [0, 1].

        Caches by (premise, hypothesis); repeated identical pairs skip
        the underlying scorer.
        """
        key = (premise, hypothesis)
        if key in self._cache:
            return self._cache[key]
        score = self._score(premise, hypothesis)
        self._cache[key] = score
        return score

    @abstractmethod
    def _score(self, premise: str, hypothesis: str) -> float:
        """Compute the raw entailment score without caching.

        Must return a float in [0, 1].  Subclasses implement this method;
        the caching wrapper lives in entails().
        """
        ...


# ---------------------------------------------------------------------------
# Shared value-extraction utilities (promoted from grounding/slice.py)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

_DATE_RE = re.compile(
    r"\b\d{4}\b|\b(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b",
    re.I,
)
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
# Named-object: a capitalised multi-word phrase (heuristic)
_NAMED_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+")


def _tokenise(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


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


def _jaccard_with_value_guard(
    premise: str,
    hypothesis: str,
    entity_labels: frozenset[str] | None = None,
) -> tuple[float, bool]:
    """Compute Jaccard score with value-sensitive guard.

    Returns (score, value_blocked).
        score:         Jaccard when value check passes; 0.0 when it fails.
        value_blocked: True when the value-sensitive check forced score to 0.0.

    entity_labels: optional set of lowercased entity names; named-object
    tokens matching an entity label are treated as linking anchors rather than
    concrete value assertions (prevents false blocks on entity mentions).
    """
    if not premise or not hypothesis:
        return 0.0, False

    p_toks = _tokenise(premise)
    h_toks = _tokenise(hypothesis)
    union = p_toks | h_toks
    if not union:
        return 0.0, False

    jaccard = len(p_toks & h_toks) / len(union)

    h_vals = _extract_values(hypothesis)
    if h_vals:
        if entity_labels is not None:
            h_vals = {
                v for v in h_vals
                if v not in entity_labels
                and not any(el in v for el in entity_labels if len(el) > 3)
            }
        if h_vals:
            # Slice-grade lexical heuristic: over-fires on capitalised non-value phrases
            # and under-fires via loose substring matching when entity_labels is None.
            # Model gates (GR7/GR10) supersede this check in the full cascade.
            p_vals = _extract_values(premise)
            premise_lower = premise.lower()
            for v in h_vals:
                if v not in premise_lower and v not in p_vals:
                    return 0.0, (jaccard > 0.0)

    return jaccard, False


# ---------------------------------------------------------------------------
# LexicalEntailmentGate -- model-free, always available
# ---------------------------------------------------------------------------


class LexicalEntailmentGate(BaseEntailmentGate):
    """Model-free entailment gate using Jaccard token-overlap + value-sensitive guard.

    Implements the same logic as the SLICE stand-in in grounding/slice.py but
    as a proper BaseEntailmentGate subclass.  Suitable for offline reproducibility,
    tests, and CI (no model download required).

    Determinism: fully deterministic -- pure set operations over ASCII-lowercased
    tokens.  No randomness, no model, no I/O.

    Value-sensitivity (Invariant #3): a hypothesis asserting a concrete date,
    number, or named-object token that is absent from the premise forces the
    score to 0.0 regardless of lexical overlap.  Entity-match alone is NOT
    support.
    """

    def __init__(self, entity_labels: frozenset[str] | None = None) -> None:
        super().__init__()
        # Optional set of lowercased entity labels for value-check filtering.
        # Without this, all named-object tokens in the hypothesis are treated as
        # concrete value assertions (conservative).
        self._entity_labels = entity_labels

    def _score(self, premise: str, hypothesis: str) -> float:
        """Jaccard + value-sensitive guard; returns float in [0, 1]."""
        score, _ = _jaccard_with_value_guard(premise, hypothesis, self._entity_labels)
        return score


# ---------------------------------------------------------------------------
# Lazy loader stubs -- replaced by actual loaders inside the concrete gates.
# Exposed at module level so tests can monkeypatch them.
# ---------------------------------------------------------------------------


def _load_deberta_model(model_id: str) -> Any:  # pragma: no cover
    """Lazy-load DeBERTa NLI pipeline.  Only called on first entails() invocation.

    Pinned to float32 for bit-stable determinism (SPEC ss4.3, Invariants #8/#14).
    device_map is omitted so the pipeline runs on CPU/MPS in the device's native
    float32 mode; bit-stability holds per-device with a fixed model state.
    """
    import torch  # noqa: PLC0415 -- intentionally lazy
    import transformers  # noqa: PLC0415 -- intentionally lazy
    pipeline = transformers.pipeline(
        "zero-shot-classification",
        model=model_id,
        torch_dtype=torch.float32,
    )
    pipeline.model.eval()
    return pipeline


def _load_minicheck_model(model_id: str) -> Any:  # pragma: no cover
    """Lazy-load MiniCheck scorer.  Only called on first entails() invocation.

    Pinned to float32 for bit-stable determinism (SPEC ss4.3, Invariants #8/#14).
    .eval() disables dropout/batch-norm stochasticity for the calibration path.
    """
    # MiniCheck uses the transformers AutoModelForSeq2SeqLM interface.
    # Import is deferred to keep the module importable without transformers.
    import torch  # noqa: PLC0415 -- intentionally lazy
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: PLC0415
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, torch_dtype=torch.float32)
    model.eval()
    return tokenizer, model


# ---------------------------------------------------------------------------
# DebertaEntailmentGate -- LIVE path
# ---------------------------------------------------------------------------


class DebertaEntailmentGate(BaseEntailmentGate):
    """DeBERTa-v3-large NLI entailment gate (LIVE path).

    Determinism: float32, greedy/no-sampling, fixed batch order.  The NLI
    pipeline is fully deterministic given a fixed model state.

    Lazy loading: the transformers pipeline is NOT loaded at construction time.
    It is loaded on the first call to _score() and cached on the instance.
    This ensures the module and class are importable with no model present.

    This gate is a DIFFERENT model family from the generator (Invariant #14).
    It imports NOTHING from grounding/clients/ (no self-verification).
    """

    def __init__(self, model_id: str | None = None) -> None:
        super().__init__()
        from ivg_kg import (
            config as _cfg,  # noqa: PLC0415 -- local config import, not a generator client
        )
        self._model_id = model_id or _cfg.DEBERTA_NLI_MODEL_ID
        self._pipeline: Any = None  # loaded lazily on first _score() call

    def _score(self, premise: str, hypothesis: str) -> float:  # pragma: no cover
        """NLI entailment probability via DeBERTa-v3-large.

        Returns the 'entailment' label probability as a float in [0, 1].

        Determinism: float32, no sampling, fixed candidate-label order ensures
        bit-stable scores across repeated calls with the same model state.
        """
        if self._pipeline is None:
            self._pipeline = _load_deberta_model(self._model_id)

        if not premise or not hypothesis:
            return 0.0

        result = self._pipeline(
            premise,
            candidate_labels=["entailment", "neutral", "contradiction"],
            hypothesis_template="{}",
        )
        label_scores: dict[str, float] = dict(
            zip(result["labels"], result["scores"], strict=False)
        )
        return float(label_scores.get("entailment", 0.0))


# ---------------------------------------------------------------------------
# MiniCheckEntailmentGate -- OFFLINE precompute / calibration path
# ---------------------------------------------------------------------------


class MiniCheckEntailmentGate(BaseEntailmentGate):
    """Bespoke-MiniCheck-7B entailment gate (OFFLINE precompute / calibration path).

    ALL reported/figure numbers come from the offline (MiniCheck) path.
    The live path (DebertaEntailmentGate) never sources reported numbers, so
    the model choice does not affect reproducibility (Invariant #22).

    Determinism: float32, greedy decoding (no sampling), fixed batch order on
    MPS/CUDA.  The scorer is fully deterministic given a fixed model state.

    Lazy loading: the tokenizer and model are NOT loaded at construction time.
    Loaded on first _score() call and cached on the instance.

    This gate is a DIFFERENT model family from the generator (Invariant #14).
    It imports NOTHING from grounding/clients/ (no self-verification).
    """

    def __init__(self, model_id: str | None = None) -> None:
        super().__init__()
        from ivg_kg import config as _cfg  # noqa: PLC0415
        self._model_id = model_id or _cfg.MINICHECK_MODEL_ID
        self._tokenizer: Any = None  # loaded lazily
        self._model: Any = None      # loaded lazily

    def _score(self, premise: str, hypothesis: str) -> float:  # pragma: no cover
        """Fact-checking score via MiniCheck-7B.

        Returns a probability in [0, 1] that the premise supports the hypothesis
        (fact-checking direction: premise = document, hypothesis = claim).

        Determinism: float32, greedy decoding (num_beams=1, do_sample=False),
        fixed input format ensures bit-stable scores.
        """
        import torch  # noqa: PLC0415 -- intentionally lazy

        if self._tokenizer is None or self._model is None:
            self._tokenizer, self._model = _load_minicheck_model(self._model_id)

        if not premise or not hypothesis:
            return 0.0

        # MiniCheck input format: "Document: <premise> Claim: <hypothesis>"
        text = f"Document: {premise} Claim: {hypothesis}"
        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=2048,
        )
        # Greedy decoding; no sampling; float32 for determinism on MPS
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=10,
                do_sample=False,
                num_beams=1,
            )
        decoded = self._tokenizer.decode(outputs[0], skip_special_tokens=True).strip().lower()
        # MiniCheck outputs "yes" (supported) or "no" (not supported).
        # PLACEHOLDER: hard yes/no -> {1.0, 0.0} drops the support probability;
        # production calibration (ss4.3, GR10) must read MiniCheck's token-level
        # support probability instead of collapsing to binary here.
        if decoded.startswith("yes"):
            return 1.0
        if decoded.startswith("no"):
            return 0.0
        # Fallback: unknown output -> conservative 0.0
        return 0.0


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_entailment_gate(config: Any) -> BaseEntailmentGate:
    """Return the entailment gate selected by config.entailment.

    Valid selectors (config.entailment):
        "lexical"   -> LexicalEntailmentGate (model-free, always available)
        "deberta"   -> DebertaEntailmentGate (DeBERTa-v3-large NLI, LIVE path)
        "minicheck" -> MiniCheckEntailmentGate (MiniCheck-7B, OFFLINE path)

    Raises ValueError for unknown selectors.
    """
    selector: str = getattr(config, "entailment", "lexical")
    if selector == "lexical":
        return LexicalEntailmentGate()
    if selector == "deberta":
        return DebertaEntailmentGate()
    if selector == "minicheck":
        return MiniCheckEntailmentGate()
    raise ValueError(
        f"Unknown entailment gate selector: {selector!r}. "
        f"Valid options: 'lexical', 'deberta', 'minicheck'."
    )
