#!/usr/bin/env python3
"""Tests for precomputed witness comparison."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compare_witnesses import coarse_diff, fine_diff, norm_words, paragraphs  # noqa: E402


class ParagraphsTest(unittest.TestCase):
    def test_splits_on_blank_lines(self):
        self.assertEqual(paragraphs("eins\nzwei\n\ndrei"), ["eins zwei", "drei"])

    def test_line_broken_page_stays_one_block(self):
        # Transcriptions have no blank lines; each line is not a paragraph.
        self.assertEqual(paragraphs("eine\nzeile\nnoch eine"), ["eine zeile noch eine"])

    def test_empty(self):
        self.assertEqual(paragraphs("   "), [])


class NormWordsTest(unittest.TestCase):
    def test_applies_orthographic_normalisation(self):
        # vnnd -> unnd, jnn -> inn, and the combining mark is folded away.
        self.assertEqual(norm_words("vnnd jnn zuͦ"), ["unnd", "inn", "zu"])

    def test_precomposed_and_combining_agree(self):
        self.assertEqual(norm_words("z" + "u" + "ͦ"), norm_words("zů"))


class FineDiffTest(unittest.TestCase):
    def test_identical_text_has_no_ops(self):
        got = fine_diff("der herr sprach", "der herr sprach")
        self.assertEqual(got["ops"], 0)
        self.assertEqual(got["similarity"], 1.0)

    def test_orthographic_variants_do_not_count_as_differences(self):
        """The point of normalising: vnnd/unnd is not a variant worth reporting."""
        got = fine_diff("vnnd der herr", "unnd der herr")
        self.assertEqual(got["ops"], 0)

    def test_original_orthography_is_preserved_for_display(self):
        """Matching is normalised; what the reader sees must be what is written."""
        got = fine_diff("vnnd der herr", "unnd der herr")
        self.assertEqual(got["segments"][0]["a"], "vnnd der herr")
        self.assertEqual(got["segments"][0]["b"], "unnd der herr")

    def test_equal_stretches_are_kept_for_context(self):
        got = fine_diff("der herr sprach", "der knecht sprach")
        tags = [s["op"] for s in got["segments"]]
        self.assertEqual(tags, ["equal", "replace", "equal"])
        self.assertEqual(got["ops"], 1)

    def test_substantive_change_is_reported(self):
        got = fine_diff("der herr sprach", "der knecht sprach")
        self.assertTrue(any(seg["op"] == "replace" for seg in got["segments"]))

    def test_reports_added_and_removed_words(self):
        self.assertTrue(any(o["op"] == "insert" for o in fine_diff("a b", "a x b")["segments"]))
        self.assertTrue(any(o["op"] == "delete" for o in fine_diff("a x b", "a b")["segments"]))

    def test_wholly_different_text_is_a_single_replace(self):
        """Not 600 ops: difflib collapses a total mismatch into one opcode."""
        a = " ".join(f"a{i}" for i in range(600))
        b = " ".join(f"b{i}" for i in range(600))
        got = fine_diff(a, b)
        self.assertEqual(len(got["segments"]), 1)
        self.assertEqual(got["segments"][0]["op"], "replace")
        self.assertFalse(got["truncated"])

    def test_op_list_is_capped_when_differences_interleave(self):
        # Alternating same/different words is what actually produces many ops.
        a = " ".join(("same" if i % 2 else f"a{i}") for i in range(1000))
        b = " ".join(("same" if i % 2 else f"b{i}") for i in range(1000))
        got = fine_diff(a, b)
        self.assertEqual(len(got["segments"]), 400)
        self.assertTrue(got["truncated"])

    def test_untruncated_flag_when_small(self):
        self.assertFalse(fine_diff("a b", "a c")["truncated"])


class CoarseDiffTest(unittest.TestCase):
    def test_identical_paragraphs_are_all_equal(self):
        text = "erster block\n\nzweiter block"
        got = coarse_diff(text, text)
        self.assertEqual(got["counts"]["equal"], 2)
        self.assertEqual(got["similarity"], 1.0)

    def test_extra_paragraph_shows_as_insert(self):
        got = coarse_diff("eins\n\nzwei", "eins\n\nzwei\n\ndrei")
        self.assertGreaterEqual(got["counts"]["insert"], 1)
        self.assertEqual(got["paragraphs"], {"a": 2, "b": 3})

    def test_rewritten_paragraph_shows_as_replace(self):
        got = coarse_diff("eins\n\nzwei", "eins\n\nvoellig anders hier")
        self.assertGreaterEqual(got["counts"]["replace"], 1)

    def test_empty_sides(self):
        got = coarse_diff("", "")
        self.assertEqual(got["paragraphs"], {"a": 0, "b": 0})


if __name__ == "__main__":
    unittest.main(verbosity=2)
