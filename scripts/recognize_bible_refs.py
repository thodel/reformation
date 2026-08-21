#!/usr/bin/env python3
"""Recognise biblical citations in the recognised texts.

The Disputation argues from Scripture throughout, so where a passage is cited
is a first-order question for the edition - and the citations are currently
mis-filed. The person recogniser reads book names as people: "Mathei" 33 times,
"Johannis" 34, "Esa" 17. Those are references, not participants.

Matching runs through the orthographic normalisation, which already folds the
long s, v/u and i/j that make "Epheſ" and "Ephes", or "Johannis" and "Iohannis",
look unrelated. Edit distance on top absorbs a misread letter, which is common
here: the corpus contains "chorin" for Corinth, "pſalmo" for Psalm, "pite" for
Petri.

A citation is book plus chapter. Verses are not attempted: the sixteenth-century
text rarely gives them, and inventing precision the source does not have would
be worse than leaving it out.

Output is an editable table, like the person register and the segment table,
because deciding that "hier" means Jeremias is a judgement a reader should be
able to overturn.
"""

from __future__ import annotations

import argparse
import collections
import csv
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_orthography import normalize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "register"

# Canonical book, its modern short form, and the spellings the period uses.
# Latin and German forms both occur, often abbreviated and often inflected -
# "zun Galatern", "Johannis", "Exodi".
BOOKS: list[tuple[str, str, list[str]]] = [
    ("Genesis", "Gen", ["genesis", "gen", "1 mose", "erst buch mose", "moses i"]),
    ("Exodus", "Ex", ["exodi", "exodus", "exod", "2 mose", "ander buch mose"]),
    ("Leviticus", "Lev", ["levitici", "leviticus", "3 mose"]),
    ("Numeri", "Num", ["numeri", "num", "4 mose"]),
    ("Deuteronomium", "Dtn", ["deuteronomii", "deutero", "deut", "5 mose"]),
    ("Josua", "Jos", ["josue", "josua", "jos"]),
    ("1 Samuel", "1 Sam", ["samuel", "samuelis", "1 reg", "kunig i"]),
    ("Psalmen", "Ps", ["psalmo", "psalm", "psalmen", "psal", "ps"]),
    ("Sprüche", "Spr", ["prouerb", "prouerbiorum", "spruch"]),
    ("Jesaja", "Jes", ["esaie", "esaia", "esaias", "esa", "jesaia", "isaie"]),
    ("Jeremia", "Jer", ["jeremie", "jeremia", "hieremie", "hierem", "jere"]),
    ("Ezechiel", "Ez", ["ezechiel", "ezech", "hesekiel"]),
    ("Daniel", "Dan", ["danielis", "daniel", "dan"]),
    ("Hosea", "Hos", ["osee", "hosea"]),
    ("Joel", "Joel", ["joel", "johel"]),
    ("Amos", "Am", ["amos"]),
    ("Micha", "Mi", ["michee", "micha"]),
    ("Maleachi", "Mal", ["malachie", "malach"]),
    ("Matthäus", "Mt", ["mathei", "matthei", "matth", "mathe", "matthaeus", "matheus"]),
    ("Markus", "Mk", ["marci", "marcus", "marc"]),
    ("Lukas", "Lk", ["luce", "lucas", "luc"]),
    ("Johannes", "Joh", ["johannis", "johannes", "johan", "joh", "iohannis"]),
    ("Apostelgeschichte", "Apg", ["actorum", "acta", "actuum", "geschicht der apostel"]),
    ("Römer", "Röm", ["romanos", "romer", "rom", "zun romern"]),
    ("1 Korinther", "1 Kor", ["corinth", "corinthios", "corint", "chorin", "korinth"]),
    ("Galater", "Gal", ["galatas", "galatern", "galat", "gala"]),
    ("Epheser", "Eph", ["ephesios", "ephesern", "ephes", "ephe"]),
    ("Philipper", "Phil", ["philippenses", "philipper", "philip"]),
    ("Kolosser", "Kol", ["colossenses", "colossern", "coloss"]),
    ("1 Thessalonicher", "1 Thess", ["thessalonicenses", "thessal"]),
    ("1 Timotheus", "1 Tim", ["timotheum", "timotheo", "timoth", "thimotheo", "chimotheum"]),
    ("Titus", "Tit", ["titum", "tito", "titus"]),
    ("Hebräer", "Hebr", ["hebreos", "hebreern", "hebre", "ebreern"]),
    ("Jakobus", "Jak", ["jacobi", "jacobus", "jacob"]),
    ("1 Petrus", "1 Petr", ["petri", "pite", "petrus i", "1 petri"]),
    ("Offenbarung", "Offb", ["apocalipsis", "apocal", "offenbarung"]),
]

ROMAN = re.compile(r"^[ivxlcIVXLC]{1,8}$")
SIMILARITY = 0.84
# A book name shorter than this matches too much noise to be trusted.
MIN_TOKEN = 3


def roman_to_int(value: str) -> int | None:
    numerals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    total = 0
    previous = 0
    for char in reversed(value.lower()):
        current = numerals.get(char)
        if current is None:
            return None
        total = total - current if current < previous else total + current
        previous = max(previous, current)
    return total or None


