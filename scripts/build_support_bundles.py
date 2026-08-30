#!/usr/bin/env python3
"""Stützpakete: die Druckpassage zu jeder unerschlossenen Handschriftenseite (P2, #75).

Ein Paket ist das Arbeitsmaterial für eine gestützte Lesung: die laut
Ankerkarte (P1) zugehörige Druckpassage im Originaltext und normalisiert
(Nasalstrich aufgelöst, ſ gefaltet), dazu die Landmarken der Umgebung aus der
Sichtung. Wer eine Seite liest — Mensch im Viewer, Claude im Batch, oder
Transkribus über Text2Image — bekommt damit die Hypothese, was der Schreiber
vor sich hatte.

Pakete werden ERZEUGT, nicht versioniert. Sie sind vollständig aus
committeten Daten ableitbar (print_anchors.json + Drucktranskription +
finding_aid.json); ein Commit von ~2 700 JSONs, die den Drucktext
duplizieren, wäre eine zweite Wahrheit mit Drift-Garantie. Standard-Ablage
ist .cache/support/, das ohnehin ignoriert ist.

Was ein Paket ehrlich sagt
--------------------------
  traegt        die Ankerquelle und ±-Unschärfe der Karte. Ein Paket mit
                ±84 Druckseiten sagt das laut, statt eine Passage zu liefern,
                die zufällig hübsch aussieht.
  gekappt       bei breiten Bereichen wird der TEXT auf die zentralen Seiten
                gekappt (Vorgabe 12) — 170 Druckseiten "Passage" wären keine
                Lesehilfe, sondern Rauschen. Der volle Bereich steht in den
                Metadaten; die Kappung ist ausgewiesen.
  leer          Seiten ohne Schrift (Tintenmessung) bekommen kein Paket, und
                bereits transkribierte auch nicht — es sei denn --all, für
                die Pilotmessung (P3), die genau auf transkribierten Seiten
                misst.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_orthography import normalize_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"
PRINT_TR = DISPUTATION / "druck_1528" / "transcriptions"
INK = DISPUTATION / "ink_coverage.json"
DEFAULT_OUT = ROOT / ".cache" / "support"

INK_BLANK = 0.01
TEXT_MIN_CHARS = 20   # darunter gilt eine Transkription als leerer Stub
MAX_TEXT_PAGES = 12   # Textkappung bei breiten Ankerbereichen

WITNESSES = [
    "a_v_1443_hertwig",
    "a_v_1444_cyro",
    "a_v_1445_schoeni",
    "a_v_1446_ruemlang",
    "a_v_1447_schlussredaktion",
]


def page_body(path: Path) -> str:
    if not path.exists():
        return ""
    return re.sub(r"^#.*$", "", path.read_text(encoding="utf-8"), flags=re.M).strip()


def print_page_text(nr: int) -> str:
    return page_body(PRINT_TR / f"page_{nr}.md")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def neighbour_landmarks(aid: dict, page: int, radius: int = 30) -> list[dict]:
    out = []
    for page_str, entry in (aid.get("pages") or {}).items():
        nr = int(page_str)
        if abs(nr - page) <= radius and entry and entry.get("headings"):
            out.append({"seite": nr, "ueberschriften": entry["headings"]})
    return sorted(out, key=lambda e: e["seite"])


def build_bundle(witness: str, page: int, anchor: dict, aid: dict,
                 max_text_pages: int) -> dict:
    von, bis = anchor["druck_von"], anchor["druck_bis"]
    width = bis - von + 1
    if width > max_text_pages:
        centre = (von + bis) // 2
        text_von = max(von, centre - max_text_pages // 2)
        text_bis = min(bis, text_von + max_text_pages - 1)
        gekappt = True
    else:
        text_von, text_bis = von, bis
        gekappt = False

    passage = []
    for nr in range(text_von, text_bis + 1):
        original = print_page_text(nr)
        if not original:
            continue
        passage.append({"druck_seite": nr,
                        "original": original,
                        "normalisiert": normalize_text(original)})

    return {
        "witness": witness,
        "page": page,
        "grundsatz": "Der Druck ist Hypothese, niemals Vorlage. "
                     "Buchstabenbefund schlägt Drucktext; Abweichung ist "
                     "Befund, kein Fehler.",
        "anker": {"druck_von": von, "druck_bis": bis,
                  "quelle": anchor["quelle"],
                  "unschaerfe_seiten": (bis - von) // 2,
                  **({"landmarke": anchor["landmarke"]}
                     if "landmarke" in anchor else {})},
        "text_gekappt": gekappt,
        "text_umfang": [text_von, text_bis],
        "landmarken_umfeld": neighbour_landmarks(aid, page),
        "druck_passage": passage,
    }


def pages_needing_support(witness: str, ink: dict, include_all: bool) -> list[int]:
    anchors_path = DISPUTATION / witness / "print_anchors.json"
    karte = load_json(anchors_path)
    scores = ink.get(witness, {})
    out = []
    for entry in karte["pages"]:
        page = entry["page"]
        if scores and scores.get(page, 1.0) < INK_BLANK:
            continue  # leeres Blatt
        if not include_all:
            body = page_body(DISPUTATION / witness / "transcriptions"
                             / f"page_{page}.md")
            if len(body) >= TEXT_MIN_CHARS:
                continue  # schon transkribiert
        out.append(page)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("witnesses", nargs="*", default=None)
    ap.add_argument("--pages", type=str, default=None,
                    help="nur diese Seiten, kommagetrennt (z. B. 700,714)")
    ap.add_argument("--all", action="store_true",
                    help="auch transkribierte Seiten (für die Pilotmessung P3)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-text-pages", type=int, default=MAX_TEXT_PAGES)
    ap.add_argument("--stats-only", action="store_true",
                    help="nur zählen, nichts schreiben")
    args = ap.parse_args()

    ink_raw = load_json(INK) if INK.exists() else {}
    ink = {w: {int(k): v for k, v in pages.items()}
           for w, pages in ink_raw.get("witnesses", {}).items()}

    wanted = ([int(x) for x in args.pages.split(",")] if args.pages else None)

    for witness in (args.witnesses or WITNESSES):
        karte = load_json(DISPUTATION / witness / "print_anchors.json")
        by_page = {e["page"]: e for e in karte["pages"]}
        aid_path = DISPUTATION / witness / "finding_aid.json"
        aid = load_json(aid_path) if aid_path.exists() else {}

        targets = pages_needing_support(witness, ink, args.all)
        if wanted:
            targets = [p for p in targets if p in wanted]

        # Tragfähigkeit: wie viele Pakete haben einen engen Bereich?
        widths = [by_page[p]["druck_bis"] - by_page[p]["druck_von"]
                  for p in targets]
        narrow = sum(1 for w in widths if w <= 24)
        print(f"  {witness:28} {len(targets):4} Seiten ohne Text-Erschliessung"
              f", davon {narrow:4} mit engem Anker (±12 oder besser)")
        if args.stats_only:
            continue

        out_dir = args.out / witness
        out_dir.mkdir(parents=True, exist_ok=True)
        for page in targets:
            bundle = build_bundle(witness, page, by_page[page], aid,
                                  args.max_text_pages)
            (out_dir / f"page_{page}.json").write_text(
                json.dumps(bundle, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
        try:
            shown = out_dir.relative_to(ROOT)
        except ValueError:  # --out ausserhalb des Repos (z. B. Test-Tmpdir)
            shown = out_dir
        print(f"    -> {shown}: {len(targets)} Pakete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
