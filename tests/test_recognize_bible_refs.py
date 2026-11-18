#!/usr/bin/env python3
"""Tests for the decision-table wiring in recognize_bible_refs.py (#46)."""

import csv
import sys
import types

import pytest

from scripts.normalization_decisions import DecisionTable
from scripts.recognize_bible_refs import find_citations, main, match_book

HEADER = ["kind", "from", "to", "scope", "decided_by", "decided_on", "note"]


def make_table(tmp_path, rows):
    path = tmp_path / "decisions.tsv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


class TestMatchBookDecisions:
    def test_without_table_unchanged(self):
        assert match_book("Johannis") == ("Johannes", "Joh", 0.875)
        assert match_book("Geneſ") is None

    def test_decision_forces_match(self, tmp_path):
        t = DecisionTable.load(make_table(tmp_path, [["bible", "Geneſ", "Genesis"]]))
        assert match_book("Geneſ", t) == ("Genesis", "Gen", 1.0)

    def test_decision_by_short_form(self, tmp_path):
        t = DecisionTable.load(make_table(tmp_path, [["bible", "Geneſ", "Gen"]]))
        assert match_book("Geneſ", t) == ("Genesis", "Gen", 1.0)

    def test_decision_rejects_match(self, tmp_path):
        t = DecisionTable.load(make_table(tmp_path, [["bible", "Römern", ""]]))
        assert match_book("Römern") is not None
        assert match_book("Römern", t) is None

    def test_scoped_decision(self, tmp_path):
        t = DecisionTable.load(
            make_table(tmp_path, [["bible", "Epheser", "Römer", "a_v_1443_hertwig"]])
        )
        assert match_book("Epheser", t) == ("Epheser", "Eph", 1.0)
        assert match_book("Epheser", t, witness="a_v_1443_hertwig") == ("Römer", "Röm", 1.0)

    def test_unknown_book_raises(self, tmp_path):
        t = DecisionTable.load(make_table(tmp_path, [["bible", "Geneſ", "Quodlibet"]]))
        with pytest.raises(ValueError, match="Unbekanntes Buch"):
            match_book("Geneſ", t)


class TestFindCitations:
    def test_decision_reaches_citations(self, tmp_path):
        t = DecisionTable.load(make_table(tmp_path, [["bible", "Geneſ", "Genesis"]]))
        cites = find_citations("Sie führen an Geneſ 5.", t)
        assert [c["reference"] for c in cites] == ["Gen 5"]
        assert cites[0]["token"] == "Geneſ"


class TestMain:
    TABLE_HEADER = ["reference", "book", "chapter", "count",
                    "min_confidence", "surfaces", "pages", "confirmed"]

    def run_main(self, tmp_path, monkeypatch, decisions, prior_rows=()):
        fake = types.ModuleType("compare_witnesses")
        fake.available_witnesses = lambda: ["a_v_1443_hertwig"]
        fake.page_texts = lambda key: {
            0: "Sie führen an Geneſ 5 und Römern 6.",
            1: "Wieder Geneſ 5.",
        }
        monkeypatch.setitem(sys.modules, "compare_witnesses", fake)
        out_dir = tmp_path / "register"
        out_dir.mkdir()
        if prior_rows:
            with (out_dir / "bible_refs.tsv").open("w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter="\t")
                writer.writerow(self.TABLE_HEADER)
                writer.writerows(prior_rows)
        decisions_path = tmp_path / "decisions.tsv"
        with decisions_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter="\t")
            writer.writerow(HEADER)
            writer.writerows(decisions)
        open_path = tmp_path / "open.tsv"
        rc = main([
            "--decisions", str(decisions_path),
            "--out-dir", str(out_dir),
            "--open", str(open_path),
        ])
        assert rc == 0
        table_rows = list(csv.reader((out_dir / "bible_refs.tsv").open(encoding="utf-8"), delimiter="\t"))
        open_rows = list(csv.reader(open_path.open(encoding="utf-8"), delimiter="\t"))
        return table_rows, open_rows

    def test_confirmed_carried_across(self, tmp_path, monkeypatch):
        table_rows, _ = self.run_main(
            tmp_path, monkeypatch,
            decisions=[["bible", "Geneſ", "Genesis"]],
            prior_rows=[["Gen 5", "Genesis", 5, 2, 1.0, "", "", "ja"]],
        )
        by_ref = {r[0]: r for r in table_rows[1:]}
        assert by_ref["Gen 5"][7] == "ja"

    def test_confirmed_never_invented(self, tmp_path, monkeypatch):
        table_rows, _ = self.run_main(tmp_path, monkeypatch, decisions=[])
        assert all(r[7] == "" for r in table_rows[1:])

    def test_decision_forces_reference_and_keeps_open_list(self, tmp_path, monkeypatch):
        table_rows, open_rows = self.run_main(
            tmp_path, monkeypatch,
            decisions=[["bible", "Geneſ", "Genesis"]],
        )
        by_ref = {r[0]: r for r in table_rows[1:]}
        assert "Gen 5" in by_ref
        assert "Röm 6" in by_ref
        open_kinds = {r[0] for r in open_rows[1:]}
        assert open_kinds == {"bible"}
        open_froms = [r[1] for r in open_rows[1:]]
        assert "Römern" in open_froms
        assert "Geneſ" not in open_froms

    def test_decided_case_leaves_open_list(self, tmp_path, monkeypatch):
        table_rows, open_rows = self.run_main(
            tmp_path, monkeypatch,
            decisions=[["bible", "Römern", ""]],
        )
        by_ref = {r[0]: r for r in table_rows[1:]}
        assert "Röm 6" not in by_ref
        open_froms = [r[1] for r in open_rows[1:]]
        assert "Römern" not in open_froms
