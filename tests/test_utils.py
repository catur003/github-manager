"""
tests/test_utils.py
PRIORITAS 8: unit test untuk fungsi-fungsi murni (pure function) yang
tidak butuh git/network/questionary — aman dijalankan di CI/sandbox mana pun.

Jalankan: python -m unittest discover tests
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.utils import (
    normalize_repo_url,
    sha1_of_file,
    sha1_of_bytes,
    human_size,
    list_top_level_dirs,
    count_files_in_dir,
)
from modules.update import _parse_version


class TestNormalizeRepoUrl(unittest.TestCase):
    def test_shorthand_owner_repo(self):
        self.assertEqual(
            normalize_repo_url("catur003/github-manager"),
            "https://github.com/catur003/github-manager.git",
        )

    def test_shorthand_strips_existing_dot_git(self):
        self.assertEqual(
            normalize_repo_url("catur003/github-manager.git"),
            "https://github.com/catur003/github-manager.git",
        )

    def test_full_https_url_unchanged(self):
        url = "https://github.com/catur003/github-manager.git"
        self.assertEqual(normalize_repo_url(url), url)

    def test_ssh_url_unchanged(self):
        url = "git@github.com:catur003/github-manager.git"
        self.assertEqual(normalize_repo_url(url), url)

    def test_empty_string(self):
        self.assertEqual(normalize_repo_url(""), "")

    def test_invalid_shorthand_with_space_unchanged(self):
        text = "bukan shorthand valid"
        self.assertEqual(normalize_repo_url(text), text)


class TestHash(unittest.TestCase):
    def test_sha1_of_bytes_known_value(self):
        # sha1("") == da39a3ee5e6b4b0d3255bfef95601890afd80709
        self.assertEqual(
            sha1_of_bytes(b""), "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        )

    def test_sha1_of_file_matches_bytes(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"halo dunia")
            path = f.name
        try:
            self.assertEqual(sha1_of_file(path), sha1_of_bytes(b"halo dunia"))
        finally:
            os.unlink(path)

    def test_sha1_of_file_missing_returns_none(self):
        self.assertIsNone(sha1_of_file("/path/tidak/ada/sama/sekali.txt"))


class TestHumanSize(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(human_size(500), "500.0 B")

    def test_kilobytes(self):
        self.assertEqual(human_size(2048), "2.0 KB")

    def test_megabytes(self):
        self.assertEqual(human_size(5 * 1024 * 1024), "5.0 MB")


class TestFolderHelpers(unittest.TestCase):
    def test_list_top_level_dirs_and_count_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "folderA"))
            os.makedirs(os.path.join(tmp, "folderB", "sub"))
            open(os.path.join(tmp, "folderA", "file1.txt"), "w").close()
            open(os.path.join(tmp, "folderB", "sub", "file2.txt"), "w").close()
            open(os.path.join(tmp, ".hidden_should_be_skipped"), "w").close()

            dirs = list_top_level_dirs(tmp, extra_levels=1)
            self.assertIn("folderA/", dirs)
            self.assertIn("folderB/", dirs)
            self.assertIn("folderB/sub/", dirs)
            self.assertTrue(all(not d.startswith(".") for d in dirs))

            self.assertEqual(count_files_in_dir(tmp), 2)


class TestParseVersion(unittest.TestCase):
    def test_plain_semver(self):
        self.assertEqual(_parse_version("1.2.3"), (1, 2, 3))

    def test_with_v_prefix(self):
        self.assertEqual(_parse_version("v1.2.3"), (1, 2, 3))

    def test_missing_patch_defaults_zero(self):
        self.assertEqual(_parse_version("v2.0"), (2, 0, 0))

    def test_comparison_newer_version(self):
        self.assertGreater(_parse_version("v1.1.0"), _parse_version("v1.0.9"))

    def test_comparison_equal_version(self):
        self.assertEqual(_parse_version("v1.0.0"), _parse_version("1.0.0"))


if __name__ == "__main__":
    unittest.main()
