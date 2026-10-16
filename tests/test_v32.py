import tempfile
import unittest
from pathlib import Path

from core.book_plan import BookPlan
from core.chapter_plan import ChapterPlan, KnowledgeChange
from core.character import Character
from core.harmony import Harmony
from core.volume_plan import VolumePlan
from engine.outline_expander import OutlineExpander
from engine.plot_validator import PlotValidator
from session import Session
from store import save_book_plan, load_characters
from tests.helpers import make_session, make_state, make_theme
from tests.test_v26 import PREMISE, _multi_session


class ProjectIsolationTest(unittest.TestCase):
    def test_book_plan_is_project_scoped(self):
        book = BookPlan(title="T", cast=["林"], cast_ids=["林"], volumes=[
            VolumePlan(number=1, chapters=[ChapterPlan(
                number=1, function="建立", pov="林", premise="p", conflict="c",
                outcome="o", summary="s")])])
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            a, b = Path(a), Path(b)
            save_book_plan(book, a / "book_plan.json")
            sa = Session.load(data_dir=a)
            self.assertEqual(sa.book_plan_path, a / "book_plan.json")
            self.assertIsNotNone(sa.book)
            self.assertEqual(sa.book.title, "T")
            # a different project must not see A's plan
            sb = Session.load(data_dir=b)
            self.assertIsNone(sb.book)


class SameNameCharacterTest(unittest.TestCase):
    def test_load_characters_keyed_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "characters.yaml"
            path.write_text(
                "characters:\n"
                "  - name: 林\n    id: a\n    desire: 查真相\n"
                "  - name: 林\n    id: b\n    desire: 让名字重见\n",
                encoding="utf-8")
            chars = load_characters(path)
        self.assertEqual(set(chars.keys()), {"a", "b"})
        self.assertEqual(len(chars), 2)


class ReimproviseMetadataTest(unittest.TestCase):
    def test_candidate_refreshes_decisions_and_knowledge(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        candidates = session.reimprovise_candidates(3, seed=1)
        self.assertTrue(candidates)
        cand = candidates[0].chapter
        # decisions/knowledge must match the *new* content, not the old chapter
        self.assertTrue(cand.character_decisions)
        self.assertEqual(cand.character_decisions[0].decision, cand.key_action)
        if cand.knowledge_changes:
            self.assertIn("·", cand.knowledge_changes[0].source)

    def test_apply_updates_structured_fields(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        candidate = session.reimprovise_candidates(3, seed=1)[0]
        book, _ = session.apply_candidate(candidate)
        ch = book.chapter(3)
        self.assertEqual(ch.character_decisions[0].decision, ch.key_action)


class OfflineConstraintTest(unittest.TestCase):
    def test_sanitize_removes_forbidden_and_hides_secrets(self):
        expander = OutlineExpander(
            make_theme(), [Character(name="林")],
            harmony=Harmony(world="", rules=[], forbidden=["魔法"]),
            story_state=make_state())
        self.assertNotIn("魔法", expander._sanitize("这里有魔法"))
        # make_state's secret statement must not be revealed
        self.assertNotIn("父亲签下了掩盖命令", expander._sanitize("父亲签下了掩盖命令"))

    def test_offline_chapters_respect_forbidden(self):
        session = make_session(seed=1)
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=6, seed=1)
        for c in book.chapters():
            blob = " ".join([c.conflict, c.outcome, c.summary, c.info_change, c.key_action])
            self.assertNotIn("魔法", blob)


class KnowledgeSourceTest(unittest.TestCase):
    def test_bare_chapter_source_flagged(self):
        ch = ChapterPlan(number=2, function="调查", pov="林", premise="p", conflict="c",
                         outcome="o", summary="s",
                         knowledge_changes=[KnowledgeChange(character_id="林", change="得知",
                                                            source="第2章")])
        book = BookPlan(title="x", cast=["林"], cast_ids=["林"],
                        volumes=[VolumePlan(number=1, chapters=[ch])])
        issues = PlotValidator().validate(book, story_state=make_state())
        self.assertTrue(any(i.kind == "knowledge" and "过于宽泛" in i.message for i in issues))

    def test_offline_source_is_concrete(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=8, template="multi_pov", seed=1)
        sources = [k.source for c in book.chapters() for k in c.knowledge_changes]
        self.assertTrue(sources)
        self.assertTrue(all("·" in s for s in sources))


if __name__ == "__main__":
    unittest.main()
