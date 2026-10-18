"""OpenCode provider — drive a local opencode server as the LLM backend.

Instead of holding its own API key, this provider talks to an opencode server
(``opencode serve``) over HTTP and asks it to run a prompt with whichever model
opencode is already connected to (OpenCode Zen / Go, Anthropic, DeepSeek, ...).

Uses only the standard library (urllib), so no extra dependency is required.

Configuration (env vars):
  NJE_OPENCODE_URL       server base URL        (default http://127.0.0.1:4096)
  NJE_OPENCODE_MODEL     "provider/model"       (default an OpenCode Go model)
  OPENCODE_SERVER_PASSWORD / OPENCODE_SERVER_USERNAME  (optional basic auth)

Start the server first::

    opencode serve --port 4096
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from llm.base import LLMError, LLMProvider
from llm.defaults import DEFAULT_OPENCODE_MODEL

DEFAULT_SYSTEM = (
    "你是一位克制、精确的文学写作者，擅长通过细节、留白和意象表达主题。"
    "你从不直接解释主题，从不使用陈词滥调。"
)


class OpenCodeProvider(LLMProvider):
    name = "opencode"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        password: Optional[str] = None,
        username: Optional[str] = None,
        timeout: float = 600.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("NJE_OPENCODE_URL")
                         or "http://127.0.0.1:4096").rstrip("/")
        self.model = model or os.getenv("NJE_OPENCODE_MODEL") or DEFAULT_OPENCODE_MODEL
        self.password = password or os.getenv("OPENCODE_SERVER_PASSWORD")
        self.username = username or os.getenv("OPENCODE_SERVER_USERNAME") or "opencode"
        self.timeout = timeout
        self._session_id: Optional[str] = None

    # -- HTTP helpers -------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = "Basic " + token
        return headers

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        url = self.base_url + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise LLMError(f"opencode server {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(
                f"无法连接 opencode server ({self.base_url})：{exc.reason}。"
                "请先运行 `opencode serve --port 4096`。"
            ) from exc

    def _ensure_session(self) -> str:
        if self._session_id:
            return self._session_id
        created = self._request("POST", "/session", {"title": "JazzWriter"})
        session_id = (created or {}).get("id")
        if not session_id:
            raise LLMError("opencode server 未返回 session id")
        self._session_id = session_id
        return session_id

    @staticmethod
    def _model_ref(model: str) -> Dict[str, str]:
        if "/" not in model:
            raise LLMError('NJE_OPENCODE_MODEL 需为 "provider/model" 形式，例如 "opencode/zen"')
        provider_id, model_id = model.split("/", 1)
        return {"providerID": provider_id, "modelID": model_id}

    # -- LLMProvider --------------------------------------------------------
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.9,
        max_tokens: int = 1500,
    ) -> str:
        session_id = self._ensure_session()
        body: Dict[str, Any] = {
            "system": system or DEFAULT_SYSTEM,
            "parts": [{"type": "text", "text": prompt}],
        }
        if self.model:
            body["model"] = self._model_ref(self.model)
        data = self._request("POST", f"/session/{session_id}/message", body)
        text = self._extract_text(data)
        if not text:
            error = self._extract_error(data)
            raise LLMError(error or "opencode 返回内容为空（检查 model 是否已连接/可用）")
        return text

    @staticmethod
    def _extract_error(data: Any) -> str:
        """Surface an upstream error instead of a bare 'empty response'."""
        if not isinstance(data, dict):
            return ""
        info = data.get("info") if isinstance(data.get("info"), dict) else data
        error = info.get("error") if isinstance(info, dict) else None
        if not isinstance(error, dict):
            return ""
        payload = error.get("data") if isinstance(error.get("data"), dict) else error
        message = str(payload.get("message") or error.get("message") or "").strip()
        if not message:
            return ""
        code = payload.get("code") or ""
        if not code and isinstance(payload.get("responseBody"), str):
            found = re.search(r'"code"\s*:\s*"([^"]+)"', payload["responseBody"])
            code = found.group(1) if found else ""
        code = code or error.get("name") or ""
        return f"opencode 上游错误{f'（{code}）' if code else ''}：{message}"

    @staticmethod
    def _extract_text(data: Any) -> str:
        if not isinstance(data, dict):
            return ""
        parts: List[dict] = data.get("parts") or []
        if not parts and isinstance(data.get("info"), dict):
            parts = data["info"].get("parts") or []
        chunks = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "".join(chunks).strip()
