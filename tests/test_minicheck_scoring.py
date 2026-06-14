"""Tests for canonical Bespoke-MiniCheck-7B scoring (FIX-MC7B).

Coverage:
  1. Pure helper _yes_prob_from_logits: no model needed, exercises softmax + id-set summing.
  2. Yes-id extraction from a fake tokenizer stub: verifies single-token filtering + dedup.
  3. _score plumbing with a full stub (monkeypatched loader): validates chat-template wiring,
     SYSTEM_PROMPT presence, Document/Claim format, and returned P(yes) value.
  4. Skip-guarded integration test (real model): runs only when IVG_KG_RUN_MINICHECK=1 and
     model is locally cached; validates value-sensitivity on a Tennessee Williams pair.

All pure-helper and stub-plumbing tests MUST pass with no model downloaded.
"""
from __future__ import annotations

import math
import os
from typing import Any

import pytest
import torch  # noqa: I001

# ---------------------------------------------------------------------------
# 1. Pure helper: _yes_prob_from_logits
# ---------------------------------------------------------------------------


class TestYesProbFromLogits:
    """Unit tests for _yes_prob_from_logits(logits, yes_token_ids) -> float."""

    def _fn(self):
        from ivg_kg.grounding.entailment import _yes_prob_from_logits

        return _yes_prob_from_logits

    def _softmax(self, logits_list):
        """Hand-compute float32 softmax for expected values."""
        t = torch.tensor(logits_list, dtype=torch.float32)
        return torch.softmax(t, dim=0).tolist()

    def test_single_yes_id_dominant(self):
        """When one yes-id has a large logit, returned prob should be high (> 0.9)."""
        fn = self._fn()
        vocab_size = 10
        logits = torch.zeros(vocab_size, dtype=torch.float32)
        yes_id = 3
        logits[yes_id] = 10.0  # dominant
        prob = fn(logits, [yes_id])
        assert isinstance(prob, float)
        # softmax(10, 0, 0, ...) at position 3 is close to 1
        assert prob > 0.9, f"Expected > 0.9 for dominant yes logit, got {prob}"

    def test_single_yes_id_tiny(self):
        """When yes-id has a very small logit vs others, prob should be low (< 0.1)."""
        fn = self._fn()
        vocab_size = 10
        logits = torch.ones(vocab_size, dtype=torch.float32) * 5.0
        yes_id = 3
        logits[yes_id] = -10.0  # suppressed
        prob = fn(logits, [yes_id])
        assert prob < 0.1, f"Expected < 0.1 for suppressed yes logit, got {prob}"

    def test_multiple_yes_ids_sum_correctly(self):
        """Prob is sum of softmax mass on ALL yes-variant ids."""
        fn = self._fn()
        vocab_size = 8
        logits = torch.zeros(vocab_size, dtype=torch.float32)
        yes_ids = [1, 3, 5]
        # Assign logit 2.0 to each yes-id; rest stay 0.0
        for i in yes_ids:
            logits[i] = 2.0
        prob = fn(logits, yes_ids)

        # Hand-compute expected
        probs_list = self._softmax(logits.tolist())
        expected = sum(probs_list[i] for i in yes_ids)
        assert abs(prob - expected) < 1e-5, f"Expected {expected}, got {prob}"

    def test_empty_yes_ids_returns_zero(self):
        """Empty yes-id set -> returned prob is 0.0."""
        fn = self._fn()
        logits = torch.ones(10, dtype=torch.float32)
        prob = fn(logits, [])
        assert prob == 0.0, f"Expected 0.0 for empty yes-id set, got {prob}"

    def test_returns_float_not_tensor(self):
        """Return type is a Python float, not a torch.Tensor."""
        fn = self._fn()
        logits = torch.zeros(5, dtype=torch.float32)
        prob = fn(logits, [2])
        assert type(prob) is float

    def test_values_sum_to_at_most_one(self):
        """Returned prob is in [0, 1] for any logit tensor."""
        fn = self._fn()
        torch.manual_seed(42)
        logits = torch.randn(1000, dtype=torch.float32)
        yes_ids = [0, 1, 42, 100, 500]
        prob = fn(logits, yes_ids)
        assert 0.0 <= prob <= 1.0, f"Prob out of range: {prob}"

    def test_single_yes_id_exact_value(self):
        """Exact match to hand-computed softmax for a two-element vocab."""
        fn = self._fn()
        # vocab size 2: logit[0] = 1.0 (yes-id), logit[1] = 2.0
        logits = torch.tensor([1.0, 2.0], dtype=torch.float32)
        expected = math.exp(1.0) / (math.exp(1.0) + math.exp(2.0))
        prob = fn(logits, [0])
        assert abs(prob - expected) < 1e-6, f"Expected {expected}, got {prob}"


