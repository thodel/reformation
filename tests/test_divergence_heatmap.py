#!/usr/bin/env python3
"""Tests for the divergence heatmap (#15)."""
from __future__ import annotations
import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import divergence_heatmap as dh  # noqa: E402


class ThinSectionTest(unittest.TestCase):
    """A section resting on one or two units is not a measurement.

    The manuscripts have very little transcribed text, so most of their
    sections are thin: a_v_1444 has 23 of 24. Colouring those like a section
    built from sixty units would invite a false reading.
    """

    def test_threshold_exists(self):
        self.assertGreaterEqual(dh.MIN_UNITS, 2)

    def test_output_marks_confidence(self):
        if not dh.OUT.exists():
            self.skipTest("heatmap not generated")
        data = json.loads(dh.OUT.read_text(encoding="utf-8"))
        for row in data["rows"].values():
            for cell in row["cells"]:
                self.assertIn("confident", cell)
                if not cell["confident"]:
                    self.assertIsNone(cell["divergence"])

    def test_thin_cells_carry_no_number(self):
        if not dh.OUT.exists():
            self.skipTest("heatmap not generated")
        data = json.loads(dh.OUT.read_text(encoding="utf-8"))
        thin = [c for r in data["rows"].values() for c in r["cells"] if not c["confident"]]
        self.assertTrue(all(c["divergence"] is None for c in thin))


class ShapeTest(unittest.TestCase):
    def test_every_row_has_the_same_number_of_sections(self):
        if not dh.OUT.exists():
            self.skipTest("heatmap not generated")
        data = json.loads(dh.OUT.read_text(encoding="utf-8"))
        widths = {len(r["cells"]) for r in data["rows"].values()}
        self.assertEqual(len(widths), 1)
        self.assertEqual(widths.pop(), data["sections"])

    def test_reference_is_not_its_own_row(self):
        if not dh.OUT.exists():
            self.skipTest("heatmap not generated")
        data = json.loads(dh.OUT.read_text(encoding="utf-8"))
        self.assertNotIn(data["reference"], data["rows"])

    def test_divergence_is_within_range(self):
        if not dh.OUT.exists():
            self.skipTest("heatmap not generated")
        data = json.loads(dh.OUT.read_text(encoding="utf-8"))
        for row in data["rows"].values():
            for cell in row["cells"]:
                if cell["divergence"] is not None:
                    self.assertGreaterEqual(cell["divergence"], 0.0)
                    self.assertLessEqual(cell["divergence"], 1.0)


class PairDiscoveryTest(unittest.TestCase):
    def test_finds_pairs_in_either_order(self):
        # Directories are named a__b; the reference may be on either side.
        found = dh.pair_dirs("druck_1528")
        if not found:
            self.skipTest("no comparison data")
        self.assertTrue(all(isinstance(w, str) for w, _ in found))
        self.assertNotIn("druck_1528", [w for w, _ in found])


if __name__ == "__main__":
    unittest.main(verbosity=2)
