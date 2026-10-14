"""Offline provider — lets the whole system run with no network / no API key.

It does not pretend to be a novelist. It composes constraint-respecting prose
from the structured context so that the *pipeline* (prompt → take → evaluation
→ motif tracking) can be exercised and tested end-to-end.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Optional

from llm.base import LLMProvider

_OPENERS = [
    "{symbol}先来的，还是声音先来的，{pov}没有分清。",
    "{pov}站了很久，直到{symbol}把空气分成两半。",
    "{pov}来的时候，{symbol}已经在等他了。",
    "事后回想，{pov}记得的只有{symbol}。",
]
_MIDDLES = [
    "{pov}想到了{memory}，但他没有让这个念头继续。",
    "他相信{worldview}，这份相信此刻成了一种负担。",
    "他想要的其实很简单：{desire}。可他害怕的也一样简单：{fear}。",
    "他知道自己正在伪装，伪装成那个{worldview}的人。",
]
_CLOSERS = [
    "{symbol}还在那里。它什么都没解释。",
    "他没有伸手。{symbol}替他沉默。",
    "很久以后他才明白，那一刻他选择了{contradiction}。",
]
_EMOTION_LINES = [
    "{emotion}像一层薄霜，落在{scene_short}的每个角落。",
    "{pov}说不出那是不是{emotion}，但{symbol}替他说了。",
    "那一刻的{emotion}很轻，轻得几乎不像真的。",
]


class MockProvider(LLMProvider):
    name = "mock"

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.9,
        max_tokens: int = 1500,
    ) -> str:
        ctx = context or {}
        seed_src = f"{prompt}|{ctx.get('chapter')}|{ctx.get('style')}"
        seed = int(hashlib.md5(seed_src.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        theme = ctx.get("theme", {}) or {}
        character = ctx.get("character", {}) or {}
        symbols: List[str] = list(theme.get("symbols") or []) or ["光"]
        emotions: List[str] = list(theme.get("emotions") or []) or ["沉默"]
        motifs: List[str] = list(ctx.get("active_motifs") or theme.get("motifs") or []) or symbols

        pov = ctx.get("pov") or character.get("name") or "他"
        scene = (ctx.get("scene") or "").strip()
        scene_short = self._first_clause(scene) or "这一晚"
        point = ctx.get("point") or rng.choice(emotions)

        fields = {
            "pov": pov,
            "symbol": rng.choice(symbols + motifs),
            "symbol2": rng.choice(symbols + motifs),
            "emotion": point,
            "scene_short": scene_short,
            "desire": character.get("desire") or "把事情弄清楚",
            "fear": character.get("fear") or "真相里有他自己",
            "memory": character.get("memory") or "很久以前的一个下午",
            "worldview": character.get("worldview") or "事情总有解释",
            "contradiction": character.get("contradiction") or "沉默",
        }

        middle_a, middle_b = rng.sample(_MIDDLES, 2)
        paragraphs = [
            self._render(rng.choice(_OPENERS), fields),
            self._render(middle_a, fields) + " " + self._render(middle_b, fields),
            self._render(rng.choice(_OPENERS), fields)
            + " "
            + self._render(rng.choice(_CLOSERS), fields),
        ]

        if scene:
            scene_sentence = scene if scene.endswith(("。", ".", "！", "？")) else scene + "。"
            paragraphs.insert(1, scene_sentence)
        paragraphs.append(self._render(rng.choice(_EMOTION_LINES), fields))
        if rng.random() < 0.5:
            paragraphs.append(
                f"他想起{motifs[0]}。它今天的意思，和昨天不太一样。"
            )

        text = "\n\n".join(p.strip() for p in paragraphs if p.strip())
        limit = max(280, max_tokens)
        return text[:limit]

    @staticmethod
    def _render(template: str, fields: Dict[str, str]) -> str:
        return template.format(**fields)

    @staticmethod
    def _first_clause(scene: str) -> str:
        for sep in ("。", "，", "\n", "；", ".", ","):
            if sep in scene:
                return scene.split(sep)[0].strip()
        return scene.strip()