# ---------------------------------------------------------------------------
# 2. Yes-id extraction from fake tokenizer
# ---------------------------------------------------------------------------


class FakeTokenizer:
    """Fake tokenizer stub whose encode() returns a controlled mapping."""

    def __init__(self, encoding_map: dict[str, list[int]]) -> None:
        # Maps string -> list of token ids returned by encode(..., add_special_tokens=False)
        self._map = encoding_map

    def encode(self, text: str, add_special_tokens: bool = True) -> list[int]:  # noqa: FBT001
        return self._map.get(text, [999])


def _get_yes_ids_from_tokenizer(tokenizer: Any) -> list[int]:
    """Collect single-token yes-variant ids from a tokenizer.

    Mirrors the approach used in MiniCheckEntailmentGate: encode each of the
    four yes-variant strings without special tokens; keep ids that decode to a
    single token (list length == 1); deduplicate.
    """
    # Import here so the helper is testable standalone
    from ivg_kg.grounding.entailment import _yes_token_ids_for_tokenizer

    return _yes_token_ids_for_tokenizer(tokenizer)


class TestYesIdExtraction:
    """Unit tests for _yes_token_ids_for_tokenizer."""

    def test_single_token_variants_collected(self):
        """All four yes-variant strings that encode to one token are collected."""
        tok = FakeTokenizer({
            "Yes": [10],
            "yes": [11],
            " Yes": [12],
            " yes": [13],
        })
        ids = _get_yes_ids_from_tokenizer(tok)
        assert set(ids) == {10, 11, 12, 13}, f"Got {ids}"

    def test_multi_token_variants_dropped(self):
        """Variants that encode to multiple tokens are excluded."""
        tok = FakeTokenizer({
            "Yes": [10],
            "yes": [11, 99],   # multi-token -> dropped
            " Yes": [12],
            " yes": [13, 88],  # multi-token -> dropped
        })
        ids = _get_yes_ids_from_tokenizer(tok)
        assert set(ids) == {10, 12}, f"Got {ids}"

    def test_deduplication(self):
        """Duplicate token ids (multiple variants map to same id) are deduplicated."""
        tok = FakeTokenizer({
            "Yes": [10],
            "yes": [10],   # same id as "Yes"
            " Yes": [12],
            " yes": [12],  # same id as " Yes"
        })
        ids = _get_yes_ids_from_tokenizer(tok)
        assert set(ids) == {10, 12}, f"Got {ids}"
        assert len(ids) == len(set(ids)), "Result must not contain duplicates"

    def test_all_multi_token_returns_empty(self):
        """If every variant encodes to multiple tokens, result is empty list."""
        tok = FakeTokenizer({
            "Yes": [10, 20],
            "yes": [11, 21],
            " Yes": [12, 22],
            " yes": [13, 23],
        })
        ids = _get_yes_ids_from_tokenizer(tok)
        assert ids == [], f"Expected empty, got {ids}"

    def test_returns_list(self):
        """Return type is a plain list (not a set or generator)."""
        tok = FakeTokenizer({"Yes": [5], "yes": [6], " Yes": [7], " yes": [8]})
        ids = _get_yes_ids_from_tokenizer(tok)
        assert isinstance(ids, list)


# ---------------------------------------------------------------------------
# 3. _score plumbing with a fully stubbed loader (no real model)
# ---------------------------------------------------------------------------


def _make_fake_forward_output(vocab_size: int, yes_ids: list[int], yes_logit: float = 5.0, seq_len: int = 4):
    """Return a fake forward-pass output with .logits of shape [1, seq_len, vocab_size].

    The last position [:, -1, :] has yes_ids set to yes_logit so they dominate.
    This mirrors CausalLMOutputWithPast returned by model(input_ids=...).
    """
    logits = torch.zeros(1, seq_len, vocab_size, dtype=torch.float32)
    for i in yes_ids:
        logits[0, -1, i] = yes_logit

    class FakeForwardOutput:
        pass

    out = FakeForwardOutput()
    out.logits = logits
    return out


