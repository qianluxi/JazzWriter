import json
import tempfile
import unittest
from pathlib import Path

from engine.project_manager import ProjectManager, slugify
from session import Session
from store import load_characters, load_relationships
from tests.test_v24 import FakeLLM

BRIEF = "2020年代中俄边境小镇，一条冬天封冻的界河。一起旧事故、两种矛盾的记录，以及与蒸汽、河、雪有关的往事。"


class ProjectCreateOfflineTest(unittest.TestCase):
    def test_creates_valid_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            manager = ProjectManager(root=root)
            path = manager.create("界河纪事", BRIEF)

            for f in ("story.yaml", "characters.yaml", "relationships.yaml",
                      "motifs.yaml", "story_state.yaml", "brief.md"):
                self.assertTrue((path / f).exists(), f)

            session = Session.load(data_dir=path)
            self.assertEqual(session.theme.title, "界河纪事")
            self.assertTrue(session.characters)
            ids = set(session.characters.keys())
            for r in session.relationships.relationships:
                self.assertIn(r.source_id, ids)
                self.assertIn(r.target_id, ids)
            self.assertTrue(session.motifs.all())

            items = manager.list_projects()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["path"], path)

    def test_unique_directory_on_name_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(root=Path(tmp) / "projects")
            a = manager.create("同名", "甲的故事")
            b = manager.create("同名", "乙的故事")
            self.assertNotEqual(a, b)
            self.assertEqual(len(manager.list_projects()), 2)

    def test_slugify(self):
        self.assertTrue(slugify("界河 纪事!").startswith("界河"))
        self.assertEqual(slugify(""), "project")


class ProjectCreateLlmTest(unittest.TestCase):
    def test_uses_llm_spec(self):
        spec = {
            "theme": {"title": "测试世界", "question": "谁在说谎？",
                      "statement": "冰下有东西。", "emotions": ["怀疑"],
                      "symbols": ["冰"], "motifs": ["冰"]},
            "world": {"world": "边境小镇", "rules": ["越界有代价"],
                      "forbidden": [], "soft_constraints": [], "emotion_curve": ["平静", "理解"]},
            "characters": [
                {"id": "a", "name": "张三", "tier": "core", "pov": True, "desire": "查明"},
                {"id": "b", "name": "李四", "tier": "supporting", "pov": True, "desire": "隐瞒"},
            ],
            "relationships": [{"source_id": "a", "target_id": "b", "type": "对手", "conflict": "真相"}],
            "motifs": [{"name": "冰", "note": "记忆"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(root=Path(tmp) / "projects",
                                     llm=FakeLLM([json.dumps(spec)]))
            path = manager.create("测试世界", BRIEF)
            chars = load_characters(path / "characters.yaml")
            self.assertEqual({c.name for c in chars.values()}, {"张三", "李四"})
            rels = load_relationships(path / "relationships.yaml")
            self.assertEqual(len(rels.relationships), 1)
            self.assertEqual(load_characters(path / "characters.yaml")["a"].desire, "查明")


if __name__ == "__main__":
    unittest.main()
