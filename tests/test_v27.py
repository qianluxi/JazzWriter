import unittest

from core.book_plan import BookPlan
from core.chapter_plan import ChapterPlan
from core.relationship import Relationship, RelationshipMap
from core.volume_plan import VolumePlan
from engine.plot_validator import PlotValidator
from tests.test_v26 import PREMISE, _multi_session


class RelationshipGenerationTest(unittest.TestCase):
    def test_turning_point_chapters_change_defined_relations(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        book = session.build_book(PREMISE, ideas, pick=0, chapters=10, template="multi_pov", seed=1)
        defined = {(r.source_id, r.target_id) for r in session.relationships.relationships}
        defined |= {(r.target_id, r.source_id) for r in session.relationships.relationships}
        changes = [rc for c in book.chapters() for rc in c.relationship_changes]
        self.assertTrue(changes, "turning-point chapters should move a relationship")
        for rc in changes:
            pair = tuple(rc.pair)
            self.assertIn(pair, defined)
            self.assertTrue(rc.change)

    def test_changes_view(self):
        session = _multi_session()
        ideas = session.story_ideas(PREMISE, count=2, seed=1)
        session.build_book(PREMISE, ideas, pick=0, chapters=10, template="multi_pov", seed=1)
        view = session.relationship_changes_view()
        self.assertEqual(len(view), len(session.relationships.relationships))
        self.assertTrue(any(row["changes"] for row in view))


def _book_with_rel_changes(cast_ids, rel_changes):
    ch = ChapterPlan(number=1, function="高潮", pov="林", premise="p",
                     conflict="c", outcome="o", summary="s",
                     pov_character_id="lin", characters_involved=["lin", "su"],
                     relationship_changes=rel_changes)
    return BookPlan(title="x", cast=["林", "苏"], cast_ids=cast_ids,
                    volumes=[VolumePlan(number=1, chapters=[ch])])


class RelationshipValidationTest(unittest.TestCase):
    def setUp(self):
        self.rels = RelationshipMap(relationships=[
            Relationship(source_id="lin", target_id="su", type="对手", conflict="c"),
        ])

    def test_undefined_pair_flagged(self):
        book = _book_with_rel_changes(["lin", "su"],
                                      [{"pair": ["lin", "zhao"], "change": "翻脸", "cause": "x"}])
        kinds = {i.kind for i in PlotValidator().validate(book, relationships=self.rels)}
        self.assertIn("relationship", kinds)

    def test_missing_cause_flagged(self):
        book = _book_with_rel_changes(["lin", "su"],
                                      [{"pair": ["lin", "su"], "change": "决裂", "cause": ""}])
        issues = PlotValidator().validate(book, relationships=self.rels)
        self.assertTrue(any(i.kind == "relationship" and "原因" in i.message for i in issues))

    def test_unknown_character_flagged(self):
        book = _book_with_rel_changes(["lin", "su"],
                                      [{"pair": ["lin", "ghost"], "change": "x", "cause": "y"}])
        kinds = {i.kind for i in PlotValidator().validate(book, relationships=self.rels)}
        self.assertIn("unknown_character", kinds)

    def test_never_changing_relationship_flagged(self):
        # relationship lin-su defined but no chapter changes it
        book = _book_with_rel_changes(["lin", "su"], [])
        issues = PlotValidator().validate(book, relationships=self.rels)
        self.assertTrue(any(i.kind == "relationship" and "从未发生变化" in i.message for i in issues))


if __name__ == "__main__":
    unittest.main()
