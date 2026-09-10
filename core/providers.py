"""Provider factory for the generic extractor.

Wraps langextract's provider infrastructure (OpenAI-compatible) so the
core never talks to an LLM API directly. Route names:
- "hermes-api"          -> Hermes API Server :8642 -> DeepSeek v4 Flash
- "openrouter-deepseek" -> OpenRouter -> deepseek/deepseek-v4-flash-0731
- "openrouter-gemma4"   -> OpenRouter -> google/gemma-4-31b-it (consenso B)
- {"model_id", "base_url", "api_key"} -> any OpenAI-compatible endpoint

⚠️ langextract's OpenAI client has NO timeout (verified) — a slow/infinite
LLM response hangs the request forever. Use `infer_with_timeout()` so web
requests degrade fast instead of hanging.
"""
import os
import json
import threading
from typing import Any, Optional

# langextract se instala con DOS layouts según la fuente:
#   - repo clonado / editable : namespace `langextract.langextract.*`
#   - pip de PyPI (>=1.5.0)   : plano `langextract.*`
# Import con fallback para que el código sea portable entre ambos.
try:  # namespace (repo)
    from langextract.langextract.providers import load_builtins_once, load_plugins_once
    from langextract.langextract.providers.openai import OpenAILanguageModel
except ImportError:  # plano (PyPI)
    from langextract.providers import load_builtins_once, load_plugins_once
    from langextract.providers.openai import OpenAILanguageModel

HERMES_API_URL = "http://127.0.0.1:8642/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEEPSEEK_DEFAULT = "deepseek/deepseek-v4-flash-0731"
GEMMA4_DEFAULT = "google/gemma-4-31b-it"
_HERMES_FALLBACK_KEY = "ht-jorge-a78e45a5aba14dc6"

# Timeout por defecto para llamadas LLM singulares (segundos).
DEFAULT_LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "90"))


class LLMTimeoutError(TimeoutError):
    """Llamada al LLM excedió el timeout."""


def run_with_timeout(fn, timeout: float = DEFAULT_LLM_TIMEOUT, *args, **kwargs):
    """Ejecuta fn(*args, **kwargs) en un hilo y corta si excede timeout."""
    result, exc = {}, {}

    def _run():
        try:
            result["v"] = fn(*args, **kwargs)
        except BaseException as e:  # noqa: BLE001
            exc["e"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise LLMTimeoutError(f"Llamada al LLM excede {timeout}s")
    if "e" in exc:
        raise exc["e"]
    return result.get("v")


def infer_with_timeout(model: OpenAILanguageModel, prompts: list[str],
                       timeout: float = DEFAULT_LLM_TIMEOUT):
    """model.infer(prompts) con timeout — degrada en vez de colgar.

    Materializa el resultado (generator -> list) DENTRO del hilo, para que
    el timeout corte también la iteración perezosa.
    """
    def _infer_all():
        out = model.infer(prompts)
        return list(out) if not isinstance(out, list) else out
    return run_with_timeout(_infer_all, timeout)


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


def get_openrouter_models() -> list[dict[str, Any]]:
    """Lista modelos OpenRouter con precios por 1M (prompt y completion separados).

    Cacheada 10 min. Se comparte entre /models y la estimación de coste
    de /extract (no duplica llamadas a OpenRouter). Modelos con precios
    negativos (sin publicar) se filtran.
    """
    import time as _t
    now = _t.time()
    cached = getattr(get_openrouter_models, "_cache", None)
    if cached and now - getattr(get_openrouter_models, "_ts", 0) < 600:
        return list(cached)

    import urllib.request
    key = get_openrouter_key()
    req = urllib.request.Request(f"{OPENROUTER_URL}/models",
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode()).get("data", [])
    out = []
    for m in data:
        pr = m.get("pricing", {})
        prompt = float(pr.get("prompt") or 0)      # USD por token
        comp = float(pr.get("completion") or 0)    # USD por token
        if prompt < 0 or comp < 0:
            continue  # sin precio publicado
        coste_1m = round((prompt + comp) * 1_000_000, 6)
        out.append({
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "coste_1m_usd": coste_1m,
            "prompt_1m_usd": round(prompt * 1_000_000, 6),
            "completion_1m_usd": round(comp * 1_000_000, 6),
        })
    out.sort(key=lambda x: (x["coste_1m_usd"], x["id"]))
    get_openrouter_models._cache = out
    get_openrouter_models._ts = now
    return out


def estimate_extract_cost(
    model_id: str,
    prompt_chars: int,
    expected_output_chars: int,
    n_calls: int = 1,
    models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Estimación de coste de una extracción (USD) para un modelo OpenRouter.

    Regla ~4 chars/token (prompt y completion) — aproximación estándar.
    Devuelve desglose: tokens estimados y coste por componente. Si el
    modelo no está en la lista, coste=None (no publica precio).
    """
    models = models if models is not None else get_openrouter_models()
    meta = next((m for m in models if m["id"] == model_id), None)
    if not meta:
        return {"model_id": model_id, "estimado": False,
                "prompt_tokens": None, "completion_tokens": None,
                "coste_estimado_usd": None,
                "nota": "Modelo sin precio publicado en OpenRouter"}
    prompt_tokens = max(1, prompt_chars // 4)
    comp_tokens = max(1, expected_output_chars // 4)
    coste = (
        prompt_tokens / 1_000_000 * meta["prompt_1m_usd"]
        + comp_tokens / 1_000_000 * meta["completion_1m_usd"]
    ) * n_calls
    return {
        "model_id": model_id,
        "estimado": True,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": comp_tokens,
        "coste_estimado_usd": round(coste, 8),
        "por_llamada": n_calls,
    }


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
    if isinstance(spec, str) and spec.startswith("openrouter-model:"):
        # Modelo arbitrario de OpenRouter por id completo (p.ej. "openrouter-model:deepseek/deepseek-v4.1-flash")
        model_id = spec[len("openrouter-model:"):]
        return _make_openai(model_id, OPENROUTER_URL, get_openrouter_key(), temperature)
    raise ValueError(f"Provider desconocido: {spec!r}. Usa 'hermes-api', 'openrouter-gemma4' o dict.")