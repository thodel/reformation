#!/usr/bin/env python3
"""Semantic similarity between sentence units (issue #35).

Complements the character comparison, which cannot tell three things apart:
recognition noise, orthographic variation, and genuine textual difference. A
pair that scores low on characters may be rewritten, misaligned, or simply
misread - the number does not say which.

What was measured before building this
--------------------------------------
Two approaches from the original plan were tested and both failed:

  Embedding the modern translations - the plan's centrepiece - is not viable.
  Only two witnesses have translations at all, and druck_1528 scores 0.234
  against its OWN translation. The reason turned out to be blunter than
  "poor translations": 472 of its 552 translation files are not translations
  but WebDAV error responses, saved verbatim when a fetch failed. Only 80
  pages of the base text are actually translated. Translations of aligned
  pages between witnesses scored 0.068, which is what comparing German prose
  against XML error documents produces.

  Embedding whole pages does not discriminate. Aligned pages scored 0.787 and
  randomly paired pages 0.750 - a separation of 0.037. At page scale the model
  reports "this is sixteenth-century German theological prose", which every
  page here satisfies.

At sentence scale the same model separates cleanly: matched sentences 0.931
against 0.533 for random pairs, a separation of 0.399. Averaging 260 words into
384 dimensions destroys what distinguishes a passage; twenty words retain it.

So this works on the sentence units from #34, on the original Early New High
German, and needs no translations.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
COMPARISON = ROOT / "data" / "comparison"

# Recorded in the output: a model change must mark the data stale rather than
# silently altering it, the same rule the recognition state follows.
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
# Below the control median (0.533) a score carries no information.
SEMANTIC_FLOOR = 0.60
# Character similarity under this, with embedding similarity over the floor, is
# the case worth surfacing: same content, different words - or a misalignment.
CHARACTER_CEILING = 0.50


def load_model(name: str = MODEL_NAME):
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "sentence-transformers is not installed. Run: pip install sentence-transformers"
        ) from exc
    return SentenceTransformer(name)


def embed(model, texts: list[str]):
    return model.encode(texts, batch_size=32, show_progress_bar=False,
                        normalize_embeddings=True)


def _cosine(a, b) -> float:
    """Dot product of two already-normalised vectors.

    Imported lazily so the module stays usable - and testable - without the
    embedding stack installed. A unit with nothing to embed must not require
    numpy to be present.
    """
    import numpy as np
    return float(np.dot(a, b))


def classify(character: float, semantic: float) -> str:
    """How to read a pair of scores.

    The interesting cell is low character with high semantic: the character
    comparison alone cannot separate that from genuine difference.
    """
    if semantic < SEMANTIC_FLOOR:
        return "different" if character < CHARACTER_CEILING else "check"
    return "reworded" if character < CHARACTER_CEILING else "same"


def annotate_unit(model, unit: dict[str, Any]) -> dict[str, Any]:
    """Add semantic similarity to a unit's sentence pairs."""
    pairs = unit.get("sentences", {}).get("pairs", [])
    matched = [p for p in pairs if p["op"] == "match" and p.get("a") and p.get("b")]
    if matched:
        ea = embed(model, [p["a"] for p in matched])
        eb = embed(model, [p["b"] for p in matched])
        for i, p in enumerate(matched):
            semantic = _cosine(ea[i], eb[i])
            p["semantic"] = round(semantic, 4)
            p["reading"] = classify(p.get("similarity", 0.0), semantic)

    # Unmatched units on both sides: the character method found nothing, but
    # the content may still correspond. This is where the two methods differ.
    only_a = [p for p in pairs if p["op"] == "only_a" and p.get("a")]
    only_b = [p for p in pairs if p["op"] == "only_b" and p.get("b")]
    recovered = 0
    if only_a and only_b:
        ea = embed(model, [p["a"] for p in only_a])
        eb = embed(model, [p["b"] for p in only_b])
        for i, pa in enumerate(only_a):
            scores = [_cosine(ea[i], eb[j]) for j in range(len(only_b))]
            best = max(range(len(scores)), key=lambda j: scores[j])
            if scores[best] >= SEMANTIC_FLOOR:
                pa["semantic"] = round(scores[best], 4)
                pa["semantic_match"] = only_b[best]["b"]
                # Deliberately NOT "reworded". Where the character matcher found
                # a pair and the embedding merely reinterprets it, hand-checking
                # gave 6 of 6 correct. Where the embedding alone proposes the
                # pair, it gave roughly 1 in 3 - and the score does not separate
                # them: false ones scored 0.72-0.78, true ones 0.66-0.89. A
                # higher floor would not fix that, so these are labelled as what
                # they are: candidates for a human to judge.
                pa["reading"] = "candidate"
                recovered += 1

    summary = unit.setdefault("sentences", {})
    scored = [p["semantic"] for p in pairs if "semantic" in p]
    summary["semantic"] = round(sum(scored) / len(scored), 4) if scored else 0.0
    summary["reworded"] = sum(1 for p in pairs if p.get("reading") == "reworded")
    summary["candidates"] = sum(1 for p in pairs if p.get("reading") == "candidate")
    summary["recovered_by_embedding"] = recovered
    summary["embedding_model"] = MODEL_NAME
    return unit


