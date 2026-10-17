"""Project management — turn a free-form brief into a new novel project.

A "project" is a directory under ``projects/`` holding its own score:
``story.yaml`` (theme + world), ``characters.yaml``, ``relationships.yaml``,
``motifs.yaml``, ``story_state.yaml`` and the original ``brief.md``.

With a model, the brief is expanded into a coherent cast/relationships/motifs.
Offline it produces a valid, editable starter set (clearly generic) so the flow
never blocks.
"""

from __future__ import annotations

import datetime as _dt
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from engine.planning_llm import generate_json

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = ROOT / "projects"

SYMBOL_POOL = ["雾", "雪", "河", "灯", "门", "铁", "火", "钟", "雨", "信", "镜",
               "机器", "车站", "海", "森林", "风", "石", "灰", "蒸汽", "船",
               "狗", "井", "酒", "药", "枪", "旗", "旧照片", "账簿"]
EMOTION_POOL = ["孤独", "怀疑", "希望", "恐惧", "温柔", "愤怒", "释然", "荒诞"]

DEFAULT_JAZZ = {
    "mode": "classic_jazz", "creativity": 0.4, "randomness": 0.3,
    "motif_reuse": 0.85, "character_freedom": 0.6, "surprise_level": 0.4,
    "style_distance": 0.3, "idea_divergence": 0.5, "causal_variation": 0.4,
    "character_agency": 0.65, "motif_transformation": 0.7,
    "revelation_delay": 0.55, "branch_count": 3, "continuity_strength": 0.8,
}


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (name or "").strip())
    s = s.strip("-")[:40]
    return s or "project"


def _sentences(brief: str) -> List[str]:
    parts = re.split(r"[。！？!?\n]+", brief or "")
    return [p.strip() for p in parts if p.strip()]


def _symbols(brief: str) -> List[str]:
    found = [s for s in SYMBOL_POOL if s in brief]
    if len(found) < 2:
        for s in ("光", "影子", "门"):
            if s not in found:
                found.append(s)
            if len(found) >= 3:
                break
    return list(dict.fromkeys(found))[:4]


def _emotions(brief: str) -> List[str]:
    found = [e for e in EMOTION_POOL if e in brief]
    return (found or ["孤独", "怀疑", "希望"])[:4]


