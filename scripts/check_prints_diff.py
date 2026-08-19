#!/usr/bin/env python3
"""Guard recognised print text before it is committed.

The recognition run commits to main unattended across 2,646 pages, so a bad
batch would be published without review. Refuses when the result looks
destructive rather than additive:

  * tracked files under data/prints were deleted
  * a page that held text is now empty
  * a page lost more than a fraction of its characters

Recognition is normally purely additive - pages go from absent to present - so
anything that removes text deserves a human look.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "data/prints"
PAGE_RE = re.compile(r"^data/prints/([^/]+)/transcriptions/page_\d+\.md$")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def body(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("# Seite"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def blob(base: str, path: str) -> str | None:
    result = subprocess.run(["git", "show", f"{base}:{path}"], cwd=ROOT,
                            capture_output=True, text=True, check=False)
    return None if result.returncode != 0 else result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard recognised print text")
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--max-page-loss", type=float, default=0.30,
                        help="Fraction of a page's characters that may vanish (default: 0.30)")
    args = parser.parse_args()

    status = git("status", "--porcelain=1", "--", PREFIX)
    entries = []
    for line in status.splitlines():
        if not line.strip():
            continue
        entries.append((line[:2].strip(), line[3:].strip().strip('"')))

    if not entries:
        print("check_prints_diff: no changes under data/prints.")
        return 0

    errors, added, changed = [], 0, 0
    deleted = [p for s, p in entries if s in {"D", "AD"}]
    if deleted:
        errors.append(f"{len(deleted)} tracked file(s) deleted, e.g. {', '.join(sorted(deleted)[:5])}")

    for status_code, path in entries:
        if not PAGE_RE.match(path):
            continue
        before_raw = blob(args.base, path)
        if before_raw is None:
            added += 1
            continue
        before, current = body(before_raw), ROOT / path
        after = body(current.read_text(encoding="utf-8")) if current.exists() else ""
        if not before:
            added += 1
            continue
        changed += 1
        if before and not after:
            errors.append(f"{path}: held {len(before)} chars, now empty")
        elif len(after) < len(before) * (1 - args.max_page_loss):
            errors.append(
                f"{path}: {len(before)} -> {len(after)} chars "
                f"(-{(1 - len(after) / len(before)) * 100:.0f}%)"
            )

    print(f"check_prints_diff: {added} page(s) newly recognised, {changed} changed")
    if errors:
        print("REFUSING to commit:")
        for item in errors[:20]:
            print(f"  ERROR: {item}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)
