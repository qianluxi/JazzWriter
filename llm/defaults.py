"""Shared application defaults.

`opencode` is the first choice (it reuses the model you already signed in to,
including an OpenCode Go subscription); `mock` stays available as an offline
fallback. Evaluation defaults to local `embedding` similarity.
"""

from __future__ import annotations

DEFAULT_PROVIDER = "opencode"
DEFAULT_EVAL_MODE = "embedding"
DEFAULT_OPENCODE_MODEL = "opencode-go/deepseek-v4.1-flash"
