#!/usr/bin/env python3
"""Tests for witness alignment."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from align_witnesses import build_units, monotone_alignment, ngrams, score_pairs  # noqa: E402


class NgramTest(unittest.TestCase):
    def test_bigrams(self):
        self.assertEqual(ngrams(["a", "b", "c"], 2), {"a b", "b c"})

    def test_unigrams_are_the_token_set(self):
        self.assertEqual(ngrams(["a", "b", "a"], 1), {"a", "b"})

    def test_short_input_yields_nothing(self):
        self.assertEqual(ngrams(["a"], 2), set())
        self.assertEqual(ngrams([], 2), set())


class ScorePairsTest(unittest.TestCase):
    def test_matches_pages_sharing_rare_wording(self):
        a = {1: "der herr sprach zu dem volk am berge".split()}
        b = {5: "der herr sprach zu dem volk am berge".split(),
             6: "ganz andere woerter ohne jede beziehung hier".split()}
        got = score_pairs(a, b, threshold=0.1)
        self.assertIn(1, got)
        self.assertEqual(got[1][0][0], 5)

    def test_common_grams_are_ignored_as_uninformative(self):
        # "und der" appears on every B page, so it must not drive a match.
        b = {i: f"und der wort{i} folgt{i} hier{i}".split() for i in range(1, 21)}
        a = {1: "und der".split()}
        self.assertEqual(score_pairs(a, b, threshold=0.1), {})

    def test_threshold_filters_weak_matches(self):
        a = {1: "alpha beta gamma delta epsilon zeta eta theta".split()}
        b = {2: "alpha beta komplett andere sache hier zum test".split()}
        self.assertEqual(score_pairs(a, b, threshold=0.99), {})

    def test_pages_without_rare_grams_are_skipped(self):
        self.assertEqual(score_pairs({1: []}, {2: ["x", "y"]}), {})


class MonotoneAlignmentTest(unittest.TestCase):
    def test_keeps_order_consistent_pairs(self):
        got = monotone_alignment({1: [(10, .9)], 2: [(20, .9)], 3: [(30, .9)]})
        self.assertEqual([(a, b) for a, b, _ in got], [(1, 10), (2, 20), (3, 30)])

    def test_result_is_always_monotone(self):
        """The invariant: B pages never run backwards as A advances.

        Which conflicting pair survives is decided by total score - here
        (2,5),(3,30) at 1.85 beats (1,10),(3,30) at 1.80 - but whatever
        survives must not contain a backwards step.
        """
        got = monotone_alignment({1: [(10, .9)], 2: [(5, .95)], 3: [(30, .9)]})
        a_pages = [a for a, _, _ in got]
        b_pages = [b for _, b, _ in got]
        self.assertEqual(a_pages, sorted(a_pages))
        self.assertEqual(b_pages, sorted(b_pages))

    def test_conflicting_pairs_cannot_both_survive(self):
        got = monotone_alignment({1: [(10, .9)], 2: [(5, .95)], 3: [(30, .9)]})
        pairs = [(a, b) for a, b, _ in got]
        self.assertFalse((1, 10) in pairs and (2, 5) in pairs)

    def test_monotone_on_a_larger_shuffled_candidate_set(self):
        import random
        random.seed(11)
        candidates = {a: [(random.randint(1, 200), random.random()) for _ in range(4)]
                      for a in range(1, 40)}
        got = monotone_alignment(candidates)
        b_pages = [b for _, b, _ in got]
        self.assertEqual(b_pages, sorted(b_pages))

    def test_prefers_the_higher_scoring_of_two_valid_chains(self):
        got = monotone_alignment({1: [(10, .2), (11, .9)], 2: [(20, .9)]})
        self.assertEqual([(a, b) for a, b, _ in got], [(1, 11), (2, 20)])

    def test_equal_b_pages_are_allowed(self):
        # Two A pages may correspond to one denser B page.
        got = monotone_alignment({1: [(10, .8)], 2: [(10, .8)]})
        self.assertEqual(len(got), 2)

    def test_empty_input(self):
        self.assertEqual(monotone_alignment({}), [])


class BuildUnitsTest(unittest.TestCase):
    def test_units_are_numbered_and_carry_both_witnesses(self):
        units = build_units([(1, 10, 0.5), (2, 11, 0.6)], "a", "b")
        self.assertEqual([u["unit"] for u in units], [1, 2])
        self.assertEqual(units[0]["pages"], {"a": [1], "b": [10]})
        self.assertEqual(units[1]["score"], 0.6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
