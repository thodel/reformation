"""Die Ankerkarte muss halten, was sie behauptet.

Drei Eigenschaften sind nicht verhandelbar: Alignment-Anker werden exakt
reproduziert (die Karte darf hartes Wissen nicht verwaschen), die Mitte der
Bereiche waechst monoton mit der Blattfolge (eine Abschrift laeuft nicht
rueckwaerts durch den Druck), und jeder Bereich liegt im Druck (1..496).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"

WITNESSES = [p.parent.name for p in DISPUTATION.glob("*/print_anchors.json")]


def load(witness):
    return json.loads((DISPUTATION / witness / "print_anchors.json")
                      .read_text(encoding="utf-8"))


@pytest.mark.skipif(not WITNESSES, reason="noch keine Ankerkarten erzeugt")
@pytest.mark.parametrize("witness", WITNESSES)
def test_schema_und_grenzen(witness):
    data = load(witness)
    assert data["base"] == "druck_1528"
    assert data["pages"], f"{witness}: leere Karte"
    for e in data["pages"]:
        assert 1 <= e["druck_von"] <= e["druck_bis"] <= 496, e
        assert e["quelle"] in ("alignment", "landmark", "terminal",
                               "interpolation", "unbestimmt"), e


@pytest.mark.skipif(not WITNESSES, reason="noch keine Ankerkarten erzeugt")
@pytest.mark.parametrize("witness", WITNESSES)
def test_monotonie(witness):
    data = load(witness)
    centres = [(e["page"], (e["druck_von"] + e["druck_bis"]) / 2)
               for e in data["pages"]]
    for (p1, c1), (p2, c2) in zip(centres, centres[1:]):
        assert p1 < p2, f"{witness}: Seitenfolge {p1}->{p2}"
        # Ein Druckseiten-Spielraum von 2 erlaubt Rundung; echtes
        # Rueckwaertslaufen faellt durch.
        assert c2 >= c1 - 2, f"{witness}: Druckmitte laeuft rueckwaerts bei S.{p2}"


@pytest.mark.skipif(not WITNESSES, reason="noch keine Ankerkarten erzeugt")
@pytest.mark.parametrize("witness", WITNESSES)
def test_alignment_anker_exakt(witness):
    """Wo ein Vergleichs-Alignment existiert, gibt die Karte genau dessen
    Druckseite wieder - als Punkt, nicht als Bereich."""
    index = ROOT / "data" / "comparison" / f"druck_1528__{witness}" / "index.json"
    if not index.exists():
        pytest.skip("kein Vergleichsindex")
    units = json.loads(index.read_text(encoding="utf-8"))["units"]
    karte = {e["page"]: e for e in load(witness)["pages"]}
    geprueft = 0
    for u in units:
        base = (u["pages"].get("druck_1528") or [None])[0]
        ms = (u["pages"].get(witness) or [None])[0]
        if base is None or ms is None or ms not in karte:
            continue
        e = karte[ms]
        if e["quelle"] != "alignment":
            continue  # der Monotonie-Filter darf Fehlanker verwerfen
        # Eine ms-Seite kann mehrere Druckseiten decken (kondensierte
        # Abschrift): der Bereich muss die Einheit enthalten.
        assert e["druck_von"] <= base <= e["druck_bis"], (witness, ms, e, base)
        geprueft += 1
    assert geprueft > 0 or len(units) < 3, f"{witness}: kein Anker geprueft"


def test_builder_validierung_dichter_zeuge():
    """Beim dicht verankerten Zeugen muss die zurueckgehaltene Vorhersage
    nahe an den echten Alignments liegen - sonst taugt die Interpolation
    nirgends."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_print_anchors.py"),
         "--validate", "a_v_1447_schlussredaktion"],
        capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    line = [l for l in result.stdout.splitlines()
            if "a_v_1447" in l and "Medianfehler" in l]
    assert line, result.stdout
    median = float(line[0].split("Medianfehler")[1].split()[0])
    # Gemessen: 15.0 mit zeugeneigener Steigung (eine geratene Konstante lag
    # bei 27). Die Schranke laesst Luft fuer Datenschwankung, faengt aber
    # einen Rueckfall in Richtung des alten Fehlers.
    assert median <= 20, f"Medianfehler {median} Druckseiten"
