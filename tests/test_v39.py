import tempfile
import unittest
from pathlib import Path

from engine.preview import rebuild_index, slugify, write_preview
from engine.project_manager import ProjectManager

BRIEF = "南方的雨季小镇，一封迟到十年的信，与雨、信、旧照片有关。"


class ProjectDeleteTest(unittest.TestCase):
    def test_delete_removes_local_and_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            prev = Path(tmp) / "preview"
            manager = ProjectManager(root=root, preview_dir=prev)
            path = manager.create("桂花巷", BRIEF)

            slug = slugify(path.name)
            write_preview(prev, f"{slug}.html", "<html>old</html>")
            rebuild_index(prev)
            self.assertIn(slug, (prev / "index.html").read_text(encoding="utf-8"))

            info = manager.delete(path, push=False)

            self.assertFalse(path.exists())
            self.assertFalse((prev / f"{slug}.html").exists())
            self.assertTrue(info["preview_removed"])
            self.assertFalse(info["pushed"])
            self.assertNotIn(slug, (prev / "index.html").read_text(encoding="utf-8"))
            self.assertIsNone(manager.find(path.name))
            self.assertEqual(manager.list_projects(), [])

    def test_delete_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager(root=Path(tmp) / "projects",
                                     preview_dir=Path(tmp) / "preview")
            with self.assertRaises(FileNotFoundError):
                manager.delete(Path(tmp) / "projects" / "nope")


if __name__ == "__main__":
    unittest.main()
