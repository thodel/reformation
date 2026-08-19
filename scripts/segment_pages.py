#!/usr/bin/env python3
"""Build reading segments from line-level transcriptions.

A page transcription is a list of lines in Transkribus reading order. Where a
page carries marginalia, that order interleaves the margin notes with the body
text, so the plain page text reads as nonsense - and any translation made from
it inherits the nonsense (see a-v-1447 page 101).

Line geometry separates them: on that page the body column starts near x=950
and runs ~1400 wide, while the margin notes start near x=450 and run ~450 wide.
This groups lines into a body column plus margin columns, restores reading
order within each, rejoins words broken across lines, and emits segments of
roughly a page, each combining two or three paragraphs.

Pages without line_coords (druck_1528 is transcribed by Gemini, not
Transkribus) fall back to splitting the transcription on blank lines.

Usage:
  python3 scripts/segment_pages.py --dry-run
  python3 scripts/segment_pages.py --variant a_v_1447_schlussredaktion
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"

# Line-end markers meaning "this word continues on the next line".
HYPHEN_RE = re.compile(r"(?:\s*(?://|¬|-|—|=))\s*$")
PARAGRAPHS_PER_SEGMENT = 3


def line_boxes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for line in payload.get("lines", []):
        text = (line.get("text") or "").strip()
        bbox = line.get("bbox")
        if not text or not bbox:
            continue
        out.append({"text": text, "x": float(bbox["x"]), "y": float(bbox["y"]),
                    "w": float(bbox["w"]), "h": float(bbox["h"]), "id": line.get("id")})
    return out


def split_columns(lines: list[dict[str, Any]]) -> tuple[list[dict], list[list[dict]]]:
    """Split lines into (body_column, [margin_columns]).

    The body is the column holding the greatest total line width - marginalia
    are short by nature, so width is a better signal than line count.
    """
    if not lines:
        return [], []

    widths = [l["w"] for l in lines]
    median_w = statistics.median(widths)
    # A line at least 70% of the median width is a body candidate; the rest are
    # short enough to be marginal.
    body = [l for l in lines if l["w"] >= median_w * 0.7]
    margins = [l for l in lines if l["w"] < median_w * 0.7]

    if not body:
        return sorted(lines, key=lambda l: l["y"]), []

    # Body lines should share a left edge; drop outliers into the margins.
    xs = sorted(l["x"] for l in body)
    centre = statistics.median(xs)
    spread = max(200.0, statistics.pstdev(xs) * 2 if len(xs) > 1 else 200.0)
    kept, moved = [], []
    for l in body:
        (kept if abs(l["x"] - centre) <= spread else moved).append(l)
    margins.extend(moved)

    kept.sort(key=lambda l: l["y"])
    margin_cols = group_margin_columns(margins)
    return kept, margin_cols


def group_margin_columns(margins: list[dict[str, Any]]) -> list[list[dict]]:
    if not margins:
        return []
    margins = sorted(margins, key=lambda l: l["x"])
    cols: list[list[dict]] = [[margins[0]]]
    for line in margins[1:]:
        if line["x"] - cols[-1][-1]["x"] > 300:
            cols.append([line])
        else:
            cols[-1].append(line)
    for col in cols:
        col.sort(key=lambda l: l["y"])
    return cols


def join_lines(lines: list[str]) -> str:
    """Join lines into flowing text, repairing words split across lines."""
    out = ""
    for raw in lines:
        text = raw.strip()
        if not text:
            continue
        if HYPHEN_RE.search(text):
            out += HYPHEN_RE.sub("", text)
        else:
            out += text + " "
    return re.sub(r"\s+", " ", out).strip()


def paragraphs_from_lines(lines: list[dict[str, Any]]) -> list[str]:
    """Break a column into paragraphs where the vertical gap jumps."""
    if not lines:
        return []
    gaps = [lines[i]["y"] - lines[i - 1]["y"] for i in range(1, len(lines))]
    typical = statistics.median(gaps) if gaps else 0.0
    threshold = typical * 1.8 if typical else float("inf")

    chunks: list[list[str]] = [[lines[0]["text"]]]
    for i in range(1, len(lines)):
        if lines[i]["y"] - lines[i - 1]["y"] > threshold:
            chunks.append([])
        chunks[-1].append(lines[i]["text"])
    return [p for p in (join_lines(c) for c in chunks) if p]


def paragraphs_from_markdown(text: str) -> list[str]:
    body = re.sub(r"^# Seite \d+\s*", "", text).strip()
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    if len(blocks) <= 1 and body:
        return [join_lines(body.splitlines())]
    return [join_lines(b.splitlines()) for b in blocks]


def build_segments(variant_id: str, page_nr: int, paragraphs: list[str]) -> list[dict[str, Any]]:
    segments = []
    for index in range(0, len(paragraphs), PARAGRAPHS_PER_SEGMENT):
        group = paragraphs[index : index + PARAGRAPHS_PER_SEGMENT]
        if not group:
            continue
        segments.append(
            {
                "id": f"{variant_id}-{page_nr}-{len(segments) + 1}",
                "page_nr": page_nr,
                "paragraphs": group,
                "text": "\n\n".join(group),
            }
        )
    return segments


def segment_page(variant_dir: Path, variant_id: str, page_nr: int) -> dict[str, Any] | None:
    coords_path = variant_dir / "line_coords" / f"page_{page_nr}.json"
    transcription_path = variant_dir / "transcriptions" / f"page_{page_nr}.md"

    marginalia: list[str] = []
    source = "line_coords"

    if coords_path.exists():
        try:
            payload = json.loads(coords_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        lines = line_boxes(payload)
        if lines:
            body, margin_cols = split_columns(lines)
            paragraphs = paragraphs_from_lines(body)
            marginalia = [join_lines([l["text"] for l in col]) for col in margin_cols]
            marginalia = [m for m in marginalia if m]
        else:
            paragraphs = []
    else:
        paragraphs = []

    if not paragraphs:
        if not transcription_path.exists():
            return None
        source = "transcription"
        paragraphs = paragraphs_from_markdown(transcription_path.read_text(encoding="utf-8"))

    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return None

    return {
        "variant_id": variant_id,
        "page_nr": page_nr,
        "source": source,
        "marginalia": marginalia,
        "segments": build_segments(variant_id, page_nr, paragraphs),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reading segments from transcriptions")
    parser.add_argument("--variant", action="append", help="Limit to a variant directory name")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    variant_dirs = sorted(d for d in DISPUTATION.iterdir() if d.is_dir())
    if args.variant:
        wanted = set(args.variant)
        variant_dirs = [d for d in variant_dirs if d.name in wanted]

    grand_pages = grand_segments = 0
    for variant_dir in variant_dirs:
        variant_id = variant_dir.name
        out_dir = variant_dir / "segments"
        pages = sorted(
            int(m.group(1))
            for p in (variant_dir / "transcriptions").glob("page_*.md")
            if (m := re.match(r"page_(\d+)\.md$", p.name))
        ) if (variant_dir / "transcriptions").exists() else []

        n_pages = n_segments = n_margin = 0
        for page_nr in pages:
            record = segment_page(variant_dir, variant_id, page_nr)
            if not record or not record["segments"]:
                continue
            n_pages += 1
            n_segments += len(record["segments"])
            n_margin += len(record["marginalia"])
            if not args.dry_run:
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / f"page_{page_nr}.json").write_text(
                    json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
        if n_pages:
            print(
                f"{variant_id}: {n_pages} page(s), {n_segments} segment(s), "
                f"{n_margin} marginal column(s)"
            )
        grand_pages += n_pages
        grand_segments += n_segments

    print(f"\n{grand_pages} page(s) segmented into {grand_segments} segment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
