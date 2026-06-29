"""Configuration management for LangExtract-Cuidum pipeline."""

import os
import yaml
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


class Config:
    """Loads and holds pipeline configuration."""

    def __init__(self, path: str | Path | None = None):
        path = Path(path or DEFAULT_CONFIG_PATH)
        with open(path) as f:
            raw = yaml.safe_load(f)

        # LLM
        llm = raw.get("llm", {})
        self.llm_provider = llm.get("provider", "deepseek")
        self.llm_model = llm.get("model", "deepseek-chat")
        self.llm_temperature = llm.get("temperature", 0.1)
        self.llm_max_tokens = llm.get("max_tokens", 4096)

        # DeepSeek
        ds = raw.get("deepseek", {})
        self.deepseek_api_key_env = ds.get("api_key_env", "DEEPSEEK_API_KEY")
        self.deepseek_base_url = ds.get("base_url", "https://api.deepseek.com")

        # Pipeline
        pipe = raw.get("pipeline", {})
        self.batch_size = pipe.get("batch_size", 50)
        self.max_workers = pipe.get("max_workers", 5)
        self.max_char_buffer = pipe.get("max_char_buffer", 3000)
        self.deduplicate = pipe.get("deduplicate", True)
        self.skip_empty_descriptions = pipe.get("skip_empty_descriptions", True)

        # Schema
        self.schema_version = raw.get("schema_version", "1.0.0")

        # Resolve API key
        self.deepseek_api_key = os.environ.get(self.deepseek_api_key_env, "")

    @property
    def deepseek_api_available(self) -> bool:
        return bool(self.deepseek_api_key)
