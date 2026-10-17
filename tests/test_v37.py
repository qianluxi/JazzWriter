import json
import tempfile
import unittest
from pathlib import Path

from engine.project_manager import ProjectManager
from session import Session

BRIEF_A = "雪山脚下的疗养院，一个失忆的医生与一群沉默的病人，与光、雪、门有关。"
BRIEF_B = "南方的雨季小镇，一封迟到十年的信，牵扯出与雨、信、旧照片有关的往事。"


class RegenTest(unittest.TestCase):
    def test_regenerate_rewrites_and_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(root=Path(tmp) / "projects")
            path = manager.create("初版", BRIEF_A)
            # simulate a previously saved structure sitting in the project
            (path / "book_plan.json").write_text(json.dumps({"title": "old"}), encoding="utf-8")

            self.assertEqual(manager.read_brief(path).strip(), BRIEF_A)

            manager.regenerate(path, BRIEF_B, name="雨季")

            # stale structure must NOT remain at the top level
            self.assertFalse((path / "book_plan.json").exists())
            backups = list(path.glob("_backup_*"))
            self.assertTrue(backups)
            self.assertTrue((backups[0] / "book_plan.json").exists())
            self.assertTrue((backups[0] / "story.yaml").exists())

            session = Session.load(data_dir=path)
            self.assertEqual(session.theme.title, "雨季")
            self.assertIn("雨", session.motifs.names())  # brief B's symbols
            self.assertEqual(Path(session.data_dir), path)

    def test_find_by_dir_and_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(root=Path(tmp) / "projects")
            path = manager.create("雪山", BRIEF_A)
            self.assertEqual(manager.find("雪山").resolve(), path.resolve())
            self.assertEqual(manager.find(path.name).resolve(), path.resolve())
            self.assertIsNone(manager.find("不存在"))

    def test_regenerate_without_brief_reuses_brief_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(root=Path(tmp) / "projects")
            path = manager.create("原样", BRIEF_A)
            manager.regenerate(path)  # no brief -> reuse brief.md
            self.assertEqual(manager.read_brief(path).strip(), BRIEF_A)


if __name__ == "__main__":
    unittest.main()
