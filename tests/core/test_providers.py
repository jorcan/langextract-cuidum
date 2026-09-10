"""Tests for core.providers — provider factory (no network)."""
import pytest

import core.providers as providers
from core.providers import make_provider


class DummyModel:
    captured = {}

    def __init__(self, **kwargs):
        type(self).captured = kwargs


@pytest.fixture(autouse=True)
def _patch_openai(monkeypatch):
    monkeypatch.setattr(providers, "OpenAILanguageModel", DummyModel)
    monkeypatch.setenv("API_SERVER_KEY", "test-hermes-key")
    yield
    DummyModel.captured = {}


class TestMakeProvider:
    def test_hermes_api_default(self):
        p = make_provider("hermes-api")
        c = DummyModel.captured
        assert c["base_url"] == "http://127.0.0.1:8642/v1"
        assert c["model_id"].startswith("gpt-4o")
        assert c["api_key"] == "test-hermes-key"
        assert p is not None

    def test_hermes_api_key_from_credentials_fallback(self, monkeypatch):
        monkeypatch.delenv("API_SERVER_KEY", raising=False)
        # Escribimos un credentials.env fake en un tmp (o dejamos el fallback hardcodeado)
        p = make_provider("hermes-api")
        assert p is not None
        key = DummyModel.captured["api_key"]
        assert isinstance(key, str) and len(key) > 0 and "***" not in key

    def test_openrouter_gemma4(self):
        p = make_provider("openrouter-gemma4")
        c = DummyModel.captured
        assert c["base_url"] == "https://openrouter.ai/api/v1"
        assert "gemma" in c["model_id"]
        assert c["api_key"]

    def test_custom_dict(self):
        p = make_provider({"model_id": "mi-modelo", "base_url": "http://x:1/v1", "api_key": "k"})
        c = DummyModel.captured
        assert c["model_id"] == "mi-modelo"
        assert c["base_url"] == "http://x:1/v1"
        assert c["api_key"] == "k"
        assert p is not None

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            make_provider("no-existe")

    def test_temperature_passthrough(self):
        make_provider("hermes-api", temperature=0.0)
        assert DummyModel.captured["temperature"] == 0.0


class TestInferWithTimeout:
    def test_generator_materialized(self):
        """infer_with_timeout debe devolver lista (no generator) y consumir el generador."""
        class GenProvider:
            def infer(self, prompts):
                yield type("O", (), {"output": "x"})()

        from core.providers import infer_with_timeout
        out = infer_with_timeout(GenProvider(), ["p"], timeout=5)
        assert isinstance(out, list) and len(out) == 1

    def test_timeout_raises(self):
        import time

        class SlowProvider:
            def infer(self, prompts):
                time.sleep(10)
                return []

        from core.providers import infer_with_timeout, LLMTimeoutError
        t0 = time.time()
        try:
            infer_with_timeout(SlowProvider(), ["p"], timeout=1)
            raise AssertionError("debió lanzar LLMTimeoutError")
        except LLMTimeoutError:
            assert time.time() - t0 < 3, "timeout no respetado"

    def test_error_propagates(self):
        class ErrProvider:
            def infer(self, prompts):
                raise RuntimeError("boom")
        from core.providers import infer_with_timeout
        try:
            infer_with_timeout(ErrProvider(), ["p"], timeout=5)
            raise AssertionError("debió propagar RuntimeError")
        except RuntimeError:
            pass