#!/usr/bin/env python3
"""Tests for semantic sentence comparison (#35).

The thresholds encode measurements, so the tests document them: at sentence
scale matched pairs score 0.931 against 0.533 for random pairs. At page scale
the same model gives 0.787 against 0.750 and is useless, which is why this
works on sentence units.
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from embed_sentences import (  # noqa: E402
    CHARACTER_CEILING, MODEL_NAME, SEMANTIC_FLOOR, classify,
)


class ClassifyTest(unittest.TestCase):
    def test_high_character_and_high_semantic_is_same(self):
        self.assertEqual(classify(0.90, 0.95), "same")

    def test_low_character_but_high_semantic_is_reworded(self):
        """The case the character comparison alone cannot identify."""
        self.assertEqual(classify(0.10, 0.90), "reworded")

    def test_low_on_both_is_different(self):
        self.assertEqual(classify(0.10, 0.30), "different")

    def test_high_character_but_low_semantic_is_flagged_for_checking(self):
        # Should be rare; it usually means something went wrong.
        self.assertEqual(classify(0.90, 0.20), "check")

    def test_boundaries(self):
        self.assertEqual(classify(CHARACTER_CEILING - 0.01, SEMANTIC_FLOOR), "reworded")
        self.assertEqual(classify(CHARACTER_CEILING, SEMANTIC_FLOOR), "same")
        self.assertEqual(classify(CHARACTER_CEILING - 0.01, SEMANTIC_FLOOR - 0.01), "different")


class ThresholdTest(unittest.TestCase):
    def test_semantic_floor_sits_above_the_measured_control(self):
        """Random sentence pairs scored 0.533; below that a score says nothing."""
        self.assertGreater(SEMANTIC_FLOOR, 0.533)

    def test_semantic_floor_sits_below_the_measured_signal(self):
        """Matched sentence pairs scored 0.931."""
        self.assertLess(SEMANTIC_FLOOR, 0.931)

    def test_model_is_recorded_for_staleness(self):
        # A model change must mark data stale rather than silently altering it.
        self.assertTrue(MODEL_NAME)
        self.assertIsInstance(MODEL_NAME, str)


class AnnotateShapeTest(unittest.TestCase):
    def test_unit_without_sentences_is_handled(self):
        from embed_sentences import annotate_unit
        unit = annotate_unit(None, {"unit": 1})
        self.assertIn("sentences", unit)
        self.assertEqual(unit["sentences"]["semantic"], 0.0)

    def test_unit_with_no_pairs_needs_no_model(self):
        from embed_sentences import annotate_unit
        unit = annotate_unit(None, {"unit": 1, "sentences": {"pairs": []}})
        self.assertEqual(unit["sentences"]["reworded"], 0)
        self.assertEqual(unit["sentences"]["recovered_by_embedding"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class RecoveredIsNotRewordedTest(unittest.TestCase):
    """Hand-checking separated two populations that the score does not.

    Pairs the character matcher found and the embedding reinterpreted held up
    6 of 6. Pairs the embedding proposed on its own held up roughly 1 in 3,
    and the scores overlap completely - false ones 0.72-0.78, true ones
    0.66-0.89. They must therefore not carry the same label.
    """

    def test_classify_alone_never_returns_candidate(self):
        # 'candidate' is assigned only where the embedding proposed the pair,
        # which classify() cannot know about.
        for c in (0.0, 0.3, 0.6, 0.9):
            for s in (0.0, 0.3, 0.6, 0.9):
                self.assertIn(classify(c, s), {"same", "reworded", "different", "check"})

    def test_summary_reports_candidates_separately(self):
        from embed_sentences import annotate_unit
        unit = annotate_unit(None, {"unit": 1, "sentences": {"pairs": []}})
        self.assertIn("candidates", unit["sentences"])
        self.assertIn("reworded", unit["sentences"])
