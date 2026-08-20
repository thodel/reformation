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
  against its OWN translation, because many of those translations render
  garbled text (see scripts/clean_translations.py). Translations of aligned
  pages between witnesses scored 0.068, which is noise.

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
                pa["reading"] = "reworded"
                recovered += 1

    summary = unit.setdefault("sentences", {})
    scored = [p["semantic"] for p in pairs if "semantic" in p]
    summary["semantic"] = round(sum(scored) / len(scored), 4) if scored else 0.0
    summary["reworded"] = sum(1 for p in pairs if p.get("reading") == "reworded")
    summary["recovered_by_embedding"] = recovered
    summary["embedding_model"] = MODEL_NAME
    return unit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add semantic similarity to sentence pairs")
    parser.add_argument("--pair", required=True, help="Directory name under data/comparison")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N units")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    directory = COMPARISON / args.pair
    if not directory.is_dir():
        print(f"[ERROR] no such pair: {args.pair}", file=sys.stderr)
        return 2

    model = load_model()
    unit_files = sorted(directory.glob("unit_*.json"),
                        key=lambda p: int(p.stem.split("_")[1]))
    if args.limit:
        unit_files = unit_files[: args.limit]

    totals = {"same": 0, "reworded": 0, "different": 0, "check": 0}
    recovered = 0
    for path in unit_files:
        unit = json.loads(path.read_text(encoding="utf-8"))
        unit = annotate_unit(model, unit)
        path.write_text(json.dumps(unit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for p in unit["sentences"]["pairs"]:
            if p.get("reading"):
                totals[p["reading"]] = totals.get(p["reading"], 0) + 1
        recovered += unit["sentences"]["recovered_by_embedding"]

    print(f"{args.pair}: {len(unit_files)} unit(s)")
    for key, count in totals.items():
        print(f"  {key:10} {count}")
    print(f"  recovered by embedding (character found nothing): {recovered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