class ProjectBuilder:
    def __init__(self, llm=None) -> None:
        self.llm = llm

    def build(self, name: str, brief: str) -> Dict[str, Any]:
        via_llm = self._from_llm(name, brief)
        if via_llm is not None:
            return via_llm
        return self._offline(name, brief)

    # -- offline starter set ------------------------------------------------
    def _offline(self, name: str, brief: str) -> Dict[str, Any]:
        sents = _sentences(brief)
        statement = "；".join(sents[:2])[:160] or (brief or "")[:160]
        question = next((s + "？" for s in sents if s.endswith(("?", "？"))), None)
        question = question or f"在「{name}」的世界里，人该如何自处？"
        symbols = _symbols(brief)
        emotions = _emotions(brief)

        chars = [
            {"id": "shen", "name": "沈川", "tier": "core", "pov": True, "role": "探寻者",
             "desire": "弄清困扰自己的那件事", "fear": "发现自己也是问题的一部分",
             "memory": "一个没能说出口的告别", "worldview": "事情总有解释",
             "contradiction": "相信理性，却常凭直觉行动", "voice": "克制、少形容词",
             "blind_spots": ["只相信可验证的东西，忽略沉默里的信息"],
             "secrets": [], "capabilities": ["观察与推演"], "constraints": ["缺少关键权限"],
             "current_goal": "找到第一个突破口",
             "arc_from": "相信事情可以被彻底弄清", "arc_to": "承认有些事只能带着疑问活下去"},
            {"id": "he", "name": "贺岚", "tier": "core", "pov": True, "role": "掌权者",
             "desire": "维持现有的秩序", "fear": "旧事重提会毁掉一切",
             "memory": "曾经为了大局做过一次选择", "worldview": "稳定比真相更重要",
             "contradiction": "想被理解，却不断阻止别人知道", "voice": "缓慢、滴水不漏",
             "blind_spots": ["把秩序当成正义"], "secrets": ["知道被隐去的那一页"],
             "capabilities": ["调动资源"], "constraints": ["受制于更高的力量"],
             "current_goal": "把麻烦压下去",
             "arc_from": "以沉默保护他人", "arc_to": "承认沉默也会伤人"},
            {"id": "gu", "name": "顾青", "tier": "supporting", "pov": True, "role": "知情者",
             "desire": "让被抹去的名字重新出现", "fear": "自己保存的记忆也被改写",
             "memory": "亲手销毁过一份材料", "worldview": "记忆即权力",
             "contradiction": "守护真相，却依赖谎言生存", "voice": "反问与留白",
             "blind_spots": ["把记忆当作唯一真相"], "secrets": ["私藏了其中一页"],
             "capabilities": ["熟悉档案"], "constraints": ["一旦公开就暴露自己"],
             "current_goal": "决定要不要交出那页纸",
             "arc_from": "藏着", "arc_to": "交出"},
            {"id": "ahe", "name": "阿禾", "tier": "functional", "pov": False, "role": "目击者",
             "desire": "不被卷进任何麻烦", "fear": "被当成替罪者",
             "memory": "那晚看见过一个不该出现的人", "worldview": "少说少错",
             "contradiction": "想说真话，又怕没人信", "voice": "短促、回避",
             "current_goal": "离事远一点"},
        ]
        relationships = [
            {"source_id": "shen", "target_id": "gu", "type": "探寻者与知情者",
             "mutual_interest": "沈川需要顾青掌握的东西，顾青需要有人替她行动",
             "conflict": "是否公开会伤到彼此", "asymmetry": "顾青有信息，沈川有行动力",
             "initial_state": "互相试探", "pressure_point": "那页纸被提起",
             "possible_transition": "从交易到有限信任，或决裂"},
            {"source_id": "shen", "target_id": "he", "type": "探寻者与掌权者",
             "mutual_interest": "都需要事件尽快有个说法",
             "conflict": "一个要真相，一个要稳定", "asymmetry": "贺岚有权力，沈川只有直觉",
             "initial_state": "表面配合、暗中设阻", "pressure_point": "关键记录出现矛盾",
             "possible_transition": "贺岚从阻挡转为承担，或更彻底地沉默"},
            {"source_id": "gu", "target_id": "he", "type": "旧识",
             "mutual_interest": "都希望过去被妥善安放",
             "conflict": "一个想留下名字，一个想让一切安静",
             "asymmetry": "贺岚知来源，顾青知材料",
             "initial_state": "心照不宣", "pressure_point": "材料面临公开",
             "possible_transition": "一方先打破沉默"},
            {"source_id": "ahe", "target_id": "he", "type": "目击者与调查者",
             "mutual_interest": "阿禾想脱身，贺岚想结案",
             "conflict": "证词指向何处", "asymmetry": "贺岚有权，阿禾无地位",
             "initial_state": "施压与回避", "pressure_point": "阿禾被要求签字",
             "possible_transition": "阿禾说谎自保，或松口"},
        ]
        motifs = [{"name": s, "note": "核心意象，可在不同章节中变义", "history": []} for s in symbols]

        return {
            "theme": {"title": name, "question": question, "statement": statement,
                      "emotions": emotions, "symbols": symbols, "motifs": symbols[:2]},
            "world": {"world": statement or f"《{name}》的世界。",
                      "rules": ["世界有其运转规则，越界需要代价", "关键信息被有意隐藏"],
                      "forbidden": ["机械降神", "无来由的超自然解释"],
                      "soft_constraints": ["允许非线性回忆", "允许留白"],
                      "emotion_curve": ["平静", "不安", "疑惑", "发现", "理解"]},
            "characters": chars,
            "relationships": relationships,
            "motifs": motifs,
        }

    # -- LLM expansion ------------------------------------------------------
    def _from_llm(self, name: str, brief: str) -> Optional[Dict[str, Any]]:
        if self.llm is None or getattr(self.llm, "name", "") in ("mock", ""):
            return None
        prompt = (
            f"根据下面的世界观/剧情简介，为长篇小说《{name}》建立初始设定。\n"
            f"简介：{brief}\n\n"
            "请给出：主题、世界规则、3-5 个功能互补的人物（含稳定 id）、人物关系网络、核心意象。"
            "关系端点必须用人物 id。只输出 JSON：\n"
            '{"theme":{"title":"","question":"","statement":"","emotions":[],"symbols":[],"motifs":[]},'
            '"world":{"world":"","rules":[],"forbidden":[],"soft_constraints":[],"emotion_curve":[]},'
            '"characters":[{"id":"","name":"","tier":"core","pov":true,"role":"","desire":"","fear":"",'
            '"memory":"","worldview":"","contradiction":"","voice":"","blind_spots":[],"secrets":[],'
            '"capabilities":[],"constraints":[],"current_goal":"","arc_from":"","arc_to":""}],'
            '"relationships":[{"source_id":"","target_id":"","type":"","mutual_interest":"","conflict":"",'
            '"asymmetry":"","initial_state":"","pressure_point":"","possible_transition":""}],'
            '"motifs":[{"name":"","note":""}]}'
        )
        data = generate_json(self.llm, prompt, max_tokens=4000)
        if not isinstance(data, dict):
            return None
        return self._normalize(data, name, brief)

    @staticmethod
    def _normalize(data: Dict[str, Any], name: str, brief: str) -> Optional[Dict[str, Any]]:
        try:
            chars = [c for c in data.get("characters", []) if isinstance(c, dict) and c.get("name")]
            if len(chars) < 2:
                return None
            ids = set()
            for i, c in enumerate(chars):
                cid = str(c.get("id") or f"c{i+1}")
                while cid in ids:
                    cid = f"{cid}{i}"
                ids.add(cid)
                c["id"] = cid
                c.setdefault("tier", "supporting")
                c.setdefault("pov", True)
            rels = []
            for r in data.get("relationships", []):
                if not isinstance(r, dict):
                    continue
                if r.get("source_id") in ids and r.get("target_id") in ids:
                    rels.append(r)
            motifs = []
            for m in data.get("motifs", []):
                if isinstance(m, str):
                    motifs.append({"name": m, "note": "", "history": []})
                elif isinstance(m, dict) and m.get("name"):
                    m.setdefault("note", "")
                    m.setdefault("history", [])
                    motifs.append(m)
            theme = dict(data.get("theme") or {})
            theme.setdefault("title", name)
            theme.setdefault("statement", brief[:160])
            theme.setdefault("question", f"在「{name}」的世界里，人该如何自处？")
            theme.setdefault("emotions", ["孤独", "怀疑", "希望"])
            theme.setdefault("symbols", [m["name"] for m in motifs][:3] or ["光"])
            theme.setdefault("motifs", [m["name"] for m in motifs][:2])
            world = dict(data.get("world") or {})
            world.setdefault("world", brief[:160])
            world.setdefault("rules", ["世界有其运转规则，越界需要代价"])
            world.setdefault("forbidden", ["机械降神"])
            world.setdefault("soft_constraints", ["允许留白"])
            world.setdefault("emotion_curve", ["平静", "不安", "疑惑", "发现", "理解"])
            return {"theme": theme, "world": world, "characters": chars,
                    "relationships": rels, "motifs": motifs or [{"name": s, "note": "", "history": []} for s in theme["symbols"][:2]]}
        except Exception:  # noqa: BLE001
            return None


