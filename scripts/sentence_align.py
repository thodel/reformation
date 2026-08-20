#!/usr/bin/env python3
"""Sentence-scale segmentation and matching (issue #34).

A middle ground between the word diff, which is too fine to read as a variant,
and the page, which is too coarse to locate one.

Segmentation does not use sentence-final punctuation. Measured across the
corpus, that produces units of unlike size between witnesses, because the
prints set the Virgel `/` where the manuscript transcription uses a comma:
splitting on `. ? !` gives a median of 13 words in druck_1528 against 24 in
a_v_1447, a ratio of 0.55. Comparing units of unlike size manufactures exactly
the false variants this layer exists to remove.

Splitting on the clause set including the Virgel gives a ratio of 1.00 - a
median of 6 words in both - and holds across all five prints (5-7 words).
Clauses that short are themselves too fine, and about 9% are single-word
fragments, so adjacent clauses are grouped up to a target length to form
sentence-scale units.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from align_witnesses import monotone_alignment  # noqa: E402
from normalize_orthography import normalize  # noqa: E402

# The Virgel is a clause marker in these prints, not a slash.
CLAUSE_SPLIT = re.compile(r"(?<=[.?!/:;])\s+")
TARGET_WORDS = 20
MIN_SENTENCE_SIMILARITY = 0.30


def split_clauses(text: str) -> list[str]:
    return [c.strip() for c in CLAUSE_SPLIT.split(text or "") if c.strip()]


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def group_sentences(clauses: list[str], target: int = TARGET_WORDS) -> list[str]:
    """Bundle adjacent clauses into units of roughly `target` words.

    A clause of six words is too fine to read as a variant, and roughly one in
    eleven is a single word. Grouping also absorbs a missing punctuation mark,
    which would otherwise merge or split a unit outright.
    """
    units: list[str] = []
    buffer: list[str] = []
    count = 0
    for clause in clauses:
        buffer.append(clause)
        count += word_count(clause)
        if count >= target:
            units.append(" ".join(buffer))
            buffer, count = [], 0
    if buffer:
        # A short tail joins the previous unit rather than standing alone.
        tail = " ".join(buffer)
        if units and count < target / 2:
            units[-1] = units[-1] + " " + tail
        else:
            units.append(tail)
    return units


def sentences(text: str, target: int = TARGET_WORDS) -> list[str]:
    return group_sentences(split_clauses(text), target)


def norm_tokens(text: str) -> list[str]:
    return [normalize(w).normalized.lower() for w in re.findall(r"\w+", text)]


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm_tokens(a), norm_tokens(b), autojunk=False).ratio()


def align_sentences(
    a_units: list[str],
    b_units: list[str],
    *,
    threshold: float = MIN_SENTENCE_SIMILARITY,
) -> list[dict]:
    """Match sentence units within an already aligned page pair.

    Candidates are scored pairwise and then reduced to an order-consistent
    chain, the same rule the page alignment uses: both witnesses transmit the
    text in the same order, so a match that runs backwards is a coincidence of
    wording. Unmatched units on either side are reported rather than dropped -
    an omission is a variant too.
    """
    if not a_units or not b_units:
        return [{"op": "only_a", "a": u, "b": None, "similarity": 0.0} for u in a_units] + \
               [{"op": "only_b", "a": None, "b": u, "similarity": 0.0} for u in b_units]

    candidates: dict[int, list[tuple[int, float]]] = {}
    for i, a in enumerate(a_units):
        scored = []
        for j, b in enumerate(b_units):
            s = similarity(a, b)
            if s >= threshold:
                scored.append((j, s))
        if scored:
            scored.sort(key=lambda t: -t[1])
            candidates[i] = scored[:4]

    # strict: a sentence in B must not be reported as matching two in A.
    chain = monotone_alignment(candidates, strict=True)
    matched_a = {i for i, _, _ in chain}
    matched_b = {j for _, j, _ in chain}

    result: list[dict] = []
    used_b = 0
    for i, a in enumerate(a_units):
        # Emit any B units skipped before this match, so order is preserved.
        pair = next(((j, s) for x, j, s in chain if x == i), None)
        if pair:
            j, s = pair
            while used_b < j:
                if used_b not in matched_b:
                    result.append({"op": "only_b", "a": None, "b": b_units[used_b], "similarity": 0.0})
                used_b += 1
            result.append({"op": "match", "a": a, "b": b_units[j], "similarity": round(s, 4)})
            used_b = j + 1
        elif i not in matched_a:
            result.append({"op": "only_a", "a": a, "b": None, "similarity": 0.0})
    while used_b < len(b_units):
        if used_b not in matched_b:
            result.append({"op": "only_b", "a": None, "b": b_units[used_b], "similarity": 0.0})
        used_b += 1
    return result


def summarise(pairs: list[dict]) -> dict:
    matched = [p for p in pairs if p["op"] == "match"]
    return {
        "units": len(pairs),
        "matched": len(matched),
        "only_a": sum(1 for p in pairs if p["op"] == "only_a"),
        "only_b": sum(1 for p in pairs if p["op"] == "only_b"),
        "similarity": round(sum(p["similarity"] for p in matched) / len(matched), 4) if matched else 0.0,
    }
