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
    - DETERMINISTIC (Invariants #8/#14): greedy decoding, fixed bfloat16, no
      sampling, pinned batch order on MPS.  Same (premise, hypothesis) ->
      identical float within a single run/machine.  Cross-machine bit-identity
      is relaxed for the 7B due to bfloat16 memory constraints, which is
      acceptable because ALL reported numbers come from ONE cached offline
      precompute run (Invariants #8/#22).
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
# MiniCheck-7B canonical system prompt (verbatim from the official minicheck
# package source).  Module-level ASCII constant; never modified at runtime.
# The apostrophe in "claim's" and the straight double-quotes in "Yes"/"No"
# are intentional -- they must match the original exactly for reproducibility.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT: str = (
    'Determine whether the provided claim is consistent with the corresponding'
    ' document. Consistency in this context implies that all information'
    ' presented in the claim is substantiated by the document. If not, it'
    " should be considered inconsistent. Please assess the claim's consistency"
    ' with the document by responding with either "Yes" or "No".'
)

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

    def entails_batch(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Score many (premise, hypothesis) pairs.

        Default implementation: per-pair via entails() (preserves the cache).
        Subclasses MAY override with a true batched forward.
        Order of returned scores matches ``pairs``.
        """
        return [self.entails(p, h) for (p, h) in pairs]

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
                v
                for v in h_vals
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
# MiniCheck-7B pure scoring helpers
# These functions are UNIT-TESTABLE without any model and contain all the
# probability arithmetic so _score() is testable via stubs.
# ---------------------------------------------------------------------------


def _yes_prob_from_logits(logits: Any, yes_token_ids: list[int]) -> float:
    """Compute P(yes) as the total softmax mass on the given yes-token ids.

    Args:
        logits: 1-D float tensor of shape (vocab_size,) from the first
                generated step (outputs.scores[0][0]).  Caller is responsible
                for ensuring torch is already imported before calling this
                helper (it is always called from _score, which does
                ``import torch`` at its head, or from tests that import torch).
        yes_token_ids: list of vocabulary ids considered as "yes" first-token
                       variants (may be empty, in which case 0.0 is returned).

    Returns:
        float in [0, 1]: sum of softmax(logits)[i] for i in yes_token_ids.

    This mirrors the official minicheck package's approach of summing
    exp(logprob) over tokens whose decoded form lowercased equals "yes",
    but operates directly on ids so the test suite can exercise it without
    a tokenizer.  Softmax is computed in float32 regardless of the input
    dtype for bit-stability.

    NOTE: no ``import torch`` here -- this function uses only tensor instance
    methods (.float(), .softmax(), .sum()) so that it does not trigger a
    re-import of torch's C extension after the module has been temporarily
    removed from sys.modules (which would re-register the dispatch registry
    and raise a RuntimeError).  Torch is guaranteed available at the call
    site: either _score() has already done ``import torch``, or the test
    suite has ``import torch`` at module level.
    """
    if not yes_token_ids:
        return 0.0
    # Use tensor instance method to avoid calling torch.softmax() directly.
    probs = logits.float().softmax(dim=0)
    yes_prob = probs[yes_token_ids].sum()
    return float(yes_prob.item())


# Yes-variant strings to probe when building the yes-token-id set.
_YES_VARIANTS: tuple[str, ...] = ("Yes", "yes", " Yes", " yes")


def _yes_token_ids_for_tokenizer(tokenizer: Any) -> list[int]:
    """Return the de-duplicated list of single-token ids for yes-variant strings.

    For each string in ("Yes", "yes", " Yes", " yes"), encode with
    add_special_tokens=False; keep only those that produce exactly one token
    id (multi-piece encodings are dropped because the first-token logit is
    ambiguous if the answer spans multiple pieces).  Deduplicate while
    preserving first-seen order.

    This matches the approach of the official minicheck package, which sums
    probability mass over decoded tokens whose .lower() == "yes".

    Args:
        tokenizer: any tokenizer with an .encode(str, add_special_tokens=bool)
                   method (real or stub).

    Returns:
        list[int]: deduplicated single-token ids for yes-variants.
    """
    seen: set[int] = set()
    ids: list[int] = []
    for variant in _YES_VARIANTS:
        token_ids = tokenizer.encode(variant, add_special_tokens=False)
        if len(token_ids) == 1:
            tok_id = token_ids[0]
            if tok_id not in seen:
                seen.add(tok_id)
                ids.append(tok_id)
    return ids


# ---------------------------------------------------------------------------
# MiniCheck batched forward: max pairs per single GPU/MPS forward pass.
# Bounds peak memory on Apple Silicon. Increase if the device has headroom.
# ---------------------------------------------------------------------------

MINICHECK_BATCH_SIZE: int = 8

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
    """Lazy-load Bespoke-MiniCheck-7B scorer.  Only called on first _score() invocation.

    MiniCheck-7B is an InternLM2 DECODER-ONLY (causal) LM, NOT seq2seq.
    It must be loaded with:
        - AutoModelForCausalLM (NOT AutoModelForSeq2SeqLM)
        - trust_remote_code=True  (InternLM2 modeling code lives in the repo)
        - dtype=torch.bfloat16  (bf16 ~14GB fits 48GB MPS; float32 ~28GB is too large)

    Determinism note: greedy decoding + fixed model state gives bit-stable scores
    within a single run/machine.  Cross-machine bit-identity is relaxed for the 7B
    due to bfloat16 precision and MPS numerics, which is acceptable because ALL
    reported/figure numbers come from ONE cached offline precompute run
    (Invariants #8/#22).  .eval() disables dropout stochasticity.

    Device: MPS when available (Apple Silicon); CPU fallback.

    Returns:
        (tokenizer, model, device) -- the device string is returned so _score
        can place input tensors on the correct device without re-detecting it.
    """
    import torch  # noqa: PLC0415 -- intentionally lazy
    from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,  # transformers 4.x kwarg (pinned <4.50)
    )
    model.eval()
    if torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    model.to(device)
    return tokenizer, model, device


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
        label_scores: dict[str, float] = dict(zip(result["labels"], result["scores"], strict=False))
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
        self._tokenizer: Any = None  # loaded lazily on first _score()
        self._model: Any = None  # loaded lazily
        self._device: str = "cpu"  # updated when model is loaded
        self._yes_token_ids: list[int] | None = None  # cached after first _score()

    def _score(self, premise: str, hypothesis: str) -> float:  # pragma: no cover
        """Fact-checking score via Bespoke-MiniCheck-7B (canonical scoring).

        Scoring method (mirrors the official minicheck package):
          1. Build a two-turn chat: system = SYSTEM_PROMPT, user = the
             "Document: {premise}\\nClaim: {hypothesis}" prompt.
          2. Apply the InternLM2 chat template via tokenizer.apply_chat_template
             with add_generation_prompt=True to obtain input_ids.  The chat
             template is REQUIRED because the model is chat-tuned; feeding a raw
             concatenated string yields incorrect results.
          3. Run a single forward pass under torch.no_grad() to obtain the
             next-token logits directly from outputs.logits[0, -1, :].
             NOTE: .generate() is NOT used here because InternLM2's remote code
             under transformers 5.x does not inherit GenerationMixin and therefore
             does not expose a .generate() method.  A forward pass is equivalent
             for our purpose (reading the first generated token's logits) and
             avoids this incompatibility entirely.
          4. Take outputs.logits[0, -1, :] -- the vocab-size 1-D tensor of
             next-token logits (what the model would produce as the first
             generated token given the prompt).
          5. Softmax over the FULL vocabulary in float32.
          6. Sum the softmax probability mass on all single-token "yes"-variant
             ids ("Yes", "yes", " Yes", " yes") -- this is P(yes), the support
             probability returned to the caller.

        Value-sensitivity (Invariant #3): a wrong-value claim causes the model
        to answer "No", producing a low P(yes) -> FABRICATED signal.

        Determinism: fixed bf16 model state, no sampling, pinned input format.
        Bit-stable within a run/machine; cross-machine relaxed per the bfloat16
        memory constraint (Invariants #8/#22).

        Empty premise or hypothesis short-circuits to 0.0 without model call.
        """
        import torch  # noqa: PLC0415 -- intentionally lazy

        if not premise or not hypothesis:
            return 0.0

        if self._tokenizer is None or self._model is None:
            self._tokenizer, self._model, self._device = _load_minicheck_model(self._model_id)

        # Build the canonical two-turn chat messages.
        user_prompt = f"Document: {premise}\nClaim: {hypothesis}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # apply_chat_template produces the full prompt with the InternLM2 chat
        # special tokens and appends the generation-start marker.
        # transformers 5.x returns a BatchEncoding (dict-like) here; older
        # versions return a bare 2-D tensor [1, seq_len]. Handle both: extract
        # the input_ids tensor whatever the container.
        encoded = self._tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
        )
        if hasattr(encoded, "input_ids"):
            input_ids = encoded.input_ids
        elif isinstance(encoded, dict):
            input_ids = encoded["input_ids"]
        else:
            input_ids = encoded

        # Single forward pass to read the next-token logits directly.
        # outputs.logits has shape [1, seq_len, vocab_size]; the last position
        # [-1, :] gives the distribution over the first generated token.
        with torch.no_grad():
            outputs = self._model(input_ids=input_ids.to(self._device), use_cache=False)

        # Next-token logits: 1-D tensor of shape (vocab_size,).
        first_step_logits = outputs.logits[0, -1, :]

        # Compute and cache the yes-variant token-id set on first _score() call.
        if self._yes_token_ids is None:
            self._yes_token_ids = _yes_token_ids_for_tokenizer(self._tokenizer)

        # P(yes) = sum of softmax(full vocab logits) at all yes-variant ids.
        return _yes_prob_from_logits(first_step_logits, self._yes_token_ids)

    def entails_batch(self, pairs: list[tuple[str, str]]) -> list[float]:  # pragma: no cover
        """Score many (premise, hypothesis) pairs with batched forwards.

        For each pair builds the same canonical two-turn chat prompt used by
        _score(), consults the evidence-pair cache to skip already-scored pairs,
        then runs at most MINICHECK_BATCH_SIZE uncached pairs per forward pass.

        Left-padding is used (tokenizer.padding_side = "left") so the last
        real token of every row is always at position -1, which makes logit
        extraction uniform: ``outputs.logits[row, -1, :]``.

        Empty premise or hypothesis short-circuits to 0.0 for that pair (no
        forward pass), matching the _score() contract.

        The returned list is in the SAME ORDER as ``pairs``.
        """
        import torch  # noqa: PLC0415 -- intentionally lazy

        if not pairs:
            return []

        # Ensure model is loaded.
        if self._tokenizer is None or self._model is None:
            self._tokenizer, self._model, self._device = _load_minicheck_model(self._model_id)

        # Compute and cache yes-token-ids once.
        if self._yes_token_ids is None:
            self._yes_token_ids = _yes_token_ids_for_tokenizer(self._tokenizer)

        # Use left-padding so the last token of every row in the batch is at
        # position -1 regardless of sequence length differences.
        original_padding_side = getattr(self._tokenizer, "padding_side", "right")
        self._tokenizer.padding_side = "left"
        # Ensure a pad token is defined (required by the tokenizer padder).
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        try:
            results: list[float] = [0.0] * len(pairs)

            # Partition into cached (immediate) and uncached (need forward).
            uncached_indices: list[int] = []
            uncached_prompts: list[str] = []

            for idx, (premise, hypothesis) in enumerate(pairs):
                if not premise or not hypothesis:
                    results[idx] = 0.0
                    continue
                key = (premise, hypothesis)
                if key in self._cache:
                    results[idx] = self._cache[key]
                    continue
                # Build the canonical chat string for this uncached pair.
                user_prompt = f"Document: {premise}\nClaim: {hypothesis}"
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
                # apply_chat_template with return_type="str" gives a plain string.
                prompt_str = self._tokenizer.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    tokenize=False,
                )
                uncached_indices.append(idx)
                uncached_prompts.append(prompt_str)

            # Process uncached pairs in chunks of MINICHECK_BATCH_SIZE.
            for chunk_start in range(0, len(uncached_prompts), MINICHECK_BATCH_SIZE):
                chunk_prompts = uncached_prompts[chunk_start : chunk_start + MINICHECK_BATCH_SIZE]
                chunk_indices = uncached_indices[chunk_start : chunk_start + MINICHECK_BATCH_SIZE]

                # Tokenize the whole chunk with padding. add_special_tokens=False
                # because apply_chat_template already rendered the BOS (<s>) into
                # the prompt string; the default (True) would prepend a SECOND BOS
                # (TemplateProcessing), diverging from the single-pair _score path
                # (apply_chat_template(tokenize=True) tokenizes with
                # add_special_tokens=False) and corrupting batched scores.
                encoded = self._tokenizer(
                    chunk_prompts,
                    padding=True,
                    return_tensors="pt",
                    add_special_tokens=False,
                )
                input_ids = encoded["input_ids"].to(self._device)
                attention_mask = encoded["attention_mask"].to(self._device)
                # NB: do NOT pass explicit position_ids. The InternLM2 model derives
                # correct positions from attention_mask under left-padding internally;
                # an explicit cumsum-based position_ids was measured to make scores
                # WORSE (an unpadded row that matched the single-pair _score exactly
                # diverged once overridden). The left-pad attention_mask is sufficient.
                with torch.no_grad():
                    outputs = self._model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        use_cache=False,
                    )

                # outputs.logits: [batch, seq_len, vocab_size]
                # With left-padding the last real position is always index -1.
                for row, orig_idx in enumerate(chunk_indices):
                    logits_last = outputs.logits[row, -1, :]
                    score = _yes_prob_from_logits(logits_last, self._yes_token_ids)
                    results[orig_idx] = score
                    # Store in the shared cache so future entails() calls hit cache.
                    premise, hypothesis = pairs[orig_idx]
                    self._cache[(premise, hypothesis)] = score

        finally:
            # Restore original padding side so single-pair _score is unaffected.
            self._tokenizer.padding_side = original_padding_side

        return results


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
