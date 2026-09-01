#!/usr/bin/env python3
"""Erkennungsartefakte aus den Drucktranskriptionen entfernen (#70-Nachlauf).

Warum es das gibt
-----------------
druck_1528 ist der einzige Zeuge der Edition, dessen Transkriptionen KEINE
Markdown-Überschrift tragen. Stattdessen steht auf 456 seiner 496 Seiten
eine erfundene Kopfzeile mitten im Text - "Seite [X]", "Seite LXIII",
"Seite 170" -, die das Erkennungsmodell dazugeschrieben hat. Auf den
sauberen Seiten 1-51 gibt es sie nicht; dort beginnt der Text direkt mit
dem echten Kolumnentitel ("Die erst", "Schlußred.", "IX"). Das Wort
"Seite" steht in diesem Druck nirgends.

Diese Zeilen sind in den Viewer und in die Stützpakete durchgeschlagen,
und `align_witnesses.py` musste sie beim Vergleich eigens wegfiltern -
ein Workaround beim Verbraucher für einen Fehler in den Daten. Hier wird
er an der Quelle behoben.

Was mit den Seitenzahlen darin passiert
---------------------------------------
Gemessen, nicht geraten: auf den ungeraden Scanseiten (Rectos) folgt die
römische Zahl der gedruckten Foliierung sehr genau (r = 0,99 über 180
Seiten). Auf den geraden Scanseiten (Versos), die im Druck gar keine Zahl
tragen, ist sie frei erfunden (r = 0,13). Eine Zeile, die zur Hälfte
Befund und zur Hälfte Erfindung ist, gehört nicht in den Text. Sie fällt
deshalb ganz weg; die echte Foliierung steht ohnehin auf vielen Seiten im
transkribierten Kolumnentitel darunter, und die verworfenen Werte bleiben
in der Git-Historie nachlesbar, falls je eine geprüfte
Foliierungskonkordanz gebaut wird.

Stattdessen bekommt jede Seite die Überschrift `# Seite N`, die jeder
andere Zeuge schon hat und die `scripts/recognize_prints.py` heute selbst
schreibt - N ist die Seitenzahl der Edition, also die, unter der zitiert
wird.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "data" / "disputation" / "druck_1528" / "transcriptions"

# Nur Zeile 1, nur "Seite" plus Zahlwerk. Inhaltszeilen wie "Die erst" oder
# ein blosses "IX" (die echte Foliierung, wie sie gedruckt steht) muessen
# ueberleben. Gegen den ganzen Bestand geprueft: trifft alle 456
# Artefaktzeilen und keine einzige Zeile sonst.
ARTIFACT_HEAD = re.compile(
    r"^\s*#*\s*Seite\s+[\[\(]?[IVXLCDMivxlcdmjJrRbBoOhHzZ0-9.\s]{1,20}[\]\)]?\s*$")

# Ein Stub des Erkennungsmodells, kein Text der Seite.
NO_TEXT_STUB = re.compile(r"no visible text", re.I)

PAGE_RE = re.compile(r"page_(\d+)\.md$")


def clean(text: str, page_nr: int) -> str:
    lines = text.splitlines()
    while lines and (not lines[0].strip() or ARTIFACT_HEAD.match(lines[0])):
        lines.pop(0)
    body = "\n".join(lines).strip()
    if NO_TEXT_STUB.search(body):
        body = ""   # leere Seite - eine ehrliche Luecke, kein Satz ueber sie
    return f"# Seite {page_nr}\n\n{body}\n" if body else f"# Seite {page_nr}\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = stubs = 0
    for path in sorted(args.directory.glob("page_*.md")):
        nr = int(PAGE_RE.search(path.name).group(1))
        before = path.read_text(encoding="utf-8")
        after = clean(before, nr)
        if after == before:
            continue
        changed += 1
        if NO_TEXT_STUB.search(before):
            stubs += 1
        if not args.dry_run:
            path.write_text(after, encoding="utf-8")

    verb = "waeren zu aendern" if args.dry_run else "geaendert"
    print(f"  {changed} Dateien {verb} ({stubs} Stub-Seiten geleert)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
