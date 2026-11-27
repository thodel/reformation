#!/usr/bin/env python3
"""Tests for normalization_decisions.py, the decision table for #46."""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.normalization_decisions import (
    KINDS,
    DecisionTable,
    load_decisions,
    norm_key,
    write_open,
)

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "normalization_decisions.py"
HEADER = ["kind", "from", "to", "scope", "decided_by", "decided_on", "note"]


def make_table(tmp_path, rows, name="decisions.tsv"):
    path = tmp_path / name
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(HEADER)
        writer.writerows(rows)
    return path


def read_rows(path):
    return list(csv.reader(path.open(encoding="utf-8"), delimiter="\t"))


class TestLoad:
    def test_missing_file_is_empty(self, tmp_path):
        assert load_decisions(tmp_path / "kein.tsv") == []

    def test_header_only_is_empty(self, tmp_path):
        assert load_decisions(make_table(tmp_path, [])) == []

    def test_parses_row_with_defaults(self, tmp_path):
        path = make_table(
            tmp_path,
            [["bible", "Matthi", "Matthäus", "", "th", "2026-11-18", "Lesung"]],
        )
        (d,) = load_decisions(path)
        assert (d.kind, d.frm, d.to, d.scope, d.decided_by) == (
            "bible", "Matthi", "Matthäus", "global", "th")
        assert d.decided_on == "2026-11-18" and d.note == "Lesung"

    def test_short_row_gets_defaults(self, tmp_path):
        (d,) = load_decisions(make_table(tmp_path, [["person", "A B", "C D"]]))
        assert (d.frm, d.to, d.scope) == ("A B", "C D", "global")

    def test_unknown_kind_raises(self, tmp_path):
        path = make_table(tmp_path, [["quantum", "x", "y"]])
        with pytest.raises(ValueError, match="unbekanntes kind"):
            load_decisions(path)

    def test_empty_from_raises(self, tmp_path):
        path = make_table(tmp_path, [["bible", "", "Mt"]])
        with pytest.raises(ValueError, match="from darf nicht leer sein"):
            load_decisions(path)

    def test_all_kinds_accepted(self, tmp_path):
        rows = [[k, "x", "y"] for k in KINDS]
        assert len(load_decisions(make_table(tmp_path, rows))) == len(KINDS)


class TestNormKey:
    def test_case_and_spelling_converge(self):
        assert norm_key("Johannes") == norm_key("johannes") == norm_key("Iohannes")

    def test_normalization_applied(self):
        assert norm_key("Epheſ") == norm_key("Ephes")

    def test_multi_word_ignores_extra_whitespace(self):
        assert norm_key("  Martinus  buijer ") == norm_key("martinus buijer")


class TestLookup:
    def _table(self, tmp_path):
        return DecisionTable.load(make_table(tmp_path, [
            ["bible", "Epheser", "Römer", "a_v_1443_hertwig", "th", "2026-11-18", "scoped"],
            ["bible", "Geneſ", "Genesis", "global", "th", "2026-11-18", "global"],
        ]))

    def test_global_hit_and_miss(self, tmp_path):
        t = self._table(tmp_path)
        assert t.lookup("bible", "Geneſ") is not None
        assert t.lookup("bible", "Genesis") is None

    def test_scoped_beats_global_and_falls_back(self, tmp_path):
        t = self._table(tmp_path)
        d = t.lookup("bible", "Epheser", witness="a_v_1443_hertwig")
        assert d is not None and d.scope == "a_v_1443_hertwig"
        assert t.lookup("bible", "Epheser") is None

    def test_lookup_ignores_case(self, tmp_path):
        t = self._table(tmp_path)
        assert t.lookup("bible", "geneſ") is not None

    def test_other_kind_misses(self, tmp_path):
        t = self._table(tmp_path)
        assert t.lookup("person", "Geneſ") is None

    def test_is_decided_any_scope(self, tmp_path):
        t = self._table(tmp_path)
        assert t.is_decided("bible", "Epheser")
        assert t.is_decided("bible", "GENES")
        assert not t.is_decided("bible", "Matthi")


class TestWriteOpen:
    def test_filters_decided(self, tmp_path):
        table = DecisionTable.load(make_table(tmp_path, [["bible", "Johannis", "Johannes"]]))
        open_path = tmp_path / "open.tsv"
        n = write_open(
            [("Johannis", "Johannes Joh", 100, "x"), ("Matt", "Matthäus Mt", 5, "y")],
            "bible", path=open_path, table=table,
        )
        assert n == 1
        rows = read_rows(open_path)
        assert rows[0] == ["kind", "from", "suggestion", "count", "note"]
        assert rows[1][1] == "Matt"

    def test_sorts_by_count(self, tmp_path):
        open_path = tmp_path / "open.tsv"
        write_open([("a", "x", 1, ""), ("b", "y", 9, "")], "bible",
                   path=open_path, table=DecisionTable([]))
        rows = read_rows(open_path)
        assert [r[1] for r in rows[1:]] == ["b", "a"]

    def test_cap_limits_new_rows(self, tmp_path):
        open_path = tmp_path / "open.tsv"
        n = write_open([(f"f{i}", "x", i, "") for i in range(10)], "bible",
                       path=open_path, table=DecisionTable([]), cap=3)
        assert n == 3
        assert len(read_rows(open_path)) == 4

    def test_keeps_other_kinds_and_sorts_all(self, tmp_path):
        open_path = tmp_path / "open.tsv"
        write_open([("A", "person", 7, "")], "person", path=open_path,
                   table=DecisionTable([]))
        n = write_open([("Johannis", "Johannes Joh", 3, "")], "bible",
                       path=open_path, table=DecisionTable([]))
        assert n == 1
        rows = read_rows(open_path)
        assert [r[0] for r in rows[1:]] == ["person", "bible"]

    def test_row_leaves_list_once_decided(self, tmp_path):
        open_path = tmp_path / "open.tsv"
        write_open([("Johannis", "Johannes Joh", 3, "")], "bible",
                   path=open_path, table=DecisionTable([]))
        table = DecisionTable.load(make_table(tmp_path, [["bible", "Johannis", "Johannes"]]))
        n = write_open([("Johannis", "Johannes Joh", 3, "")], "bible",
                       path=open_path, table=table)
        assert n == 0
        assert len(read_rows(open_path)) == 1


class TestCli:
    def test_check_prints_rows(self, tmp_path, capsys):
        path = make_table(tmp_path, [["bible", "Johannis", "Johannes"]])
        rc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "--decisions", str(path)],
            capture_output=True, text=True,
        )
        assert rc.returncode == 0
        assert "bible\tJohannis\tJohannes\tglobal" in rc.stdout
        assert "1 Entscheidungen" in rc.stderr

    def test_check_fails_on_bad_kind(self, tmp_path):
        path = make_table(tmp_path, [["quantum", "x", "y"]])
        rc = subprocess.run(
            [sys.executable, str(SCRIPT), "--check", "--decisions", str(path)],
            capture_output=True, text=True,
        )
        assert rc.returncode != 0
        assert "unbekanntes kind" in rc.stderr