def norm(word: str) -> str:
    return normalize(word).normalized.lower()


def build_index() -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}
    for canonical, short, variants in BOOKS:
        for variant in variants:
            index[norm(variant.replace(" ", ""))] = (canonical, short)
        index[norm(canonical)] = (canonical, short)
    return index


BOOK_INDEX = build_index()
BOOK_KEYS = list(BOOK_INDEX)


def match_book(token: str) -> tuple[str, str, float] | None:
    key = norm(token)
    if len(key) < MIN_TOKEN:
        return None
    if key in BOOK_INDEX:
        canonical, short = BOOK_INDEX[key]
        return canonical, short, 1.0
    best, score = None, 0.0
    for candidate in BOOK_KEYS:
        # Only compare where lengths are close; otherwise "joh" matches too much.
        if abs(len(candidate) - len(key)) > 3:
            continue
        ratio = difflib.SequenceMatcher(None, key, candidate).ratio()
        if ratio > score:
            best, score = candidate, ratio
    if best and score >= SIMILARITY:
        canonical, short = BOOK_INDEX[best]
        return canonical, short, round(score, 3)
    return None


# The book and the chapter must be separated by a period or whitespace. Without
# that requirement the pattern splits a single word: "Matthei" became Matthe +
# i = Mt 1 forty-eight times, "pitel" (the tail of "capitel") became 1 Petr 50,
# and "ſeel" became Hosea 50. A trailing Roman numeral glued to a word is part
# of the word, not a chapter.
CITATION = re.compile(
    r"(?ix)"
    r"(?:\b(?:zun?|zum|im|in|am)\s+)?"          # "zun Galatern", "am 5."
    r"\b([A-Za-zſäöüͤ]{3,16})"                   # book, abbreviated or inflected
    r"(?:\.\s*|\s+)"                            # a real boundary, not nothing
    r"(?:cap(?:itel|it)?\.?\s*)?"
    r"(?:am\s+)?"
    r"([ivxlcIVXLC]{1,8}|\d{1,3})\b\.?"         # chapter, Roman or Arabic
    r"\s*(?:cap(?:itel|it)?\.?)?"
)


def find_citations(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for m in CITATION.finditer(text or ""):
        token, chapter_raw = m.group(1), m.group(2)
        book = match_book(token)
        if not book:
            continue
        canonical, short, score = book
        chapter = (roman_to_int(chapter_raw) if ROMAN.match(chapter_raw)
                   else int(chapter_raw))
        if not chapter or chapter > 150:
            continue
        found.append({
            "book": canonical,
            "short": short,
            "chapter": chapter,
            "reference": f"{short} {chapter}",
            "surface": m.group(0).strip(),
            "confidence": score,
        })
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Recognise biblical citations")
    parser.add_argument("--witness", action="append",
                        help="Witness key; repeatable. Default: all with text.")
    args = parser.parse_args()

    from compare_witnesses import available_witnesses, page_texts

    witnesses = args.witness or available_witnesses()
    per_ref: dict[str, dict[str, Any]] = {}
    total = 0

    for key in witnesses:
        try:
            texts = page_texts(key)
        except Exception:
            continue
        for page in sorted(texts):
            for cite in find_citations(texts[page]):
                total += 1
                entry = per_ref.setdefault(cite["reference"], {
                    "reference": cite["reference"],
                    "book": cite["book"],
                    "chapter": cite["chapter"],
                    "count": 0,
                    "surfaces": collections.Counter(),
                    "places": [],
                    "min_confidence": 1.0,
                })
                entry["count"] += 1
                entry["surfaces"][cite["surface"]] += 1
                entry["min_confidence"] = min(entry["min_confidence"], cite["confidence"])
                if len(entry["places"]) < 60:
                    entry["places"].append({"doc": key, "page": page})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = OUT_DIR / "bible_refs.tsv"
    rows = sorted(per_ref.values(), key=lambda e: (-e["count"], e["reference"]))

    with table.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["reference", "book", "chapter", "count",
                         "min_confidence", "surfaces", "pages", "confirmed"])
        for e in rows:
            pages = collections.defaultdict(list)
            for place in e["places"]:
                if place["page"] not in pages[place["doc"]]:
                    pages[place["doc"]].append(place["page"])
            page_str = "; ".join(
                f"{doc}:{','.join(str(p) for p in sorted(v)[:12])}" for doc, v in sorted(pages.items()))
            writer.writerow([
                e["reference"], e["book"], e["chapter"], e["count"],
                e["min_confidence"],
                " | ".join(f"{s} ({n})" for s, n in e["surfaces"].most_common(6)),
                page_str, "",
            ])

    print(f"{total} citation(s) recognised, {len(rows)} distinct reference(s)")
    print(f"wrote {table.relative_to(ROOT)}")
    for e in rows[:14]:
        top = e["surfaces"].most_common(1)[0][0]
        print(f"  {e['count']:4}x  {e['reference']:10} {e['book'][:18]:20} "
              f"conf {e['min_confidence']:.2f}  z.B. {top[:28]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
