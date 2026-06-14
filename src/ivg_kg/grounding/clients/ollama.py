"""
OllamaClient: HTTP adapter for a local Ollama server (GR1).

Uses the Ollama REST API (/api/generate) over plain HTTP.
SPEC lists requests as the HTTP library (it is already a dep under the 'data' extra).

LAZY IMPORT GUARD: requests is imported ONLY inside _load_requests().
Importing this module or constructing OllamaClient does NOT require requests
to be installed and does NOT hit the network.
"""
from __future__ import annotations

from typing import Any

from ivg_kg import config as cfg
from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.grounding.clients.local import _build_prompt
from ivg_kg.schema import GenerationContext


def _load_requests() -> Any:
    """Lazy loader: import requests and return the module.

    Raises ImportError with a helpful message if requests is not installed.
    Monkeypatch this in tests to avoid network calls.
    """
    try:
        import requests  # noqa: PLC0415

        return requests
    except ImportError as exc:
        raise ImportError(
            "requests is not installed. "
            "Install the 'data' extra: pip install ivg-kg[data]"
        ) from exc


class OllamaClient(BaseAIClient):
    """LLM generation via a local Ollama server (HTTP /api/generate).

    Args:
        base_url: Ollama server base URL.  Defaults to config.OLLAMA_BASE_URL.
        model:    Model name served by Ollama.  Defaults to config.OLLAMA_MODEL_ID.
    """

    supports_evidence_trace: bool = False

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self._base_url: str = (base_url or cfg.OLLAMA_BASE_URL).rstrip("/")
        self._model: str = model or cfg.OLLAMA_MODEL_ID

    def _generate(
        self,
        question: str,
        context: GenerationContext,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> GenerationResult:
        """Call Ollama /api/generate and return the response text.

        Raises RuntimeError on HTTP or network failure.
        """
        requests = _load_requests()
        prompt = _build_prompt(question, context)
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }
        if seed is not None:
            payload["options"]["seed"] = seed  # type: ignore[index]

        url = f"{self._base_url}/api/generate"
        # Gather the "server unreachable" exception types from the requests module,
        # plus builtin OSError/TimeoutError so tests that stub a minimal fake module
        # still work correctly.
        _conn_exc = getattr(
            getattr(requests, "exceptions", None), "ConnectionError", ConnectionError
        )
        _timeout_exc = getattr(
            getattr(requests, "exceptions", None), "Timeout", TimeoutError
        )
        try:
            response = requests.post(url, json=payload, timeout=60)
        except (_conn_exc, _timeout_exc, ConnectionError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                f"OllamaClient: Ollama server is not reachable at {self._base_url}. "
                f"Start it with: ollama serve"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"OllamaClient: unexpected error contacting {self._base_url}: {exc}"
            ) from exc

        if response.status_code >= 400:
            raise RuntimeError(
                f"OllamaClient: model not available (HTTP {response.status_code}). "
                f"Pull it with: ollama pull {self._model}"
            )

        data: dict[str, Any] = response.json()
        answer: str = data.get("response", "")
        if not answer:
            raise RuntimeError(
                f"OllamaClient: Ollama returned an empty response for model '{self._model}'. "
                f"Check that the model is fully loaded and the prompt is valid. "
                f"To re-pull the model: ollama pull {self._model}"
            )
        return GenerationResult(answer=answer, evidence_trace=None)