class ProjectManager:
    def __init__(self, root: Optional[Path] = None, llm=None) -> None:
        self.root = Path(root) if root else PROJECTS_ROOT
        self.builder = ProjectBuilder(llm)

    def list_projects(self) -> List[Dict[str, Any]]:
        if not self.root.exists():
            return []
        out: List[Dict[str, Any]] = []
        for d in sorted(self.root.iterdir()):
            story = d / "story.yaml"
            if not d.is_dir() or not story.exists():
                continue
            try:
                data = yaml.safe_load(story.read_text(encoding="utf-8")) or {}
                title = (data.get("theme") or {}).get("title") or d.name
            except Exception:  # noqa: BLE001
                title = d.name
            out.append({"name": title, "dir": d.name, "path": d})
        return out

    def create(self, name: str, brief: str) -> Path:
        if not name.strip():
            raise ValueError("项目名称不能为空")
        spec = self.builder.build(name.strip(), brief or "")
        directory = self._unique_dir(slugify(name))
        self._write(directory, name.strip(), brief or "", spec)
        return directory

    def find(self, target: str) -> Optional[Path]:
        """Resolve a project by directory name or display title."""
        direct = Path(target)
        if direct.is_dir():
            return direct
        for it in self.list_projects():
            if it["dir"] == target or it["name"] == target:
                return it["path"]
        return None

    def read_brief(self, project: Path) -> str:
        project = Path(project)
        brief_file = project / "brief.md"
        if brief_file.exists():
            text = brief_file.read_text(encoding="utf-8")
            # strip the generated header lines
            lines = [ln for ln in text.splitlines()
                     if not ln.startswith("# ") and not ln.startswith("创建于 ")]
            return "\n".join(lines).strip()
        try:
            data = yaml.safe_load((project / "story.yaml").read_text(encoding="utf-8")) or {}
            return (data.get("theme") or {}).get("statement", "")
        except Exception:  # noqa: BLE001
            return ""

    def regenerate(self, project: Path, brief: Optional[str] = None,
                   name: Optional[str] = None) -> Path:
        """Rebuild a project's score from a (possibly updated) brief.

        Existing files — including any saved book_plan / vector store — are
        **moved into a timestamped `_backup_*` folder** first, so a rebuilt world
        never silently renders a stale structure.
        """
        project = Path(project)
        try:
            data = yaml.safe_load((project / "story.yaml").read_text(encoding="utf-8")) or {}
            title = name or (data.get("theme") or {}).get("title") or project.name
        except Exception:  # noqa: BLE001
            title = name or project.name
        brief = brief if brief is not None else self.read_brief(project)
        spec = self.builder.build(title, brief)

        backup = project / f"_backup_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup.mkdir(parents=True, exist_ok=True)
        for fname in ("story.yaml", "characters.yaml", "relationships.yaml",
                      "motifs.yaml", "story_state.yaml", "brief.md",
                      "book_plan.json", "book_outline.md", "story_report.md",
                      "story_report.html", "vector_store.json",
                      "motif_state.yaml", "jazz_state.yaml"):
            src = project / fname
            if src.exists():
                shutil.move(str(src), str(backup / fname))
        self._write(project, title, brief or "", spec)
        return project

    def _unique_dir(self, slug: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        candidate = self.root / slug
        i = 2
        while candidate.exists():
            candidate = self.root / f"{slug}-{i}"
            i += 1
        return candidate

    @staticmethod
    def _write(directory: Path, name: str, brief: str, spec: Dict[str, Any]) -> None:
        directory.mkdir(parents=True, exist_ok=True)

        def dump(filename: str, payload: Any) -> None:
            (directory / filename).write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8")

        dump("story.yaml", {"theme": spec["theme"], "world": spec["world"], "jazz": DEFAULT_JAZZ})
        dump("characters.yaml", {"characters": spec["characters"]})
        dump("relationships.yaml", {"relationships": spec["relationships"]})
        dump("motifs.yaml", {"motifs": spec["motifs"]})
        dump("story_state.yaml", {"chapter": 0, "established_facts": [],
                                  "character_knowledge": {}, "open_threads": [],
                                  "recent_events": []})
        (directory / "brief.md").write_text(
            f"# {name}\n\n创建于 {_dt.datetime.now().isoformat(timespec='seconds')}\n\n{brief}\n",
            encoding="utf-8")
