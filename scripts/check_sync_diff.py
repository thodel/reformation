#!/usr/bin/env python3
"""Guard an automated Transkribus sync before its changes are committed.

The scheduled sync commits straight to main, so a bad upstream state would be
published without anyone looking at it. This compares the working tree against
HEAD and fails when the sync looks destructive rather than incremental:

  * tracked files under data/disputation were deleted
  * a variant lost pages from its viewer manifest
  * transcribed text shrank by more than an allowed fraction

Exit codes: 0 = safe to commit, 1 = refused, 2 = usage/environment error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PREFIX = "data/disputation"
TRANSCRIPTION_RE = re.compile(r"^data/disputation/([^/]+)/transcriptions/page_\d+\.md$")
MANIFEST_RE = re.compile(r"^data/disputation/([^/]+)/viewer_manifest\.json$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refuse destructive Transkribus sync results")
    parser.add_argument(
        "--max-text-loss",
        type=float,
        default=0.02,
        help="Maximum fraction of transcribed characters a variant may lose (default: 0.02 = 2%%)",
    )
    parser.add_argument(
        "--base",
        default="HEAD",
        help="Git revision to compare the working tree against (default: HEAD)",
    )
    return parser.parse_args()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def changed_files(base: str) -> list[tuple[str, str]]:
    """Return (status, path) for every change under data/disputation."""
    output = git("status", "--porcelain=1", "--", DATA_PREFIX)
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        status = line[:2].strip()
        path = line[3:].strip()
        if " -> " in path:  # rename
            path = path.split(" -> ", 1)[1]
        entries.append((status, path.strip('"')))
    return entries


def blob_at(base: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{base}:{path}"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    return result.stdout


def transcription_body(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# Seite"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    notes: list[str] = []

    entries = changed_files(args.base)
    if not entries:
        print("check_sync_diff: no changes under data/disputation.")
        return 0

    deleted = [path for status, path in entries if status in {"D", "AD"}]
    if deleted:
        errors.append(
            f"{len(deleted)} tracked file(s) deleted, e.g. {', '.join(sorted(deleted)[:5])}"
        )

    # Manifest page counts must not shrink.
    for status, path in entries:
        match = MANIFEST_RE.match(path)
        if not match or status == "D":
            continue
        before_raw = blob_at(args.base, path)
        if before_raw is None:
            continue
        try:
            before = json.loads(before_raw)
            after = json.loads((ROOT / path).read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path}: unreadable manifest ({exc})")
            continue
        before_n = len(before.get("pages") or [])
        after_n = len(after.get("pages") or [])
        if after_n < before_n:
            errors.append(f"{path}: page count dropped {before_n} -> {after_n}")
        elif after_n > before_n:
            notes.append(f"{path}: page count grew {before_n} -> {after_n}")

    # Transcribed text must not shrink materially, per variant.
    per_variant: dict[str, list[int]] = {}
    for status, path in entries:
        match = TRANSCRIPTION_RE.match(path)
        if not match:
            continue
        variant = match.group(1)
        before_raw = blob_at(args.base, path)
        before_len = len(transcription_body(before_raw)) if before_raw is not None else 0
        current = ROOT / path
        after_len = len(transcription_body(current.read_text(encoding="utf-8"))) if current.exists() else 0
        totals = per_variant.setdefault(variant, [0, 0, 0])
        totals[0] += before_len
        totals[1] += after_len
        totals[2] += 1

    for variant, (before_len, after_len, n_files) in sorted(per_variant.items()):
        delta = after_len - before_len
        if before_len > 0 and delta < 0:
            fraction = -delta / before_len
            message = (
                f"{variant}: {n_files} changed page(s), transcribed text "
                f"{before_len} -> {after_len} chars ({delta:+d}, -{fraction:.1%})"
            )
            if fraction > args.max_text_loss:
                errors.append(message + f" exceeds the {args.max_text_loss:.1%} limit")
            else:
                notes.append(message)
        else:
            notes.append(
                f"{variant}: {n_files} changed page(s), transcribed text "
                f"{before_len} -> {after_len} chars ({delta:+d})"
            )

    for note in notes:
        print(f"  note: {note}")

    if errors:
        print("check_sync_diff: REFUSING to commit this sync result:")
        for item in errors:
            print(f"  ERROR: {item}")
        print(
            "\nInspect with 'git diff -- data/disputation'. If the change is genuinely "
            "intended, commit it manually."
        )
        return 1

    print(f"check_sync_diff: {len(entries)} changed path(s) look like a normal incremental sync.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(2)
