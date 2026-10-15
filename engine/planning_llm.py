"""Optional LLM helper for structure planning.

Structure planning can use a real model (great with opencode) or fall back to
deterministic generators. This helper asks the model for **JSON only** and
validates the parse; any failure returns ``None`` so the caller can fall back.
The offline ``mock`` provider never produces planning JSON (deterministic path).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

JSON_SYSTEM = (
    "你是长篇小说结构策划。只输出一个合法的 JSON 对象，不要任何解释文字、"
    "不要 Markdown 代码块。字段与结构严格遵循用户要求。"
)


def _extract_json(text: str) -> Optional[Any]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def generate_json(
    llm,
    prompt: str,
    *,
    system: Optional[str] = None,
    retries: int = 1,
    max_tokens: int = 4000,
) -> Optional[Dict[str, Any]]:
    if llm is None or getattr(llm, "name", "") in ("mock", ""):
        return None
    for _ in range(retries + 1):
        try:
            text = llm.generate(
                prompt, system=system or JSON_SYSTEM, temperature=0.7, max_tokens=max_tokens
            )
        except Exception:  # noqa: BLE001 - planning must degrade gracefully
            return None
        data = _extract_json(text)
        if isinstance(data, dict):
            return data
    return None
