#!/usr/bin/env python3
"""Die Segment-JSON aus der handkorrigierten Tabelle erzeugen (Vorarbeit zu P1, #75).

Warum es das gibt
-----------------
`segment_print.py` schreibt beides: die editierbare TSV-Tabelle und die
JSON daneben. Die Tabelle ist danach von Hand korrigiert worden - Commit
64a7a5f7 „Correct the thesis labels" hat vier Zeilen richtiggestellt, mit
dem Kolumnentitel als Beleg: die neunte Schlussrede laeuft ab S. 465, die
zehnte ab S. 482, und das Schlussstueck ab S. 491 gehoert zu keiner These.
Die JSON hat diese Korrektur nie bekommen. Sie fuehrt bis heute die
Maschinengrenzen (These 9 ab 466, keine These 10) und dazu 16 Segmente
ohne Titel, die in der Tabelle laengst beschrieben sind.

Das ist nicht folgenlos: `build_print_anchors.py` liest die JSON und muss
den Beginn der zehnten These deshalb aus der Position erschliessen - es
kam 485 heraus, wo die geprueften Daten 482 sagen. Genau dieser Behelf
war im Epic als Vorarbeit notiert.

Die Tabelle ist die Wahrheit
----------------------------
Sie ist die Datei, die von Hand gepflegt wird (der describe-Workflow
sagt es selbst: „the table is meant to be corrected by hand"). Die JSON
ist Ableitung fuer die Skripte. Dieses Skript stellt das Verhaeltnis her,
statt die Korrektur ein zweites Mal in die JSON zu tippen - und ein Test
haelt die beiden fortan zusammen.

Nicht verwechseln mit `segment_print.py`: das erkennt die Segmente neu
aus dem Text und ueberschreibt dabei die Grenzen. Wer das laufen laesst,
verwirft die Handkorrektur wieder.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = ROOT / "data" / "segments"

INT_FIELDS = ("segment", "first_page", "last_page", "pages")


def rows_to_segments(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            seg = {k: (int(row[k]) if k in INT_FIELDS else row[k])
                   for k in ("segment", "thesis", "first_page", "last_page",
                             "pages", "title", "summary")}
            # thesis bleibt Zahl, wo die Tabelle eine nennt, und "" sonst -
            # genau die Form, die build_print_anchors.py erwartet.
            thesis = row["thesis"].strip()
            seg["thesis"] = int(thesis) if thesis.isdigit() else ""
            out.append(seg)
    return out


def build(witness: str) -> list[dict]:
    return rows_to_segments(SEGMENTS / f"{witness}_segments.tsv")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("witness", nargs="?", default="druck_1528")
    ap.add_argument("--check", action="store_true",
                    help="nur pruefen, ob die JSON der Tabelle folgt")
    args = ap.parse_args()

    segments = build(args.witness)
    target = SEGMENTS / f"{args.witness}_segments.json"
    text = json.dumps({"witness": args.witness, "segments": segments},
                      ensure_ascii=False, indent=2) + "\n"

    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            print(f"{target.name} folgt der Tabelle nicht - "
                  "scripts/segments_json_from_table.py laufen lassen")
            return 1
        print(f"{target.name} folgt der Tabelle")
        return 0

    target.write_text(text, encoding="utf-8")
    ohne_titel = sum(1 for s in segments if not s["title"].strip())
    thesen = sorted({s["thesis"] for s in segments if s["thesis"] != ""})
    print(f"  {len(segments)} Segmente, {ohne_titel} ohne Titel, "
          f"Thesen {thesen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
