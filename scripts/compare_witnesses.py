#!/usr/bin/env python3
"""Precompute comparison data between witnesses (issue #12).

Produces two granularities for every aligned page pair:

  coarse - paragraph level: which paragraphs match, which are only in one
           witness, which were rewritten
  fine   - word level within a pair, as difflib opcodes over normalised text
           while carrying the original wording for display

Results are precomputed to JSON so the published site needs no server.

Rerunning
---------
The sources are not static. Manuscript transcriptions are corrected by hand in
Transkribus and arrive through the daily sync, and recognised print text may be
redone with a better model. So every output records a fingerprint of the exact
source text it was built from: the md5 of each witness's normalised page text.
A run whose fingerprints match the stored ones does nothing and writes nothing,
so an unchanged day produces no diff and therefore no commit; a run whose
sources moved regenerates the pair.

Usage:
  python3 scripts/compare_witnesses.py --a druck_1528 --b a_v_1447_schlussredaktion
  python3 scripts/compare_witnesses.py --all --check    # report staleness only
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import itertools
import json
import re
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
    witness_dir,
)
from normalize_orthography import normalize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "comparison"
PAGE_RE = re.compile(r"page_(\d+)\.md$")
MAX_FINE_SEGMENTS = 400  # a pair with more segments than this is not a comparison


def page_texts(key: str) -> dict[int, str]:
    """page number -> original (un-normalised) body text."""
    texts: dict[int, str] = {}
    for path in witness_dir(key).glob("page_*.md"):
        match = PAGE_RE.match(path.name)
        if not match:
            continue
        body = re.sub(r"^# Seite \d+\s*", "", path.read_text(encoding="utf-8")).strip()
        if body:
            texts[int(match.group(1))] = body
    return texts


_FINGERPRINTS: dict[str, str] = {}


def fingerprint(key: str) -> str:
    """Hash of the witness's normalised text, stable across reruns.

    Normalised rather than raw, so a correction that only changes orthography
    - which the comparison folds away anyway - does not force a regeneration.
    """
    if key in _FINGERPRINTS:
        return _FINGERPRINTS[key]
    texts = page_texts(key)          # read once; this used to re-read every page
    digest = hashlib.md5()
    for page in sorted(texts):
        digest.update(str(page).encode())
        digest.update(normalize(texts[page]).normalized.encode("utf-8"))
    _FINGERPRINTS[key] = digest.hexdigest()
    return _FINGERPRINTS[key]


def paragraphs(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:
        # Line-broken transcriptions have no blank lines; treat the page as one
        # block rather than pretending every line is a paragraph.
        return [" ".join(text.split())] if text.strip() else []
    return [" ".join(b.split()) for b in blocks]


def norm_words(text: str) -> list[str]:
    return [normalize(w).normalized.lower() for w in re.findall(r"\w+", text)]


def original_words(text: str) -> list[str]:
    """Words as written. Index-aligned with norm_words, so the comparison runs
    on normalised forms while the display keeps the original orthography."""
    return re.findall(r"\w+", text)


def coarse_diff(a_text: str, b_text: str) -> dict[str, Any]:
    a_paras, b_paras = paragraphs(a_text), paragraphs(b_text)
    a_norm = [" ".join(norm_words(p)) for p in a_paras]
    b_norm = [" ".join(norm_words(p)) for p in b_paras]
    # autojunk=False is essential: difflib otherwise discards any element
    # occurring in more than 1% of a sequence of 200+ items as "popular junk".
    # Pages here run a median of 260 words, so 440 of 496 cross that threshold
    # and common words like der/vnd would be silently dropped from the
    # comparison. On the worst measured page it reported 0.127 similarity where
    # the true value is 0.480.
    matcher = difflib.SequenceMatcher(None, a_norm, b_norm, autojunk=False)
    counts = {"equal": 0, "replace": 0, "delete": 0, "insert": 0}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        counts[tag] += max(i2 - i1, j2 - j1)
    return {
        "paragraphs": {"a": len(a_paras), "b": len(b_paras)},
        "counts": counts,
        "similarity": round(matcher.ratio(), 4),
    }


def fine_diff(a_text: str, b_text: str) -> dict[str, Any]:
    """Word-level comparison.

    Equal stretches are kept alongside the differing ones, so the viewer can
    show each witness's full page with the differences marked in place. Showing
    only the differing fragments strips away the context that makes a variant
    legible.

    Matching runs on normalised forms while the emitted text is the original
    orthography, which is the point of the edition: `vnnd` and `unnd` must not
    count as a variant, but the reader should still see what is on the page.
    """
    a_norm, b_norm = norm_words(a_text), norm_words(b_text)
    a_orig, b_orig = original_words(a_text), original_words(b_text)
    matcher = difflib.SequenceMatcher(None, a_norm, b_norm, autojunk=False)

    segments: list[dict[str, Any]] = []
    ops = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            ops += 1
        segments.append({
            "op": tag,
            "a": " ".join(a_orig[i1:i2]),
            "b": " ".join(b_orig[j1:j2]),
        })
    truncated = len(segments) > MAX_FINE_SEGMENTS
    return {
        "similarity": round(matcher.ratio(), 4),
        "words": {"a": len(a_norm), "b": len(b_norm)},
        "segments": segments[:MAX_FINE_SEGMENTS],
        "ops": ops,
        "truncated": truncated,
    }


def compare(a_key: str, b_key: str, *, threshold: float, ngram: int, df_ratio: float) -> dict[str, Any]:
    a_pages, b_pages = load_pages(a_key), load_pages(b_key)
    candidates = score_pairs(
        a_pages, b_pages, n=ngram, df_ratio=df_ratio, threshold=threshold
    )
    pairs = monotone_alignment(candidates)

    a_text, b_text = page_texts(a_key), page_texts(b_key)
    units = []
    for index, (a_page, b_page, score) in enumerate(pairs, start=1):
        at, bt = a_text.get(a_page, ""), b_text.get(b_page, "")
        units.append({
            "unit": index,
            "pages": {a_key: [a_page], b_key: [b_page]},
            "alignment_score": round(score, 4),
            "coarse": coarse_diff(at, bt),
            "fine": fine_diff(at, bt),
        })

    similarities = [u["fine"]["similarity"] for u in units]
    return {
        "a": a_key,
        "b": b_key,
        "source_fingerprints": {a_key: fingerprint(a_key), b_key: fingerprint(b_key)},
        "method": {"ngram": ngram, "df_ratio": df_ratio, "threshold": threshold},
        "aligned_pages": len(units),
        "mean_similarity": round(sum(similarities) / len(similarities), 4) if similarities else 0.0,
        "units": units,
    }


def pair_dir(a_key: str, b_key: str) -> Path:
    return OUT_DIR / f"{a_key}__{b_key}"


def out_path(a_key: str, b_key: str) -> Path:
    """The pair's index file."""
    return pair_dir(a_key, b_key) / "index.json"


