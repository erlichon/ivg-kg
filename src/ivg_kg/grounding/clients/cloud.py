"""
CloudAIClient: seam for a cloud-hosted LLM backend (GR1).

This is an intentional STUB.  The class and config wiring exist so business logic
can select it via make_client("cloud") without importing any provider SDK.

The actual call raises NotImplementedError until a cloud provider is wired up.
See ivg_kg.config for provider selection constants (added post-M-BOOKS).

Note: no provider SDK is imported here.  When a real cloud backend is added,
the SDK import must remain LAZY (inside _generate) following the same pattern
as LocalModelClient._load_transformers().
"""
from __future__ import annotations

from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.schema import GenerationContext


class CloudAIClient(BaseAIClient):
    """Stub cloud LLM adapter (seam only -- not yet implemented).

    Construction succeeds; calling generate raises NotImplementedError with
    a message explaining that no cloud credentials or provider are configured.

    When a real provider is added (post-M-BOOKS):
    - Set supports_evidence_trace = True if the provider supports it.
    - Implement _generate() with a lazy provider SDK import.
    - Add provider config constants to ivg_kg.config.
    """

    supports_evidence_trace: bool = False

    def _generate(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        raise NotImplementedError(
            "CloudAIClient is a seam stub: no cloud provider is configured. "
            "Set DEFAULT_CLIENT_BACKEND to 'local' or 'ollama', or implement "
            "a concrete cloud adapter and wire it here."
        )
