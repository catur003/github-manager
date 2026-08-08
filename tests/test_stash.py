"""
tests/test_stash.py
Unit test untuk fungsi murni (tidak butuh git/network/questionary) di
modules/stash.py, konsisten dengan tests/test_utils.py.

Jalankan: python -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.stash import _parse_stash_entry


class TestParseStashEntry(unittest.TestCase):
    def test_ref_and_description(self):
        self.assertEqual(
            _parse_stash_entry("stash@{0}|WIP on main: 1a2b3c pesan commit"),
            ("stash@{0}", "WIP on main: 1a2b3c pesan commit"),
        )

    def test_ref_with_custom_message(self):
        self.assertEqual(
            _parse_stash_entry("stash@{1}|On feature/x: perubahan sementara"),
            ("stash@{1}", "On feature/x: perubahan sementara"),
        )

    def test_no_separator_returns_line_as_ref(self):
        self.assertEqual(_parse_stash_entry("stash@{0}"), ("stash@{0}", ""))

    def test_empty_string(self):
        self.assertEqual(_parse_stash_entry(""), ("", ""))


if __name__ == "__main__":
    unittest.main()
