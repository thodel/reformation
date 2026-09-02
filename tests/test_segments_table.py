"""Die Segment-JSON muss der handkorrigierten Tabelle folgen.

`segment_print.py` schreibt beides, aber die TSV wird danach von Hand
korrigiert - Commit 64a7a5f7 hat mit dem Kolumnentitel als Beleg vier
Thesenzuweisungen richtiggestellt. Die JSON bekam das nie und fuehrte
seither eigene Grenzen (These 9 ab 466 statt 465, gar keine These 10)
sowie 16 titellose Segmente. `build_print_anchors.py` liest die JSON und
musste den Beginn der zehnten These deshalb aus der Position erschliessen.

Diese Tests halten die beiden Dateien zusammen. Wer die Segmentierung neu
erkennen laesst, sieht hier sofort, dass er die Handkorrektur verwirft.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_print_anchors import load_segments, thesis_start_pages  # noqa: E402

SEGMENTS = ROOT / "data" / "segments"
TSV = SEGMENTS / "druck_1528_segments.tsv"


def table_rows() -> list[dict]:
    with TSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def test_json_folgt_der_tabelle():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "segments_json_from_table.py"),
         "--check"], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_jedes_segment_ist_beschrieben():
    """Ein titelloses Segment ist ein Loch in der Erschliessung."""
    ohne = [s["segment"] for s in load_segments()["segments"]
            if not (s.get("title") or "").strip()]
    assert not ohne, f"Segmente ohne Titel: {ohne}"


def test_alle_zehn_thesen_sind_verortet():
    """Fehlt eine, raet build_print_anchors.py ihren Beginn aus der Position."""
    starts = thesis_start_pages(load_segments())
    assert sorted(starts) == list(range(1, 11)), starts
    # Die Handkorrektur, mit dem Kolumnentitel belegt: die zehnte
    # Schlussrede beginnt auf S. 482, nicht auf der positionell
    # erschlossenen 485.
    assert starts[9] == 465 and starts[10] == 482, starts


def test_segmente_decken_den_druck_monoton():
    rows = table_rows()
    letzte = 0
    for row in rows:
        von, bis = int(row["first_page"]), int(row["last_page"])
        assert von > letzte, f"Segment {row['segment']} laeuft rueckwaerts"
        assert bis >= von
        letzte = bis
    assert int(rows[-1]["last_page"]) == 496


def test_thesen_laufen_aufsteigend():
    """Eine These, die nach einer hoeheren wieder auftaucht, ist ein Fehler
    in der Zuweisung - genau der, den 64a7a5f7 behoben hat."""
    hoechste = 0
    for row in table_rows():
        t = row["thesis"].strip()
        if not t.isdigit():
            continue
        assert int(t) >= hoechste, f"These {t} nach These {hoechste}"
        hoechste = int(t)
