#!/usr/bin/env python3
"""Tests for sentence-scale segmentation and matching (#34)."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sentence_align import (  # noqa: E402
    align_sentences, group_sentences, sentences, similarity, split_clauses, summarise, word_count,
)


class ClauseSplitTest(unittest.TestCase):
    def test_virgel_is_a_clause_marker(self):
        """The prints set / where we would set a comma; it must split."""
        self.assertEqual(split_clauses("erster teil/ zweiter teil"),
                         ["erster teil/", "zweiter teil"])

    def test_sentence_final_punctuation_splits(self):
        self.assertEqual(len(split_clauses("Eins. Zwei? Drei!")), 3)

    def test_colon_and_semicolon_split(self):
        self.assertEqual(len(split_clauses("a: b; c")), 3)

    def test_comma_does_not_split(self):
        # The manuscript uses commas heavily; splitting on them would produce
        # units 20% shorter there than in the prints.
        self.assertEqual(len(split_clauses("eins, zwei, drei")), 1)

    def test_empty(self):
        self.assertEqual(split_clauses(""), [])
        self.assertEqual(split_clauses("   "), [])


class GroupingTest(unittest.TestCase):
    def test_groups_up_to_the_target(self):
        clauses = ["ein wort " * 5] * 4          # 10 words each
        units = group_sentences([c.strip() for c in clauses], target=20)
        self.assertEqual(len(units), 2)

    def test_short_tail_joins_the_previous_unit(self):
        clauses = ["wort " * 20, "kurz"]
        units = group_sentences([c.strip() for c in clauses], target=20)
        self.assertEqual(len(units), 1)
        self.assertTrue(units[0].endswith("kurz"))

    def test_single_short_clause_still_yields_a_unit(self):
        self.assertEqual(len(group_sentences(["kurz"], target=20)), 1)

    def test_no_clauses(self):
        self.assertEqual(group_sentences([], target=20), [])

    def test_word_count_ignores_punctuation(self):
        self.assertEqual(word_count("eins/ zwei. drei"), 3)


class SimilarityTest(unittest.TestCase):
    def test_orthographic_variation_is_not_a_difference(self):
        self.assertEqual(similarity("vnnd der herr", "unnd der herr"), 1.0)

    def test_different_wording_scores_below_one(self):
        self.assertLess(similarity("der herr sprach", "der knecht schwieg"), 1.0)


class AlignSentencesTest(unittest.TestCase):
    def test_matching_units_pair_up(self):
        a = ["der herr sprach zum volk", "es war ein grosser tag"]
        pairs = align_sentences(a, list(a))
        self.assertEqual([p["op"] for p in pairs], ["match", "match"])

    def test_each_b_unit_is_used_at_most_once(self):
        """Without strict matching, one B sentence is reported against two in A."""
        a = ["der herr sprach zum volk", "der herr sprach zum volk", "ganz anderer text hier"]
        b = ["der herr sprach zum volk"]
        pairs = align_sentences(a, b)
        self.assertEqual(sum(1 for p in pairs if p["op"] == "match"), 1)

    def test_surplus_on_each_side_is_reported_not_dropped(self):
        pairs = align_sentences(["gemeinsam text hier", "nur in a zu finden"],
                                ["gemeinsam text hier"])
        self.assertEqual(sum(1 for p in pairs if p["op"] == "only_a"), 1)
        pairs = align_sentences(["gemeinsam text hier"],
                                ["gemeinsam text hier", "nur in b zu finden"])
        self.assertEqual(sum(1 for p in pairs if p["op"] == "only_b"), 1)

    def test_order_is_preserved(self):
        a = ["erster satz mit inhalt", "zweiter satz mit inhalt", "dritter satz mit inhalt"]
        pairs = align_sentences(a, list(a))
        texts = [p["a"] for p in pairs if p["a"]]
        self.assertEqual(texts, a)

    def test_empty_sides(self):
        self.assertEqual(align_sentences([], []), [])
        self.assertEqual(len(align_sentences(["nur a"], [])), 1)

    def test_summary_counts(self):
        s = summarise(align_sentences(["gemeinsam text hier", "nur in a"], ["gemeinsam text hier"]))
        self.assertEqual(s["matched"], 1)
        self.assertEqual(s["only_a"], 1)
        self.assertEqual(s["units"], 2)


class RealPrintTest(unittest.TestCase):
    def test_clause_units_are_comparable_between_prints(self):
        """The property the whole design rests on."""
        import statistics
        from compare_witnesses import page_texts
        medians = []
        for key in ("druck_1528", "druck_1701"):
            try:
                texts = page_texts(key)
            except Exception:
                self.skipTest("witness not available")
            sample = "\n".join(list(texts.values())[:40])
            lens = [word_count(u) for u in sentences(sample)]
            lens = [x for x in lens if x]
            if not lens:
                self.skipTest("no text")
            medians.append(statistics.median(lens))
        ratio = medians[0] / medians[1]
        self.assertGreater(ratio, 0.7)
        self.assertLess(ratio, 1.4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
