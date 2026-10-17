import json
import unittest

from core.story_state import StoryState
from engine.narrative_reviewer import NarrativeReviewer
from tests.helpers import make_session, make_state
from tests.test_v24 import FakeLLM

PREMISE = "一场技术事故改变了一个家庭"


def _book(session, chapters=6):
    ideas = session.story_ideas(PREMISE, count=2, seed=1)
    return session.build_book(PREMISE, ideas, pick=0, chapters=chapters, seed=1)


class FactConflictOfflineTest(unittest.TestCase):
    def test_offline_reports_requires_model(self):
        session = make_session(seed=1)
        book = _book(session)
        findings = NarrativeReviewer(story_state=make_state()).review(book)
        fact = [f for f in findings if f.kind == "fact_check"]
        self.assertTrue(fact)
        self.assertIn("需接入模型", " ".join(f.issue for f in fact))

    def test_offline_without_facts(self):
        session = make_session(seed=1)
        book = _book(session)
        findings = NarrativeReviewer(story_state=StoryState()).review(book)
        self.assertTrue(any(f.kind == "fact_check" for f in findings))


class FactConflictLlmTest(unittest.TestCase):
    def test_llm_fact_conflict_parsed(self):
        session = make_session(seed=1)
        book = _book(session)
        payload = json.dumps({"findings": [
            {"chapter": 3, "issue": "与已确定事实冲突：章节称设备已修复，但事实是设备从未修复",
             "evidence": "事实：事故报告存在两个版本", "type": "fact_conflict"},
            {"chapter": 4, "issue": "冲突升级不足", "evidence": "outcome 过短", "type": "narrative"},
        ]})
        reviewer = NarrativeReviewer(FakeLLM([payload]), story_state=make_state())
        findings = reviewer.review(book)
        conflicts = [f for f in findings if f.kind == "fact_conflict"]
        self.assertTrue(conflicts)
        self.assertEqual(conflicts[0].chapter, 3)

    def test_llm_no_conflict_adds_fact_check(self):
        session = make_session(seed=1)
        book = _book(session)
        payload = json.dumps({"findings": [
            {"chapter": 1, "issue": "开篇略平", "evidence": "x", "type": "narrative"}]})
        findings = NarrativeReviewer(FakeLLM([payload]), story_state=make_state()).review(book)
        self.assertTrue(any(f.kind == "fact_check" for f in findings))
        self.assertFalse(any(f.kind == "fact_conflict" for f in findings))


class ValidateBookReviewTest(unittest.TestCase):
    def test_validate_report_includes_fact_check(self):
        session = make_session(seed=1)
        book = _book(session)
        report = session.validate_book(book)
        kinds = {f["kind"] for f in report.review}
        self.assertIn("fact_check", kinds)


if __name__ == "__main__":
    unittest.main()
