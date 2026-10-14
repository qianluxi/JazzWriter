"""OpenAI-compatible provider.

Works with OpenAI, DeepSeek, Qwen (DashScope compatible mode), local vLLM /
Ollama OpenAI endpoints — anything exposing /v1/chat/completions.

Configuration (env vars):
  OPENAI_API_KEY        required (or NJE_API_KEY)
  OPENAI_BASE_URL       optional (or NJE_BASE_URL), e.g. https://api.deepseek.com/v1
  NJE_MODEL             optional, default "gpt-4o-mini"
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from llm.base import LLMError, LLMProvider

DEFAULT_SYSTEM = (
    "你是一位克制、精确的文学写作者，擅长通过细节、留白和意象表达主题。"
    "你从不直接解释主题，从不使用陈词滥调。"
)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model or os.getenv("NJE_MODEL") or "gpt-4o-mini"
        self.base_url = base_url or os.getenv("NJE_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        self.api_key = api_key or os.getenv("NJE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise LLMError(
                "no API key found; set OPENAI_API_KEY (or NJE_API_KEY), "
                "or run with provider 'mock'"
            )
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMError(
                "the 'openai' package is not installed. "
                "`pip install openai` or use provider 'mock'."
            ) from exc
        kwargs: Dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.9,
        max_tokens: int = 1500,
    ) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system or DEFAULT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content or ""
