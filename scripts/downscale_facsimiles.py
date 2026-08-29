#!/usr/bin/env python3
"""Downscale the manuscript facsimiles for publication (issue #72).

The published site had grown to roughly 1.9 GB against GitHub's 1 GB
guidance, and the Pages upload step had become the slowest part of every
deploy. 1.8 GB of that is the five Staatsarchiv manuscripts at full scan
resolution (~3500 px, ~600 KB a page); everything else together is ~90 MB. Unlike the prints, they are not on e-rara, so
there is no external IIIF service to point at - the images have to be served
from here, which makes their size our problem to solve.

Long edge 1600 px is what the viewer can actually use: the facsimile pane is
well under 1000 px on a normal screen, and OpenSeadragon only ever renders one
page at a time. Deep zoom past that would need tiles, which a static site
cannot serve anyway.

Two things this deliberately does NOT do:

  * touch the PAGE XML. Line coordinates stay in their original pixel space
    and keep their declared imageWidth/imageHeight; the viewer scales them by
    the ratio between that declared size and the image it actually loaded. The
    source data stays true to the scan it was made from.
  * discard the originals. They remain in git history, and the manuscripts are
    still held by the Staatsarchiv - this is a publication resolution, not an
    archival decision.

Note on what this does NOT fix: the repository still carries the originals in
its history, so .git grows rather than shrinks. Shrinking that would mean
rewriting history, which is not worth it for a published edition others may
have cloned.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"

WITNESSES = [
    "a_v_1443_hertwig",
    "a_v_1444_cyro",
    "a_v_1445_schoeni",
    "a_v_1446_ruemlang",
    "a_v_1447_schlussredaktion",
]

LONG_EDGE = 1600
# 72 rather than a higher setting, measured rather than guessed: at this
# reduction the long edge is what carries a hand's legibility, and dropping
# quality from 82 to 72 is visually indistinguishable on the script while
# taking the corpus from 919 MB to roughly 700 MB. Encode once from the
# originals - re-encoding an already-compressed JPEG compounds the loss.
QUALITY = 72


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} GB"


def process(path: Path, long_edge: int, quality: int, dry_run: bool):
    from PIL import Image

    before = path.stat().st_size
    with Image.open(path) as img:
        w, h = img.size
        if max(w, h) <= long_edge:
            return before, before, False
        scale = long_edge / max(w, h)
        new = (max(1, round(w * scale)), max(1, round(h * scale)))
        if dry_run:
            # Rough and known to be optimistic: JPEG size does not fall with
            # pixel count, so this over-predicts the saving (it claimed -79%
            # where the real figure at q82 was -50%). Good enough to see the
            # order of magnitude, not to plan against.
            return before, int(before * (scale ** 2)), True
        # LANCZOS keeps the strokes of a manuscript hand legible; a cheaper
        # filter smears them at this reduction factor.
        out = img.convert("RGB").resize(new, Image.Resampling.LANCZOS)
        out.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    return before, path.stat().st_size, True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("witnesses", nargs="*", default=None)
    ap.add_argument("--long-edge", type=int, default=LONG_EDGE)
    ap.add_argument("--quality", type=int, default=QUALITY)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        import PIL  # noqa: F401
    except ModuleNotFoundError:
        print("Pillow fehlt: pip install pillow", file=sys.stderr)
        return 1

    total_before = total_after = changed = skipped = 0
    for key in (args.witnesses or WITNESSES):
        folder = DISPUTATION / key / "images"
        if not folder.is_dir():
            print(f"  {key}: kein images/ - übersprungen", file=sys.stderr)
            continue
        w_before = w_after = w_changed = 0
        files = sorted(folder.glob("page_*.jpg"))
        for i, path in enumerate(files, 1):
            before, after, did = process(path, args.long_edge, args.quality,
                                         args.dry_run)
            w_before += before
            w_after += after
            if did:
                w_changed += 1
            else:
                skipped += 1
            if i % 200 == 0:
                print(f"    {key}: {i}/{len(files)}")
        total_before += w_before
        total_after += w_after
        changed += w_changed
        pct = 100 * (1 - w_after / w_before) if w_before else 0
        print(f"  {key:30} {len(files):4} Seiten  "
              f"{human(w_before):>9} -> {human(w_after):>9}  (-{pct:.0f} %)")

    pct = 100 * (1 - total_after / total_before) if total_before else 0
    verb = "würde sparen" if args.dry_run else "gespart"
    print(f"\n  {changed} Bilder verkleinert, {skipped} bereits klein genug")
    print(f"  {human(total_before)} -> {human(total_after)}  ({verb}: {pct:.0f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
