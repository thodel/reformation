"""Die Tagestabelle des Drucks von 1528 muss zum Druck und zur Segmenttabelle passen.

Der Druck datiert jede Sitzung mit einer Überschrift ("Am xv. tag Jenners") und
nennt einmal einen Tag ohne Sitzung. `data/segments/druck_1528_days.tsv` hält
diese Marker mit Seite und Zeile fest; die Website gliedert das
Inhaltsverzeichnis danach. Die Tabelle ist von Hand gepflegt, darum prüfen die
Tests, was sich prüfen lässt: dass jeder Marker auf der genannten Zeile steht,
dass die Wochentage zum julianischen Kalender stimmen, dass die Sitzungstage
den Druck lückenlos abdecken und dass die genannten Schlussreden mit den
Thesengrenzen der Segmenttabelle übereinstimmen.
"""

from __future__ import annotations

import csv
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAYS = ROOT / "data" / "segments" / "druck_1528_days.tsv"
SEGMENTS = ROOT / "data" / "segments" / "druck_1528_segments.tsv"
PAGES = ROOT / "data" / "disputation" / "druck_1528" / "transcriptions"

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def sessions() -> list[dict]:
    return [r for r in rows(DAYS) if r["first_page"]]


def test_marker_steht_auf_der_genannten_zeile():
    for row in rows(DAYS):
        lines = (PAGES / f"page_{row['marker_page']}.md").read_text(encoding="utf-8").splitlines()
        line = lines[int(row["marker_line"]) - 1].lower()
        assert "tag" in line or "januar" in line or "merz" in line, (row["date"], line)


def test_wochentag_ist_julianisch_richtig():
    # 1528 gilt der julianische Kalender; zehn Tage Abstand zum gregorianischen.
    for row in rows(DAYS):
        y, m, d = (int(x) for x in row["date"].split("-"))
        gregorian = datetime.date(y, m, d) + datetime.timedelta(days=10)
        assert row["weekday"] == WEEKDAYS[gregorian.weekday()], row["date"]


def test_daten_laufen_aufsteigend():
    dates = [r["date"] for r in rows(DAYS)]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))


def test_sitzungstage_decken_den_druck_lueckenlos():
    """Jeder Tag reicht bis zur Markerseite des nächsten; die Grenzseite
    gehört zu beiden."""
    days = sessions()
    assert days[0]["date"] == "1528-01-07" and days[-1]["date"] == "1528-01-26"
    for a, b in zip(days, days[1:]):
        assert int(a["first_page"]) == int(a["marker_page"])
        assert int(a["last_page"]) == int(b["marker_page"]), (a["date"], b["date"])
        assert int(a["pages"]) == int(a["last_page"]) - int(a["first_page"]) + 1
    assert int(days[-1]["last_page"]) == 489  # "Hiemit ist diß gesprech beschlossen"


def test_pause_am_22_januar():
    pause = [r for r in rows(DAYS) if "nit gedi" in r["printed"]]
    assert [r["date"] for r in pause] == ["1528-01-22"]
    assert not pause[0]["first_page"]


def test_schlussreden_folgen_der_segmenttabelle():
    thesis_pages: dict[int, set[int]] = {}
    for seg in rows(SEGMENTS):
        if seg["thesis"].strip().isdigit():
            thesis_pages.setdefault(int(seg["thesis"]), set()).update(
                range(int(seg["first_page"]), int(seg["last_page"]) + 1))
    for day in sessions():
        span = set(range(int(day["first_page"]), int(day["last_page"]) + 1))
        expected = sorted(t for t, pages in thesis_pages.items() if pages & span)
        listed = sorted(int(t) for t in day["theses"].split(",") if t.strip())
        # Die Segmenttabelle lässt eine These auf der Seite beginnen, auf der
        # ihr Wortlaut steht; der Druck setzt die Überschrift zum Teil eine
        # Seite früher (2. These S. 159, 5. These S. 355). Ein Unterschied um
        # die Grenzseite ist deshalb erlaubt, ein fehlender oder zusätzlicher
        # Tag nicht.
        assert set(listed) >= set(expected) or set(listed) <= set(expected), (day["date"], listed, expected)
        assert len(set(listed) ^ set(expected)) <= 1, (day["date"], listed, expected)