def pair_dirs() -> list[Path]:
    return [d for d in sorted(COMPARISON.iterdir())
            if d.is_dir() and "__" in d.name]


def missing_semantic(directory: Path) -> tuple[int, int]:
    """(units lacking semantic data, units total) for one pair.

    Semantic annotation is added on top of the comparison output, so
    regenerating a pair removes it. That is correct - a changed text needs
    re-embedding - but it must be visible rather than silent, which is what
    this reports.
    """
    total = missing = 0
    for path in directory.glob("unit_*.json"):
        total += 1
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            missing += 1
            continue
        sentences = payload.get("sentences", {})
        if sentences.get("embedding_model") != MODEL_NAME:
            missing += 1
    return missing, total


def cmd_check() -> int:
    stale = []
    for directory in pair_dirs():
        missing, total = missing_semantic(directory)
        if total and missing:
            stale.append((directory.name, missing, total))
    if not stale:
        print("semantic annotation: current for every pair")
        return 0
    print(f"semantic annotation missing or outdated in {len(stale)} pair(s):")
    for name, missing, total in stale:
        print(f"  {name}: {missing}/{total} unit(s)")
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add semantic similarity to sentence pairs")
    parser.add_argument("--pair", help="Directory name under data/comparison")
    parser.add_argument("--all", action="store_true", help="Every pair that needs it")
    parser.add_argument("--check", action="store_true",
                        help="Report which pairs lack semantic data, exit 1 if any do")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N units")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        return cmd_check()

    if args.all:
        targets = [d for d in pair_dirs() if missing_semantic(d)[0]]
        if not targets:
            print("semantic annotation current for every pair; nothing to do.")
            return 0
    elif args.pair:
        directory = COMPARISON / args.pair
        if not directory.is_dir():
            print(f"[ERROR] no such pair: {args.pair}", file=sys.stderr)
            return 2
        targets = [directory]
    else:
        print("[ERROR] give --pair, --all, or --check", file=sys.stderr)
        return 2

    model = load_model()
    for directory in targets:
        annotate_pair(model, directory, args.limit)
    return 0


def annotate_pair(model, directory: Path, limit: int = 0) -> None:
    unit_files = sorted(directory.glob("unit_*.json"),
                        key=lambda p: int(p.stem.split("_")[1]))
    if limit:
        unit_files = unit_files[:limit]

    totals = {"same": 0, "reworded": 0, "candidate": 0, "different": 0, "check": 0}
    recovered = 0
    for path in unit_files:
        unit = json.loads(path.read_text(encoding="utf-8"))
        unit = annotate_unit(model, unit)
        path.write_text(json.dumps(unit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for p in unit["sentences"]["pairs"]:
            if p.get("reading"):
                totals[p["reading"]] = totals.get(p["reading"], 0) + 1
        recovered += unit["sentences"]["recovered_by_embedding"]

    print(f"{directory.name}: {len(unit_files)} unit(s)")
    for key, count in totals.items():
        print(f"  {key:10} {count}")
    print(f"  of which proposed by embedding alone: {recovered} "
          f"(labelled 'candidate' - roughly one in three held up by hand)")


if __name__ == "__main__":
    raise SystemExit(main())