def _make_fake_model(forward_output):
    """Return a callable fake model that returns forward_output when called."""
    class FakeModel:
        def __call__(self, input_ids=None, **kwargs):
            return forward_output

    return FakeModel()


class TestMiniCheckScorePlumbing:
    """Stub-based tests for MiniCheckEntailmentGate._score wiring."""

    def _build_stub_tokenizer(self, vocab_size: int = 50, yes_ids: list[int] | None = None):
        """Build a minimal fake tokenizer that supports apply_chat_template and encode."""
        if yes_ids is None:
            yes_ids = [5]

        encoding_map = {
            "Yes": yes_ids[:1] if yes_ids else [999],
            "yes": yes_ids[:1] if yes_ids else [999],
            " Yes": yes_ids[:1] if yes_ids else [999],
            " yes": yes_ids[:1] if yes_ids else [999],
        }

        captured_messages = []

        class FakeStubTokenizer:
            _vocab_size = vocab_size
            _yes_ids = yes_ids
            _captured = captured_messages

            def encode(self, text: str, add_special_tokens: bool = True) -> list[int]:  # noqa: FBT001
                return encoding_map.get(text, [999])

            def apply_chat_template(
                self,
                messages: list[dict],
                add_generation_prompt: bool = True,
                return_tensors: str = "pt",
            ) -> torch.Tensor:
                # Capture messages so tests can inspect them
                self._captured.clear()
                self._captured.extend(messages)
                # Return a small dummy input_ids tensor
                return torch.zeros(1, 4, dtype=torch.long)

        tok = FakeStubTokenizer()
        return tok, captured_messages

    def test_score_returns_float_in_unit_interval(self, monkeypatch):
        """_score returns a float in [0, 1] when model stub is injected."""
        from ivg_kg.grounding import entailment as mod

        vocab_size = 50
        yes_id = 5
        tok, _ = self._build_stub_tokenizer(vocab_size=vocab_size, yes_ids=[yes_id])
        fake_output = _make_fake_forward_output(vocab_size, [yes_id], yes_logit=8.0)
        fake_model = _make_fake_model(fake_output)
        device = "cpu"

        monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: (tok, fake_model, device))

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        score = gate._score("Tennessee Williams wrote The Glass Menagerie.", "It was authored by Williams.")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0, f"Score out of range: {score}"

    def test_score_high_when_yes_id_dominates(self, monkeypatch):
        """When the yes-id logit dominates, _score returns a value close to 1."""
        from ivg_kg.grounding import entailment as mod

        vocab_size = 50
        yes_id = 5
        tok, _ = self._build_stub_tokenizer(vocab_size=vocab_size, yes_ids=[yes_id])
        fake_output = _make_fake_forward_output(vocab_size, [yes_id], yes_logit=20.0)
        fake_model = _make_fake_model(fake_output)

        monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: (tok, fake_model, "cpu"))

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        score = gate._score("Alice wrote the book in 1944.", "The book was written by Alice in 1944.")
        assert score > 0.9, f"Expected > 0.9 when yes-id dominates, got {score}"

    def test_score_low_when_yes_id_suppressed(self, monkeypatch):
        """When the yes-id logit is suppressed, _score returns a value close to 0."""
        from ivg_kg.grounding import entailment as mod

        vocab_size = 50
        yes_id = 5
        tok, _ = self._build_stub_tokenizer(vocab_size=vocab_size, yes_ids=[yes_id])

        # Suppressed yes logit: all others high, yes-id very negative.
        seq_len = 4
        logits_3d = torch.ones(1, seq_len, vocab_size, dtype=torch.float32) * 5.0
        logits_3d[0, -1, yes_id] = -20.0

        class FakeOutputLow:
            pass

        out = FakeOutputLow()
        out.logits = logits_3d
        fake_model = _make_fake_model(out)

        monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: (tok, fake_model, "cpu"))

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        score = gate._score("Evidence about 1944.", "Claim asserting 1999.")
        assert score < 0.1, f"Expected < 0.1 when yes-id suppressed, got {score}"

    def test_system_prompt_in_messages(self, monkeypatch):
        """SYSTEM_PROMPT must appear as the system message in apply_chat_template call."""
        from ivg_kg.grounding import entailment as mod
        from ivg_kg.grounding.entailment import SYSTEM_PROMPT

        vocab_size = 20
        yes_id = 3
        tok, captured = self._build_stub_tokenizer(vocab_size=vocab_size, yes_ids=[yes_id])
        fake_output = _make_fake_forward_output(vocab_size, [yes_id])
        fake_model = _make_fake_model(fake_output)

        monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: (tok, fake_model, "cpu"))

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        gate._score("premise text", "hypothesis text")

        assert len(captured) >= 1, "apply_chat_template must receive at least one message"
        system_msgs = [m for m in captured if m.get("role") == "system"]
        assert system_msgs, "No system message found in captured messages"
        assert system_msgs[0]["content"] == SYSTEM_PROMPT, (
            f"System message content mismatch.\nExpected: {SYSTEM_PROMPT!r}\n"
            f"Got: {system_msgs[0]['content']!r}"
        )

    def test_document_and_claim_in_user_message(self, monkeypatch):
        """User message must contain 'Document: <premise>' and 'Claim: <hypothesis>'."""
        from ivg_kg.grounding import entailment as mod

        vocab_size = 20
        yes_id = 3
        tok, captured = self._build_stub_tokenizer(vocab_size=vocab_size, yes_ids=[yes_id])
        fake_output = _make_fake_forward_output(vocab_size, [yes_id])
        fake_model = _make_fake_model(fake_output)

        monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: (tok, fake_model, "cpu"))

        premise = "Tennessee Williams wrote The Glass Menagerie."
        hypothesis = "The Glass Menagerie was written by Harold Pinter."

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        gate._score(premise, hypothesis)

        user_msgs = [m for m in captured if m.get("role") == "user"]
        assert user_msgs, "No user message found in captured messages"
        user_content = user_msgs[0]["content"]
        assert f"Document: {premise}" in user_content, (
            f"'Document: <premise>' not in user message: {user_content!r}"
        )
        assert f"Claim: {hypothesis}" in user_content, (
            f"'Claim: <hypothesis>' not in user message: {user_content!r}"
        )

    def test_empty_premise_returns_zero(self, monkeypatch):
        """Empty premise short-circuits to 0.0 without calling the model."""
        from ivg_kg.grounding import entailment as mod

        loaded = []

        def fake_load(model_id: str):
            loaded.append(model_id)
            raise RuntimeError("Model must not be loaded for empty-input test")

        monkeypatch.setattr(mod, "_load_minicheck_model", fake_load)

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        score = gate._score("", "some claim")
        assert score == 0.0
        assert not loaded, "Loader must not be called for empty premise"

    def test_empty_hypothesis_returns_zero(self, monkeypatch):
        """Empty hypothesis short-circuits to 0.0 without calling the model."""
        from ivg_kg.grounding import entailment as mod

        loaded = []

        def fake_load(model_id: str):
            loaded.append(model_id)
            raise RuntimeError("Model must not be loaded for empty-input test")

        monkeypatch.setattr(mod, "_load_minicheck_model", fake_load)

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        score = gate._score("some premise", "")
        assert score == 0.0
        assert not loaded, "Loader must not be called for empty hypothesis"

    def test_model_called_with_input_ids_kwarg(self, monkeypatch):
        """model must be called as model(input_ids=...) -- forward pass, not generate."""
        from ivg_kg.grounding import entailment as mod

        vocab_size = 20
        yes_id = 3
        tok, _ = self._build_stub_tokenizer(vocab_size=vocab_size, yes_ids=[yes_id])
        fake_output = _make_fake_forward_output(vocab_size, [yes_id])

        call_log = []

        class TrackingModel:
            def __call__(self, input_ids=None, **kwargs):
                call_log.append({"input_ids": input_ids, "kwargs": kwargs})
                return fake_output

        monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: (tok, TrackingModel(), "cpu"))

        gate = mod.MiniCheckEntailmentGate(model_id="stub")
        gate._score("The book was published in 1944.", "It was published in 1944.")

        assert len(call_log) == 1, f"Model must be called exactly once, got {len(call_log)}"
        call = call_log[0]
        assert call["input_ids"] is not None, "input_ids must be passed to the model"
        # Must be a 2-D tensor [1, seq_len]
        assert call["input_ids"].ndim == 2, (
            f"input_ids must be 2-D [1, seq_len], got shape {call['input_ids'].shape}"
        )
        assert call["input_ids"].shape[0] == 1, (
            f"Batch dim must be 1, got {call['input_ids'].shape[0]}"
        )

    def test_yes_id_cache_reused_on_second_call(self, monkeypatch):
        """Yes-token-id set is computed once and reused across _score calls on same instance."""
        from ivg_kg.grounding import entailment as mod

        vocab_size = 20
        yes_id = 3
        tok, _ = self._build_stub_tokenizer(vocab_size=vocab_size, yes_ids=[yes_id])
        fake_output = _make_fake_forward_output(vocab_size, [yes_id])
        fake_model = _make_fake_model(fake_output)

        monkeypatch.setattr(mod, "_load_minicheck_model", lambda _: (tok, fake_model, "cpu"))

        gate = mod.MiniCheckEntailmentGate(model_id="stub")

        # Count calls to encode (used for yes-id extraction)
        encode_calls = []
        original_encode = tok.encode

        def tracked_encode(text: str, add_special_tokens: bool = True) -> list[int]:  # noqa: FBT001
            encode_calls.append(text)
            return original_encode(text, add_special_tokens=add_special_tokens)

        tok.encode = tracked_encode

        gate._score("premise one", "hypothesis one")
        count_first = len(encode_calls)

        gate._score("premise two", "hypothesis two")
        count_second = len(encode_calls)

        # Yes-id encode calls should happen at most once (cached after first _score)
        # The count should not grow by the yes-variant queries on the second call
        yes_variants = {"Yes", "yes", " Yes", " yes"}
        second_yes_calls = [c for c in encode_calls[count_first:count_second] if c in yes_variants]
        assert len(second_yes_calls) == 0, (
            f"Yes-id extraction should be cached; got extra encode calls on second _score: {second_yes_calls}"
        )


