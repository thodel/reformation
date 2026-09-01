#!/usr/bin/env python3
"""Text2Image-Pakete: Druck-Referenztext für Transkribus, je Handschrift (P6, #75).

Der dauerhafte Weg aus dem Stützplan: statt Seiten abzutippen wird der
Drucktext in Transkribus mit dem Text2Image-Werkzeug auf die Handschriften-
zeilen aligniert, das Alignment reviewt, und aus der so gewonnenen Ground
Truth ein HTR-Modell auf genau diesen fünf Händen trainiert. Dieses Skript
liefert die Repo-Seite davon: den Referenztext, portioniert und mit der
Hypothese, welcher Handschriftenbereich ihn trägt.

Portionierung
-------------
Einheit ist die THESE (plus Vorspann), nicht das Einzelsegment: die
Thesengrenzen sind die härtesten Landmarken der Ankerkarte, und bei
Handschriften fast ohne Anker (Schöni: ±127 Druckseiten) wäre jede feinere
ms-Zuordnung Scheingenauigkeit. Lange Thesen werden an Segmentgrenzen in
Teile von höchstens --max-pages Druckseiten geschnitten — Segmentgrenzen
sind echte Struktur (Rednerwechsel), kein willkürlicher Schnitt.

Was eine Paketdatei enthält — und was nicht
-------------------------------------------
Reiner Lauftext. Keine Seitenmarken, keine Überschriften-Zeilen aus dem
Markdown, keine Transkriptionsartefakte: alles, was nicht Drucktext ist,
würde Text2Image als Zeilen anbieten, die es im Bild nie geben kann. Die
Seitenzuordnung steht im Manifest, nicht im Text. Die erfundenen
"Seite [485]"-Zeilen und der "no visible text"-Stub sind inzwischen an der
Quelle bereinigt (scripts/clean_print_transcriptions.py); die Filter unten
bleiben als Schutzgitter für einen künftigen Erkennungslauf stehen.

Pakete werden ERZEUGT, nicht versioniert (wie die Stützpakete, P2): sie
sind vollständig aus committeten Daten ableitbar. Standard-Ablage ist
.cache/t2i/.

Der Grundsatz gilt auch hier: Der Druck ist Hypothese, niemals Vorlage.
Die Pilotmessung (P3, #80) hat gemessen, dass der Druck den INHALT einer
Handschriftenseite verortet, aber nicht ihren Wortlaut diktiert (mediane
Wortdeckung 0,60). Für Text2Image ist das kein Todesurteil, sondern die
Erwartungshaltung: das Werkzeug matcht nur Zeilen, die es sicher zuordnen
kann — treue Kopierpassagen (dort lag die Deckung bei 0,88–0,96) liefern
Ground Truth, freie Passagen bleiben unaligniert liegen. Genau so soll es
sein; erzwungene Vollabdeckung wäre gefälschte GT.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_print_anchors import load_segments, thesis_start_pages  # noqa: E402
from normalize_orthography import normalize_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"
PRINT_TR = DISPUTATION / "druck_1528" / "transcriptions"
INK = DISPUTATION / "ink_coverage.json"
DEFAULT_OUT = ROOT / ".cache" / "t2i"

BASE_LAST_PAGE = 496
INK_BLANK = 0.01
MAX_PAGES = 50  # Druckseiten je Referenzdatei; lange Thesen werden geteilt

# Schutzgitter, keine laufende Reparatur: der Bestand ist bereinigt, aber
# ein neuer Erkennungslauf koennte solche Zeilen wieder erzeugen, und
# Text2Image bekaeme Zeilen angeboten, die im Bild nie stehen.
ARTIFACT_LINE = re.compile(r"^Seite \[?\d+\]?\s*$")
NO_TEXT_STUB = re.compile(r"no visible text", re.I)

WITNESSES = [
    "a_v_1443_hertwig",
    "a_v_1444_cyro",
    "a_v_1445_schoeni",
    "a_v_1446_ruemlang",
    "a_v_1447_schlussredaktion",
]


def print_page_text(nr: int) -> str:
    path = PRINT_TR / f"page_{nr}.md"
    if not path.exists():
        return ""
    body = re.sub(r"^#.*$", "", path.read_text(encoding="utf-8"), flags=re.M)
    if NO_TEXT_STUB.search(body):
        return ""
    lines = [ln for ln in body.splitlines() if not ARTIFACT_LINE.match(ln.strip())]
    return "\n".join(lines).strip()


def thesis_units(segments: dict) -> list[dict]:
    """Vorspann + zehn Thesen, lückenlos über S. 1–496."""
    starts = thesis_start_pages(segments)
    bounds = sorted(starts.items())  # [(1, 20), ..., (10, 485)]
    units = [{"key": "vorspann", "titel": "Vorspann (Ausschreiben, Schlussreden, Eröffnung)",
              "von": 1, "bis": bounds[0][1] - 1}]
    for i, (thesis, start) in enumerate(bounds):
        end = bounds[i + 1][1] - 1 if i + 1 < len(bounds) else BASE_LAST_PAGE
        titel = f"These {thesis}"
        if thesis == bounds[-1][0]:
            titel += " und Schluss"
        units.append({"key": f"these_{thesis:02}", "titel": titel,
                      "von": start, "bis": end})
    return units


def split_at_segments(unit: dict, segments: dict, max_pages: int) -> list[dict]:
    """Lange Einheiten an Segmentgrenzen in Teile <= max_pages schneiden."""
    if unit["bis"] - unit["von"] + 1 <= max_pages:
        return [dict(unit)]
    seg_ends = sorted(s["last_page"] for s in segments["segments"]
                      if unit["von"] <= s["last_page"] < unit["bis"])
    parts, start = [], unit["von"]
    while start <= unit["bis"]:
        limit = start + max_pages - 1
        cut = max([e for e in seg_ends if start <= e <= limit], default=None)
        end = unit["bis"] if limit >= unit["bis"] else (cut or limit)
        parts.append(dict(unit, von=start, bis=end))
        start = end + 1
    for i, p in enumerate(parts, 1):
        p["key"] = f"{unit['key']}{chr(96 + i)}"  # these_01a, these_01b, ...
        p["titel"] = f"{unit['titel']}, Teil {i}/{len(parts)}"
    return parts


def load_ink() -> dict[str, dict[int, float]]:
    raw = json.loads(INK.read_text(encoding="utf-8")).get("witnesses", {})
    return {w: {int(k): v for k, v in pages.items()} for w, pages in raw.items()}


def ms_range(karte: dict, ink_pages: dict[int, float],
             von: int, bis: int) -> dict | None:
    """Welche beschriebenen ms-Seiten kann dieser Druckbereich tragen?

    Überlappung der Ankerbereiche mit dem Druckbereich der Einheit. Bei
    ankerarmen Karten (Schöni) sind die Bereiche breit und die ms-Bereiche
    entsprechend gross — das ist die ehrliche Auskunft, keine Schwäche des
    Formats: wer in Transkribus aligniert, wählt lieber grosszügig und lässt
    das Werkzeug die Nicht-Treffer liegen.
    """
    hits = [e["page"] for e in karte["pages"]
            if e["druck_von"] <= bis and e["druck_bis"] >= von
            and ink_pages.get(e["page"], 1.0) >= INK_BLANK]
    if not hits:
        return None
    widths = [e["druck_bis"] - e["druck_von"] for e in karte["pages"]
              if e["page"] in set(hits)]
    return {"ms_von": min(hits), "ms_bis": max(hits), "seiten": len(hits),
            "median_unschaerfe": sorted(widths)[len(widths) // 2] // 2}


def readme(witness: str, rows: list[dict]) -> str:
    lines = [
        f"# Text2Image-Paket: {witness}",
        "",
        "Referenztext aus dem Druck vom März 1528 (druck_1528) für das",
        "Text2Image-Werkzeug von Transkribus. Ziel: Ground Truth für ein",
        "HTR-Modell auf dieser Hand, ohne abzutippen (P6 im Epic #75).",
        "",
        "**Der Druck ist Hypothese, niemals Vorlage.** Die Pilotmessung",
        "(#80) zeigt: der Druck verortet den Inhalt einer Seite, diktiert",
        "aber nicht ihren Wortlaut (mediane Wortdeckung 0,60; auf treuen",
        "Kopierpassagen 0,88–0,96). Für Text2Image heisst das: viele Zeilen",
        "werden NICHT matchen, und das ist richtig so — nur sicher",
        "alignierte Zeilen werden Ground Truth. Beim Review entscheidet",
        "der Buchstabenbefund, nie der Drucktext.",
        "",
        "## Arbeitsgang in Transkribus",
        "",
        "1. Auf den Zielseiten eine Basiserkennung mit einem generischen",
        "   Kurrent-Modell laufen lassen (Text2Image braucht eine",
        "   Zeilenerkennung als Gerüst).",
        "2. Text2Image mit der jeweiligen .txt-Datei auf dem angegebenen",
        "   ms-Seitenbereich starten. Lieber grosszügig wählen: was nicht",
        "   passt, bleibt unaligniert liegen.",
        "3. Alignierte Zeilen reviewen — gegen die Feder, nicht gegen den",
        "   Druck. Abweichung vom Druck ist Befund, kein Fehler.",
        "4. Aus den reviewten Seiten ein Modell auf dieser Hand trainieren;",
        "   die Ergebnisse kommen über den bestehenden Transkribus-Sync",
        "   zurück ins Repo.",
        "",
        "Die Dateien enthalten reinen Lauftext in Originalorthographie",
        "(kein Seitenumbruch-Marker, keine Kopfzeilen); unter",
        "`normalisiert/` liegt jede Datei zusätzlich mit aufgelöstem",
        "Nasalstrich und gefaltetem ſ, falls das Matching gegen die",
        "Basiserkennung damit besser trägt. Ground Truth wird die Fassung,",
        "die eingespielt und reviewt wird — im Zweifel die Original-",
        "fassung nehmen.",
        "",
        "## Dateien",
        "",
        "| Datei | Druck | ms-Hypothese | Unschärfe |",
        "|---|---|---|---|",
    ]
    for r in rows:
        ms = (f"S. {r['ms']['ms_von']}–{r['ms']['ms_bis']}"
              f" ({r['ms']['seiten']} beschriebene S.)" if r["ms"] else "—")
        unsch = f"±{r['ms']['median_unschaerfe']} Druckseiten" if r["ms"] else "—"
        lines.append(f"| {r['datei']} | S. {r['von']}–{r['bis']}"
                     f" ({r['titel']}) | {ms} | {unsch} |")
    lines += [
        "",
        "Die ms-Hypothese nennt alle beschriebenen Seiten, deren",
        "Ankerbereich (P1) den Druckbereich der Datei überlappt. Bei",
        "ankerarmen Handschriften sind diese Bereiche breit — das ist die",
        "ehrliche Auskunft der Karte, und Text2Image kommt damit zurecht.",
        "",
    ]
    return "\n".join(lines)


def build_witness(witness: str, parts: list[dict], ink: dict,
                  out_root: Path, stats_only: bool) -> dict:
    karte = json.loads((DISPUTATION / witness / "print_anchors.json")
                       .read_text(encoding="utf-8"))
    ink_pages = ink.get(witness, {})
    rows = []
    for part in parts:
        texts = [t for nr in range(part["von"], part["bis"] + 1)
                 if (t := print_page_text(nr))]
        rows.append({"datei": f"{part['key']}.txt", "titel": part["titel"],
                     "von": part["von"], "bis": part["bis"],
                     "druckseiten_mit_text": len(texts),
                     "zeichen": sum(len(t) for t in texts),
                     "ms": ms_range(karte, ink_pages, part["von"], part["bis"]),
                     "_text": "\n\n".join(texts)})

    covered = sum(1 for r in rows if r["ms"])
    print(f"  {witness:28} {len(rows):2} Dateien, "
          f"{covered:2} mit ms-Hypothese")
    if stats_only:
        return {}

    out = out_root / witness
    (out / "normalisiert").mkdir(parents=True, exist_ok=True)
    for r in rows:
        (out / r["datei"]).write_text(r["_text"] + "\n", encoding="utf-8")
        (out / "normalisiert" / r["datei"]).write_text(
            normalize_text(r["_text"]) + "\n", encoding="utf-8")
    manifest = {
        "witness": witness,
        "grundsatz": "Der Druck ist Hypothese, niemals Vorlage. "
                     "Buchstabenbefund schlägt Drucktext; Abweichung ist "
                     "Befund, kein Fehler.",
        "quelle": "druck_1528 (e-rara), Transkription korrigiert",
        "pilotmessung": "P3 (#80): mediane Wortdeckung 0,60 - der Druck "
                        "verortet Inhalt, diktiert keinen Wortlaut. "
                        "Unalignierte Zeilen sind erwartet.",
        "dateien": [{k: v for k, v in r.items() if k != "_text"}
                    for r in rows],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    (out / "README.md").write_text(readme(witness, rows), encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("witnesses", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-pages", type=int, default=MAX_PAGES)
    ap.add_argument("--stats-only", action="store_true")
    args = ap.parse_args()

    segments = load_segments()
    parts = [p for unit in thesis_units(segments)
             for p in split_at_segments(unit, segments, args.max_pages)]
    ink = load_ink()

    for witness in (args.witnesses or WITNESSES):
        build_witness(witness, parts, ink, args.out, args.stats_only)
    if not args.stats_only:
        try:
            shown = args.out.relative_to(ROOT)
        except ValueError:
            shown = args.out
        print(f"    -> {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
