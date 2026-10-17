import tempfile
import unittest
from pathlib import Path

from engine.project_manager import ProjectManager

BRIEF = "边境小镇的旧事故与两种记录。"


class PathContainmentTest(unittest.TestCase):
    def test_find_rejects_outside_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            manager = ProjectManager(root=tmp / "projects", preview_dir=tmp / "preview")
            project = manager.create("甲", BRIEF)

            outside = tmp / "outside"
            outside.mkdir()
            (outside / "story.yaml").write_text("theme: {title: x}\n", encoding="utf-8")

            self.assertIsNone(manager.find(str(outside)))     # outside projects root
            self.assertEqual(manager.find("甲").resolve(), project.resolve())          # title
            self.assertEqual(manager.find(project.name).resolve(), project.resolve())  # dir

    def test_delete_refuses_outside_and_non_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            manager = ProjectManager(root=tmp / "projects", preview_dir=tmp / "preview")
            manager.create("甲", BRIEF)

            outside = tmp / "outside"
            outside.mkdir()
            (outside / "story.yaml").write_text("theme: {title: x}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                manager.delete(outside)
            self.assertTrue(outside.exists())  # untouched

            no_project = tmp / "projects" / "plain"
            no_project.mkdir()
            with self.assertRaises(ValueError):
                manager.delete(no_project)
            self.assertTrue(no_project.exists())

    def test_regenerate_refuses_outside(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            manager = ProjectManager(root=tmp / "projects", preview_dir=tmp / "preview")
            outside = tmp / "outside"
            outside.mkdir()
            (outside / "story.yaml").write_text("theme: {title: x}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                manager.regenerate(outside)


if __name__ == "__main__":
    unittest.main()
