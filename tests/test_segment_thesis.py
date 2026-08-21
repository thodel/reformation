#!/usr/bin/env python3
"""Tests for thesis detection from the print's running head.

The ninth thesis was missed entirely: this print spells its head "Die nuͤn̄te",
"Die nůndte" and "Die nünte", none of which the ordinals table held, so pages
466-481 were read as a continuation of the eighth.
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from segment_print import ORDINALS, thesis_of  # noqa: E402


class OrdinalTest(unittest.TestCase):
    def test_all_ten_are_recognised(self):
        heads = {
            "Die erſt": 1, "Die ander": 2, "Die dritt": 3, "Die vierde": 4,
            "Die fünfft": 5, "Die sechst": 6, "Die ſibend": 7,
            "Die achteſch": 8, "Die nůndte": 9, "Die zehend": 10,
        }
        for head, expected in heads.items():
            self.assertEqual(thesis_of(head), expected, head)

    def test_every_spelling_of_the_ninth(self):
        """Three spellings occur in this print; all were previously missed."""
        for head in ("Die nuͤn̄te", "Die nůndte", "Die nůn̄dte", "Die nünte"):
            self.assertEqual(thesis_of(head), 9, head)

    def test_the_fourth_survives_the_v_to_u_fold(self):
        """normalize() turns "vierde" into "uierde"; keys are folded to match."""
        self.assertEqual(thesis_of("Die vierde"), 4)
        self.assertIn("uierd", ORDINALS)

    def test_a_content_line_is_not_a_head(self):
        self.assertIsNone(thesis_of("Die prieſter von Appenzell ſprachen"))

    def test_no_head_at_all(self):
        self.assertIsNone(thesis_of("gemeine kilch gloubt hatt"))
        self.assertIsNone(thesis_of(""))


class KeyNormalisationTest(unittest.TestCase):
    def test_keys_are_stored_normalised(self):
        # Both sides of the comparison must pass through the same transform.
        for key in ORDINALS:
            self.assertEqual(key, key.lower())
            self.assertNotIn("v", key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
