"""Der ausgewiesene Erschliessungsgrad muss stimmen (#70, Weg 3).

Die Zahlen sind versioniert, damit der Viewer sie laden kann, ohne 3 666
Dateien zu zaehlen - und genau deshalb koennen sie veralten. Der erste
Test hier ist der wichtige: er baut die Datei neu und vergleicht. Driftet
sie, ist die CI rot, statt dass die Website eine falsche Zahl behauptet.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_coverage  # noqa: E402

COVERAGE = ROOT / "data" / "disputation" / "coverage.json"
INDEX = ROOT / "index.html"

MANUSCRIPTS = ["a_v_1443_hertwig", "a_v_1444_cyro", "a_v_1445_schoeni",
               "a_v_1446_ruemlang", "a_v_1447_schlussredaktion"]


def test_versionierte_datei_ist_aktuell():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_coverage.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_handschriften_tragen_beide_nenner():
    data = json.loads(COVERAGE.read_text(encoding="utf-8"))["witnesses"]
    for key in MANUSCRIPTS:
        entry = data[key]
        assert entry["beschrieben"] + entry["leer"] == entry["blaetter"], key
        assert entry["transkribiert"] <= entry["beschrieben"], (
            f"{key}: mehr Transkriptionen als beschriebene Blätter - "
            "entweder zählt eine Leerseite falsch oder der Nenner ist kaputt")


def test_drucke_bekommen_keinen_eigenen_nenner():
    """Die Seitenzahl steht in der Zeugentabelle; hier waere sie die zweite
    Wahrheit, gegen die dieses Skript sonst antritt."""
    data = json.loads(COVERAGE.read_text(encoding="utf-8"))["witnesses"]
    for key, entry in data.items():
        if key.startswith("druck_"):
            assert "beschrieben" not in entry, key
            assert entry["transkribiert"] > 0, key


def test_der_befund_aus_70_steht_noch():
    """Vier Abschriften weit unter der Haelfte, A V 1447 fast vollstaendig.

    Kippt das, ist entweder Text dazugekommen (dann gehoert #70 neu
    bewertet) oder die Messung ist kaputt - beides will gesehen werden.
    """
    data = json.loads(COVERAGE.read_text(encoding="utf-8"))["witnesses"]
    for key in MANUSCRIPTS[:4]:
        assert data[key]["anteil_beschrieben"] < 0.5, key
    assert data["a_v_1447_schlussredaktion"]["anteil_beschrieben"] > 0.9


def test_schwelle_ist_die_der_lesehilfe():
    """20 Zeichen - dieselbe Grenze wie in den Stuetzpaketen und im Viewer.

    Liefen die auseinander, waere eine Seite in der Uebersicht erschlossen
    und im Lesebereich nicht.
    """
    assert build_coverage.TEXT_MIN_CHARS == 20
    from build_support_bundles import TEXT_MIN_CHARS as BUNDLE_MIN
    assert BUNDLE_MIN == build_coverage.TEXT_MIN_CHARS
    assert 'length < 20' in INDEX.read_text(encoding="utf-8")


def test_viewer_zeigt_die_spalte_und_den_vorbehalt():
    html = INDEX.read_text(encoding="utf-8")
    assert "<th>Erschliessung</th>" in html
    assert 'id="coverage-note"' in html
    assert "data/disputation/coverage.json" in html
    # Der Vorbehalt ist der Punkt der Uebung: erkannt heisst nicht ediert.
    assert "nicht, dass er ediert oder geprüft wäre" in html
    # Ein Inline-Span nimmt keine Breite an - der Balken bliebe leer.
    assert ".cov-fill { display: block;" in html
