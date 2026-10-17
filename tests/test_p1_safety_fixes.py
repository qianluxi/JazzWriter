"""Regression tests for JazzWriter P1 project-path and publishing fixes.

Regression suite added by the companion patch.
Run: python -m unittest discover -s tests -p test_p1_safety_fixes.py -v
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from engine.project_manager import ProjectManager
from engine.preview import git_publish


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def git_origin(origin: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "--git-dir", str(origin), *args],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


class ProjectPathSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "projects"
        self.root.mkdir()
        self.preview = base / "docs" / "preview"
        self.preview.mkdir(parents=True)
        self.manager = ProjectManager(root=self.root, preview_dir=self.preview)
        self.external = base / "not_a_project"
        self.external.mkdir()
        (self.external / "story.yaml").write_text(
            "theme:\n  title: External\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_find_rejects_existing_directory_outside_project_root(self) -> None:
        self.assertIsNone(self.manager.find(str(self.external)))

    def test_delete_rejects_external_directory_before_side_effects(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.delete(self.external, push=False)
        self.assertTrue(self.external.exists())
        self.assertTrue((self.external / "story.yaml").exists())

    def test_regenerate_rejects_external_directory(self) -> None:
        original = (self.external / "story.yaml").read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            self.manager.regenerate(self.external, brief="overwrite attempt")
        self.assertEqual(
            (self.external / "story.yaml").read_text(encoding="utf-8"), original
        )

    def test_delete_rejects_project_root_itself(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.delete(self.root, push=False)
        self.assertTrue(self.root.exists())


class GitPublishIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.repo = base / "repo"
        self.origin = base / "origin.git"
        subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(self.origin)],
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "init", "--initial-branch=main", str(self.repo)],
                       check=True, capture_output=True, text=True)
        git(self.repo, "config", "user.name", "JazzWriter Tests")
        git(self.repo, "config", "user.email", "tests@example.invalid")
        (self.repo / "docs" / "preview").mkdir(parents=True)
        (self.repo / "docs" / "preview" / "index.html").write_text("old", encoding="utf-8")
        (self.repo / "src.py").write_text("value = 1\n", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "initial")
        git(self.repo, "remote", "add", "origin", str(self.origin))
        git(self.repo, "push", "-u", "origin", "main")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_unrelated_staged_file_is_not_in_preview_commit(self) -> None:
        (self.repo / "src.py").write_text("value = 2\n", encoding="utf-8")
        git(self.repo, "add", "src.py")  # pre-existing staged change
        (self.repo / "docs" / "preview" / "index.html").write_text("new", encoding="utf-8")
        (self.repo / "docs" / "preview" / "book.html").write_text("book", encoding="utf-8")

        result = git_publish(self.repo, "preview: update")

        self.assertTrue(result["pushed"], result["message"])
        committed = set(git(self.repo, "show", "--format=", "--name-only", "HEAD").splitlines())
        self.assertEqual(committed, {"docs/preview/index.html", "docs/preview/book.html"})
        staged_after = set(git(self.repo, "diff", "--cached", "--name-only").splitlines())
        self.assertEqual(staged_after, {"src.py"})

    def test_preexisting_outgoing_commit_blocks_auto_push(self) -> None:
        (self.repo / "src.py").write_text("value = 2\n", encoding="utf-8")
        git(self.repo, "add", "src.py")
        git(self.repo, "commit", "-m", "unrelated local work")
        local_head = git(self.repo, "rev-parse", "HEAD")
        remote_head_before = git_origin(self.origin, "rev-parse", "refs/heads/main")
        (self.repo / "docs" / "preview" / "index.html").write_text("new", encoding="utf-8")

        result = git_publish(self.repo, "preview: update")

        self.assertFalse(result["pushed"])
        self.assertIn("尚未推送", result["message"])
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), local_head)
        self.assertEqual(
            git_origin(self.origin, "rev-parse", "refs/heads/main"),
            remote_head_before,
        )

    def test_unsafe_paths_are_rejected(self) -> None:
        for path in ("../src.py", ".", "src.py", "docs/../src.py", ":(top)**"):
            with self.subTest(path=path):
                result = git_publish(self.repo, "preview: update", add_path=path)
                self.assertFalse(result["pushed"])
                self.assertIn("unsafe", result["message"])


if __name__ == "__main__":
    unittest.main()
