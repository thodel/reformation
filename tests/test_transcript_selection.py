#!/usr/bin/env python3
"""Tests for transcript selection.

The regressions these cover do not exist in the current Transkribus data --
today every policy picks the same transcript -- so without them the selection
rule would only be exercised by data that cannot fail.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sync_disputation_transkribus import (  # noqa: E402
    DEFAULT_STATUS_PREFERENCE,
    pick_latest_transcript,
    status_rank,
)

PREF = DEFAULT_STATUS_PREFERENCE


def ts(ts_id, status, timestamp, lines=10, chars=100):
    return {
        "tsId": ts_id,
        "status": status,
        "timestamp": timestamp,
        "nrOfTranscribedLines": lines,
        "nrOfCharsInLines": chars,
    }


def page(*transcripts):
    return {"tsList": {"transcripts": list(transcripts)}}


class StatusRankTest(unittest.TestCase):
    def test_orders_by_preference(self):
        ranks = [status_rank(s, PREF) for s in PREF]
        self.assertEqual(ranks, sorted(ranks, reverse=True))

    def test_unknown_status_ranks_below_everything(self):
        self.assertLess(status_rank("SOMETHING_ELSE", PREF), status_rank("NEW", PREF))

    def test_is_case_insensitive(self):
        self.assertEqual(status_rank("done", PREF), status_rank("DONE", PREF))


class PickLatestTranscriptTest(unittest.TestCase):
    def test_returns_none_without_transcripts(self):
        self.assertIsNone(pick_latest_transcript(page(), PREF))
        self.assertIsNone(pick_latest_transcript({}, PREF))

    def test_prefers_newer_transcript_at_equal_status(self):
        old = ts(1, "IN_PROGRESS", 1000)
        new = ts(2, "IN_PROGRESS", 2000)
        self.assertEqual(pick_latest_transcript(page(old, new), PREF)["tsId"], 2)

    def test_resegmentation_does_not_supersede_reviewed_work(self):
        """A NEW transcript written after a DONE one must not win on recency."""
        done = ts(1, "DONE", 1000)
        resegmented = ts(2, "NEW", 5000, lines=0, chars=0)
        self.assertEqual(pick_latest_transcript(page(done, resegmented), PREF)["tsId"], 1)

    def test_later_in_progress_does_not_supersede_done(self):
        done = ts(1, "DONE", 1000)
        later = ts(2, "IN_PROGRESS", 5000)
        self.assertEqual(pick_latest_transcript(page(done, later), PREF)["tsId"], 1)

    def test_newest_done_wins_among_several_done(self):
        chosen = pick_latest_transcript(
            page(ts(1, "DONE", 1000), ts(2, "DONE", 3000), ts(3, "IN_PROGRESS", 9000)), PREF
        )
        self.assertEqual(chosen["tsId"], 2)

    def test_empty_transcript_never_beats_one_with_text(self):
        with_text = ts(1, "IN_PROGRESS", 1000, lines=40)
        empty = ts(2, "DONE", 2000, lines=0, chars=0)
        self.assertEqual(pick_latest_transcript(page(with_text, empty), PREF)["tsId"], 1)

    def test_falls_back_to_empty_when_page_has_nothing_else(self):
        only = ts(1, "NEW", 1000, lines=0, chars=0)
        self.assertEqual(pick_latest_transcript(page(only), PREF)["tsId"], 1)

    def test_empty_preference_uses_the_default_order(self):
        done = ts(1, "DONE", 1000)
        later = ts(2, "IN_PROGRESS", 5000)
        self.assertEqual(pick_latest_transcript(page(done, later), [])["tsId"], 1)

    def test_custom_preference_is_respected(self):
        """A project that trusts recency over status can invert the ranking."""
        done = ts(1, "DONE", 1000)
        later = ts(2, "IN_PROGRESS", 5000)
        flat = ["DONE", "IN_PROGRESS"]
        self.assertEqual(pick_latest_transcript(page(done, later), flat)["tsId"], 1)
        inverted = ["IN_PROGRESS", "DONE"]
        self.assertEqual(pick_latest_transcript(page(done, later), inverted)["tsId"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
