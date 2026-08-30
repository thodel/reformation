#!/usr/bin/env python3
"""Ankerkarte: welche Druckpassage gehört zu welcher Handschriftenseite (P1, #75).

Für jede Handschrift wird eine Karte ms-Seite -> druck_1528-Seitenbereich
gebaut, aus Quellen absteigender Härte:

  alignment      die Vergleichseinheiten druck_1528__<ms> (harte Anker;
                 vorhanden nur, wo die Seite transkribiert ist)
  landmark       Struktur-Landmarken der Sichtung (finding_aid.json), auf
                 Thesengrenzen der Druck-Segmentierung gematcht. Nur
                 Thesen-Überschriften sind belastbar: die Sitzungsdaten und
                 die Protestatio der Handschriften kommen im Drucktext nicht
                 vor (geprüft), und "Vincenty"-Treffer im Druck meinen den
                 Münsterpatron, nicht das Sitzungsdatum.
  terminal       das Buchende: die letzte beschriebene ms-Seite lauft auf das
                 Druckende (S. 496) zu - schwacher, aber richtungsgebender
                 Anker fuer die Interpolation im Schwanz
  interpolation  linear zwischen Ankern - aber ueber den Index der
                 BESCHRIEBENEN Seiten, nicht die rohe Seitenzahl. Leere
                 Blaetter (Tintenanteil < 1 %) tragen keinen Text und duerfen
                 die Steigung nicht verduennen; im Cyro-Schwanz sind 35 von
                 50 Blaettern leer.

Jeder Eintrag nennt seine Quelle und eine Unschärfe (± Druckseiten), die mit
der Distanz zum nächsten Anker wächst. Die Karte behauptet nie mehr, als sie
weiss: eine Seite mitten in einer 600-Seiten-Lücke bekommt ehrliche ±30, kein
scheingenaues Einzelziel.

Validierung eingebaut (--validate): die Alignment-Anker werden zurückgehalten
und aus Landmarken + Interpolation vorhergesagt; berichtet wird der mediane
Absolutfehler in Druckseiten. Das misst genau die Vorhersage, auf die sich
die unerschlossenen Seiten verlassen müssen.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"
COMPARISON = ROOT / "data" / "comparison"
SEGMENTS = ROOT / "data" / "segments" / "druck_1528_segments.json"

BASE = "druck_1528"
BASE_LAST_PAGE = 496
INK_BLANK = 0.01  # unter 1 % Tintenanteil gilt ein Blatt als leer

WITNESSES = [
    "a_v_1443_hertwig",
    "a_v_1444_cyro",
    "a_v_1445_schoeni",
    "a_v_1446_ruemlang",
    "a_v_1447_schlussredaktion",
]

# Landmarken-Muster -> Thesennummer. Bewusst eng: nur was eindeutig eine
# Thesengrenze benennt, wird gematcht.
THESIS_PATTERNS = [
    # ".{0,24}" statt "\s*": "Der Zehend vnd Lest Artickell" traegt Woerter
    # zwischen Zahl und Artickel und fiel mit engem Muster durch.
    (re.compile(r"\b(erst|1)\b.{0,24}?(artickell?|schlussred)", re.I), 1),
    (re.compile(r"\b(ander|zweyt|2)\b.{0,24}?(artickell?|schlussred)", re.I), 2),
    (re.compile(r"\b(dritt|3)\b.{0,24}?(artickell?|schlussred)", re.I), 3),
    (re.compile(r"\b(vierd|4)\b.{0,24}?(artickell?|schlussred)", re.I), 4),
    (re.compile(r"\b(f[uü]nfft|5)\b.{0,24}?(artickell?|schlussred)", re.I), 5),
    (re.compile(r"\b(sechst|6)\b.{0,24}?(artickell?|schlussred)", re.I), 6),
    (re.compile(r"\b(sibend|7)\b.{0,24}?(artickell?|schlussred)", re.I), 7),
    (re.compile(r"\b(acht|8)\b.{0,24}?(artickell?|schlussred)", re.I), 8),
    (re.compile(r"\b(n[uü]nd|neunt|9)\b.{0,24}?(artickell?|schlussred)", re.I), 9),
    (re.compile(r"\b(zehend|10)\b.{0,24}?(artickell?|schlussred)", re.I), 10),
]


def load_segments() -> dict:
    return json.loads(SEGMENTS.read_text(encoding="utf-8"))


def thesis_start_pages(segments: dict) -> dict[int, int]:
    """Erste Druckseite je These.

    These 10 hat in der Segmentierung (noch) keine thesis-Angabe - die
    Schwanzsegmente 85/86 sind unbeschriftet. Positionsschluss: das erste
    Segment nach dem letzten Segment der These 9 eröffnet die These 10. Der
    describe-Lauf für diese Segmente ist als Vorarbeit im Epic #75 notiert;
    sobald er gelaufen ist, ersetzt die echte Beschriftung diesen Schluss.
    """
    starts: dict[int, int] = {}
    last_seg9_end = None
    for seg in segments["segments"]:
        thesis = seg.get("thesis")
        if isinstance(thesis, int) and thesis not in starts:
            starts[thesis] = seg["first_page"]
        if thesis == 9:
            last_seg9_end = seg["last_page"]
    if 10 not in starts and last_seg9_end:
        for seg in segments["segments"]:
            if seg["first_page"] > last_seg9_end:
                starts[10] = seg["first_page"]
                break
    return starts


def alignment_anchors(witness: str) -> list[dict]:
    index = COMPARISON / f"{BASE}__{witness}" / "index.json"
    if not index.exists():
        return []
    data = json.loads(index.read_text(encoding="utf-8"))
    # Eine kondensierte Abschrift traegt mehrere Druckseiten auf EINER
    # ms-Seite (Ruemlang S.10 deckt Druck 18 UND 19). Die Einheiten werden
    # deshalb je ms-Seite zu einem Bereich zusammengelegt, statt dass ein
    # zweiter Anker mit derselben ms-Seite im Monotoniefilter verworfen wird.
    by_ms: dict[int, list[int]] = {}
    for unit in data.get("units", []):
        base_pages = unit.get("pages", {}).get(BASE) or []
        ms_pages = unit.get("pages", {}).get(witness) or []
        if base_pages and ms_pages:
            by_ms.setdefault(ms_pages[0], []).extend(base_pages)
    return [{"ms": ms, "druck": min(pages), "druck_bis_anker": max(pages),
             "quelle": "alignment"}
            for ms, pages in sorted(by_ms.items())]


def landmark_anchors(witness: str, thesis_starts: dict[int, int]) -> list[dict]:
    aid_path = DISPUTATION / witness / "finding_aid.json"
    if not aid_path.exists():
        return []
    aid = json.loads(aid_path.read_text(encoding="utf-8"))
    anchors = []
    for page_str, entry in (aid.get("pages") or {}).items():
        note = ((entry or {}).get("note") or "")
        for heading in (entry or {}).get("headings", []):
            # Eingebundene Druckblaetter (Cyro 834-838) nennen Schlussreden im
            # TITEL des Blatts - das ist Beilage, keine Position im Textfluss.
            if "edruckt" in heading or "edruckt" in note:
                continue
            for pattern, thesis in THESIS_PATTERNS:
                if pattern.search(heading) and thesis in thesis_starts:
                    anchors.append({"ms": int(page_str),
                                    "druck": thesis_starts[thesis],
                                    "quelle": "landmark",
                                    "landmarke": heading[:60]})
                    break
    return anchors


def load_ink(ink_path: Path | None) -> dict[str, dict[int, float]]:
    if ink_path and ink_path.exists():
        raw = json.loads(ink_path.read_text(encoding="utf-8"))
        raw = raw.get("witnesses", raw)  # versionierte Form hat einen Mantel
        return {w: {int(k): v for k, v in pages.items()} for w, pages in raw.items()}
    return {}


def written_pages(witness: str, ink: dict) -> list[int]:
    """Seiten mit Schrift, in Blattfolge - die Achse der Interpolation."""
    images = DISPUTATION / witness / "images"
    numbers = sorted(int(re.search(r"\d+", p.name).group())
                     for p in images.glob("page_*.jpg"))
    scores = ink.get(witness, {})
    if not scores:
        return numbers  # ohne Tintendaten zählt jede Seite
    return [n for n in numbers if scores.get(n, 1.0) >= INK_BLANK]


def monotone(anchors: list[dict]) -> tuple[list[dict], list[dict]]:
    """Behalte die längste in beiden Achsen steigende Ankerfolge.

    Ein einzelner Fehlanker (etwa ein Alignment, das zwei ähnliche Passagen
    verwechselt) darf nicht die ganze Karte verbiegen; er fliegt raus und
    wird gemeldet statt verschwiegen.
    """
    anchors = sorted(anchors, key=lambda a: (a["ms"], a["druck"]))
    if not anchors:
        return [], []
    # Längste steigende Teilfolge über druck bei aufsteigendem ms
    best_prev = [-1] * len(anchors)
    best_len = [1] * len(anchors)
    for i, a in enumerate(anchors):
        for j in range(i):
            if anchors[j]["druck"] <= a["druck"] and anchors[j]["ms"] < a["ms"]:
                if best_len[j] + 1 > best_len[i]:
                    best_len[i] = best_len[j] + 1
                    best_prev[i] = j
    end = max(range(len(anchors)), key=lambda i: best_len[i])
    keep_idx = []
    while end != -1:
        keep_idx.append(end)
        end = best_prev[end]
    keep_idx = set(keep_idx)
    kept = [a for i, a in enumerate(anchors) if i in keep_idx]
    dropped = [a for i, a in enumerate(anchors) if i not in keep_idx]
    return kept, dropped


def interpolate(witness: str, anchors: list[dict], writable: list[int]) -> list[dict]:
    """Linear zwischen Ankern über den Index der beschriebenen Seiten."""
    if not writable:
        return []
    pos = {page: i for i, page in enumerate(writable)}
    # Steigung fuer die Extrapolation jenseits des letzten Ankers: aus dem
    # Zeugen selbst (Druckseiten je beschriebener Seite), nicht als Konstante.
    # Die Validierung zeigte, was eine geratene 0.7 kostet: beim dicht
    # beschriebenen a_v_1447 akkumulierte sie 27 Druckseiten Medianfehler.
    slope = BASE_LAST_PAGE / max(1, len(writable))
    fixed = [a for a in anchors if a["ms"] in pos]
    fixed.sort(key=lambda a: pos[a["ms"]])

    entries = []
    for page in writable:
        exact = next((a for a in fixed if a["ms"] == page), None)
        if exact:
            entries.append({"page": page, "druck_von": exact["druck"],
                            "druck_bis": exact.get("druck_bis_anker",
                                                   exact["druck"]),
                            "quelle": exact["quelle"],
                            **({"landmarke": exact["landmarke"]}
                               if "landmarke" in exact else {})})
            continue
        before = [a for a in fixed if pos[a["ms"]] < pos[page]]
        after = [a for a in fixed if pos[a["ms"]] > pos[page]]
        if before and after:
            a, b = before[-1], after[0]
            span = pos[b["ms"]] - pos[a["ms"]]
            frac = (pos[page] - pos[a["ms"]]) / span if span else 0.0
            centre = a["druck"] + frac * (b["druck"] - a["druck"])
            distance = min(pos[page] - pos[a["ms"]], pos[b["ms"]] - pos[page])
        elif before:
            a = before[-1]
            distance = pos[page] - pos[a["ms"]]
            centre = min(BASE_LAST_PAGE, a["druck"] + distance * slope)
        elif after:
            b = after[0]
            distance = pos[b["ms"]] - pos[page]
            centre = max(1, b["druck"] - distance * slope)
        else:
            entries.append({"page": page, "druck_von": 1,
                            "druck_bis": BASE_LAST_PAGE,
                            "quelle": "unbestimmt"})
            continue
        # Unschärfe wächst mit dem Abstand zum nächsten Anker: ±2 direkt
        # daneben, ungedeckelt in grossen Lücken. Ein Deckel stand hier und
        # flog raus: die Validierung mass im ankerlosen Fall ~92 Druckseiten
        # echten Fehler, ein ±30-Deckel hätte Scheingenauigkeit behauptet.
        # Der Faktor 0.35 ist an derselben Messung geeicht.
        margin = max(2, round(distance * 0.35))
        entries.append({"page": page,
                        "druck_von": max(1, round(centre - margin)),
                        "druck_bis": min(BASE_LAST_PAGE, round(centre + margin)),
                        "quelle": "interpolation"})
    return entries


def build(witness: str, thesis_starts: dict, ink: dict) -> dict:
    anchors = alignment_anchors(witness) + landmark_anchors(witness, thesis_starts)
    writable = written_pages(witness, ink)
    if writable:
        anchors.append({"ms": writable[-1], "druck": BASE_LAST_PAGE,
                        "quelle": "terminal"})
    kept, dropped = monotone(anchors)
    entries = interpolate(witness, kept, writable)
    counts = {}
    for e in entries:
        counts[e["quelle"]] = counts.get(e["quelle"], 0) + 1
    return {
        "witness": witness, "base": BASE,
        "method": "build_print_anchors.py: Alignment + Thesen-Landmarken + "
                  "Terminalanker, linear interpoliert über beschriebene Seiten",
        "anchors_kept": len(kept), "anchors_dropped": len(dropped),
        "dropped": dropped[:20],
        "by_source": counts,
        "pages": entries,
    }


def validate(witness: str, thesis_starts: dict, ink: dict) -> dict | None:
    """Alignment-Anker zurückhalten, aus dem Rest vorhersagen, Fehler messen."""
    hard = alignment_anchors(witness)
    if len(hard) < 3:
        return None
    soft = landmark_anchors(witness, thesis_starts)
    writable = written_pages(witness, ink)
    if writable:
        soft = soft + [{"ms": writable[-1], "druck": BASE_LAST_PAGE,
                        "quelle": "terminal"}]
    kept, _ = monotone(soft)
    entries = {e["page"]: e for e in interpolate(witness, kept, writable)}
    errors = []
    for a in hard:
        e = entries.get(a["ms"])
        if not e:
            continue
        centre = (e["druck_von"] + e["druck_bis"]) / 2
        errors.append(abs(centre - a["druck"]))
    if not errors:
        return None
    return {"witness": witness, "anker_geprueft": len(errors),
            "median_fehler_druckseiten": round(statistics.median(errors), 1),
            "max_fehler": round(max(errors), 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("witnesses", nargs="*", default=None)
    ap.add_argument("--ink", type=Path,
                    default=DISPUTATION / "ink_coverage.json",
                    help="Tintenmessung (leere Blätter); im Repo versioniert")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()

    thesis_starts = thesis_start_pages(load_segments())
    print(f"Thesenanker im Druck: {thesis_starts}")
    ink = load_ink(args.ink)
    if not ink:
        print("WARNUNG: keine Tintendaten - leere Blätter zählen als "
              "beschrieben, die Interpolation wird dadurch flacher als die "
              "Wirklichkeit.", file=sys.stderr)

    for witness in (args.witnesses or WITNESSES):
        if args.validate:
            result = validate(witness, thesis_starts, ink)
            if result:
                print(f"  {witness:28} {result['anker_geprueft']:3} Anker  "
                      f"Medianfehler {result['median_fehler_druckseiten']:6.1f}  "
                      f"max {result['max_fehler']:6.1f} Druckseiten")
            else:
                print(f"  {witness:28} zu wenige Anker für Validierung")
            continue
        result = build(witness, thesis_starts, ink)
        out = DISPUTATION / witness / "print_anchors.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print(f"  {out.relative_to(ROOT)}: {len(result['pages'])} Seiten, "
              f"Anker {result['anchors_kept']} (verworfen {result['anchors_dropped']}), "
              f"Quellen {result['by_source']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
