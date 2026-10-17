import subprocess
import tempfile
import unittest
from pathlib import Path

from engine.preview import git_publish
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
            self.assertEqual(manager.find("甲"), project)      # real project by title
            self.assertEqual(manager.find(project.name), project)  # by dir

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


class CommitScopeTest(unittest.TestCase):
    def _git(self, repo, *args):
        return subprocess.run(["git", "-C", str(repo), *args],
                              capture_output=True, text=True)

    def test_commit_only_touches_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._git(repo, "init")
            self._git(repo, "config", "user.email", "t@example.com")
            self._git(repo, "config", "user.name", "tester")

            (repo / "a.txt").write_text("secret source", encoding="utf-8")
            self._git(repo, "add", "a.txt")  # staged, unrelated to the preview

            (repo / "preview").mkdir()
            (repo / "preview" / "index.html").write_text("<html>x</html>", encoding="utf-8")

            info = git_publish(repo, "preview: test", add_path="preview")
            self.assertFalse(info["pushed"])  # no remote in temp repo

            committed = self._git(repo, "show", "--name-only", "--pretty=format:", "HEAD").stdout
            self.assertIn("preview/index.html", committed)
            self.assertNotIn("a.txt", committed)          # unrelated change NOT committed
            status = self._git(repo, "status", "--porcelain").stdout
            self.assertIn("a.txt", status)                # still staged/pending


if __name__ == "__main__":
    unittest.main()
