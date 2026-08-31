"""Die Text2Image-Pakete (P6, #75) müssen tragen, was das README verspricht.

Drei Dinge sind hier abgesichert: die Portionierung deckt den Druck
lückenlos und überlappungsfrei (sonst fehlt in Transkribus Text oder er
kommt doppelt an), der Referenztext ist frei von Transkriptionsartefakten
(eine "Seite [485]"-Zeile wäre eine Zeile, die Text2Image im Bild nie
finden kann), und die ms-Hypothesen wandern monoton mit dem Druck (eine
rückläufige Hypothese hiesse, die Ankerkarte wird falsch gelesen).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_print_anchors import load_segments  # noqa: E402
from build_t2i_packages import (  # noqa: E402
    BASE_LAST_PAGE,
    MAX_PAGES,
    print_page_text,
    split_at_segments,
    thesis_units,
)


def all_parts():
    segments = load_segments()
    return [p for u in thesis_units(segments)
            for p in split_at_segments(u, segments, MAX_PAGES)]


def test_portionierung_deckt_den_druck_lueckenlos():
    parts = all_parts()
    covered = []
    for p in parts:
        assert p["von"] <= p["bis"], p
        covered.extend(range(p["von"], p["bis"] + 1))
    assert covered == list(range(1, BASE_LAST_PAGE + 1)), (
        "Lücke oder Überlappung in der Portionierung")


def test_teile_respektieren_max_pages():
    for p in all_parts():
        assert p["bis"] - p["von"] + 1 <= MAX_PAGES, p


def test_teilung_schneidet_an_segmentgrenzen():
    segments = load_segments()
    seg_ends = {s["last_page"] for s in segments["segments"]}
    for p in all_parts():
        # Jedes Teil-Ende ist entweder ein Einheiten-Ende (Thesengrenze,
        # per Konstruktion ein Segmentende) oder eine Segmentgrenze.
        assert p["bis"] in seg_ends or p["bis"] == BASE_LAST_PAGE, p


def test_referenztext_ohne_artefakte():
    """Stichprobe über die bekannten Artefaktseiten (485, 496)."""
    assert "Seite [" not in print_page_text(485)
    assert print_page_text(485)  # der echte Text der Seite bleibt
    assert print_page_text(496) == ""  # "no visible text"-Stub fällt weg


@pytest.fixture(scope="module")
def schoeni(tmp_path_factory):
    out = tmp_path_factory.mktemp("t2i")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_t2i_packages.py"),
         "a_v_1445_schoeni", "--out", str(out)],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    return out / "a_v_1445_schoeni"


def test_paket_vollstaendig(schoeni):
    manifest = json.loads((schoeni / "manifest.json").read_text())
    assert (schoeni / "README.md").exists()
    for row in manifest["dateien"]:
        assert (schoeni / row["datei"]).exists()
        assert (schoeni / "normalisiert" / row["datei"]).exists()
    # Die erste These beginnt mit Hallers Eröffnung - steht der Satz nicht
    # in der Datei, ist der Text der falschen Seite zugeordnet.
    assert "Die erste Schlufzred" in (schoeni / "these_01a.txt").read_text()


def test_grundsatz_und_pilotmessung_reisen_mit(schoeni):
    """Wer nur das Paket bekommt, muss beides trotzdem erfahren."""
    manifest = json.loads((schoeni / "manifest.json").read_text())
    assert "Hypothese, niemals Vorlage" in manifest["grundsatz"]
    readme = (schoeni / "README.md").read_text()
    assert "Hypothese, niemals Vorlage" in readme
    assert "0,60" in readme  # das Messergebnis, nicht nur seine Moral


def test_ms_hypothesen_monoton(schoeni):
    manifest = json.loads((schoeni / "manifest.json").read_text())
    ranges = [r["ms"] for r in manifest["dateien"] if r["ms"]]
    vons = [r["ms_von"] for r in ranges]
    bis = [r["ms_bis"] for r in ranges]
    assert vons == sorted(vons) and bis == sorted(bis), (
        "ms-Hypothese läuft gegen die Blattfolge")


def test_keine_seitenmarken_im_referenztext(schoeni):
    for txt in schoeni.glob("*.txt"):
        text = txt.read_text()
        assert not re.search(r"^Seite \[?\d+\]?\s*$", text, re.M), txt.name
        assert "no visible text" not in text.lower(), txt.name
