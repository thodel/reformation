#!/usr/bin/env python3
"""Align witnesses page by page (issue #11).

The witnesses paginate differently (496 / 570 / 568 / 836 / 672 pages), so
comparing page against page is meaningless. This establishes which page of one
witness corresponds to which page of another.

Approach, chosen after measuring alternatives on druck_1528 against
a_v_1447_schlussredaktion:

The issue proposed anchoring on the numbered Schlussreden. Measured, that does
not hold: they occur 27 times in the print and 96 in the manuscript, scattered
through running text as references rather than as section headings, so they
would seed mostly false anchors.

What does work is content matching on rare word bigrams. Text is normalised
(scripts/normalize_orthography), reduced to bigrams, and bigrams occurring in
more than a few percent of pages are dropped as uninformative. Scoring a page
by how much of its rare-bigram set is contained in a candidate matched 473 of
484 pages with a perfectly monotone result - order consistency emerges from the
content rather than being imposed.

A monotone dynamic program then picks the best order-consistent set of pairs,
which discards the occasional high-scoring but out-of-order match.

Usage:
  python3 scripts/align_witnesses.py --a druck_1528 --b a_v_1447_schlussredaktion
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_orthography import normalize  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEARCH_ROOTS = (ROOT / "data" / "disputation", ROOT / "data" / "prints")

DEFAULT_NGRAM = 2
DEFAULT_DF_RATIO = 0.05   # bigrams in more than this share of pages are noise
DEFAULT_THRESHOLD = 0.10  # containment below this is not a match
PAGE_RE = re.compile(r"page_(\d+)\.md$")


def witness_dir(key: str) -> Path:
    for root in SEARCH_ROOTS:
        candidate = root / key / "transcriptions"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"No transcriptions directory for witness '{key}'")


def load_pages(key: str) -> dict[int, list[str]]:
    """page number -> normalised word tokens, skipping pages without text."""
    pages: dict[int, list[str]] = {}
    for path in witness_dir(key).glob("page_*.md"):
        match = PAGE_RE.match(path.name)
        if not match:
            continue
        body = re.sub(r"^# Seite \d+\s*", "", path.read_text(encoding="utf-8")).strip()
        if not body:
            continue
        tokens = re.findall(r"\w+", normalize(body).normalized.lower())
        if tokens:
            pages[int(match.group(1))] = tokens
    return pages


def ngrams(tokens: list[str], n: int) -> set[str]:
    if n <= 1:
        return set(tokens)
    return {" ".join(tokens[i : i + n]) for i in range(max(0, len(tokens) - n + 1))}


def score_pairs(
    a_pages: dict[int, list[str]],
    b_pages: dict[int, list[str]],
    *,
    n: int = DEFAULT_NGRAM,
    df_ratio: float = DEFAULT_DF_RATIO,
    threshold: float = DEFAULT_THRESHOLD,
    keep: int = 5,
) -> dict[int, list[tuple[int, float]]]:
    """For each A page, the best-scoring B candidates above the threshold."""
    a_sets = {p: ngrams(t, n) for p, t in a_pages.items()}
    b_sets = {p: ngrams(t, n) for p, t in b_pages.items()}

    document_frequency: collections.Counter[str] = collections.Counter()
    for grams in b_sets.values():
        document_frequency.update(grams)
    cap = max(1.0, len(b_sets) * df_ratio)

    index: dict[str, set[int]] = collections.defaultdict(set)
    for page, grams in b_sets.items():
        for gram in grams:
            if document_frequency[gram] <= cap:
                index[gram].add(page)

    candidates: dict[int, list[tuple[int, float]]] = {}
    for page, grams in a_sets.items():
        rare = {g for g in grams if document_frequency.get(g, 0) <= cap}
        if not rare:
            continue
        counts: collections.Counter[int] = collections.Counter()
        for gram in rare:
            for other in index.get(gram, ()):
                counts[other] += 1
        scored = [(other, hits / len(rare)) for other, hits in counts.items()]
        scored = [(o, s) for o, s in scored if s >= threshold]
        if scored:
            scored.sort(key=lambda item: -item[1])
            candidates[page] = scored[:keep]
    return candidates


def monotone_alignment(candidates: dict[int, list[tuple[int, float]]]) -> list[tuple[int, int, float]]:
    """Best set of pairs whose B pages never run backwards as A advances.

    Both witnesses transmit the same work in the same order, so a pair that
    breaks that order is a coincidence of wording rather than a correspondence.
    """
    options: list[tuple[int, int, float]] = []
    for a_page in sorted(candidates):
        for b_page, score in candidates[a_page]:
            options.append((a_page, b_page, score))
    if not options:
        return []

    # Weighted longest non-decreasing subsequence over (a asc, b asc).
    options.sort(key=lambda item: (item[0], item[1]))
    best = [item[2] for item in options]
    previous = [-1] * len(options)
    for i in range(len(options)):
        for j in range(i):
            if options[j][0] < options[i][0] and options[j][1] <= options[i][1]:
                if best[j] + options[i][2] > best[i]:
                    best[i] = best[j] + options[i][2]
                    previous[i] = j
    end = max(range(len(options)), key=lambda i: best[i])
    chain: list[tuple[int, int, float]] = []
    while end != -1:
        chain.append(options[end])
        end = previous[end]
    return list(reversed(chain))


def build_units(pairs: list[tuple[int, int, float]], a_key: str, b_key: str) -> list[dict[str, Any]]:
    units = []
    for index, (a_page, b_page, score) in enumerate(pairs, start=1):
        units.append({
            "unit": index,
            "score": round(score, 4),
            "pages": {a_key: [a_page], b_key: [b_page]},
        })
    return units


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Align two witnesses page by page")
    parser.add_argument("--a", required=True, help="Reference witness key")
    parser.add_argument("--b", required=True, help="Witness to align against the reference")
    parser.add_argument("--ngram", type=int, default=DEFAULT_NGRAM)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--df-ratio", type=float, default=DEFAULT_DF_RATIO)
    parser.add_argument("--out", default=None, help="Write JSON here")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    a_pages, b_pages = load_pages(args.a), load_pages(args.b)
    print(f"{args.a}: {len(a_pages)} page(s) with text")
    print(f"{args.b}: {len(b_pages)} page(s) with text")

    candidates = score_pairs(
        a_pages, b_pages, n=args.ngram, df_ratio=args.df_ratio, threshold=args.threshold
    )
    pairs = monotone_alignment(candidates)
    coverage = len(pairs) / max(len(a_pages), 1)
    mean = sum(p[2] for p in pairs) / len(pairs) if pairs else 0.0
    print(f"candidates: {len(candidates)} page(s); aligned: {len(pairs)} "
          f"({coverage:.0%} of {args.a}); mean containment {mean:.1%}")

    payload = {
        "reference": args.a,
        "witness": args.b,
        "method": {
            "ngram": args.ngram,
            "df_ratio": args.df_ratio,
            "threshold": args.threshold,
        },
        "aligned": len(pairs),
        "units": build_units(pairs, args.a, args.b),
    }
    out = Path(args.out) if args.out else ROOT / "data" / "alignment" / f"{args.a}__{args.b}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
