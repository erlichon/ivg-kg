"""
TDD tests for GEN-CFG: generator = Qwen2.5 via Ollama + loud-fail seam + dropdown label.

Tests written FIRST (red), then implementation follows.
All tests run offline: no real Ollama server, no real network.
"""
from __future__ import annotations

import types
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_ctx() -> Any:
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


def _make_fake_requests(
    *,
    connection_error: bool = False,
    timeout_error: bool = False,
    status_code: int = 200,
    json_body: dict | None = None,
) -> types.ModuleType:
    """Build a fake requests module for monkeypatching _load_requests."""

    # Build a minimal exceptions sub-namespace.
    exc_ns = types.ModuleType("requests.exceptions")

    class _ConnectionError(OSError):
        pass

    class _TimeoutError(OSError):
        pass

    class _HTTPError(OSError):
        pass

    exc_ns.ConnectionError = _ConnectionError  # type: ignore[attr-defined]
    exc_ns.Timeout = _TimeoutError  # type: ignore[attr-defined]
    exc_ns.HTTPError = _HTTPError  # type: ignore[attr-defined]
    exc_ns.RequestException = OSError  # type: ignore[attr-defined]

    fake_mod = types.ModuleType("requests")
    fake_mod.exceptions = exc_ns  # type: ignore[attr-defined]

    if connection_error:
        def fake_post(*args: Any, **kwargs: Any) -> None:
            raise exc_ns.ConnectionError("Connection refused")

        fake_mod.post = fake_post  # type: ignore[attr-defined]
        return fake_mod

    if timeout_error:
        def fake_post_timeout(*args: Any, **kwargs: Any) -> None:
            raise exc_ns.Timeout("Read timed out")

        fake_mod.post = fake_post_timeout  # type: ignore[attr-defined]
        return fake_mod

    # Otherwise return an HTTP response stub.
    class _FakeResponse:
        def __init__(self) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise exc_ns.HTTPError(
                    "404 Client Error: Not Found for model"
                )

        def json(self) -> dict:
            return json_body or {}

    def fake_post_ok(*args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse()

    fake_mod.post = fake_post_ok  # type: ignore[attr-defined]
    return fake_mod


# ---------------------------------------------------------------------------
# 1. Config values: DEFAULT_CLIENT_BACKEND and OLLAMA_MODEL_ID
# ---------------------------------------------------------------------------


class TestConfigGeneratorValues:
    def test_default_client_backend_is_ollama(self) -> None:
        from ivg_kg import config

        assert config.DEFAULT_CLIENT_BACKEND == "ollama", (
            f"Expected 'ollama', got {config.DEFAULT_CLIENT_BACKEND!r}"
        )

    def test_ollama_model_id_is_qwen25(self) -> None:
        from ivg_kg import config

        assert config.OLLAMA_MODEL_ID == "qwen2.5", (
            f"Expected 'qwen2.5', got {config.OLLAMA_MODEL_ID!r}"
        )

    def test_local_llm_model_id_unchanged(self) -> None:
        """LOCAL_LLM_MODEL_ID must NOT be changed (Invariant #14 generator vs verifier)."""
        from ivg_kg import config

        # Still refers to Llama family; we only check it is non-empty and unchanged.
        assert isinstance(config.LOCAL_LLM_MODEL_ID, str)
        assert len(config.LOCAL_LLM_MODEL_ID) > 0

    def test_verifier_model_ids_unchanged(self) -> None:
        """Verifier model IDs must remain untouched (Invariant #14)."""
        from ivg_kg import config

        assert "MiniCheck" in config.MINICHECK_MODEL_ID or "minicheck" in config.MINICHECK_MODEL_ID.lower()
        assert "DeBERTa" in config.DEBERTA_NLI_MODEL_ID or "deberta" in config.DEBERTA_NLI_MODEL_ID.lower()

    def test_vlm_model_id_unchanged(self) -> None:
        """VLM_MODEL_ID must remain untouched (Invariant #7/23)."""
        from ivg_kg import config

        assert isinstance(config.VLM_MODEL_ID, str)
        assert len(config.VLM_MODEL_ID) > 0


# ---------------------------------------------------------------------------
# 2. Factory: make_client() with no arg returns OllamaClient
# ---------------------------------------------------------------------------


class TestFactoryDefaultIsOllama:
    def test_make_client_no_arg_returns_ollama_client(self) -> None:
        from ivg_kg.grounding.clients.factory import make_client
        from ivg_kg.grounding.clients.ollama import OllamaClient

        client = make_client()
        assert isinstance(client, OllamaClient), (
            f"Expected OllamaClient when DEFAULT_CLIENT_BACKEND='ollama', got {type(client)}"
        )

    def test_make_client_none_returns_ollama_client(self) -> None:
        from ivg_kg.grounding.clients.factory import make_client
        from ivg_kg.grounding.clients.ollama import OllamaClient

        client = make_client(None)
        assert isinstance(client, OllamaClient)


# ---------------------------------------------------------------------------
# 3. OllamaClient: loud-fail modes (offline, monkeypatched)
# ---------------------------------------------------------------------------


class TestOllamaLoudFail:
    """All tests monkeypatch _load_requests -- no real network."""

    def _client(self) -> Any:
        from ivg_kg.grounding.clients.ollama import OllamaClient

        return OllamaClient(base_url="http://localhost:11434", model="qwen2.5")

    # 3a. Connection error -> message contains 'ollama serve' and the base_url
    def test_connection_error_mentions_ollama_serve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ivg_kg.grounding.clients.ollama as ollama_mod

        fake_reqs = _make_fake_requests(connection_error=True)
        monkeypatch.setattr(ollama_mod, "_load_requests", lambda: fake_reqs)

        client = self._client()
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_answer("Q?", _dummy_ctx())

        msg = str(exc_info.value)
        assert "ollama serve" in msg, f"Expected 'ollama serve' in error, got: {msg!r}"
        assert "localhost:11434" in msg or "11434" in msg, (
            f"Expected base_url in error, got: {msg!r}"
        )

    # 3b. Timeout -> also treated as server unreachable, same message
    def test_timeout_error_mentions_ollama_serve(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ivg_kg.grounding.clients.ollama as ollama_mod

        fake_reqs = _make_fake_requests(timeout_error=True)
        monkeypatch.setattr(ollama_mod, "_load_requests", lambda: fake_reqs)

        client = self._client()
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_answer("Q?", _dummy_ctx())

        msg = str(exc_info.value)
        assert "ollama serve" in msg, f"Expected 'ollama serve' in error, got: {msg!r}"

    # 3c. HTTP 404 (model not pulled) -> message contains exact 'ollama pull qwen2.5'
    def test_404_response_mentions_ollama_pull(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ivg_kg.grounding.clients.ollama as ollama_mod

        fake_reqs = _make_fake_requests(status_code=404)
        monkeypatch.setattr(ollama_mod, "_load_requests", lambda: fake_reqs)

        client = self._client()
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_answer("Q?", _dummy_ctx())

        msg = str(exc_info.value)
        assert "ollama pull qwen2.5" in msg, (
            f"Expected 'ollama pull qwen2.5' in error, got: {msg!r}"
        )

    # 3d. HTTP ok but empty 'response' key -> RuntimeError, not silent empty answer
    def test_empty_response_body_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ivg_kg.grounding.clients.ollama as ollama_mod

        fake_reqs = _make_fake_requests(status_code=200, json_body={"response": ""})
        monkeypatch.setattr(ollama_mod, "_load_requests", lambda: fake_reqs)

        client = self._client()
        with pytest.raises(RuntimeError) as exc_info:
            client.generate_answer("Q?", _dummy_ctx())

        # Must NOT silently return an empty string
        msg = str(exc_info.value)
        assert len(msg) > 0, "RuntimeError must have a non-empty message"

    # 3e. HTTP ok with missing 'response' key -> also RuntimeError
    def test_missing_response_key_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ivg_kg.grounding.clients.ollama as ollama_mod

        fake_reqs = _make_fake_requests(status_code=200, json_body={})
        monkeypatch.setattr(ollama_mod, "_load_requests", lambda: fake_reqs)

        client = self._client()
        with pytest.raises(RuntimeError):
            client.generate_answer("Q?", _dummy_ctx())

    # 3f. Successful response (non-empty) -> works fine, no error
    def test_valid_response_returns_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ivg_kg.grounding.clients.ollama as ollama_mod

        fake_reqs = _make_fake_requests(
            status_code=200,
            json_body={"response": "Douglas Adams wrote it."},
        )
        monkeypatch.setattr(ollama_mod, "_load_requests", lambda: fake_reqs)

        client = self._client()
        answer = client.generate_answer("Q?", _dummy_ctx())
        assert answer == "Douglas Adams wrote it."


# ---------------------------------------------------------------------------
# 4. Layout: gen-model dropdown first option is Qwen2.5 / ollama default
# ---------------------------------------------------------------------------


def _find_all(component: Any, pred: Any) -> list:
    """Recursively collect components matching pred."""
    found = []
    if pred(component):
        found.append(component)
    children = getattr(component, "children", None)
    if children is None:
        return found
    if not isinstance(children, (list, tuple)):
        children = [children]
    for ch in children:
        found.extend(_find_all(ch, pred))
    return found


class TestLayoutDropdown:
    def _get_gen_model_dropdown(self) -> Any:
        from app.layout import get_layout

        layout = get_layout()
        dropdowns = _find_all(
            layout,
            lambda c: getattr(c, "id", None) == "gen-model",
        )
        assert dropdowns, "layout must contain a component with id='gen-model'"
        return dropdowns[0]

    def test_gen_model_dropdown_default_is_ollama(self) -> None:
        dd = self._get_gen_model_dropdown()
        assert dd.value == "ollama", (
            f"Expected default value 'ollama', got {dd.value!r}"
        )

    def test_gen_model_first_option_label_mentions_qwen25(self) -> None:
        dd = self._get_gen_model_dropdown()
        first_label = dd.options[0]["label"]
        assert "Qwen2.5" in first_label or "qwen2.5" in first_label.lower(), (
            f"First option label should mention Qwen2.5, got {first_label!r}"
        )

    def test_gen_model_first_option_value_is_ollama(self) -> None:
        dd = self._get_gen_model_dropdown()
        assert dd.options[0]["value"] == "ollama", (
            f"First option value should be 'ollama', got {dd.options[0]['value']!r}"
        )

    def test_gen_model_cloud_option_still_present(self) -> None:
        dd = self._get_gen_model_dropdown()
        values = [opt["value"] for opt in dd.options]
        assert "cloud" in values, f"Cloud option must still be present, got {values}"
