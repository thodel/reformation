#!/usr/bin/env python3
"""Locate each segment of the base text in the other printed editions.

The segments are defined on the March 1528 print. The page alignment from #11
already maps its pages onto every other witness, so placing a segment elsewhere
is a lookup rather than a new computation: take the pages the segment covers,
collect whatever those pages align to, and report the span.

Coverage is reported, not hidden. A segment whose pages mostly failed to align
is marked as such rather than given a confident-looking range, because the
alignment is 95% at best and lower for the manuscripts. Where a witness has
nothing at all for a segment, that is stated too - an edition that drops a
passage is a finding, not a gap to paper over.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPARISON = ROOT / "data" / "comparison"
SEGMENTS = ROOT / "data" / "segments"
OUT = SEGMENTS / "concordance.json"

BASE = "druck_1528"
PRINTS_CONFIG = ROOT / "config" / "prints.json"
# e-rara resolves a canvas id directly as a page view, so a segment can be
# opened at the right leaf in the other editions rather than at their title page.
ERARA_PAGEVIEW = "https://www.e-rara.ch/content/pageview/"
# Below this share of aligned pages the span is a guess, not a location.
GOOD_COVERAGE = 0.5


def alignment_for(witness: str) -> dict[int, int]:
    """base page -> witness page, from the precomputed comparison index."""
    for name in (f"{BASE}__{witness}", f"{witness}__{BASE}"):
        index = COMPARISON / name / "index.json"
        if not index.exists():
            continue
        payload = json.loads(index.read_text(encoding="utf-8"))
        mapping: dict[int, int] = {}
        for unit in payload.get("units", []):
            base_pages = unit["pages"].get(BASE) or []
            other_pages = unit["pages"].get(witness) or []
            if base_pages and other_pages:
                mapping[base_pages[0]] = other_pages[0]
        return mapping
    return {}


def erara_page_ids(witness: str) -> dict[int, str]:
    """page number -> e-rara canvas id, for deep links into the digitisation."""
    if not PRINTS_CONFIG.exists():
        return {}
    payload = json.loads(PRINTS_CONFIG.read_text(encoding="utf-8"))
    entry = next((w for w in payload.get("witnesses", []) if w["key"] == witness), None)
    if not entry or not entry.get("erara_id"):
        return {}
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import erara
        manifest = erara.load_manifest(entry["erara_id"])
        pages = erara.pages_from_manifest(manifest)
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] no page ids for {witness}: {type(exc).__name__}", file=sys.stderr)
        return {}
    ids: dict[int, str] = {}
    for page in pages:
        canvas = page.canvas_id.rstrip("/").rsplit("/", 1)[-1]
        if canvas.isdigit():
            ids[page.page_nr] = canvas
    return ids


def witnesses() -> list[str]:
    found = []
    for directory in sorted(COMPARISON.iterdir()):
        if not directory.is_dir() or "__" not in directory.name:
            continue
        a, _, b = directory.name.partition("__")
        other = b if a == BASE else (a if b == BASE else None)
        if other:
            found.append(other)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Place the segments in the other prints")
    parser.add_argument("--witness", default=BASE)
    args = parser.parse_args()

    table = SEGMENTS / f"{args.witness}_segments.tsv"
    if not table.exists():
        print(f"[ERROR] no segment table: {table}", file=sys.stderr)
        return 2
    with table.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    header, body = rows[0], rows[1:]
    idx = {name: i for i, name in enumerate(header)}

    others = witnesses()
    maps = {w: alignment_for(w) for w in others}
    page_ids = {w: erara_page_ids(w) for w in others}

    segments = []
    for row in body:
        first = int(row[idx["first_page"]])
        last = int(row[idx["last_page"]])
        span = list(range(first, last + 1))
        entry: dict[str, Any] = {
            "segment": int(row[idx["segment"]]),
            "first_page": first,
            "last_page": last,
            "witnesses": {},
        }
        for witness, mapping in maps.items():
            hits = [mapping[p] for p in span if p in mapping]
            coverage = len(hits) / max(len(span), 1)
            if not hits:
                entry["witnesses"][witness] = {"status": "missing", "coverage": 0.0}
            else:
                canvas = page_ids.get(witness, {}).get(min(hits))
                entry["witnesses"][witness] = {
                    "status": "ok" if coverage >= GOOD_COVERAGE else "partial",
                    "first_page": min(hits),
                    "last_page": max(hits),
                    "coverage": round(coverage, 2),
                    "aligned": len(hits),
                    "of": len(span),
                    "erara": f"{ERARA_PAGEVIEW}{canvas}" if canvas else None,
                }
        segments.append(entry)

    OUT.write_text(json.dumps({"base": args.witness, "witnesses": others,
                               "good_coverage": GOOD_COVERAGE,
                               "segments": segments},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(segments)} segment(s) placed across {len(others)} witness(es)")
    print(f"{'witness':30} {'ok':>5} {'partial':>8} {'missing':>8}")
    for witness in others:
        counts = {"ok": 0, "partial": 0, "missing": 0}
        for seg in segments:
            counts[seg["witnesses"][witness]["status"]] += 1
        print(f"{witness:30} {counts['ok']:5} {counts['partial']:8} {counts['missing']:8}")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
