#!/usr/bin/env python3
"""Tests for translation boilerplate stripping.

The risk here is over-matching: the words the model uses in its scaffolding
also occur in genuine translated prose, so most of these tests assert that
text is LEFT ALONE.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from clean_translations import clean  # noqa: E402


class CleanTest(unittest.TestCase):
    def test_removes_leading_preamble(self):
        text = (
            "# Seite 649\n\n"
            "Hier ist die Übersetzung des frühneuhochdeutschen Textes ins moderne Deutsch, "
            "Zeile für Zeile beibehalten:\n\n"
            "Die vierte Schlussrede.\n"
        )
        out, removed = clean(text)
        self.assertNotIn("Hier ist die Übersetzung", out)
        self.assertIn("Die vierte Schlussrede.", out)
        self.assertTrue(out.startswith("# Seite 649\n"))
        self.assertEqual(len(removed), 1)

    def test_removes_stray_text_label_after_preamble(self):
        text = (
            "# Seite 335\n\n"
            "Hier die Übersetzung des Textes ins moderne Deutsch, Zeile für Zeile:\n\n"
            "Text:\n\n"
            "ad ipjus\n"
        )
        out, _ = clean(text)
        self.assertNotIn("Text:", out)
        self.assertIn("ad ipjus", out)

    def test_removes_trailing_commentary_section(self):
        text = (
            "# Seite 104\n\n"
            "Echter übersetzter Fliesstext.\n\n"
            "**Anmerkungen zur Übersetzung:**\n\n"
            "*   Der Text ist fragmentarisch.\n"
        )
        out, _ = clean(text)
        self.assertIn("Echter übersetzter Fliesstext.", out)
        self.assertNotIn("Anmerkungen", out)
        self.assertNotIn("fragmentarisch", out)

    def test_removes_preamble_with_conversational_opener(self):
        for opener in ("Absolut! ", "Okay, ", "Gerne, "):
            text = (
                "# Seite 104\n\n"
                f"{opener}Hier ist die Übersetzung des Textes ins moderne Deutsch, "
                "Zeile für Zeile:\n\n"
                "Echter Text.\n"
            )
            out, removed = clean(text)
            self.assertNotIn("Übersetzung des Textes", out, opener)
            self.assertIn("Echter Text.", out)

    def test_removes_preamble_ending_in_a_caveat_sentence(self):
        text = (
            "# Seite 399\n\n"
            "Hier ist die Übersetzung des frühneuhochdeutschen Textes ins moderne Deutsch, "
            "wobei die Zeilenstruktur beibehalten wird. Bitte beachte, dass die Bedeutung "
            "unklar bleibt.\n\n"
            "Echter Text.\n"
        )
        out, _ = clean(text)
        self.assertNotIn("Bitte beachte", out)
        self.assertIn("Echter Text.", out)

    # --- the important half: things that must survive ---

    def test_keeps_prose_containing_gerne(self):
        """'gerne von ihm verstanden habe' is translation, not scaffolding."""
        text = (
            "# Seite 187\n\n"
            "sei es ein Pfarrer oder im Pfarrbezirk. Welches ich\n"
            "gerne von ihm verstanden habe. Denn der\n"
        )
        out, removed = clean(text)
        self.assertEqual(out, text)
        self.assertEqual(removed, [])

    def test_keeps_inline_anmerkung_aside(self):
        text = (
            "# Seite 122\n\n"
            "*gerechter, suis epens gleneens*\n"
            "(Anmerkung: Diese Zeilen scheinen fragmentarisch.)\n"
            "weiterer Text\n"
        )
        out, removed = clean(text)
        self.assertEqual(out, text)
        self.assertEqual(removed, [])

    def test_keeps_prose_mentioning_uebersetzung_without_colon(self):
        text = "# Seite 5\n\nDie Übersetzung der Bibel war ein Streitpunkt\n"
        out, removed = clean(text)
        self.assertEqual(out, text)
        self.assertEqual(removed, [])

    def test_keeps_body_line_ending_in_colon(self):
        text = "# Seite 7\n\nEr sprach also:\n\nUnd dann weiter.\n"
        out, removed = clean(text)
        self.assertEqual(out, text)
        self.assertEqual(removed, [])

    def test_is_idempotent(self):
        text = (
            "# Seite 1\n\n"
            "Hier die Übersetzung des Textes ins moderne Deutsch:\n\n"
            "Inhalt\n"
        )
        once, _ = clean(text)
        twice, removed = clean(once)
        self.assertEqual(once, twice)
        self.assertEqual(removed, [])

    def test_preserves_heading_and_trailing_newline(self):
        text = "# Seite 42\n\nHier die Übersetzung des Textes:\n\nInhalt\n"
        out, _ = clean(text)
        self.assertTrue(out.startswith("# Seite 42\n"))
        self.assertTrue(out.endswith("\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
