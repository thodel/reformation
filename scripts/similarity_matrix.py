#!/usr/bin/env python3
"""Pairwise similarity across all witnesses (issue #16).

The detailed comparison in compare_witnesses.py stores every differing stretch,
which is why it is published for a curated set of ten pairs rather than all
forty-five. A similarity matrix needs only one number per pair, so the full
matrix costs a few kilobytes and can cover every combination.

Similarity is the mean word-level ratio over aligned pages, computed on
normalised text so orthographic variation does not register as distance.

Also emits, for each pair, the per-unit similarity sequence - the divergence
band the viewer draws along the document to show where witnesses run together
and where they part.

Usage:
  python3 scripts/similarity_matrix.py
  python3 scripts/similarity_matrix.py --check
"""

from __future__ import annotations

import argparse
import difflib
import itertools
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from align_witnesses import (  # noqa: E402
    DEFAULT_DF_RATIO,
    DEFAULT_NGRAM,
    DEFAULT_THRESHOLD,
    load_pages,
    monotone_alignment,
    score_pairs,
)
from compare_witnesses import available_witnesses, fingerprint, norm_words, page_texts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "comparison" / "similarity_matrix.json"
BANDS = ROOT / "data" / "comparison" / "bands"
# Below this many aligned pages a mean is not a measurement, it is an accident.
MIN_UNITS_FOR_CONFIDENCE = 20


def pair_similarity(a_key: str, b_key: str, cache: dict[str, Any]) -> dict[str, Any]:
    a_pages = cache.setdefault(a_key, load_pages(a_key))
    b_pages = cache.setdefault(b_key, load_pages(b_key))
    candidates = score_pairs(
        a_pages, b_pages, n=DEFAULT_NGRAM,
        df_ratio=DEFAULT_DF_RATIO, threshold=DEFAULT_THRESHOLD,
    )
    pairs = monotone_alignment(candidates)
    if not pairs:
        return {"aligned": 0, "similarity": None, "band": [], "confident": False}

    a_text = cache.setdefault(f"t:{a_key}", page_texts(a_key))
    b_text = cache.setdefault(f"t:{b_key}", page_texts(b_key))

    band: list[dict[str, Any]] = []
    total = 0.0
    for a_page, b_page, _score in pairs:
        aw = norm_words(a_text.get(a_page, ""))
        bw = norm_words(b_text.get(b_page, ""))
        ratio = difflib.SequenceMatcher(None, aw, bw, autojunk=False).ratio()
        total += ratio
        band.append({"a": a_page, "b": b_page, "s": round(ratio, 3)})

    return {
        "aligned": len(pairs),
        "similarity": round(total / len(pairs), 4),
        "band": band,
        "confident": len(pairs) >= MIN_UNITS_FOR_CONFIDENCE,
    }


def build() -> dict[str, Any]:
    witnesses = available_witnesses()
    cache: dict[str, Any] = {}
    matrix: dict[str, dict[str, Any]] = {}
    for a_key, b_key in itertools.combinations(witnesses, 2):
        result = pair_similarity(a_key, b_key, cache)
        matrix.setdefault(a_key, {})[b_key] = result
        note = "" if result["confident"] else "  (too few aligned pages to be meaningful)"
        sim = result["similarity"]
        print(f"  {a_key:28} {b_key:28} "
              f"{'—' if sim is None else f'{sim:6.1%}'}  {result['aligned']:4} pages{note}")
    return {
        "witnesses": witnesses,
        "fingerprints": {w: fingerprint(w) for w in witnesses},
        "min_units_for_confidence": MIN_UNITS_FOR_CONFIDENCE,
        "matrix": matrix,
    }


def is_stale() -> bool:
    if not OUT.exists():
        return True
    try:
        stored = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return True
    witnesses = available_witnesses()
    if stored.get("witnesses") != witnesses:
        return True
    return any(stored.get("fingerprints", {}).get(w) != fingerprint(w) for w in witnesses)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pairwise similarity across all witnesses")
    parser.add_argument("--check", action="store_true", help="Report staleness, exit 1 if stale")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.check:
        stale = is_stale()
        print("similarity matrix: " + ("stale" if stale else "current"))
        return 1 if stale else 0

    if not args.force and not is_stale():
        print("similarity matrix current; nothing regenerated.")
        return 0

    payload = build()

    # The bands are 98% of the data and are only needed once a pair is chosen,
    # so the heatmap is not made to wait for them.
    OUT.parent.mkdir(parents=True, exist_ok=True)
    BANDS.mkdir(parents=True, exist_ok=True)
    for stale in BANDS.glob("*.json"):
        stale.unlink()

    band_bytes = 0
    for a_key, row in payload["matrix"].items():
        for b_key, result in row.items():
            band = result.pop("band", [])
            if not band:
                continue
            text = json.dumps({"a": a_key, "b": b_key, "band": band}, ensure_ascii=False) + "\n"
            (BANDS / f"{a_key}__{b_key}.json").write_text(text, encoding="utf-8")
            band_bytes += len(text.encode("utf-8"))

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pairs = sum(len(v) for v in payload["matrix"].values())
    print(f"\nwrote {OUT.relative_to(ROOT)}: {pairs} pair(s), "
          f"{OUT.stat().st_size / 1024:.1f} KB")
    print(f"wrote {len(list(BANDS.glob('*.json')))} band file(s), {band_bytes / 1024:.0f} KB total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
