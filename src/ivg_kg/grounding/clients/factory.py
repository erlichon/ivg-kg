"""
Factory for selecting and constructing an AI generation client (GR1).

make_client(backend) returns a configured BaseAIClient instance.
get_default_client() uses config.DEFAULT_CLIENT_BACKEND.

Supported backends: "local", "ollama", "cloud".
"""
from __future__ import annotations

from ivg_kg import config as cfg
from ivg_kg.grounding.clients.base import BaseAIClient


def make_client(backend: str | None = None) -> BaseAIClient:
    """Construct a BaseAIClient for the named backend.

    Args:
        backend: One of "local", "ollama", "cloud".
                 If None, falls back to config.DEFAULT_CLIENT_BACKEND.

    Returns:
        A concrete BaseAIClient instance (no model download triggered).

    Raises:
        ValueError: If backend is not a recognised value.
    """
    resolved = (backend or cfg.DEFAULT_CLIENT_BACKEND).lower()

    if resolved == "local":
        from ivg_kg.grounding.clients.local import LocalModelClient  # noqa: PLC0415

        return LocalModelClient()

    if resolved == "ollama":
        from ivg_kg.grounding.clients.ollama import OllamaClient  # noqa: PLC0415

        return OllamaClient()

    if resolved == "cloud":
        from ivg_kg.grounding.clients.cloud import CloudAIClient  # noqa: PLC0415

        return CloudAIClient()

    raise ValueError(
        f"Unknown client backend '{resolved}'. "
        "Valid values: 'local', 'ollama', 'cloud'."
    )


def get_default_client() -> BaseAIClient:
    """Return a client configured by config.DEFAULT_CLIENT_BACKEND."""
    return make_client(cfg.DEFAULT_CLIENT_BACKEND)
