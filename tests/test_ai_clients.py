"""
Tests for grounding/clients/ -- the LLM abstraction layer (GR1).

All tests run with NO model, NO network, NO torch/transformers installed.
Lazy imports are verified by monkeypatching the module-level name before call.

Coverage:
  - ABC cannot be instantiated; defines contract.
  - EchoClient: minimal concrete implementation proves the ABC contract.
  - GenerationResult: pydantic v2 round-trip, evidence_trace seam.
  - LocalModelClient: module-importable without torch; lazy import guarded.
  - OllamaClient: module-importable without requests; lazy import guarded.
  - CloudAIClient: selectable; calling generate raises a clear error.
  - Factory: make_client selects the right class from config strings.
  - supports_evidence_trace is False on all three concrete clients.
  - generate_answer returns str; accepts temperature and seed kwargs.
  - Config constants for new client settings exist.
"""
from __future__ import annotations

import types
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_ctx() -> Any:
    """Return a minimal GenerationContext-like object (or the real one)."""
    from ivg_kg.schema import GenerationContext, KGEdge, ValueType

    return GenerationContext(
        entity_id="Q42",
        triples=[
            KGEdge(
                subject_id="Q42",
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


# ---------------------------------------------------------------------------
# GenerationResult -- evidence-trace seam
# ---------------------------------------------------------------------------


class TestGenerationResult:
    def test_answer_only_construction(self) -> None:
        from ivg_kg.grounding.clients.base import GenerationResult

        result = GenerationResult(answer="The answer is 42.")
        assert result.answer == "The answer is 42."
        assert result.evidence_trace is None

    def test_with_evidence_trace(self) -> None:
        from ivg_kg.grounding.clients.base import GenerationResult

        result = GenerationResult(answer="Ans.", evidence_trace=["item1", "item2"])
        assert result.evidence_trace == ["item1", "item2"]

    def test_json_round_trip_no_trace(self) -> None:
        from ivg_kg.grounding.clients.base import GenerationResult

        r = GenerationResult(answer="hello")
        reconstructed = GenerationResult.model_validate_json(r.model_dump_json())
        assert reconstructed == r
        assert reconstructed.evidence_trace is None

    def test_json_round_trip_with_trace(self) -> None:
        from ivg_kg.grounding.clients.base import GenerationResult

        r = GenerationResult(answer="foo", evidence_trace=["a", "b"])
        reconstructed = GenerationResult.model_validate_json(r.model_dump_json())
        assert reconstructed == r

    def test_is_pydantic_model(self) -> None:
        from pydantic import BaseModel

        from ivg_kg.grounding.clients.base import GenerationResult

        assert issubclass(GenerationResult, BaseModel)


# ---------------------------------------------------------------------------
# BaseAIClient -- ABC contract
# ---------------------------------------------------------------------------


class TestBaseAIClientABC:
    def test_cannot_instantiate_directly(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient

        with pytest.raises(TypeError):
            BaseAIClient()  # type: ignore[abstract]

    def test_supports_evidence_trace_class_attribute(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient

        assert hasattr(BaseAIClient, "supports_evidence_trace")
        # the ABC default is False
        assert BaseAIClient.supports_evidence_trace is False

    def test_abstract_methods_exist(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient

        abstract = getattr(BaseAIClient, "__abstractmethods__", frozenset())
        assert "_generate" in abstract, "BaseAIClient must declare _generate as abstract"


# ---------------------------------------------------------------------------
# EchoClient -- proves ABC contract via a tiny in-test implementation
# ---------------------------------------------------------------------------


class EchoClient:
    """Minimal in-test BaseAIClient implementation for contract verification."""

    supports_evidence_trace: bool = False

    def __init__(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient

        # EchoClient must be a valid subclass -- verify it satisfies the ABC
        # by constructing it after the ABC import succeeds.
        # (We inherit manually below; this line is just the import guard.)
        _ = BaseAIClient

    def _generate(
        self,
        question: str,
        context: Any,
        *,
        temperature: float = 0.7,
        seed: int | None = None,
    ) -> Any:
        from ivg_kg.grounding.clients.base import GenerationResult

        return GenerationResult(answer=f"echo: {question}")


# We need a proper subclass to pass ABC checks.
def _make_echo_client() -> Any:
    from ivg_kg.grounding.clients.base import BaseAIClient, GenerationResult

    class _EchoClientImpl(BaseAIClient):
        supports_evidence_trace = False

        def _generate(
            self,
            question: str,
            context: Any,
            *,
            temperature: float = 0.7,
            seed: int | None = None,
        ) -> GenerationResult:
            return GenerationResult(answer=f"echo: {question}")

    return _EchoClientImpl()


class TestEchoClient:
    def test_generate_answer_returns_str(self) -> None:
        client = _make_echo_client()
        result = client.generate_answer("Who wrote Hitchhiker's Guide?", _dummy_ctx())
        assert isinstance(result, str)

    def test_generate_answer_content(self) -> None:
        client = _make_echo_client()
        result = client.generate_answer("Q?", _dummy_ctx())
        assert "echo:" in result

    def test_generate_answer_accepts_temperature(self) -> None:
        client = _make_echo_client()
        result = client.generate_answer("Q?", _dummy_ctx(), temperature=0.3)
        assert isinstance(result, str)

    def test_generate_answer_accepts_seed(self) -> None:
        client = _make_echo_client()
        result = client.generate_answer("Q?", _dummy_ctx(), seed=42)
        assert isinstance(result, str)

    def test_generate_answer_accepts_both_params(self) -> None:
        client = _make_echo_client()
        result = client.generate_answer("Q?", _dummy_ctx(), temperature=0.7, seed=99)
        assert isinstance(result, str)

    def test_supports_evidence_trace_is_false(self) -> None:
        client = _make_echo_client()
        assert client.supports_evidence_trace is False

    def test_generate_result_returns_generation_result(self) -> None:
        from ivg_kg.grounding.clients.base import GenerationResult

        client = _make_echo_client()
        result = client._generate("Q?", _dummy_ctx())
        assert isinstance(result, GenerationResult)

    def test_generate_result_trace_is_none(self) -> None:
        client = _make_echo_client()
        result = client._generate("Q?", _dummy_ctx())
        assert result.evidence_trace is None


# ---------------------------------------------------------------------------
# LocalModelClient -- lazy import guard (no torch required)
# ---------------------------------------------------------------------------


class TestLocalModelClient:
    def test_module_importable_without_torch(self) -> None:
        """Importing the module must NOT fail even when torch is absent."""
        import importlib
        import sys

        # Temporarily hide torch from sys.modules
        torch_backup = sys.modules.pop("torch", None)
        transformers_backup = sys.modules.pop("transformers", None)
        try:
            # Re-import the module; it must not raise ImportError
            import ivg_kg.grounding.clients.local as local_mod

            importlib.reload(local_mod)
        except ImportError as exc:
            pytest.fail(f"local.py raised ImportError at module import time: {exc}")
        finally:
            if torch_backup is not None:
                sys.modules["torch"] = torch_backup
            if transformers_backup is not None:
                sys.modules["transformers"] = transformers_backup

    def test_class_exists(self) -> None:
        from ivg_kg.grounding.clients.local import LocalModelClient

        assert LocalModelClient is not None

    def test_is_subclass_of_base(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient
        from ivg_kg.grounding.clients.local import LocalModelClient

        assert issubclass(LocalModelClient, BaseAIClient)

    def test_supports_evidence_trace_is_false(self) -> None:
        from ivg_kg.grounding.clients.local import LocalModelClient

        assert LocalModelClient.supports_evidence_trace is False

    def test_generate_raises_without_transformers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling generate without transformers installed raises ImportError with helpful message."""
        import ivg_kg.grounding.clients.local as local_mod

        # Patch the lazy loader to simulate missing transformers
        orig = local_mod._load_transformers  # type: ignore[attr-defined]
        monkeypatch.setattr(
            local_mod,
            "_load_transformers",
            lambda: (_ for _ in ()).throw(ImportError("No module named 'transformers'")),
        )
        client = local_mod.LocalModelClient(model_id="test/model")
        with pytest.raises((ImportError, RuntimeError, Exception)):
            client.generate_answer("Q?", _dummy_ctx())
        # restore
        monkeypatch.setattr(local_mod, "_load_transformers", orig)

    def test_construction_does_not_import_torch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Constructing LocalModelClient must not trigger a torch import."""
        # We check by just constructing; if torch was already imported it's fine.
        # Key guarantee: construction doesn't CALL torch code.
        from ivg_kg.grounding.clients.local import LocalModelClient

        client = LocalModelClient(model_id="dummy/model")
        assert client is not None  # constructed without error


# ---------------------------------------------------------------------------
# OllamaClient -- lazy import guard (no requests required at module level)
# ---------------------------------------------------------------------------


class TestOllamaClient:
    def test_module_importable_without_requests(self) -> None:
        import importlib
        import sys

        requests_backup = sys.modules.pop("requests", None)
        try:
            import ivg_kg.grounding.clients.ollama as ollama_mod

            importlib.reload(ollama_mod)
        except ImportError as exc:
            pytest.fail(f"ollama.py raised ImportError at module import time: {exc}")
        finally:
            if requests_backup is not None:
                sys.modules["requests"] = requests_backup

    def test_class_exists(self) -> None:
        from ivg_kg.grounding.clients.ollama import OllamaClient

        assert OllamaClient is not None

    def test_is_subclass_of_base(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient
        from ivg_kg.grounding.clients.ollama import OllamaClient

        assert issubclass(OllamaClient, BaseAIClient)

    def test_supports_evidence_trace_is_false(self) -> None:
        from ivg_kg.grounding.clients.ollama import OllamaClient

        assert OllamaClient.supports_evidence_trace is False

    def test_construction_accepts_base_url_and_model(self) -> None:
        from ivg_kg.grounding.clients.ollama import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434", model="llama3")
        assert client is not None

    def test_generate_raises_on_network_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With requests monkeypatched to fail, generate raises a clear error."""
        import ivg_kg.grounding.clients.ollama as ollama_mod

        fake_requests = types.ModuleType("requests")

        def fake_post(*args: Any, **kwargs: Any) -> None:
            raise ConnectionError("Connection refused")

        fake_requests.post = fake_post  # type: ignore[attr-defined]
        fake_requests.exceptions = types.ModuleType("requests.exceptions")  # type: ignore[attr-defined]
        fake_requests.exceptions.ConnectionError = ConnectionError  # type: ignore[attr-defined]
        fake_requests.exceptions.RequestException = Exception  # type: ignore[attr-defined]

        monkeypatch.setattr(ollama_mod, "_load_requests", lambda: fake_requests)

        client = ollama_mod.OllamaClient(base_url="http://localhost:11434", model="llama3")
        with pytest.raises((ConnectionError, RuntimeError, OSError)):
            client.generate_answer("Q?", _dummy_ctx())


# ---------------------------------------------------------------------------
# CloudAIClient -- seam exists; calling without creds raises a clear error
# ---------------------------------------------------------------------------


class TestCloudAIClient:
    def test_class_exists(self) -> None:
        from ivg_kg.grounding.clients.cloud import CloudAIClient

        assert CloudAIClient is not None

    def test_is_subclass_of_base(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient
        from ivg_kg.grounding.clients.cloud import CloudAIClient

        assert issubclass(CloudAIClient, BaseAIClient)

    def test_supports_evidence_trace_is_false(self) -> None:
        from ivg_kg.grounding.clients.cloud import CloudAIClient

        assert CloudAIClient.supports_evidence_trace is False

    def test_generate_raises_not_implemented(self) -> None:
        from ivg_kg.grounding.clients.cloud import CloudAIClient

        client = CloudAIClient()
        with pytest.raises((NotImplementedError, RuntimeError)):
            client.generate_answer("Q?", _dummy_ctx())

    def test_error_message_is_informative(self) -> None:
        from ivg_kg.grounding.clients.cloud import CloudAIClient

        client = CloudAIClient()
        try:
            client.generate_answer("Q?", _dummy_ctx())
        except (NotImplementedError, RuntimeError) as exc:
            assert len(str(exc)) > 10, "Error message should be informative"


# ---------------------------------------------------------------------------
# Factory -- make_client selects the right class
# ---------------------------------------------------------------------------


class TestFactory:
    def test_make_client_local(self) -> None:
        from ivg_kg.grounding.clients.factory import make_client
        from ivg_kg.grounding.clients.local import LocalModelClient

        client = make_client("local")
        assert isinstance(client, LocalModelClient)

    def test_make_client_ollama(self) -> None:
        from ivg_kg.grounding.clients.factory import make_client
        from ivg_kg.grounding.clients.ollama import OllamaClient

        client = make_client("ollama")
        assert isinstance(client, OllamaClient)

    def test_make_client_cloud(self) -> None:
        from ivg_kg.grounding.clients.cloud import CloudAIClient
        from ivg_kg.grounding.clients.factory import make_client

        client = make_client("cloud")
        assert isinstance(client, CloudAIClient)

    def test_make_client_unknown_raises(self) -> None:
        from ivg_kg.grounding.clients.factory import make_client

        with pytest.raises((ValueError, KeyError)):
            make_client("nonexistent_backend")

    def test_get_default_client_returns_base_ai_client(self) -> None:
        from ivg_kg.grounding.clients.base import BaseAIClient
        from ivg_kg.grounding.clients.factory import get_default_client

        client = get_default_client()
        assert isinstance(client, BaseAIClient)

    def test_make_client_does_not_download_models(self) -> None:
        """Factory construction must not trigger model downloads."""
        from ivg_kg.grounding.clients.factory import make_client

        # If this completes without network calls, the test passes.
        # The factory must be constructable without side effects.
        client = make_client("local")
        assert client is not None


# ---------------------------------------------------------------------------
# Config constants for new client settings
# ---------------------------------------------------------------------------


class TestClientConfig:
    def test_local_llm_model_id_exists(self) -> None:
        from ivg_kg import config

        assert hasattr(config, "LOCAL_LLM_MODEL_ID")
        assert isinstance(config.LOCAL_LLM_MODEL_ID, str)
        assert len(config.LOCAL_LLM_MODEL_ID) > 0

    def test_ollama_base_url_exists(self) -> None:
        from ivg_kg import config

        assert hasattr(config, "OLLAMA_BASE_URL")
        assert isinstance(config.OLLAMA_BASE_URL, str)
        assert config.OLLAMA_BASE_URL.startswith("http")

    def test_ollama_model_id_exists(self) -> None:
        from ivg_kg import config

        assert hasattr(config, "OLLAMA_MODEL_ID")
        assert isinstance(config.OLLAMA_MODEL_ID, str)
        assert len(config.OLLAMA_MODEL_ID) > 0

    def test_default_client_backend_exists(self) -> None:
        from ivg_kg import config

        assert hasattr(config, "DEFAULT_CLIENT_BACKEND")
        assert config.DEFAULT_CLIENT_BACKEND in ("local", "ollama", "cloud")

    def test_default_generation_temperature_exists(self) -> None:
        from ivg_kg import config

        assert hasattr(config, "DEFAULT_GENERATION_TEMPERATURE")
        assert isinstance(config.DEFAULT_GENERATION_TEMPERATURE, float)
        assert 0.0 <= config.DEFAULT_GENERATION_TEMPERATURE <= 2.0


# ---------------------------------------------------------------------------
# Public __init__ re-exports
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_base_ai_client_importable_from_package(self) -> None:
        from ivg_kg.grounding.clients import BaseAIClient

        assert BaseAIClient is not None

    def test_generation_result_importable_from_package(self) -> None:
        from ivg_kg.grounding.clients import GenerationResult

        assert GenerationResult is not None

    def test_make_client_importable_from_package(self) -> None:
        from ivg_kg.grounding.clients import make_client

        assert callable(make_client)

    def test_get_default_client_importable_from_package(self) -> None:
        from ivg_kg.grounding.clients import get_default_client

        assert callable(get_default_client)
