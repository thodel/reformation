#!/usr/bin/env python3
"""Strip model boilerplate from translation files.

Gemini sometimes wraps a translation in conversational scaffolding: a leading
"Hier ist die Uebersetzung ...:" line, a stray "Text:" label, or a trailing
block of commentary about the translation. That scaffolding is published as if
it were part of the scholarly translation.

The rules here are deliberately narrow, because the same words occur in
genuine translated prose - "gerne von ihm verstanden habe" is text, not
boilerplate. Only these shapes are removed:

  * a preamble line directly after the "# Seite N" heading that announces a
    translation and ends in a colon
  * a lone "Text:" label immediately following such a preamble
  * a trailing section introduced by a bolded Anmerkung/Hinweis heading

Anything else - including inline "(Anmerkung: ...)" asides inside the text -
is left alone.

Usage:
  python3 scripts/clean_translations.py --dry-run
  python3 scripts/clean_translations.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# "Hier ist die Uebersetzung ...:", "Hier die Uebersetzung ...:", "Uebersetzung:"
# Optional conversational opener ("Absolut!", "Okay,", "Gerne,") before the
# announcement. The announcement itself may end in a colon or run on into a
# caveat sentence, so the terminator cannot be pinned to ":".
_OPENER = r"(?:absolut|okay|ok|gerne|klar|natürlich|sicher)\s*[!,.]?\s*"
PREAMBLE_RE = re.compile(
    r"^\s*(?:" + _OPENER + r")?"
    r"(?:hier\s+(?:ist\s+|folgt\s+|kommt\s+)?(?:die|der)?\s*\b(?:übersetzung|übersetzte)\b.*"
    r"|übersetzung\s*"
    r"|(?:nachfolgend|im\s+folgenden)\b.*?\bübersetzung\b.*"
    r")$",
    re.IGNORECASE,
)
LABEL_RE = re.compile(r"^\s*(?:text|original)\s*:\s*$", re.IGNORECASE)
TRAILING_SECTION_RE = re.compile(
    r"^\s*\*{2}\s*(?:anmerkung|anmerkungen|hinweis|hinweise|erläuterung|erläuterungen)\b[^*]*\*{2}\s*:?\s*$",
    re.IGNORECASE,
)


def clean(text: str) -> tuple[str, list[str]]:
    """Return (cleaned_text, list_of_removals)."""
    lines = text.splitlines()
    removed: list[str] = []

    # Locate the body: everything after the "# Seite N" heading.
    start = 0
    if lines and lines[0].startswith("# Seite"):
        start = 1

    i = start
    while i < len(lines) and not lines[i].strip():
        i += 1

    # Rule 1: a preamble line announcing the translation.
    if i < len(lines) and PREAMBLE_RE.match(lines[i]):
        removed.append(f"preamble: {lines[i].strip()[:70]}")
        del lines[i]
        while i < len(lines) and not lines[i].strip():
            del lines[i]

        # Rule 2: a stray label directly after the preamble.
        if i < len(lines) and LABEL_RE.match(lines[i]):
            removed.append(f"label: {lines[i].strip()}")
            del lines[i]
            while i < len(lines) and not lines[i].strip():
                del lines[i]

    # Rule 3: a trailing commentary section.
    for idx in range(len(lines) - 1, start - 1, -1):
        if TRAILING_SECTION_RE.match(lines[idx]):
            removed.append(f"trailing section from line {idx + 1}: {lines[idx].strip()[:60]}")
            del lines[idx:]
            while lines and not lines[-1].strip():
                lines.pop()
            break

    cleaned = "\n".join(lines)
    if text.endswith("\n") and not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned, removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strip model boilerplate from translations")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    parser.add_argument(
        "--root", default="data", help="Directory to scan for */translations (default: data)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = ROOT / args.root
    changed = 0
    scanned = 0
    per_rule: dict[str, int] = {}

    dirs = sorted(base.glob("*/translations")) + sorted(base.glob("*/*/translations"))
    for directory in dirs:
        for path in sorted(directory.glob("page_*.md")):
            scanned += 1
            original = path.read_text(encoding="utf-8")
            cleaned, removed = clean(original)
            if not removed or cleaned == original:
                continue
            changed += 1
            for item in removed:
                per_rule[item.split(":")[0]] = per_rule.get(item.split(":")[0], 0) + 1
            rel = path.relative_to(ROOT)
            print(f"{'would clean' if args.dry_run else 'cleaned'} {rel}")
            for item in removed:
                print(f"    - {item}")
            if not args.dry_run:
                path.write_text(cleaned, encoding="utf-8")

    print(f"\nscanned {scanned} translation file(s); {changed} affected")
    for rule, count in sorted(per_rule.items()):
        print(f"  {rule}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