# ---------------------------------------------------------------------------
# 4. SYSTEM_PROMPT constant shape
# ---------------------------------------------------------------------------


class TestSystemPromptConstant:
    """Verify the SYSTEM_PROMPT module-level constant."""

    def test_system_prompt_is_string(self):
        from ivg_kg.grounding.entailment import SYSTEM_PROMPT

        assert isinstance(SYSTEM_PROMPT, str)

    def test_system_prompt_nonempty(self):
        from ivg_kg.grounding.entailment import SYSTEM_PROMPT

        assert len(SYSTEM_PROMPT) > 20

    def test_system_prompt_contains_key_phrases(self):
        """SYSTEM_PROMPT must contain canonical phrases from the MiniCheck package."""
        from ivg_kg.grounding.entailment import SYSTEM_PROMPT

        assert "consistent" in SYSTEM_PROMPT.lower()
        assert "claim" in SYSTEM_PROMPT.lower()
        assert "document" in SYSTEM_PROMPT.lower()
        # Must instruct responding with Yes/No
        assert "Yes" in SYSTEM_PROMPT
        assert "No" in SYSTEM_PROMPT

    def test_system_prompt_is_ascii(self):
        """SYSTEM_PROMPT must be pure ASCII (no unicode, no emojis)."""
        from ivg_kg.grounding.entailment import SYSTEM_PROMPT

        SYSTEM_PROMPT.encode("ascii")  # raises UnicodeEncodeError if non-ASCII

    def test_system_prompt_mentions_consistency(self):
        """The canonical prompt explains consistency in terms of substantiation."""
        from ivg_kg.grounding.entailment import SYSTEM_PROMPT

        assert "substantiated" in SYSTEM_PROMPT or "consistent" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 5. Skip-guarded integration test (real model, NOT run in CI)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (os.environ.get("IVG_KG_RUN_MINICHECK") == "1"),
    reason="Real MiniCheck-7B integration test; set IVG_KG_RUN_MINICHECK=1 to run",
)
class TestMiniCheckIntegration:
    """Integration test against the real Bespoke-MiniCheck-7B model.

    Requires:
        - IVG_KG_RUN_MINICHECK=1 environment variable
        - Model weights cached locally (bespokelabs/Bespoke-MiniCheck-7B)
        - ~14GB VRAM/unified memory (MPS) or CPU RAM

    Validates value-sensitivity (Invariant #3): correct entailment scores HIGH,
    wrong-value claim scores LOW.
    """

    def test_true_entailment_scores_high(self):
        """A correct paraphrase of the premise scores > 0.5."""
        from ivg_kg.grounding.entailment import MiniCheckEntailmentGate

        gate = MiniCheckEntailmentGate()
        premise = "Tennessee Williams wrote The Glass Menagerie."
        hypothesis = "The Glass Menagerie was written by Tennessee Williams."
        score = gate.entails(premise, hypothesis)
        assert score > 0.5, f"True entailment should score > 0.5, got {score}"

    def test_wrong_value_claim_scores_low(self):
        """A claim with a wrong author scores < 0.5."""
        from ivg_kg.grounding.entailment import MiniCheckEntailmentGate

        gate = MiniCheckEntailmentGate()
        premise = "Tennessee Williams wrote The Glass Menagerie."
        hypothesis = "The Glass Menagerie was written by Harold Pinter."
        score = gate.entails(premise, hypothesis)
        assert score < 0.5, f"Wrong-value claim should score < 0.5, got {score}"

    def test_value_sensitivity_gap(self):
        """Correct claim must score strictly higher than wrong-value claim."""
        from ivg_kg.grounding.entailment import MiniCheckEntailmentGate

        gate = MiniCheckEntailmentGate()
        premise = "Tennessee Williams wrote The Glass Menagerie."
        score_correct = gate.entails(
            premise, "The Glass Menagerie was written by Tennessee Williams."
        )
        score_wrong = gate.entails(
            premise, "The Glass Menagerie was written by Harold Pinter."
        )
        assert score_correct > score_wrong, (
            f"Correct claim ({score_correct:.3f}) must beat wrong-value claim ({score_wrong:.3f})"
        )


