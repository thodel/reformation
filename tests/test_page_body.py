#!/usr/bin/env python3
"""Tests for page body extraction.

druck_1528 is the base text of every comparison and was transcribed by Gemini,
which wrote headings in several shapes with no marker. 445 of its 496 pages
carried heading text into the compared content while every other witness was
clean, so this ran through every pairing.
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from align_witnesses import page_body  # noqa: E402


class HeadingTest(unittest.TestCase):
    def test_strips_the_marked_heading(self):
        self.assertEqual(page_body("# Seite 120\n\nechter text"), "echter text")

    def test_strips_an_unmarked_heading(self):
        self.assertEqual(page_body("Seite 170\n\ntext"), "text")

    def test_strips_a_roman_numeral_heading(self):
        self.assertEqual(page_body("Seite CXIII\n\ntext"), "text")

    def test_strips_a_bracketed_placeholder(self):
        self.assertEqual(page_body("Seite [X]\n\ntext"), "text")

    def test_keeps_content_that_merely_starts_a_page(self):
        """"Die erst" and "Schlussred." open pages and are text, not headings."""
        for opener in ("Die erst", "Schlußred.", "Die vierdte Schlußred"):
            self.assertTrue(page_body(f"{opener}\n\nweiter").startswith(opener), opener)

    def test_keeps_a_line_mentioning_Seite_with_words_after_it(self):
        self.assertTrue(page_body("Seite und andere worte\n\nx").startswith("Seite und"))

    def test_no_heading_at_all(self):
        self.assertEqual(page_body("nur text\nzweite zeile"), "nur text\nzweite zeile")


class MarkupTest(unittest.TestCase):
    def test_strips_html_tags(self):
        got = page_body('Seite [X]\n<div align="center">\n\n**Titel**\n</div>\n\ntext')
        self.assertNotIn("div", got)
        self.assertNotIn("align", got)
        self.assertIn("**Titel**", got)   # markdown emphasis is content
        self.assertIn("text", got)

    def test_strips_br_and_p(self):
        self.assertNotIn("br", page_body("wort<br>wort"))

    def test_leaves_ordinary_angle_free_text_alone(self):
        self.assertEqual(page_body("ganz normaler text"), "ganz normaler text")


class EmptyTest(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(page_body(""), "")
        self.assertEqual(page_body("   \n\n  "), "")

    def test_heading_only_page_is_empty(self):
        self.assertEqual(page_body("# Seite 5\n"), "")
        self.assertEqual(page_body("Seite [X]\n"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
