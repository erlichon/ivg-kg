"""
BaseAIClient: the single generation interface for IVG-KG (GR1, SPEC-text SS4.3).

This module is the ONLY place business logic should touch.  No provider SDK,
no HTTP call, no torch import lives here.  All of that is in the concrete
adapter modules (local.py, ollama.py, cloud.py).

Generator vs verifier discipline (Invariant #14):
- This client is the GENERATOR ONLY (stochastic, seeded, sampled N times).
- It MUST NEVER be used to verify or grade claims.
- The verifier is BaseEntailmentGate (separate module, different model family).

Evidence-trace seam:
- GenerationResult carries an optional evidence_trace field.
- Concrete clients set supports_evidence_trace = False and return trace=None.
- future ClaudeCodeClient: ivg-kg over claude-code, showing what it grounded on.
  It would set supports_evidence_trace = True and populate evidence_trace with
  the specific GenerationContext items it attended to when producing the answer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from ivg_kg.schema import GenerationContext


class GenerationResult(BaseModel):
    """Result of a single generation call.

    answer:         The model's generated text response.
    evidence_trace: Optional list of context items the model grounded on.
                    Currently None for all concrete clients (supports_evidence_trace=False).
                    Populated by future ClaudeCodeClient (see module docstring).

    JSON-serialisable; pydantic v2.
    """

    answer: str
    evidence_trace: list[Any] | None = None


class BaseAIClient(ABC):
    """Abstract base for all LLM generation adapters.

    Public interface:
        generate_answer(question, context, *, temperature, seed) -> str
            Convenience method: calls _generate and returns answer text only.

        _generate(question, context, *, temperature, seed) -> GenerationResult
            Abstract: subclasses implement this.  Returns full result including
            the optional evidence_trace for clients that support it.

    Seam for future ClaudeCodeClient:
        Override supports_evidence_trace = True and populate evidence_trace in
        the returned GenerationResult.  The caller uses _generate() directly
        to access the trace.  generate_answer() stays the same for callers
        that only need the text.

    Invariant: NEVER add grading/entailment methods here.
    """

    supports_evidence_trace: bool = False

    @abstractmethod
    def _generate(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        """Generate an answer given the (possibly ablated) context.

        Args:
            question:    The question posed to the model.
            context:     The ablated evidence shown to the generator.
            temperature: Sampling temperature.  ~0.7 for stochastic draws;
                         callers SEED via seed=f(question_id, condition, sample_index).
            seed:        Deterministic seed for reproducible sampling.
                         None = no seed (non-reproducible draw).

        Returns:
            GenerationResult with answer text and optional evidence_trace.
        """

    def generate_answer(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> str:
        """Convenience wrapper: generate and return the answer text only.

        Callers that need the evidence_trace should call _generate() directly.
        """
        result = self._generate(question, context, temperature=temperature, seed=seed)
        return result.answer