@pytest.mark.skipif(
    not (os.environ.get("IVG_KG_RUN_MINICHECK") == "1"),
    reason="Real MiniCheck-7B tokenizer/forward; set IVG_KG_RUN_MINICHECK=1 to run",
)
class TestMiniCheckBatchRegression:
    """Regression guards for entails_batch (the path the offline sweep uses).

    Catches the doubled-BOS bug: the batch path renders the chat template with
    tokenize=False then re-tokenizes; that re-tokenize MUST pass
    add_special_tokens=False, else TemplateProcessing prepends a SECOND BOS and
    batched scores diverge from the canonical single-pair _score path.
    """

    def _messages(self, premise, hypothesis):
        from ivg_kg.grounding.entailment import SYSTEM_PROMPT

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Document: {premise}\nClaim: {hypothesis}"},
        ]

    def test_batch_tokenization_has_no_doubled_bos(self):
        """The batch re-tokenization must match the single path's leading ids."""
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(
            "bespokelabs/Bespoke-MiniCheck-7B", trust_remote_code=True
        )
        msgs = self._messages("A.", "B.")
        single = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
        single_ids = (single.input_ids if hasattr(single, "input_ids") else single)[0].tolist()
        rendered = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        batch_ids = tok(rendered, return_tensors="pt", add_special_tokens=False)["input_ids"][
            0
        ].tolist()
        assert single_ids[:5] == batch_ids[:5], (
            f"batch tokenization diverges from single (doubled BOS?): "
            f"single={single_ids[:5]} batch={batch_ids[:5]}"
        )
        # And the bug form (default add_special_tokens=True) WOULD double the BOS:
        doubled = tok(rendered, return_tensors="pt")["input_ids"][0].tolist()
        assert doubled[:2] == [tok.bos_token_id, tok.bos_token_id], (
            "expected the default re-tokenize to double the BOS (guards the fix's necessity)"
        )

    def test_entails_batch_deterministic_and_value_sensitive(self):
        """Fresh gate, batch path FIRST (no cache priming): deterministic + value-sensitive."""
        from ivg_kg.grounding.entailment import MiniCheckEntailmentGate

        prem = "Tennessee Williams wrote The Glass Menagerie."
        pairs = [
            (prem, "The Glass Menagerie was written by Tennessee Williams."),
            (prem, "The Glass Menagerie was written by Harold Pinter."),
        ]
        gate = MiniCheckEntailmentGate()
        r1 = gate.entails_batch(pairs)
        gate._cache.clear()
        r2 = gate.entails_batch(pairs)
        assert r1 == r2, f"batched forward must be deterministic: {r1} != {r2}"
        assert r1[0] > 0.5 > r1[1], f"batch must stay value-sensitive: {r1}"
