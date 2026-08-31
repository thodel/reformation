#!/usr/bin/env python3
"""Erschliessungsgrad je Zeuge: wie viel Text steht wirklich da (Weg 3 aus #70).

Die Edition zeigt zehn Zeugen und blättert durch 3 666 Handschriftenseiten;
lesbarer Text steht auf einem Bruchteil davon. Ohne Ausweis wirkt die
Übersicht vollständiger, als der Bestand ist - das ist der Punkt von #70,
Weg 3: "dann sollte die Übersicht pro Handschrift den Erschliessungsgrad
nennen, damit niemand vollständigen Text erwartet".

Zwei Nenner, beide ehrlich
--------------------------
Ein Prozentsatz gegen ALLE Blätter bestraft eine Handschrift für ihre
Leerseiten: A V 1444 hat 87 unbeschriebene Blätter, die nie Text tragen
werden. Ein Prozentsatz gegen die BESCHRIEBENEN Blätter (Tintenmessung,
< 1 % Tinte = leer) misst, was tatsächlich fehlt. Ausgegeben werden beide;
die Anzeige nennt den zweiten, weil er die Frage beantwortet, die ein
Leser stellt.

Was als erschlossen zählt
-------------------------
Eine Seite mit mindestens TEXT_MIN_CHARS Zeichen Text ausserhalb der
Markdown-Überschrift - dieselbe Schwelle wie in den Stützpaketen (P2) und
in der Lesehilfe des Viewers (P4). Ein Stub "# Seite 12" ohne Körper ist
keine Transkription; er sah im Viewer lange wie eine aus.

Die Zahlen werden VERSIONIERT (anders als die Stütz- und t2i-Pakete): der
Viewer kann sie zur Laufzeit nicht selbst zählen, ohne 3 666 Dateien zu
laden. Gegen das Drift-Risiko einer zweiten Wahrheit steht ein Test, der
die Datei neu berechnet und auf Gleichheit prüft - stimmt sie nicht mehr,
ist die CI rot statt die Website falsch.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"
INK = DISPUTATION / "ink_coverage.json"
OUT = DISPUTATION / "coverage.json"

TEXT_MIN_CHARS = 20   # wie in build_support_bundles.py und der Lesehilfe
INK_BLANK = 0.01

# Reihenfolge wie in der Zeugentabelle des Viewers. Die Pfade folgen dem
# Viewer: nur der Basistext und die Handschriften liegen unter
# data/disputation/, die uebrigen Drucke unter data/prints/.
WITNESSES = [
    ("druck_1528", "data/disputation/druck_1528"),
    ("druck_1528_04", "data/prints/druck_1528_04"),
    ("druck_1608_bern", "data/prints/druck_1608_bern"),
    ("druck_1608_zuerich", "data/prints/druck_1608_zuerich"),
    ("druck_1701", "data/prints/druck_1701"),
    ("a_v_1447_schlussredaktion", "data/disputation/a_v_1447_schlussredaktion"),
    ("a_v_1443_hertwig", "data/disputation/a_v_1443_hertwig"),
    ("a_v_1444_cyro", "data/disputation/a_v_1444_cyro"),
    ("a_v_1445_schoeni", "data/disputation/a_v_1445_schoeni"),
    ("a_v_1446_ruemlang", "data/disputation/a_v_1446_ruemlang"),
]


def transcribed_pages(base: str) -> set[int]:
    """Seiten mit echtem Text - aus git, nicht aus dem Dateisystem.

    Der Sparse-Checkout der CI holt data/ zwar, aber die Lektion aus PR #77
    steht: was gezählt wird, muss aus versionierten Daten kommen und darf
    nicht davon abhängen, was zufällig auf der Platte liegt. `git ls-files`
    plus Inhalt aus dem Arbeitsbaum ist der Kompromiss - die Dateiliste ist
    autoritativ, ungetrackte Dateien zählen nie mit.
    """
    rel = f"{base}/transcriptions"
    listed = subprocess.run(["git", "ls-files", rel], cwd=ROOT,
                            capture_output=True, text=True).stdout.split()
    pages = set()
    for name in listed:
        m = re.search(r"page_(\d+)\.md$", name)
        if not m:
            continue
        path = ROOT / name
        if not path.exists():
            continue
        body = re.sub(r"^#.*$", "", path.read_text(encoding="utf-8"), flags=re.M)
        if len(body.strip()) >= TEXT_MIN_CHARS:
            pages.add(int(m.group(1)))
    return pages


def build() -> dict:
    ink_raw = json.loads(INK.read_text(encoding="utf-8")).get("witnesses", {})
    ink = {w: {int(k): v for k, v in p.items()} for w, p in ink_raw.items()}

    out = {}
    for witness, base in WITNESSES:
        tr = transcribed_pages(base)
        entry = {"transkribiert": len(tr)}
        scores = ink.get(witness, {})
        if scores:
            # Handschriften: die Tintenmessung kennt den ehrlichen Nenner.
            beschrieben = sum(1 for v in scores.values() if v >= INK_BLANK)
            entry["blaetter"] = len(scores)
            entry["beschrieben"] = beschrieben
            entry["leer"] = len(scores) - beschrieben
            entry["anteil_beschrieben"] = (round(len(tr) / beschrieben, 4)
                                           if beschrieben else 0.0)
        # Drucke bekommen hier KEINEN Nenner: die Seitenzahl des
        # digitalisierten Exemplars steht bereits in der Zeugentabelle des
        # Viewers, und sie hier zu wiederholen wäre genau die zweite
        # Wahrheit, die dieses Skript sonst vermeidet. Der Viewer rechnet
        # gegen seine eigene Angabe.
        out[witness] = entry

    return {
        "erzeugt_von": "scripts/build_coverage.py",
        "schwelle_zeichen": TEXT_MIN_CHARS,
        "hinweis": "anteil_beschrieben misst gegen die beschriebenen "
                   "Blätter (Tintenmessung), nicht gegen alle - Leerseiten "
                   "tragen nie Text und sollen den Grad nicht druecken.",
        "witnesses": out,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="nur pruefen, ob die versionierte Datei stimmt")
    args = ap.parse_args()

    data = build()
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"

    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("coverage.json ist veraltet - "
                  "scripts/build_coverage.py neu laufen lassen")
            return 1
        print("coverage.json ist aktuell")
        return 0

    OUT.write_text(text, encoding="utf-8")
    for w, e in data["witnesses"].items():
        if "beschrieben" in e:
            print(f"  {w:28} {e['transkribiert']:4} von {e['beschrieben']:4} "
                  f"beschriebenen ({e['anteil_beschrieben']*100:5.1f} %, "
                  f"{e['leer']} leer)")
        else:
            print(f"  {w:28} {e['transkribiert']:4} Seiten mit Text")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
