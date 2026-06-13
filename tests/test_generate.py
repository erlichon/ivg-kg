"""
Tests for grounding/generate.py -- the seeded generation cache (GR4, SPEC-text SS4.3).

Coverage:
  - generate_answer with no cache calls the client and returns its answer.
  - With cache: first call hits client (calls==1), second identical call returns
    cached answer without calling client (calls stays 1).
  - Seed is in the key: same (question, context, temperature) but different seed
    produces two distinct cache entries and two distinct answers.
  - Key determinism: same inputs -> same key across two GenerationCache instances;
    differs when question/context/temperature/seed differ; stable (not Python-hash).
  - get returns None for absent key; put then get round-trips the answer;
    cache file lands at <cache_dir>/<key>.json.
  - Determinism: same (question, context, seed) via cache -> identical answer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.schema import GenerationContext, KGEdge, ValueType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ctx(entity_id: str = "Q42") -> GenerationContext:
    """Return a minimal GenerationContext for testing."""
    return GenerationContext(
        entity_id=entity_id,
        triples=[
            KGEdge(
                subject_id=entity_id,
                property_id="P31",
                property_label="instance of",
                object_id="Q5",
                object_label="human",
                value_type=ValueType.ITEM,
            )
        ],
        description="British author",
        image_path=None,
    )


class _StubClient(BaseAIClient):
    """Minimal stub: records call count and varies answer by seed."""

    def __init__(self, answer: str = "canned answer") -> None:
        self._answer = answer
        self.calls = 0

    def _generate(
        self,
        question: str,
        context: Any,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        self.calls += 1
        return GenerationResult(answer=f"{self._answer}|seed={seed}")


# ---------------------------------------------------------------------------
# Tests: generate_answer (no cache)
# ---------------------------------------------------------------------------


class TestGenerateAnswerNoCache:
    def test_calls_client_and_returns_answer(self) -> None:
        from ivg_kg.grounding.generate import generate_answer

        client = _StubClient()
        ctx = _make_ctx()
        result = generate_answer("Who wrote Hitchhiker?", ctx, client)
        assert isinstance(result, str)
        assert client.calls == 1

    def test_returns_client_answer_content(self) -> None:
        from ivg_kg.grounding.generate import generate_answer

        client = _StubClient("my-answer")
        ctx = _make_ctx()
        result = generate_answer("Q?", ctx, client, seed=7)
        assert "my-answer" in result
        assert "seed=7" in result

    def test_no_cache_always_calls_client(self) -> None:
        from ivg_kg.grounding.generate import generate_answer

        client = _StubClient()
        ctx = _make_ctx()
        generate_answer("Q?", ctx, client, cache=None)
        generate_answer("Q?", ctx, client, cache=None)
        assert client.calls == 2


# ---------------------------------------------------------------------------
# Tests: GenerationCache get/put/miss
# ---------------------------------------------------------------------------


class TestGenerationCacheStorage:
    def test_get_returns_none_for_absent_key(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        cache = GenerationCache(cache_dir=tmp_path)
        assert cache.get("nonexistent-key") is None

    def test_put_then_get_round_trips(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        cache = GenerationCache(cache_dir=tmp_path)
        cache.put("abc123", "the answer is 42")
        assert cache.get("abc123") == "the answer is 42"

    def test_cache_file_lands_at_expected_path(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        cache = GenerationCache(cache_dir=tmp_path)
        cache.put("mykey", "some text")
        expected = tmp_path / "mykey.json"
        assert expected.exists()

    def test_cache_file_is_valid_json(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        cache = GenerationCache(cache_dir=tmp_path)
        cache.put("k1", "hello world")
        with (tmp_path / "k1.json").open() as f:
            data = json.load(f)
        # The JSON must at minimum contain the answer string
        assert "hello world" in json.dumps(data)

    def test_cache_dir_created_if_missing(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        new_dir = tmp_path / "deep" / "nested" / "cache"
        assert not new_dir.exists()
        GenerationCache(cache_dir=new_dir)
        # Cache dir is created on init or first use; put triggers it
        cache = GenerationCache(cache_dir=new_dir)
        cache.put("x", "y")
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# Tests: cache key determinism and seed isolation
# ---------------------------------------------------------------------------


class TestCacheKeyDeterminism:
    def test_same_inputs_same_key_across_instances(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        ctx = _make_ctx()
        cache1 = GenerationCache(cache_dir=tmp_path)
        cache2 = GenerationCache(cache_dir=tmp_path)
        k1 = cache1.key("Q?", ctx, temperature=0.7, seed=42)
        k2 = cache2.key("Q?", ctx, temperature=0.7, seed=42)
        assert k1 == k2

    def test_key_is_hex_string(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        ctx = _make_ctx()
        cache = GenerationCache(cache_dir=tmp_path)
        k = cache.key("Q?", ctx, temperature=0.7, seed=1)
        assert isinstance(k, str)
        # sha256 hex is 64 chars
        assert len(k) == 64
        int(k, 16)  # must be valid hex

    def test_different_question_different_key(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        ctx = _make_ctx()
        cache = GenerationCache(cache_dir=tmp_path)
        k1 = cache.key("Q1?", ctx, temperature=0.7, seed=0)
        k2 = cache.key("Q2?", ctx, temperature=0.7, seed=0)
        assert k1 != k2

    def test_different_temperature_different_key(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        ctx = _make_ctx()
        cache = GenerationCache(cache_dir=tmp_path)
        k1 = cache.key("Q?", ctx, temperature=0.7, seed=0)
        k2 = cache.key("Q?", ctx, temperature=0.5, seed=0)
        assert k1 != k2

    def test_different_seed_different_key(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        ctx = _make_ctx()
        cache = GenerationCache(cache_dir=tmp_path)
        k1 = cache.key("Q?", ctx, temperature=0.7, seed=1)
        k2 = cache.key("Q?", ctx, temperature=0.7, seed=2)
        assert k1 != k2

    def test_none_seed_vs_int_seed_different_key(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        ctx = _make_ctx()
        cache = GenerationCache(cache_dir=tmp_path)
        k1 = cache.key("Q?", ctx, temperature=0.7, seed=None)
        k2 = cache.key("Q?", ctx, temperature=0.7, seed=0)
        assert k1 != k2

    def test_key_stable_not_python_hash(self, tmp_path: Path) -> None:
        """Key must be stable (not Python hash()-salted): compute it twice."""
        from ivg_kg.grounding.generate import GenerationCache

        ctx = _make_ctx()
        cache = GenerationCache(cache_dir=tmp_path)
        k1 = cache.key("stable?", ctx, temperature=0.7, seed=42)
        k2 = cache.key("stable?", ctx, temperature=0.7, seed=42)
        assert k1 == k2
        # Both must be identical hex strings (if Python hash were involved,
        # PYTHONHASHSEED could change them between processes; within one process
        # they must at minimum match each other)
        assert k1 == k2

    def test_different_context_entity_different_key(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache

        ctx_a = _make_ctx("Q42")
        ctx_b = _make_ctx("Q100")
        cache = GenerationCache(cache_dir=tmp_path)
        k1 = cache.key("Q?", ctx_a, temperature=0.7, seed=0)
        k2 = cache.key("Q?", ctx_b, temperature=0.7, seed=0)
        assert k1 != k2


# ---------------------------------------------------------------------------
# Tests: generate_answer with cache (hit/miss semantics)
# ---------------------------------------------------------------------------


class TestGenerateAnswerWithCache:
    def test_first_call_hits_client(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache, generate_answer

        client = _StubClient()
        cache = GenerationCache(cache_dir=tmp_path)
        ctx = _make_ctx()
        generate_answer("Q?", ctx, client, seed=1, cache=cache)
        assert client.calls == 1

    def test_second_identical_call_uses_cache(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache, generate_answer

        client = _StubClient()
        cache = GenerationCache(cache_dir=tmp_path)
        ctx = _make_ctx()
        r1 = generate_answer("Q?", ctx, client, seed=1, cache=cache)
        r2 = generate_answer("Q?", ctx, client, seed=1, cache=cache)
        assert client.calls == 1  # only called once
        assert r1 == r2

    def test_different_seed_both_call_client(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache, generate_answer

        client = _StubClient()
        cache = GenerationCache(cache_dir=tmp_path)
        ctx = _make_ctx()
        r1 = generate_answer("Q?", ctx, client, seed=1, cache=cache)
        r2 = generate_answer("Q?", ctx, client, seed=2, cache=cache)
        assert client.calls == 2  # different seeds -> different cache entries
        assert r1 != r2  # stub varies by seed

    def test_different_seed_two_distinct_cache_files(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache, generate_answer

        client = _StubClient()
        cache = GenerationCache(cache_dir=tmp_path)
        ctx = _make_ctx()
        generate_answer("Q?", ctx, client, seed=10, cache=cache)
        generate_answer("Q?", ctx, client, seed=20, cache=cache)
        json_files = list(tmp_path.glob("*.json"))
        assert len(json_files) == 2

    def test_cached_answer_identical_to_original(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import GenerationCache, generate_answer

        client = _StubClient()
        cache = GenerationCache(cache_dir=tmp_path)
        ctx = _make_ctx()
        r1 = generate_answer("same question", ctx, client, seed=99, cache=cache)
        r2 = generate_answer("same question", ctx, client, seed=99, cache=cache)
        assert r1 == r2

    def test_cache_none_always_calls_client(self, tmp_path: Path) -> None:
        from ivg_kg.grounding.generate import generate_answer

        client = _StubClient()
        ctx = _make_ctx()
        generate_answer("Q?", ctx, client, seed=1, cache=None)
        generate_answer("Q?", ctx, client, seed=1, cache=None)
        assert client.calls == 2

    def test_pre_populated_cache_skips_client(self, tmp_path: Path) -> None:
        """If cache is pre-populated (put), generate_answer never calls client."""
        from ivg_kg.grounding.generate import GenerationCache, generate_answer

        client = _StubClient()
        cache = GenerationCache(cache_dir=tmp_path)
        ctx = _make_ctx()
        k = cache.key("Q?", ctx, temperature=0.7, seed=5)
        cache.put(k, "pre-canned answer")

        result = generate_answer("Q?", ctx, client, temperature=0.7, seed=5, cache=cache)
        assert result == "pre-canned answer"
        assert client.calls == 0


# ---------------------------------------------------------------------------
# Tests: public API
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_importable_from_module(self) -> None:
        from ivg_kg.grounding.generate import GenerationCache, generate_answer

        assert callable(generate_answer)
        assert GenerationCache is not None

    def test_all_exports(self) -> None:
        import ivg_kg.grounding.generate as mod

        assert hasattr(mod, "__all__")
        assert "GenerationCache" in mod.__all__
        assert "generate_answer" in mod.__all__
