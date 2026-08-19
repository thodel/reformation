#!/usr/bin/env python3
"""Tests for the pairwise similarity matrix."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import similarity_matrix as sm  # noqa: E402


class ConfidenceTest(unittest.TestCase):
    """A mean over three pages is not a measurement.

    The matrix contains real examples: a_v_1443 against a_v_1445 reports 28%
    over three aligned pages. Presenting that beside a figure drawn from 560
    pages, with no distinction, would invite a false comparison.
    """

    def test_threshold_is_set(self):
        self.assertGreaterEqual(sm.MIN_UNITS_FOR_CONFIDENCE, 10)

    def test_few_pages_is_not_confident(self):
        self.assertLess(3, sm.MIN_UNITS_FOR_CONFIDENCE)

    def test_many_pages_is_confident(self):
        self.assertGreaterEqual(560, sm.MIN_UNITS_FOR_CONFIDENCE)


class OutputShapeTest(unittest.TestCase):
    def test_bands_are_separated_from_the_matrix(self):
        # Bands are 98% of the data and are not needed to draw the heatmap.
        self.assertNotEqual(sm.OUT, sm.BANDS)
        self.assertEqual(sm.BANDS.name, "bands")

    def test_matrix_and_bands_share_a_directory(self):
        self.assertEqual(sm.OUT.parent, sm.BANDS.parent)


class RealMatrixTest(unittest.TestCase):
    """Guards the finding the matrix exists to support (issue #17)."""

    @classmethod
    def setUpClass(cls):
        import json
        cls.data = json.loads(sm.OUT.read_text(encoding="utf-8")) if sm.OUT.exists() else None

    def _lookup(self, a, b):
        m = self.data["matrix"]
        return (m.get(a, {}).get(b)) or (m.get(b, {}).get(a))

    def test_every_pair_is_present(self):
        if not self.data:
            self.skipTest("matrix not generated")
        n = len(self.data["witnesses"])
        pairs = sum(len(v) for v in self.data["matrix"].values())
        self.assertEqual(pairs, n * (n - 1) // 2)

    def test_the_two_1608_copies_stand_apart(self):
        if not self.data:
            self.skipTest("matrix not generated")
        same = self._lookup("druck_1608_bern", "druck_1608_zuerich")
        self.assertIsNotNone(same)
        self.assertTrue(same["confident"])
        others = [
            self._lookup(a, b)
            for a, b in [("druck_1528", "druck_1608_bern"),
                         ("druck_1528", "druck_1701"),
                         ("druck_1528_04", "druck_1701")]
        ]
        for other in others:
            self.assertGreater(same["similarity"], other["similarity"] + 0.25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
