"""
Public API for ivg_kg.grounding.clients (GR1).

Business logic imports BaseAIClient and GenerationResult from here.
Concrete client classes are available for type-checks and testing.
"""
from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult
from ivg_kg.grounding.clients.cloud import CloudAIClient
from ivg_kg.grounding.clients.factory import get_default_client, make_client
from ivg_kg.grounding.clients.local import LocalModelClient
from ivg_kg.grounding.clients.ollama import OllamaClient

__all__ = [
    "BaseAIClient",
    "GenerationResult",
    "LocalModelClient",
    "OllamaClient",
    "CloudAIClient",
    "make_client",
    "get_default_client",
]
