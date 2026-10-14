"""Provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.9,
        max_tokens: int = 1500,
    ) -> str:
        """Return generated text.

        ``context`` carries the structured scene/persona data so that offline
        or test providers can produce meaningful output without parsing the
        prompt. Real providers may ignore it.
        """
        raise NotImplementedError
