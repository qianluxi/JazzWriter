"""Shared fixtures for the test-suite (hermetic, no data files needed)."""

from __future__ import annotations

from core.character import Character
from core.harmony import Harmony
from core.motif import MotifLibrary
from core.story_state import CharacterKnowledge, Fact, StoryState, Thread
from core.theme import Theme
from improvisation.improvisation_score import params_for_mode
from llm.mock import MockProvider
from session import Session


def make_theme() -> Theme:
    return Theme(
        title="蒸汽时代的人类孤独",
        question="技术在进步，人是否更接近幸福",
        statement="我们造出了轰鸣的机器，却学会了更安静地彼此远离。",
        emotions=["孤独", "怀疑"],
        symbols=["蒸汽", "雾"],
        motifs=["蒸汽", "阀门"],
    )


def make_harmony() -> Harmony:
    return Harmony(
        world="蒸汽工业城市",
        rules=["技术事故被系统性掩盖"],
        forbidden=["魔法"],
        emotion_curve=["平静", "不安", "发现", "理解"],
    )


def make_character() -> Character:
    return Character(
        name="林",
        role="检修工程师",
        desire="查清事故真相",
        fear="发现父亲也是共谋",
        memory="父亲消失在白雾里",
        worldview="任何故障都有可查明的原因",
        contradiction="相信理性却凭直觉",
        voice="短句",
        arc_from="相信技术中立",
        arc_to="承认技术是欲望的延伸",
    )


def make_state() -> StoryState:
    return StoryState(
        chapter=2,
        established_facts=[
            Fact(id="fact_001", statement="事故报告存在两个版本", status="confirmed"),
            Fact(id="secret_001", statement="父亲签下了掩盖命令", status="secret"),
        ],
        character_knowledge={
            "林": CharacterKnowledge(known=["fact_001"], unknown=["secret_001"]),
        },
        open_threads=[
            Thread(id="thread_001", question="谁修改了事故记录", status="open"),
        ],
    )


def make_session(mode: str = "free_jazz", seed: int = 123, state=None) -> Session:
    motifs = MotifLibrary()
    motifs.ensure(["蒸汽", "阀门"])
    return Session(
        make_theme(),
        make_harmony(),
        {"林": make_character()},
        motifs,
        provider=MockProvider(),
        jazz=params_for_mode(mode, seed=seed),
        story_state=state if state is not None else make_state(),
        eval_mode="lexical",
    )