def write_pair(payload: dict[str, Any]) -> tuple[int, int]:
    """Write a light index plus one file per unit.

    The viewer must not download the whole comparison to show one page: the
    druck_1528/a_v_1447 pair is 2.7 MB while a single unit is about 3 KB. The
    index carries only what a list needs - page numbers and scores - and each
    unit's diff is fetched when it is opened.
    """
    a_key, b_key = payload["a"], payload["b"]
    directory = pair_dir(a_key, b_key)
    directory.mkdir(parents=True, exist_ok=True)

    # Drop any units left from a previous, longer run.
    for stale in directory.glob("unit_*.json"):
        stale.unlink()

    index_units = []
    unit_bytes = 0
    for unit in payload["units"]:
        number = unit["unit"]
        text = json.dumps(unit, ensure_ascii=False, indent=2) + "\n"
        (directory / f"unit_{number}.json").write_text(text, encoding="utf-8")
        unit_bytes += len(text.encode("utf-8"))
        index_units.append({
            "unit": number,
            "pages": unit["pages"],
            "alignment_score": unit["alignment_score"],
            "similarity": unit["fine"]["similarity"],
            "coarse_similarity": unit["coarse"]["similarity"],
            "ops": unit["fine"]["ops"],
        })

    index = {k: v for k, v in payload.items() if k != "units"}
    index["units"] = index_units
    index_text = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    (directory / "index.json").write_text(index_text, encoding="utf-8")
    return len(index_text.encode("utf-8")), unit_bytes


def is_stale(a_key: str, b_key: str) -> bool:
    path = out_path(a_key, b_key)
    if not path.exists():
        return True
    try:
        stored = json.loads(path.read_text(encoding="utf-8")).get("source_fingerprints", {})
    except Exception:
        return True
    return stored.get(a_key) != fingerprint(a_key) or stored.get(b_key) != fingerprint(b_key)


def available_witnesses() -> list[str]:
    keys = []
    for root in (ROOT / "data" / "disputation", ROOT / "data" / "prints"):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if (child / "transcriptions").is_dir() and any(
                (child / "transcriptions").glob("page_*.md")
            ):
                keys.append(child.name)
    return keys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute witness comparison data")
    parser.add_argument("--a")
    parser.add_argument("--b")
    parser.add_argument("--all", action="store_true", help="Every pair of available witnesses")
    parser.add_argument("--check", action="store_true",
                        help="Report which pairs are stale and exit non-zero if any are")
    parser.add_argument("--force", action="store_true", help="Rebuild even if fingerprints match")
    parser.add_argument("--ngram", type=int, default=DEFAULT_NGRAM)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--df-ratio", type=float, default=DEFAULT_DF_RATIO)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.all:
        pairs = list(itertools.combinations(available_witnesses(), 2))
    elif args.a and args.b:
        pairs = [(args.a, args.b)]
    else:
        print("[ERROR] give --a and --b, or --all", file=sys.stderr)
        return 2

    stale = [pair for pair in pairs if args.force or is_stale(*pair)]

    if args.check:
        print(f"{len(pairs)} pair(s); {len(stale)} stale")
        for a_key, b_key in stale:
            print(f"  stale: {a_key} <-> {b_key}")
        return 1 if stale else 0

    if not stale:
        print(f"{len(pairs)} pair(s), all current. Nothing regenerated.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for a_key, b_key in stale:
        payload = compare(a_key, b_key, threshold=args.threshold,
                          ngram=args.ngram, df_ratio=args.df_ratio)
        index_bytes, unit_bytes = write_pair(payload)
        print(f"{a_key} <-> {b_key}: {payload['aligned_pages']} unit(s), "
              f"mean word similarity {payload['mean_similarity']:.1%}, "
              f"index {index_bytes / 1024:.0f} KB + units {unit_bytes / 1048576:.1f} MB")
    print(f"\nregenerated {len(stale)} of {len(pairs)} pair(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
