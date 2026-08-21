#!/usr/bin/env python3
"""Propose chapter-scale segments for the March 1528 print.

A semi-manual layer: this proposes boundaries, and the table it writes is meant
to be corrected by hand. Nothing downstream should assume the machine got it
right.

Two sources of structure, in order of authority:

  The print carries a running head naming the Schlussred under discussion -
  "Die erſt", "Die ſibend" - on one side of each opening. 202 of 495 pages
  carry a legible one, and they give the work's real divisions: thesis 1 runs
  from about page 20 to 158, thesis 4 from 220 to 354. These are taken as major
  boundaries because they come from the document rather than from a guess.

  Within a thesis, which can run to 139 pages, boundaries are placed where the
  topic moves, measured as a dip in similarity between adjacent pages, subject
  to a segment being between one and ten pages.

The running heads are removed before embedding. Left in, they dominate the
signal: the head alternates between recto and verso, so the sharpest apparent
"topic shifts" were simply the alternation, not the argument moving on.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare_witnesses import page_texts  # noqa: E402
from normalize_orthography import normalize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "segments"
MIN_PAGES = 1
MAX_PAGES = 10
TARGET_PAGES = 6
# Heads alternate sides, so one intervening page is expected; beyond this the
# heads have ended.
HEAD_GAP = 4

# Keys are compared after orthographic normalisation, which folds ů and ü to u
# and removes the combining macron - so "Die nuͤn̄te", "Die nůndte" and "Die
# nünte", the three spellings this print uses for the ninth, all arrive as
# "nunte" or "nundte". Without these the ninth thesis was read as a
# continuation of the eighth.
ORDINALS = {
    "erst": 1, "ander": 2, "dritt": 3, "vierd": 4, "funfft": 5, "funft": 5,
    "sechst": 6, "sibend": 7, "siebend": 7, "acht": 8,
    # The nasal bar is now expanded rather than dropped (#21), so "nuͤn̄te"
    # arrives as "nunnte" and "nůn̄dte" as "nunndte".
    "neunt": 9, "neundt": 9, "nunt": 9, "nundt": 9, "nunnt": 9, "nunndt": 9,
    "zehend": 10, "zehnd": 10, "zehent": 10,
}
HEAD_RE = re.compile(r"(?im)^\s*(?:\*\*)?\s*(?:Die\s+\w+|Schlu[sſß]+red\.?[^\n]{0,12})\s*(?:\*\*)?\s*$")
# The class must admit ů and combining marks: with a narrower one "Die nůndte"
# captured just "n", and "Die nuͤn̄te" stopped at the macron, so the ninth
# thesis was never recognised.
ORDINAL_RE = re.compile(r"(?i)^\s*(?:\*\*)?Die\s+(\S+)")


# Both sides must pass through the same transform. normalize() folds v to u, so
# a raw key of "vierd" stops matching once the observed word becomes "uierde" -
# which is exactly what happened when this switched to full normalisation.
ORDINALS = {normalize(k).normalized.lower(): v for k, v in ORDINALS.items()}


def thesis_of(text: str) -> int | None:
    match = ORDINAL_RE.search(text[:60])
    if not match:
        return None
    # normalize() folds ů/ü to u and strips combining marks; the previous
    # hand-rolled substitution handled only ſ and the combining e.
    word = normalize(match.group(1)).normalized.lower()
    for key, number in ORDINALS.items():
        if word.startswith(key):
            return number
    return None


def strip_running_head(text: str) -> str:
    """Drop the running head, which otherwise dominates page similarity."""
    lines = text.splitlines()
    while lines and (not lines[0].strip() or HEAD_RE.match(lines[0])):
        lines.pop(0)
    return "\n".join(lines).strip()


def thesis_spans(texts: dict[int, str], pages: list[int]) -> dict[int, int]:
    """Assign each page to a thesis, filling gaps forward.

    Only about 40% of pages carry a legible head, and OCR occasionally reads
    one wrongly, so the sequence is forced to run forwards: a head that would
    send the reader back to an earlier thesis is treated as a misreading.
    """
    assigned: dict[int, int] = {}
    current = 0
    since_head = 0
    for page in pages:
        found = thesis_of(texts[page])
        if found is not None and found >= current:
            current = found
            since_head = 0
        else:
            since_head += 1
        # The running head is the evidence. It alternates recto/verso, so a gap
        # of one page is normal; a long gap means the heads have stopped, as
        # they do after p481 where the closing matter begins. Claiming a thesis
        # there would assert something the print does not say.
        assigned[page] = current if since_head <= HEAD_GAP else 0
    return assigned


def boundaries_within(block: list[int], sims: dict[int, float]) -> list[list[int]]:
    """Split one thesis into segments of MIN_PAGES..MAX_PAGES pages."""
    if len(block) <= MAX_PAGES:
        return [block]
    segments: list[list[int]] = []
    start = 0
    while start < len(block):
        remaining = len(block) - start
        if remaining <= MAX_PAGES:
            segments.append(block[start:])
            break
        # Choose the weakest link in the window where a cut is allowed.
        lo = start + MIN_PAGES
        hi = min(start + MAX_PAGES, len(block) - 1)
        window = range(lo, hi + 1)
        cut = min(window, key=lambda i: sims.get(block[i - 1], 1.0))
        # Prefer a cut near the target length when scores are close.
        segments.append(block[start:cut])
        start = cut
    return [s for s in segments if s]


def build(witness: str, out_dir: Path) -> dict[str, Any]:
    texts = page_texts(witness)
    pages = sorted(texts)
    bodies = {p: strip_running_head(texts[p]) for p in pages}

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        emb = model.encode([bodies[p] for p in pages], batch_size=32,
                           show_progress_bar=False, normalize_embeddings=True)
        sims = {pages[i]: float(np.dot(emb[i], emb[i + 1])) for i in range(len(pages) - 1)}
    except ModuleNotFoundError:
        print("[WARN] sentence-transformers absent; cutting on length alone", file=sys.stderr)
        sims = {}

    thesis = thesis_spans(texts, pages)
    blocks: list[tuple[int, list[int]]] = []
    for page in pages:
        if blocks and blocks[-1][0] == thesis[page]:
            blocks[-1][1].append(page)
        else:
            blocks.append((thesis[page], [page]))

    segments = []
    for number, block in blocks:
        for part in boundaries_within(block, sims):
            segments.append({
                "segment": len(segments) + 1,
                "thesis": number or "",
                "first_page": part[0],
                "last_page": part[-1],
                "pages": len(part),
                "title": "",
                "summary": "",
            })
    return {"witness": witness, "segments": segments,
            "sims": {str(k): round(v, 4) for k, v in sims.items()}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Propose chapter-scale segments")
    parser.add_argument("--witness", default="druck_1528")
    args = parser.parse_args()

    payload = build(args.witness, OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    segments = payload["segments"]

    table = OUT_DIR / f"{args.witness}_segments.tsv"

    # Carry forward anything a human wrote. Re-running previously discarded all
    # 83 titles and summaries without warning, which would have thrown away
    # work this table exists to hold.
    previous: dict[tuple[int, int], tuple[str, str]] = {}
    if table.exists():
        with table.open(encoding="utf-8") as fh:
            old = list(csv.reader(fh, delimiter="\t"))
        if old:
            head = old[0]
            fp, lp = head.index("first_page"), head.index("last_page")
            ti, su = head.index("title"), head.index("summary")
            for row in old[1:]:
                if len(row) > su:
                    previous[(int(row[fp]), int(row[lp]))] = (row[ti], row[su])
    carried = 0
    for seg in segments:
        prior = previous.get((seg["first_page"], seg["last_page"]))
        if prior and prior[0]:
            seg["title"], seg["summary"] = prior
            carried += 1

    with table.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["segment", "thesis", "first_page", "last_page", "pages", "title", "summary"])
        for s in segments:
            writer.writerow([s["segment"], s["thesis"], s["first_page"],
                             s["last_page"], s["pages"], s["title"], s["summary"]])

    (OUT_DIR / f"{args.witness}_segments.json").write_text(
        json.dumps({"witness": args.witness, "segments": segments},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lengths = [s["pages"] for s in segments]
    print(f"{len(segments)} segment(s) over {sum(lengths)} pages")
    print(f"  pages per segment: min {min(lengths)}, median {statistics.median(lengths):.0f}, max {max(lengths)}")
    by_thesis: dict[Any, int] = {}
    for s in segments:
        by_thesis[s["thesis"]] = by_thesis.get(s["thesis"], 0) + 1
    print(f"  segments per thesis: {dict(sorted(by_thesis.items(), key=lambda x: str(x[0])))}")
    print(f"  carried forward {carried} existing title(s)")
    print(f"wrote {table.relative_to(ROOT)} (editable) and the JSON beside it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
