#!/usr/bin/env python3
"""Give the recognised prints a viewer manifest.

The four prints were recognised from IIIF without storing any images (issue #7),
so they have transcriptions and nothing else. The viewer needs a manifest per
witness to show a page, so this writes one that points every facsimile at
e-rara rather than at a local file - the same decision as the recognition:
the images stay where they are, the repository keeps the text.

Pages the recogniser produced no text for are still listed. A blank leaf is
part of the book, and dropping it would shift every page number after it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import erara  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRINTS = ROOT / "data" / "prints"
CONFIG = ROOT / "config" / "prints.json"
PAGE_RE = re.compile(r"page_(\d+)\.md$")


def transcribed_pages(key: str) -> set[int]:
    directory = PRINTS / key / "transcriptions"
    if not directory.is_dir():
        return set()
    out = set()
    for path in directory.glob("page_*.md"):
        m = PAGE_RE.match(path.name)
        if m and path.read_text(encoding="utf-8").strip():
            out.add(int(m.group(1)))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Write viewer manifests for the prints")
    parser.add_argument("--size", default="!1600,1600",
                        help="IIIF size for the viewer (default: !1600,1600)")
    args = parser.parse_args()

    payload = json.loads(CONFIG.read_text(encoding="utf-8"))
    written = 0
    for witness in payload.get("witnesses", []):
        key = witness["key"]
        if witness.get("skip"):
            continue
        directory = PRINTS / key
        if not (directory / "transcriptions").is_dir():
            print(f"  [skip] {key}: no transcriptions")
            continue

        try:
            manifest = erara.load_manifest(witness["erara_id"])
            pages = erara.pages_from_manifest(manifest)
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] {key}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue

        have_text = transcribed_pages(key)
        entries = []
        for page in pages:
            canvas = page.canvas_id.rstrip("/").rsplit("/", 1)[-1]
            entries.append({
                "page_nr": page.page_nr,
                "image": page.image_url(args.size),
                "transcription": (f"transcriptions/page_{page.page_nr}.md"
                                  if page.page_nr in have_text else None),
                "translation": None,
                "label": page.label,
                "erara": f"https://www.e-rara.ch/content/pageview/{canvas}" if canvas.isdigit() else None,
            })

        out = {
            "variant_id": witness["key"],
            "source": "e-rara",
            "doi": witness.get("doi"),
            "library": witness.get("library"),
            "page_count": len(entries),
            "transcribed_pages": len(have_text),
            "pages": entries,
        }
        (directory / "viewer_manifest.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
        print(f"  {key:22} {len(entries):4} pages, {len(have_text):4} with text")

    print(f"wrote {written} manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
