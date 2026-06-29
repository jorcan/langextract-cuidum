"""
DeepSeek Language Model Provider for LangExtract.

Extends the OpenAI provider with DeepSeek-specific defaults
(base URL, API key env var, model patterns).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from langextract.core import exceptions
from langextract.providers import router
from langextract.providers.openai import OpenAILanguageModel


# Register for any model starting with "deepseek"
# Priority 20 beats Ollama's 10 so deepseek models route here, not to Ollama
@router.register(r"^deepseek", priority=20)
@dataclasses.dataclass(init=False)
class DeepSeekLanguageModel(OpenAILanguageModel):
    """Language model using DeepSeek's OpenAI-compatible API.

    Uses the same infrastructure as OpenAILanguageModel but defaults to
    DeepSeek's API endpoint and API key environment variable.
    """

    model_id: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    api_key: str | None = None

    def __init__(
        self,
        model_id: str = "deepseek-chat",
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        **kwargs: Any,
    ) -> None:
        """Initialize DeepSeek language model.

        Args:
            model_id: DeepSeek model (deepseek-chat, deepseek-reasoner).
            api_key: DeepSeek API key. Falls back to DEEPSEEK_API_KEY env var.
            base_url: DeepSeek API base URL.
            **kwargs: Additional OpenAILanguageModel parameters.
        """
        # Resolve API key from env if not provided
        import os
        if api_key is None:
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")

        if not api_key:
            raise exceptions.InferenceConfigError(
                "DeepSeek API key not found. Set DEEPSEEK_API_KEY environment "
                "variable or pass api_key directly."
            )

        # Delegate to OpenAI parent with DeepSeek defaults
        super().__init__(
            model_id=model_id,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )
