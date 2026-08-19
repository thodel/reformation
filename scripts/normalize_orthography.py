#!/usr/bin/env python3
"""
Normalize Early New High German (frühneuhochdeutsch) orthography.

This is a rule-based normalizer that produces a normalized form for comparison
while preserving the original transcription unchanged.

Rules (in order):
  1. u/v → u (context-insensitive, historical u/v variation)
  2. i/j → i (i/j interchange, notably "jnn" → "inn")
  3. ſ (long s) → s
  4. Übergeschriebene Vokale: the combining mark is stripped and the base letter
     kept - uͦ→u, aͤ→a, oͤ→o. Folding to the base rather than to ä/ö/ü is
     deliberate: it makes a witness spelling "goͤtlich" match one spelling
     "gotlich", which is the point of normalising for collation.
     Input is decomposed to NFD first, so precomposed spellings (ů, ö, ē, ñ)
     normalise identically to their combining equivalents. The corpus contains
     both: Transkribus writes u+U+0366, druck_1528 writes ů.
  5. Abbreviaturen: uel → "uel", "̄" (macron) stripped as quant. marker
  6. Nasalstriche: x̄ → "x" (z̄ → z, m̄ → m, n̄ → n) — x̄/m̄/n̄/z̄ stripped
  7. Interpunktion: Virgel "/" kept as word separator (not stripped)
  8. Whitespace collapsed to single space

Usage:
  python3 -c "from normalize_orthography import normalize; print(normalize('vnnderscheid'))"
  python3 scripts/normalize_orthography.py --text "bas ſchadē" --stats
  python3 scripts/normalize_orthography.py --file data/disputation/druck_1528/transcriptions/page_100.md

Config (via environment or config/normalization.yaml):
  STRIP_MACRON: strip ̄ as quantitative marker (default: True)
  PRESERVE_COMBINING: keep combining marks in original (default: True)
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import NamedTuple

# ── Single-character substitutions (applied first, in order) ────────────────

# Long-s → s
LONG_S = str.maketrans("\u017f", "s")  # ſ → s

# u/v normalization: v in orthographic function is always u in Early NHG
UV = str.maketrans("v", "u")

# i/j normalization: j used for consonant i
IJ = str.maketrans("j", "i")

# ── Combining diacritics (Unicode combining characters) ──────────────────────

# Combining Macron (U+0304) — stripped as quantitative marker, value preserved
COMBINING_MACRON = "\u0304"
# Combiningbreve (U+0306)
COMBINING_BREVE = "\u0306"
# Combining diacritic above (U+0307 - dot above, as in oͤ)
COMBINING_DOT_ABOVE = "\u0307"
# Combiningdiaeresis (U+0308 - oͤ, aͤ)
COMBINING_DIAERESIS = "\u0308"

# Map of combining mark → preferred resolution
COMBINING_RESOLVE = {
    COMBINING_MACRON: "",      # quantitative marker stripped
    COMBINING_BREVE: "",       # strip
    COMBINING_DOT_ABOVE: "",   # strip
    COMBINING_DIAERESIS: "",   # strip
}

# Characters that, when combined with a combining mark, form a known ligature
# e.g. u + combining macron + combiningdiaeresis → "ur" removed as "uel" type
COMBINING_SEQUENCES: list[tuple[str, str, str]] = [
    # (base_char, combining_mark, resolved_string)
    ("u", COMBINING_MACRON, "u"),
    ("u", COMBINING_DIAERESIS, ""),  # uͤ → ue
    ("o", COMBINING_DIAERESIS, "ö"),
    ("a", COMBINING_DIAERESIS, "ä"),
    ("e", COMBINING_DIAERESIS, "ë"),
]

# ── Abbreviation patterns ────────────────────────────────────────────────────

# Patterns matched as word suffixes / standalone tokens
ABBREVIATIONS: dict[str, str] = {
    "̄":   "",     # macrons alone = quantitative marker (already handled)
    "x̄":  "x",    # x with macron → x (x̄ = "et" abbreviation)
    "z̄":  "z",
    "m̄":  "m",
    "n̄":  "n",
    "uel": "uel",  # "uel" retained as-is (not resolved)
}

# ── Normalization result ─────────────────────────────────────────────────────

class Normalized(NamedTuple):
    original: str
    normalized: str
    normalization_info: dict

    def as_dict(self) -> dict:
        return {
            "original": self.original,
            "normalized": self.normalized,
            "normalization_info": self.normalization_info,
        }


def _resolve_combining(text: str) -> tuple[str, list[str]]:
    """Resolve combining diacritics attached to vowels.

    Returns (resolved_text, list_of_notes).
    """
    info: list[str] = []
    chars = list(text)
    i = 0
    out: list[str] = []
    while i < len(chars):
        c = chars[i]
        if isinstance(c, str) and not c.isalpha() and not c.isspace():
            # Non-alphanumeric: pass through and check for combining following
            next_c = chars[i + 1] if i + 1 < len(chars) else ""
            # Check for known combining sequences
            resolved = False
            for base, combining, replacement in COMBINING_SEQUENCES:
                if c == base and next_c == combining:
                    out.append(base)
                    if replacement:
                        out.append(replacement)
                    elif combining == COMBINING_DIAERESIS:
                        out.append("e")  # uͤ → ue, oͤ → ö handled above
                    info.append(f"combining_{unicodedata.name(combining, 'UNKNOWN').lower()}")
                    i += 2
                    resolved = True
                    break
            if resolved:
                continue

            # Standalone combining mark
            if next_c in COMBINING_RESOLVE:
                info.append(f"stripped_{unicodedata.name(next_c, 'UNKNOWN').lower()}")
                i += 2  # skip combining char
                out.append(c)
                continue
            out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out), info


def _strip_abbreviations(text: str) -> tuple[str, list[str]]:
    """Strip known abbreviation markers."""
    info: list[str] = []
    result = text
    for abbr, replacement in ABBREVIATIONS.items():
        if abbr in result:
            count = result.count(abbr)
            info.append(f"abbreviation_{repr(abbr)}:{count}")
            result = result.replace(abbr, replacement)
    return result, info


def normalize(text: str, *, preserve_original: bool = True) -> Normalized:
    """
    Normalize a piece of Early New High German text.

    The normalized form is suitable for comparison; the original is returned
    unchanged.

    Args:
        text: The text to normalize (may contain newlines, punctuation, etc.)
        preserve_original: If True, return a Normalized with the original
                           preserved as-is. If False, the normalized field
                           is the same as the input would be after normalization
                           (useful for in-place replacement).

    Returns:
        Normalized(original, normalized_text, normalization_info)
    """
    original = text
    info: list[str] = []

    # Step 0: collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Step 0b: decompose to NFD so precomposed and combining spellings of the
    # same character are treated identically.
    #
    # This corpus encodes the same letter both ways: the Transkribus variants
    # write u + U+0366 while druck_1528 writes precomposed U+016F (1067 times,
    # and 87 combining as well). Without decomposition those compare as
    # different characters, which would manufacture thousands of false variants
    # in the print collation. It also brings 6,654 precomposed diacritics -
    # ü, ů, ö, ä, å, ñ, ē, ẽ - into reach of the rules below, which previously
    # only saw combining marks.
    decomposed = unicodedata.normalize("NFD", text)
    if decomposed != text:
        text = decomposed
        info.append("nfd_decomposed")

    # Step 1: normalize combining diacritics
    text, diac_info = _resolve_combining(text)
    info.extend(diac_info)

    # Step 2: ſ → s (long s)
    if "\u017f" in text:
        text = text.translate(LONG_S)
        info.append("long_s")

    # Step 3: u/v → u
    if "v" in text:
        text = text.translate(UV)
        info.append("u_v")

    # Step 4: i/j → i
    if "j" in text:
        text = text.translate(IJ)
        info.append("i_j")

    # Step 5: strip remaining combining diacritics (fallback: strip)
    chars = list(text)
    cleaned_chars: list[str] = []
    i = 0
    while i < len(chars):
        c = chars[i]
        n = unicodedata.category(c) if isinstance(c, str) else "Cn"
        if n == "Mn":  # Mark, Nonspacing — strip
            info.append(f"stripped_combining_{unicodedata.name(c, 'UNKNOWN').lower()}")
            i += 1
            continue
        cleaned_chars.append(c)
        i += 1
    text = "".join(cleaned_chars)

    # Step 6: abbreviations
    text, abbr_info = _strip_abbreviations(text)
    info.extend(abbr_info)

    # Step 7: collapse multiple spaces (again, after diacritic stripping)
    text = re.sub(r" +", " ", text).strip()

    if not preserve_original:
        original = text

    return Normalized(
        original=original,
        normalized=text,
        normalization_info={"rules_applied": list(set(info))} if info else {},
    )


def normalize_text(text: str) -> str:
    """Convenience: return just the normalized string."""
    return normalize(text).normalized


def normalize_file(path: Path) -> list[Normalized]:
    """Normalize all paragraphs in a transcription markdown file."""
    content = path.read_text(encoding="utf-8")
    # Strip page header
    body = re.sub(r"^# Seite \d+\s*", "", content, flags=re.MULTILINE)
    paragraphs = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    return [normalize(p) for p in paragraphs]


def normalize_segment(segment_text: str) -> Normalized:
    """Normalize a single segment text block (paragraph(s))."""
    return normalize(segment_text)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Early New High German orthography"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", metavar="TEXT", help="Text to normalize")
    group.add_argument("--file", metavar="PATH", type=Path,
                       help="Transcription .md file to normalize")
    parser.add_argument("--stats", action="store_true",
                        help="Print per-rule statistics")
    parser.add_argument("--output", metavar="PATH", type=Path,
                        help="Write results to JSON file")
    args = parser.parse_args()

    if args.text:
        result = normalize(args.text)
        print(f"Original:     {result.original}")
        print(f"Normalized:   {result.normalized}")
        if args.stats and result.normalization_info:
            print(f"Rules:        {result.normalization_info}")
        return 0

    # File mode
    if not args.file.exists():
        print(f"File not found: {args.file}", file=__import__("sys").stderr)
        return 1

    results = normalize_file(args.file)
    output = [r.as_dict() for r in results]

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        import json
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(f"Wrote {len(output)} paragraph(s) → {args.output}")
    else:
        for r in results[:5]:
            print(f"Original:     {r.original[:80]}")
            print(f"Normalized:   {r.normalized[:80]}")
            if args.stats and r.normalization_info:
                print(f"Rules:        {r.normalization_info}")
            print()
        if len(results) > 5:
            print(f"... ({len(results) - 5} more)")

    if args.stats:
        from collections import Counter
        rule_counts: Counter = Counter()
        for r in results:
            for rule in r.normalization_info.get("rules_applied", []):
                rule_counts[rule] += 1
        print("\nRule statistics:")
        for rule, count in rule_counts.most_common():
            print(f"  {rule}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
