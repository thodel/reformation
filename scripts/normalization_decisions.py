#!/usr/bin/env python3
"""
Entscheidungstabelle für Normalisierung: Menschenentscheidungen, gegen die
die Skripte nie entscheiden (#46).

`data/normalization/decisions.tsv` wird von Menschen im Spreadsheet oder
im Editor gepflegt und mit der Recherche versioniert. Die Register-Skripte
fragen sie vor ihren Ähnlichkeitsschwellwerten: eine Zeile
`bible  Matthi  Matthäus` erzwingt den Zusammenzug, ein leeres `to` ist die
Entscheidung «passt nicht».

Die Skripte schlagen vor, entscheiden aber nie gegen einen Eintrag:
1. Ein Eintrag schlägt den Ähnlichkeitsschwellwert.
2. Entscheidungen werden nie überschrieben: Läufe tragen die Tabelle weiter
   und ergänzen nur Vorschläge für noch nicht Entschiedenes.
3. Jeder Lauf schreibt die offenen Fälle nach `data/normalization/open.tsv`,
   sortiert nach Häufigkeit — die Arbeitsliste, die ein Mensch von oben
   durcharbeitet. Ein Lauf ersetzt nur die Zeilen seiner eigenen Art.

Spalten:  kind  from  to  scope  decided_by  decided_on  note
  kind   orthography | person | bible
  from   die beobachtete Form (im normalisierten, kleingeschriebenen
         Vergleichsformat abgeglichen)
  to     die entschiedene Form; leer = «keine Zusammenführung» bzw.
         «passt nicht»
  scope  global (Standard) oder ein Zeugenschlüssel wie a_v_1443_hertwig;
         zeugenspezifische Einträge schlagen globale

Ein unbekanntes `kind` oder ein leeres `from` ist ein Fehler: die Skripte
versagen laut, statt die Tabelle still zu ignorieren.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize_orthography import normalize  # noqa: E402

KINDS = ("orthography", "person", "bible")
HEADER = ("kind", "from", "to", "scope", "decided_by", "decided_on", "note")
OPEN_HEADER = ("kind", "from", "suggestion", "count", "note")

ROOT = Path(__file__).resolve().parents[1]
NORM_DIR = ROOT / "data" / "normalization"
DECISIONS_FILE = NORM_DIR / "decisions.tsv"
OPEN_FILE = NORM_DIR / "open.tsv"

# Pro Lauf landen höchstens so viele offene Fälle pro Art in open.tsv;
# darunter liegt Rauschen. Das ist eine Display-Grenze, keine Entscheidung:
# nichts wird dadurch zusammengeführt oder weggelassen.
OPEN_CAP = 50


@dataclass(frozen=True)
class Decision:
    kind: str
    frm: str
    to: str
    scope: str
    decided_by: str
    decided_on: str
    note: str


def norm_key(text: str) -> str:
    """Das Vergleichsformat: normalisiert, kleingeschrieben, Wort für Wort.

    Die i/j-Faltung des Normalisators ist grössenbuchstabenabhängig; ein
    zusätzlicher j→i-Schritt lässt «Johannes» und «johannes» auf denselben
    Schlüssel laufen, damit Einträge und Text immer aufeinander treffen.
    """
    return " ".join(
        normalize(w).normalized.lower().replace("j", "i") for w in text.strip().split()
    )


def load_decisions(path: Path | str = DECISIONS_FILE) -> list[Decision]:
    """Liest decisions.tsv; eine fehlende Datei ist die leere Tabelle."""
    path = Path(path)
    if not path.exists():
        return []
    decisions: list[Decision] = []
    with open(path, encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.reader(fh, delimiter="\t"), start=1):
            if i == 1 and row and row[0].strip().lower() == "kind":
                continue
            if not row or not any(c.strip() for c in row):
                continue
            cells = [c.strip() for c in row]
            cells += [""] * (7 - len(cells))
            kind, frm, to, scope, by, on, note = cells[:7]
            if kind not in KINDS:
                raise ValueError(
                    f"{path.name} Zeile {i}: unbekanntes kind {kind!r}"
                    f" (erlaubt: {', '.join(KINDS)})"
                )
            if not frm:
                raise ValueError(f"{path.name} Zeile {i}: from darf nicht leer sein")
            decisions.append(Decision(kind, frm, to, scope or "global", by, on, note))
    return decisions


class DecisionTable:
    """Nachschlageindex über decisions.tsv."""

    def __init__(self, decisions: list[Decision]):
        self.decisions = decisions
        self._index: dict[tuple[str, str, str], Decision] = {
            (d.kind, d.scope, norm_key(d.frm)): d for d in decisions
        }

    @classmethod
    def load(cls, path: Path | str = DECISIONS_FILE) -> "DecisionTable":
        return cls(load_decisions(path))

    def lookup(self, kind: str, frm: str, witness: str | None = None) -> Decision | None:
        """Zeugenspezifischer Eintrag schlägt globaler; sonst global."""
        key = norm_key(frm)
        if witness:
            hit = self._index.get((kind, witness, key))
            if hit is not None:
                return hit
        return self._index.get((kind, "global", key))

    def is_decided(self, kind: str, frm: str) -> bool:
        """Irgendein Eintrag zu dieser Form (jeder scope): vom Tisch."""
        key = norm_key(frm)
        return any(k[0] == kind and k[2] == key for k in self._index)


def write_open(
    cases: list[tuple[str, str, int, str]],
    kind: str,
    path: Path | str = OPEN_FILE,
    table: DecisionTable | None = None,
    cap: int = OPEN_CAP,
) -> int:
    """Schreibt die offenen Fälle einer Art nach open.tsv.

    cases: (beobachtete Form, Vorschlag, Anzahl Nennungen, Notiz).
    Ersetzt die Zeilen dieser Art, behält die anderer (bis deren nächster
    Lauf), sortiert die ganze Liste nach Häufigkeit und liest Fälle, die
    schon entschieden sind, nicht mehr. Liefert die Anzahl geschriebener Zeilen.
    """
    path = Path(path)
    if table is None:
        table = DecisionTable.load()
    rows: list[list[str]] = []
    for frm, suggestion, count, note in cases:
        if table.is_decided(kind, frm):
            continue
        rows.append([kind, frm, suggestion, str(count), note])
    rows.sort(key=lambda r: (-int(r[3]), r[0], r[1]))
    rows = rows[:cap]
    written = len(rows)
    if path.exists():
        with open(path, encoding="utf-8", newline="") as fh:
            for row in list(csv.reader(fh, delimiter="\t"))[1:]:
                if row and row[0] != kind:
                    rows.append(row)
        rows.sort(key=lambda r: (-int(r[3]), r[0], r[1]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(OPEN_HEADER)
        writer.writerows(rows)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decisions",
        default=str(DECISIONS_FILE),
        help="Pfad zur decisions.tsv (Standard: %(default)s)",
    )
    parser.add_argument(
        "--check", action="store_true", help="Tabelle validieren und ausgeben"
    )
    args = parser.parse_args(argv)
    if not args.check:
        parser.print_help()
        return 1
    decisions = load_decisions(args.decisions)
    for d in decisions:
        print(f"{d.kind}\t{d.frm}\t{d.to}\t{d.scope}")
    print(f"{len(decisions)} Entscheidungen", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
