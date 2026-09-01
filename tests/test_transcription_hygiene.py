"""Keine erfundenen Kopfzeilen im transkribierten Text.

druck_1528 trug auf 456 seiner 496 Seiten eine Zeile "Seite [X]" bzw.
"Seite LXIII" mitten im Text - vom Erkennungsmodell dazugeschrieben, im
Druck nirgends vorhanden. Sie stand im Viewer, in den Stützpaketen und
in den Text2Image-Paketen, und `align_witnesses.py` musste sie beim
Vergleich eigens wegfiltern. Bereinigt mit
`scripts/clean_print_transcriptions.py`; diese Tests halten sie draussen.

Der zweite Test sichert die Konvention, die druck_1528 als einziger Zeuge
nicht hatte: Zeile 1 ist `# Seite N` mit der Seitenzahl der Edition -
also der, unter der zitiert wird.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from clean_print_transcriptions import ARTIFACT_HEAD, NO_TEXT_STUB, clean  # noqa: E402

WITNESS_DIRS = sorted(
    [p for p in (ROOT / "data" / "disputation").glob("*/transcriptions")]
    + [p for p in (ROOT / "data" / "prints").glob("*/transcriptions")])

PAGE_RE = re.compile(r"page_(\d+)\.md$")


def pages(directory: Path) -> list[Path]:
    """Nur die kanonischen Seiten.

    A V 1446 fuehrt daneben page_N_gemini.md - eine zweite, probeweise
    Erkennung, die der Viewer nicht laedt. Sie ist nicht der publizierte
    Text und wird hier nicht geprueft.
    """
    found = [p for p in directory.glob("page_*.md") if PAGE_RE.search(p.name)]
    return sorted(found, key=lambda p: int(PAGE_RE.search(p.name).group(1)))


@pytest.mark.parametrize("directory", WITNESS_DIRS,
                         ids=lambda p: p.parent.name)
def test_keine_erfundene_kopfzeile_im_text(directory):
    """Eine "Seite ..."-Zeile ohne Markdown-# ist Erfindung, kein Befund."""
    offenders = []
    for path in pages(directory):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if line.lstrip().startswith("#"):
                continue  # die echte Überschrift
            if ARTIFACT_HEAD.match(line):
                offenders.append(f"{path.name}:{i + 1}: {line!r}")
    assert not offenders, (
        f"{len(offenders)} erfundene Kopfzeilen, u. a. " + "; ".join(offenders[:5]))


@pytest.mark.parametrize("directory", WITNESS_DIRS,
                         ids=lambda p: p.parent.name)
def test_keine_modell_stubs(directory):
    """"There is no visible text in the image" ist keine Transkription."""
    offenders = [p.name for p in pages(directory)
                 if NO_TEXT_STUB.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"Stub-Antwort des Modells in: {offenders[:5]}"


@pytest.mark.parametrize("directory", WITNESS_DIRS,
                         ids=lambda p: p.parent.name)
def test_seitenzahl_der_ueberschrift_stimmt(directory):
    """Die Überschrift muss die Seite benennen, unter der zitiert wird.

    Eine falsche Zahl hier waere schlimmer als gar keine: sie sieht aus
    wie eine Zitierangabe.
    """
    wrong = []
    for path in pages(directory):
        nr = int(PAGE_RE.search(path.name).group(1))
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
        if not re.match(rf"^#+\s.*\bSeite {nr}\b", first):
            wrong.append(f"{path.name}: {first!r}")
    assert not wrong, f"{len(wrong)} Seiten mit falscher Überschrift: {wrong[:5]}"


def test_reiniger_ist_idempotent():
    """Ein zweiter Lauf darf nichts mehr aendern - sonst frisst er Text."""
    sample = ROOT / "data" / "disputation" / "druck_1528" / "transcriptions" / "page_103.md"
    once = clean(sample.read_text(encoding="utf-8"), 103)
    assert clean(once, 103) == once


def test_reiniger_verschont_echte_kolumnentitel():
    """"Die erst", "Schlußred." und die blosse gedruckte Foliierung sind
    Text der Seite und muessen bleiben - nur das Wort "Seite" davor ist
    erfunden."""
    text = "Seite LXIII\n**Schlußred.** LXIII\nsin/des Prouincials ampt\n"
    out = clean(text, 103)
    assert out.startswith("# Seite 103\n\n**Schlußred.** LXIII")
    assert "Prouincials" in out
    for keep in ("Die erst\nsomething\n", "IX\nsomething\n",
                 "Schlußred.\nsomething\n"):
        assert keep.splitlines()[0] in clean(keep, 7)
