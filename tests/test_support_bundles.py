"""Stützpakete (P2, #75): das Paket muss liefern, was die Lesung braucht.

Der Kerntest ist inhaltlich, nicht formal: für Hertwig S.700 - eine
gesichtete, aber untranskribierte Seite, deren Rede ("Philippus der Apostel
hatte eine Frau") bekannt ist - muss die gelieferte Druckpassage genau dieses
Argument enthalten. Besteht der Test, hat die Kette Ankerkarte -> Passage
end-to-end getragen; formale Schema-Checks allein können das nicht zeigen.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_support_bundles.py"


def run(*args, tmp=None):
    cmd = [sys.executable, str(SCRIPT), *args]
    if tmp:
        cmd += ["--out", str(tmp)]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


@pytest.fixture(scope="module")
def hertwig_bundles(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("support")
    # --all: seit dem HTR-Lauf vom 24.10.2026 sind diese Hertwig-Seiten
    # transkribiert, und ohne --all bekommt eine transkribierte Seite kein
    # Paket (das prueft test_transkribierte_seiten_ausgeschlossen). Hier
    # geht es um den Inhalt des Pakets, nicht um die Auswahl.
    result = run("a_v_1443_hertwig", "--pages", "700,714", "--all", tmp=tmp)
    assert result.returncode == 0, result.stderr
    return tmp / "a_v_1443_hertwig"


def test_passage_traegt_das_bekannte_argument(hertwig_bundles):
    bundle = json.loads((hertwig_bundles / "page_700.json").read_text(encoding="utf-8"))
    text = " ".join(p["original"] for p in bundle["druck_passage"])
    # Die Sichtung las auf Hertwig 700 die Philippus-Stelle; der Druck traegt
    # sie auf S.473. Liegt sie nicht in der Passage, ist die Ankerkette
    # gerissen - egal wie gueltig das JSON aussieht.
    assert "wyb habe gehabt" in text.replace("ſ", "s").replace("ó", "o") \
        or "Philippo" in text, "Philippus-Argument nicht in der Passage"


def test_paket_nennt_grundsatz_und_anker(hertwig_bundles):
    bundle = json.loads((hertwig_bundles / "page_700.json").read_text(encoding="utf-8"))
    assert "niemals Vorlage" in bundle["grundsatz"]
    a = bundle["anker"]
    assert a["druck_von"] <= a["druck_bis"]
    assert a["quelle"] in ("alignment", "landmark", "interpolation",
                           "terminal", "unbestimmt")
    assert bundle["druck_passage"], "leere Passage"
    for p in bundle["druck_passage"]:
        assert p["original"] and p["normalisiert"]


def test_landmarken_umfeld_dabei(hertwig_bundles):
    bundle = json.loads((hertwig_bundles / "page_700.json").read_text(encoding="utf-8"))
    seiten = {l["seite"] for l in bundle["landmarken_umfeld"]}
    assert 688 in seiten, "These-9-Landmarke fehlt im Umfeld"


def test_transkribierte_seiten_ausgeschlossen(tmp_path):
    # Hertwig S.3 ist transkribiert: ohne --all darf kein Paket entstehen.
    result = run("a_v_1443_hertwig", "--pages", "3", tmp=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "a_v_1443_hertwig" / "page_3.json").exists()
    # Mit --all (Pilotmessung) schon.
    result = run("a_v_1443_hertwig", "--pages", "3", "--all", tmp=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "a_v_1443_hertwig" / "page_3.json").exists()


def breitester_anker() -> tuple[str, int, int]:
    """(Zeuge, Seite, Breite) des breitesten Ankerbereichs ueber alle
    Handschriften. Frueher stand hier fest Hertwig 300, mitten in dessen
    grosser Luecke; seit dem HTR-Lauf vom 24.10.2026 ist Hertwig durchgehend
    abgeglichen und der Bereich dort 0 breit. Welche Handschrift noch eine
    Luecke hat, wechselt mit jedem Lauf der Pipeline - also suchen."""
    best = ("", 0, -1)
    for karte in sorted((ROOT / "data" / "disputation").glob("a_v_*/print_anchors.json")):
        witness = karte.parent.name
        for a in json.loads(karte.read_text(encoding="utf-8"))["pages"]:
            breite = a["druck_bis"] - a["druck_von"]
            if breite > best[2]:
                best = (witness, a["page"], breite)
    return best


def test_kappung_bei_breitem_anker(tmp_path):
    # Bei einem breiten Bereich muss der Text gekappt und die Kappung
    # ausgewiesen sein.
    witness, page, breite = breitester_anker()
    if breite <= 24:
        pytest.skip("keine Handschrift hat mehr einen breiten Ankerbereich")
    result = run(witness, "--pages", str(page), "--all", tmp=tmp_path)
    assert result.returncode == 0, result.stderr
    bundle = json.loads((tmp_path / witness / f"page_{page}.json")
                        .read_text(encoding="utf-8"))
    assert bundle["anker"]["druck_bis"] - bundle["anker"]["druck_von"] == breite
    assert bundle["text_gekappt"] is True
    assert len(bundle["druck_passage"]) <= 12
