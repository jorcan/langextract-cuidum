"""Provider factory for the generic extractor.

Wraps langextract's provider infrastructure (OpenAI-compatible) so the
core never talks to an LLM API directly. Route names:
- "hermes-api"          -> Hermes API Server :8642 -> DeepSeek v4 Flash
- "openrouter-gemma4"   -> OpenRouter -> google/gemma-4-31b-it (consenso B)
- {"model_id", "base_url", "api_key"} -> any OpenAI-compatible endpoint
"""
import os
from typing import Any, Optional

from langextract.langextract.providers import load_builtins_once, load_plugins_once
from langextract.langextract.providers.openai import OpenAILanguageModel

HERMES_API_URL = "http://127.0.0.1:8642/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEEPSEEK_DEFAULT = "deepseek/deepseek-v4-flash-0731"
GEMMA4_DEFAULT = "google/gemma-4-31b-it"
_HERMES_FALLBACK_KEY = "ht-jorge-a78e45a5aba14dc6"


def _read_key(env_var: str, config_key: str, fallback: str = "") -> str:
    """Key from env, then ~/.hermes/credentials.env (skipping redacted '***')."""
    key = os.environ.get(env_var, "")
    if key and "***" not in key:
        return key
    try:
        with open(os.path.expanduser("~/.hermes/credentials.env")) as f:
            for line in f:
                if f"{config_key}=" in line and "***" not in line:
                    parts = line.split("=", 1)
                    return parts[1].strip().strip("\"'")
    except Exception:
        pass
    return fallback


def get_hermes_api_key() -> str:
    return _read_key("API_SERVER_KEY", "API_SERVER_KEY", _HERMES_FALLBACK_KEY)


def get_openrouter_key() -> str:
    return _read_key("OPENROUTER_API_KEY", "OPENROUTER_API_KEY")


def _make_openai(model_id: str, base_url: str, api_key: str, temperature: float) -> OpenAILanguageModel:
    load_builtins_once()
    load_plugins_once()
    return OpenAILanguageModel(
        model_id=model_id,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_workers=1,
    )


def make_provider(spec: Any, temperature: float = 0.05) -> OpenAILanguageModel:
    """Factory: name string or dict -> OpenAILanguageModel instance."""
    if isinstance(spec, dict):
        return _make_openai(
            model_id=spec["model_id"],
            base_url=spec["base_url"],
            api_key=spec.get("api_key", ""),
            temperature=spec.get("temperature", temperature),
        )

    if spec == "hermes-api":
        return _make_openai("gpt-4o-mini", HERMES_API_URL, get_hermes_api_key(), temperature)
    if spec == "openrouter-deepseek":
        return _make_openai(DEEPSEEK_DEFAULT, OPENROUTER_URL, get_openrouter_key(), temperature)
    if spec == "openrouter-gemma4":
        return _make_openai(GEMMA4_DEFAULT, OPENROUTER_URL, get_openrouter_key(), temperature)
    raise ValueError(f"Provider desconocido: {spec!r}. Usa 'hermes-api', 'openrouter-gemma4' o dict.")