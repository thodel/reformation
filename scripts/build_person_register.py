#!/usr/bin/env python3
"""Build a person register from the recognised entities.

The existing register was not usable. Of 986 person entities, every one of the
969 that carried a "link" pointed at the same Metagrid id, which does not
resolve. The list also counted Bible books as people - Mathei 33 times,
Johannis 34 - kept titles like "Doctor" as names, and split each real person
across the spellings the text happens to use: Zwingli appears as "Vlrich
Zwingli", "Vlrich" and "Meister Vlrich zwingli", Haller as "Berchtold",
"Berchtoldus", "Berchtolden" and "Werchtoldus haller", the last a misreading.

This clusters the surface forms, drops what is not a person, and writes an
editable table for a human to correct - the same arrangement as the segment
table, because identifying a sixteenth-century person from a noisy
transcription is not a decision a script should make alone.
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
ENTITIES = ROOT / "data" / "entities" / "named_entities.json"
OUT_DIR = ROOT / "data" / "register"

# Books of the Bible read as people by the recogniser, plus the divine names.
# These belong in a scriptural index, not a register of historical persons.
SCRIPTURAL = re.compile(
    r"(?i)^(christ|jesu|gott|herr(en)?$|heiland|paul|petr|johann?is$|johann?es$|"
    # mat+h?e, not matth?e: the latter needs two t's and so never matched
    # "Mathei", which the recogniser produced 33 times.
    r"mat+h?e|marc|luc|marx$|moses|moyses|david|abraham|adam|eva$|maria$|"
    r"esa$|esa[ijy]|jesa[ijy]|jerem|ezech|daniel$|amos$|hosea|joel$|micha|malach|"
    r"timoth|tito$|hebre|corinth|galat|ephes|coloss|thessal|apocal)"
)
# Titles and roles the recogniser picked up as names.
TITLES = re.compile(
    r"(?i)^(doctor|doctores|meister|herr|pfarrer|predicant|prediger|bischoff?|"
    r"bapst|papst|keyser|kaiser|künig|konig|fürst|schultheiss|burgermeister|"
    r"amman|weibel|vogt|prior|abt|bruder|vatter|junker|gnaden)s?$"
)
MIN_MENTIONS = 3
SIMILARITY = 0.86


def norm_key(name: str) -> str:
    """Normalised comparison form: folds v/u, i/j, long s and diacritics."""
    words = re.findall(r"\w+", name)
    return " ".join(normalize(w).normalized.lower() for w in words)


def is_person(name: str) -> bool:
    stripped = name.strip()
    if len(stripped) < 3:
        return False
    if SCRIPTURAL.match(stripped) or TITLES.match(stripped):
        return False
    if not re.search(r"[A-Za-zÄÖÜäöüſ]", stripped):
        return False
    return True


def same_person(a: str, b: str) -> bool:
    """Whether two normalised name forms plausibly denote one person.

    A bare substring test is far too loose: "joh" sits inside both "johannes
    buchstab" and "johannes oecolampadius", which merged a Catholic opponent
    into a reformer. Where both forms name a surname, the surnames must agree;
    a single given name may only join a group whose given name it matches.
    """
    if a == b:
        return True
    a_words, b_words = a.split(), b.split()
    if len(a_words) >= 2 and len(b_words) >= 2:
        # Surnames decide. Allow a misread letter: berchtoldus/werchtoldus.
        return difflib.SequenceMatcher(None, a_words[-1], b_words[-1]).ratio() >= SIMILARITY
    # One side is a single word: it must match a word of the other, not merely
    # sit inside it.
    single, other = (a_words, b_words) if len(a_words) == 1 else (b_words, a_words)
    token = single[0]
    if len(token) < 4:
        return False
    return any(
        difflib.SequenceMatcher(None, token, word).ratio() >= SIMILARITY
        for word in other
    )


def cluster(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group surface forms that are plausibly the same person.

    Matching runs on the normalised form, which already folds the v/u and i/j
    variation that makes "Vlrich" and "Ulrich" look unrelated, then on string
    similarity to catch a misread letter such as "Werchtoldus" for
    "Berchtoldus".
    """
    candidates = [e for e in entities if e.get("type") == "PERSON" and is_person(e["name"])]
    candidates.sort(key=lambda e: -len(e.get("occurrences", [])))

    clusters: list[dict[str, Any]] = []
    for entity in candidates:
        key = norm_key(entity["name"])
        if not key:
            continue
        placed = False
        for group in clusters:
            # Compare against every form already in the group, not only its
            # label. "Werchtoldus haller" is a misreading of "Berchtoldus
            # Haller", which sits in the Berchtold group as a secondary form -
            # comparing labels alone leaves the two apart.
            for form in group["form_keys"]:
                if same_person(key, form):
                    placed = True
                    break
            if placed:
                group["forms"].append(entity["name"])
                group["form_keys"].append(key)
                group["mentions"] += len(entity.get("occurrences", []))
                group["occurrences"].extend(entity.get("occurrences", []))
                break
        if not placed:
            clusters.append({
                "key": key,
                "label": entity["name"],
                "forms": [entity["name"]],
                "form_keys": [key],
                "mentions": len(entity.get("occurrences", [])),
                "occurrences": list(entity.get("occurrences", [])),
            })
    return clusters


def pages_of(occurrences: list[dict[str, Any]], limit: int = 12) -> str:
    seen: dict[str, list[int]] = collections.defaultdict(list)
    for occ in occurrences:
        doc, page = occ.get("doc"), occ.get("page")
        if doc and page and page not in seen[doc]:
            seen[doc].append(page)
    parts = []
    for doc in sorted(seen):
        pages = sorted(seen[doc])[:limit]
        more = "…" if len(seen[doc]) > limit else ""
        parts.append(f"{doc}:{','.join(str(p) for p in pages)}{more}")
    return "; ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the person register")
    parser.add_argument("--min-mentions", type=int, default=MIN_MENTIONS)
    args = parser.parse_args()

    entities = json.loads(ENTITIES.read_text(encoding="utf-8"))
    clusters = cluster(entities)
    kept = [c for c in clusters if c["mentions"] >= args.min_mentions]
    kept.sort(key=lambda c: -c["mentions"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table = OUT_DIR / "persons.tsv"

    existing: dict[str, list[str]] = {}
    if table.exists():
        with table.open(encoding="utf-8") as fh:
            rows = list(csv.reader(fh, delimiter="\t"))
        head = rows[0]
        for row in rows[1:]:
            existing[row[head.index("key")]] = row

    header = ["key", "label", "mentions", "forms", "hls_id", "hls_title",
              "hls_years", "confirmed", "pages"]
    with table.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        for c in kept:
            prior = existing.get(c["key"])
            writer.writerow([
                c["key"], c["label"], c["mentions"],
                " | ".join(dict.fromkeys(c["forms"]))[:200],
                # Anything a human already decided is carried forward untouched.
                prior[4] if prior else "",
                prior[5] if prior else "",
                prior[6] if prior else "",
                prior[7] if prior else "",
                pages_of(c["occurrences"]),
            ])

    dropped = len([e for e in entities if e.get("type") == "PERSON"]) - sum(
        len(c["forms"]) for c in clusters)
    print(f"{len(clusters)} cluster(s) from person entities; "
          f"{len(kept)} with at least {args.min_mentions} mention(s)")
    print(f"  discarded as scripture, title or fragment: {dropped}")
    print(f"wrote {table.relative_to(ROOT)}")
    for c in kept[:12]:
        print(f"  {c['mentions']:4}x  {c['label'][:34]:36} {' | '.join(dict.fromkeys(c['forms']))[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
