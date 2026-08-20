#!/usr/bin/env python3
"""Variant apparatus anchored on the base text (issue #14).

For each page of the base text, gathers what every other witness has there:
its page, its substantive readings, and how it spells what it shares.

Two kinds of variant, separated
-------------------------------
The comparison runs on normalised text, so a difference it reports is one that
survives normalisation - a substantive variant. Orthographic variants are the
ones it folded away, and they are recoverable from the segments it marked
equal, where the normalised forms agree but the original spellings differ.

That separation is what makes an apparatus readable here. Between druck_1528
and druck_1701 there are 4,555 orthographic variants against 7,013 substantive
ones, and the orthographic ones are overwhelmingly the same handful of
alternations - vnd/und, ist/iſt, zů/zu. Listed undifferentiated they would bury
every reading that matters.

Page references only, as specified: no line references.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPARISON = ROOT / "data" / "comparison"
OUT = ROOT / "data" / "apparatus"
CONFIG = ROOT / "config" / "prints.json"


def erara_links() -> dict[str, dict[str, str]]:
    """DOI and library per witness, for citing a reading."""
    links: dict[str, dict[str, str]] = {}
    if CONFIG.exists():
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        for witness in payload.get("witnesses", []):
            links[witness["key"]] = {
                "doi": witness.get("doi", ""),
                "library": witness.get("library", ""),
                "label": witness.get("label", witness["key"]),
            }
    # The base text is held under its own key in the edition.
    links.setdefault("druck_1528", {"doi": "10.3931/e-rara-141267",
                                    "library": "UB Bern", "label": "Druck, 23. März 1528"})
    return links


def pair_dirs(reference: str) -> list[tuple[str, Path]]:
    out = []
    for directory in sorted(COMPARISON.iterdir()):
        if not directory.is_dir() or "__" not in directory.name:
            continue
        a, _, b = directory.name.partition("__")
        if a == reference:
            out.append((b, directory))
        elif b == reference:
            out.append((a, directory))
    return out


def split_variants(segments: list[dict[str, Any]]) -> tuple[list[dict], collections.Counter]:
    """Substantive readings, and a tally of orthographic alternations."""
    substantive: list[dict] = []
    orthographic: collections.Counter = collections.Counter()
    for seg in segments:
        if seg["op"] == "equal":
            a_words, b_words = seg["a"].split(), seg["b"].split()
            if len(a_words) == len(b_words):
                for x, y in zip(a_words, b_words):
                    if x != y:
                        orthographic[(x, y)] += 1
            continue
        if seg.get("a") or seg.get("b"):
            substantive.append({"op": seg["op"], "base": seg.get("a", ""),
                                "witness": seg.get("b", "")})
    return substantive, orthographic


def build(reference: str, limit: int = 0) -> dict[str, Any]:
    links = erara_links()
    pages: dict[int, dict[str, Any]] = {}

    for witness, directory in pair_dirs(reference):
        index_path = directory / "index.json"
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for entry in index.get("units", []):
            ref_pages = entry["pages"].get(reference) or []
            wit_pages = entry["pages"].get(witness) or []
            if not ref_pages or not wit_pages:
                continue
            ref_page = ref_pages[0]
            unit_path = directory / f"unit_{entry['unit']}.json"
            if not unit_path.exists():
                continue
            unit = json.loads(unit_path.read_text(encoding="utf-8"))
            # The pair may be stored in either order.
            base_is_a = unit["pages"].get(reference) == ref_pages
            segments = unit["fine"]["segments"]
            if not base_is_a:
                segments = [{"op": s["op"], "a": s["b"], "b": s["a"]} for s in segments]

            substantive, orthographic = split_variants(segments)
            record = pages.setdefault(ref_page, {"page": ref_page, "witnesses": {}})
            record["witnesses"][witness] = {
                "page": wit_pages[0],
                "similarity": entry.get("similarity"),
                "sentence_similarity": entry.get("sentence_similarity"),
                "substantive": substantive[:40],
                "substantive_total": len(substantive),
                "orthographic_total": sum(orthographic.values()),
                "orthographic_top": [
                    {"base": a, "witness": b, "n": n}
                    for (a, b), n in orthographic.most_common(8)
                ],
                "doi": links.get(witness, {}).get("doi", ""),
                "library": links.get(witness, {}).get("library", ""),
            }

    ordered = sorted(pages)
    if limit:
        ordered = ordered[:limit]
    return {"reference": reference,
            "reference_doi": links.get(reference, {}).get("doi", ""),
            "pages": [pages[p] for p in ordered]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the variant apparatus")
    parser.add_argument("--reference", default="druck_1528")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    payload = build(args.reference, args.limit)
    if not payload["pages"]:
        print("[ERROR] no comparison data for that reference", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("page_*.json"):
        stale.unlink()

    index = []
    total_sub = total_orth = 0
    for record in payload["pages"]:
        page = record["page"]
        (OUT / f"page_{page}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sub = sum(w["substantive_total"] for w in record["witnesses"].values())
        orth = sum(w["orthographic_total"] for w in record["witnesses"].values())
        total_sub += sub
        total_orth += orth
        index.append({"page": page, "witnesses": len(record["witnesses"]),
                      "substantive": sub, "orthographic": orth})

    (OUT / "index.json").write_text(
        json.dumps({"reference": payload["reference"],
                    "reference_doi": payload["reference_doi"],
                    "pages": index}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(payload['pages'])} base page(s)")
    print(f"  substantive readings: {total_sub}")
    print(f"  orthographic variants: {total_orth}")
    print(f"wrote {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
