"""
LocalModelClient: HuggingFace transformers / MLX (Apple-Silicon MPS) adapter (GR1).

LAZY IMPORT GUARD: transformers and torch are imported ONLY inside _load_transformers().
Importing this module or constructing LocalModelClient does NOT require torch/transformers
to be installed and does NOT trigger any model download.

The tests run with no model present; _load_transformers() is the single
import-time gate that downstream tests can monkeypatch.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ivg_kg import config as cfg
from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.schema import GenerationContext

if TYPE_CHECKING:
    # Type-only import; never executed at runtime.
    pass


def _load_transformers() -> Any:
    """Lazy loader: import transformers and return the module.

    Raises ImportError with a helpful message if transformers is not installed.
    This is the single choke-point for the lazy-import guard; monkeypatch it
    in tests to avoid requiring torch/transformers at test time.
    """
    try:
        import transformers  # noqa: PLC0415

        return transformers
    except ImportError as exc:
        raise ImportError(
            "transformers is not installed. "
            "Install the 'grounding' extra: pip install ivg-kg[grounding]"
        ) from exc


class LocalModelClient(BaseAIClient):
    """LLM generation via a local HuggingFace model (POC default backend).

    Model is loaded lazily on first generate call; construction is always
    safe regardless of torch/transformers availability.

    Args:
        model_id: HuggingFace model id.  Defaults to config.LOCAL_LLM_MODEL_ID.
    """

    supports_evidence_trace: bool = False

    def __init__(self, model_id: str | None = None) -> None:
        self._model_id: str = model_id or cfg.LOCAL_LLM_MODEL_ID
        self._pipeline: Any = None  # loaded lazily on first call

    def _get_pipeline(self) -> Any:
        """Load and cache the HuggingFace text-generation pipeline."""
        if self._pipeline is not None:
            return self._pipeline
        transformers = _load_transformers()
        self._pipeline = transformers.pipeline(
            "text-generation",
            model=self._model_id,
            device_map="auto",
        )
        return self._pipeline

    def _generate(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        """Generate an answer using the local HF model.

        The context is serialised to a plain-text prompt; the model is loaded
        on first call.  Seeding is handled via transformers set_seed if a seed
        is provided.
        """
        _load_transformers()  # guard: raises ImportError if not installed

        if seed is not None:
            try:
                from transformers import set_seed as _set_seed  # noqa: PLC0415

                _set_seed(seed)
            except ImportError:
                pass

        prompt = _build_prompt(question, context)
        pipe = self._get_pipeline()
        outputs = pipe(
            prompt,
            max_new_tokens=256,
            temperature=temperature,
            do_sample=True,
        )
        # HF pipeline returns [{"generated_text": "..."}]
        generated: str = outputs[0]["generated_text"]
        # Strip the prompt prefix if the model echoes it
        if generated.startswith(prompt):
            generated = generated[len(prompt):].strip()
        return GenerationResult(answer=generated, evidence_trace=None)


def _build_prompt(question: str, context: GenerationContext) -> str:
    """Serialise a GenerationContext to a plain-text generation prompt."""
    lines: list[str] = []
    if context.description:
        lines.append(f"Entity: {context.description}")
    for triple in context.triples:
        lines.append(f"- {triple.property_label}: {triple.object_label}")
    context_block = "\n".join(lines) if lines else "(no context provided)"
    return f"Context:\n{context_block}\n\nQuestion: {question}\nAnswer:"
