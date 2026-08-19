#!/usr/bin/env python3
"""Tests for page segmentation."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from segment_pages import (  # noqa: E402
    build_segments, join_lines, paragraphs_from_markdown, split_columns,
)

def L(text, x, y, w, h=40):
    return {"text": text, "x": float(x), "y": float(y), "w": float(w), "h": float(h), "id": None}

class JoinLinesTest(unittest.TestCase):
    def test_rejoins_words_split_across_lines(self):
        self.assertEqual(join_lines(["disputie //", "ren wellenn"]), "disputieren wellenn")

    def test_handles_several_continuation_markers(self):
        for marker in ("//", "¬", "-", "—", "="):
            self.assertEqual(join_lines([f"wort{marker}", "teil"]), "wortteil", marker)

    def test_keeps_normal_lines_separated_by_a_space(self):
        self.assertEqual(join_lines(["erste zeile", "zweite zeile"]), "erste zeile zweite zeile")

    def test_collapses_whitespace_and_skips_blanks(self):
        self.assertEqual(join_lines(["a  b", "", "  c "]), "a b c")

class SplitColumnsTest(unittest.TestCase):
    def test_separates_narrow_marginalia_from_the_body(self):
        lines = [L("body one", 950, 100, 1400), L("body two", 955, 200, 1390),
                 L("body three", 948, 300, 1410), L("nota", 450, 150, 450)]
        body, margins = split_columns(lines)
        self.assertEqual([l["text"] for l in body], ["body one", "body two", "body three"])
        self.assertEqual(len(margins), 1)
        self.assertEqual(margins[0][0]["text"], "nota")

    def test_orders_the_body_top_to_bottom(self):
        lines = [L("third", 950, 300, 1400), L("first", 950, 100, 1400), L("second", 950, 200, 1400)]
        body, _ = split_columns(lines)
        self.assertEqual([l["text"] for l in body], ["first", "second", "third"])

    def test_page_without_marginalia_keeps_every_line(self):
        lines = [L(f"line {i}", 950, i * 100, 1400) for i in range(5)]
        body, margins = split_columns(lines)
        self.assertEqual(len(body), 5)
        self.assertEqual(margins, [])

    def test_empty_input(self):
        self.assertEqual(split_columns([]), ([], []))

class SegmentGroupingTest(unittest.TestCase):
    def test_groups_paragraphs_three_to_a_segment(self):
        segs = build_segments("v", 7, [f"p{i}" for i in range(7)])
        self.assertEqual([len(s["paragraphs"]) for s in segs], [3, 3, 1])
        self.assertEqual(segs[0]["id"], "v-7-1")
        self.assertEqual(segs[0]["page_nr"], 7)

    def test_segment_text_joins_paragraphs_with_a_blank_line(self):
        segs = build_segments("v", 1, ["alpha", "beta"])
        self.assertEqual(segs[0]["text"], "alpha\n\nbeta")

    def test_no_paragraphs_yields_no_segments(self):
        self.assertEqual(build_segments("v", 1, []), [])

class MarkdownFallbackTest(unittest.TestCase):
    def test_strips_heading_and_splits_on_blank_lines(self):
        paras = paragraphs_from_markdown("# Seite 3\n\nerster block\nzweite zeile\n\nzweiter block\n")
        self.assertEqual(paras, ["erster block zweite zeile", "zweiter block"])

    def test_single_block_becomes_one_paragraph(self):
        self.assertEqual(paragraphs_from_markdown("# Seite 3\n\nnur eine\nzeile\n"), ["nur eine zeile"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
