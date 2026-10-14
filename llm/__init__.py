"""LLM backends. Any provider exposing `generate(prompt, context=...)` works."""

from __future__ import annotations

import os
from typing import Optional

from llm.base import LLMProvider, LLMError
from llm.mock import MockProvider

__all__ = ["LLMProvider", "LLMError", "MockProvider", "get_provider"]


def get_provider(name: Optional[str] = None, **kwargs) -> LLMProvider:
    """Resolve a provider by name.

    ``name`` falls back to the ``NJE_PROVIDER`` env var, then to "mock".
    Names: mock | openai (any OpenAI-compatible endpoint via base_url).
    """
    resolved = (name or os.getenv("NJE_PROVIDER") or "mock").lower()

    if resolved in ("mock", "offline", "stub"):
        return MockProvider(**kwargs)
    if resolved in ("openai", "oai", "compatible", "deepseek", "qwen"):
        from llm.openai_provider import OpenAIProvider

        return OpenAIProvider(**kwargs)
    raise LLMError(f"unknown provider: {resolved!r} (use 'mock' or 'openai')")
