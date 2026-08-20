#!/usr/bin/env python3
"""Where in the work the witnesses diverge (issue #15).

A matrix of witness against section, coloured by how much each witness departs
from the base text there. The similarity matrix (#16) says how far apart two
witnesses are overall; this says where.

Sections are positional - equal spans of the base text - not the numbered
Schlussreden the issue suggested. Those occur throughout as references rather
than as headings: 25 pages of druck_1528 mention one, and "erst Schlussred"
alone appears on pages 14, 18, 21, 25, 61, 68, 69 and 106. They cannot mark
section boundaries. Positional sections are well defined because the alignment
is monotone: section five of the base text corresponds to whatever each witness
has there.

Reads the existing comparison output, so it costs an aggregation rather than a
recomputation.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPARISON = ROOT / "data" / "comparison"
OUT = COMPARISON / "divergence_heatmap.json"
DEFAULT_SECTIONS = 24
# A section resting on fewer aligned units than this is not a measurement.
MIN_UNITS = 3


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


def section_rows(reference: str, sections: int) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    span: dict[str, int] = {}

    for witness, directory in pair_dirs(reference):
        index_path = directory / "index.json"
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        units = index.get("units", [])
        if not units:
            continue
        pages = [u["pages"].get(reference, [0])[0] for u in units]
        span[witness] = max(pages)

    if not span:
        return {}
    # One page scale for every row, so columns line up across witnesses.
    last_page = max(span.values())

    for witness, directory in pair_dirs(reference):
        index_path = directory / "index.json"
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        units = index.get("units", [])
        buckets: list[list[float]] = [[] for _ in range(sections)]
        semantic_buckets: list[list[float]] = [[] for _ in range(sections)]
        for unit in units:
            page = unit["pages"].get(reference, [0])[0]
            slot = min(sections - 1, int((page - 1) / last_page * sections))
            buckets[slot].append(unit.get("similarity", 0.0))
            if unit.get("sentence_similarity") is not None:
                semantic_buckets[slot].append(unit["sentence_similarity"])

        cells = []
        for i, values in enumerate(buckets):
            if len(values) < MIN_UNITS:
                cells.append({"section": i, "units": len(values),
                              "divergence": None, "confident": False})
                continue
            cells.append({
                "section": i,
                "units": len(values),
                "divergence": round(1 - statistics.mean(values), 4),
                "sentence_divergence": (
                    round(1 - statistics.mean(semantic_buckets[i]), 4)
                    if len(semantic_buckets[i]) >= MIN_UNITS else None
                ),
                "confident": True,
            })
        rows[witness] = {"cells": cells, "aligned_units": len(units)}
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Divergence by section")
    parser.add_argument("--reference", default="druck_1528")
    parser.add_argument("--sections", type=int, default=DEFAULT_SECTIONS)
    args = parser.parse_args()

    rows = section_rows(args.reference, args.sections)
    if not rows:
        print("[ERROR] no comparison data for that reference", file=sys.stderr)
        return 2

    payload = {
        "reference": args.reference,
        "sections": args.sections,
        "min_units": MIN_UNITS,
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{len(rows)} witness row(s), {args.sections} section(s)")
    for witness, row in sorted(rows.items()):
        values = [c["divergence"] for c in row["cells"] if c["divergence"] is not None]
        thin = sum(1 for c in row["cells"] if not c["confident"])
        if values:
            print(f"  {witness:30} mean divergence {statistics.mean(values):.1%} "
                  f"(min {min(values):.1%}, max {max(values):.1%}, {thin} thin section(s))")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
