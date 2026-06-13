"""
Answer generation cache for IVG-KG (GR4, SPEC-text SS4.3).

This module is the GENERATOR-ONLY layer: it calls BaseAIClient and caches the
result so that the offline sweep is reproducible across process runs.

Generator vs verifier discipline:
- This module is GENERATOR-ONLY (stochastic, seeded, sampled N times per condition).
- It MUST NEVER be used to verify or grade claims.
- The verifier is BaseEntailmentGate (separate module, different model family).

Seeded stochastic generation rationale:
- Generation is stochastic (temperature ~0.7) and SEEDED for reproducibility.
- seed = f(question_id, condition, sample_index) in the sweep harness.
- The cache key INCLUDES both seed AND temperature because N seeded draws of the
  same (question, context) are DIFFERENT answers and MUST NOT collide.
- Key serialization uses json.dumps(..., sort_keys=True, ensure_ascii=True) so the
  key is deterministic across Python runs (no Python hash() / PYTHONHASHSEED).

Cache layout:
- Files live at data/cache/<sha256hex>.json (gitignored, same convention as
  wikidata.py).  cache_dir is overridable so tests can use tmp_path.
- Stored JSON includes {question, seed, temperature, answer} for debuggability;
  GenerationCache.get() returns just the answer string.

Client is INJECTED as a parameter so tests pass a tiny stub without any live model.
No torch/transformers/requests is imported at module top level.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from ivg_kg.schema import GenerationContext

if TYPE_CHECKING:
    from ivg_kg.grounding.clients.base import BaseAIClient

__all__ = ["GenerationCache", "generate_answer"]

# Default cache directory (relative to cwd, same convention as wikidata.py).
_DEFAULT_CACHE_DIR = Path("data/cache")


class GenerationCache:
    """Disk-backed cache for seeded LLM generation results.

    Files are stored as <cache_dir>/<sha256key>.json.  The JSON payload stores
    the answer plus metadata for debuggability; get() returns just the answer.

    The key includes question, context, temperature, AND seed because stochastic
    seeded generation produces DIFFERENT answers for different seeds even when
    all other inputs are identical -- they must not collide in the cache.
    """

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self._cache_dir: Path = (
            Path(cache_dir) if cache_dir is not None else _DEFAULT_CACHE_DIR
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def key(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float,
        seed: int | None,
    ) -> str:
        """Return a deterministic sha256 hex key for the given generation inputs.

        Includes question, context (via model_dump with sort_keys), temperature,
        and seed.  Uses json.dumps(sort_keys=True, ensure_ascii=True) -- NOT
        Python hash() -- so the key is stable across process restarts even with
        different PYTHONHASHSEED values.

        N seeded draws of the same (question, context, temperature) produce
        DIFFERENT keys because seed is part of the payload.
        """
        payload = json.dumps(
            {
                "question": question,
                "context": context.model_dump(),
                "temperature": temperature,
                "seed": seed,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        """Return the cached answer string, or None on a cache miss."""
        cache_file = self._cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        with cache_file.open(encoding="utf-8") as f:
            data = json.load(f)
        return data["answer"]

    def put(self, key: str, answer: str) -> None:
        """Write the answer to the cache file at <cache_dir>/<key>.json."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_dir / f"{key}.json"
        payload = {"answer": answer}
        with cache_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, sort_keys=True, ensure_ascii=True)


def generate_answer(
    question: str,
    context: GenerationContext,
    client: BaseAIClient,
    *,
    temperature: float = 0.7,
    seed: int | None = None,
    cache: GenerationCache | None = None,
) -> str:
    """Generate an answer, using cache when available.

    Args:
        question:    The question posed to the generator.
        context:     The (possibly ablated) evidence shown to the generator.
        client:      Injected BaseAIClient; must NOT be the verifier.
        temperature: Sampling temperature (default 0.7 for stochastic draws).
        seed:        Deterministic seed for this draw.
                     None = non-reproducible draw (cache still keyed on None).
        cache:       GenerationCache instance.  If provided: cache-hit -> return
                     cached answer without calling client; cache-miss -> call
                     client, store result, return.  If None -> always call client.

    Returns:
        The generated answer string.
    """
    if cache is not None:
        k = cache.key(question, context, temperature=temperature, seed=seed)
        cached = cache.get(k)
        if cached is not None:
            return cached
        answer = client.generate_answer(question, context, temperature=temperature, seed=seed)
        cache.put(k, answer)
        return answer

    return client.generate_answer(question, context, temperature=temperature, seed=seed)
