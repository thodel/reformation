#!/usr/bin/env python3
"""Guard an automated Transkribus sync before its changes are committed.

The scheduled sync commits straight to main, so a bad upstream state would be
published without anyone looking at it. This compares the working tree against
HEAD and fails when the sync looks destructive rather than incremental:

  * tracked files under data/disputation were deleted
  * a variant lost pages from its viewer manifest
  * a page that held real text was emptied (the re-segmentation wipe that cost
    pages 1-51 in 275dbeab)
  * a variant lost more than a fraction of ALL its transcribed text

The job is to stop automated mass destruction, not to referee editorial
judgement. Transcribers legitimately shorten a page - removing over-segmented
lines or junk regions - so a single page losing text is reported and allowed.
Loss is therefore measured against the variant's entire transcribed corpus,
not just the pages this sync happened to touch: otherwise one hand-corrected
page trips the threshold and the daily job stays red forever.

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
        default=0.15,
        help=(
            "Maximum fraction of a variant's TOTAL transcribed characters that may "
            "disappear in one sync (default: 0.15 = 15%%)"
        ),
    )
    parser.add_argument(
        "--emptied-page-chars",
        type=int,
        default=100,
        help=(
            "A page that held at least this many characters and is now empty counts "
            "as a wipe and blocks the commit (default: 100)"
        ),
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


def page_number(path: str) -> int:
    match = re.search(r"page_(\d+)\.md$", path)
    return int(match.group(1)) if match else 0


_CORPUS_CACHE: dict[tuple[str, str], int] = {}


def variant_corpus_size(base: str, variant: str) -> int:
    """Total transcribed characters the variant held at `base`.

    Reads every blob through a single `git cat-file --batch` process; spawning
    one `git show` per page costs hundreds of subprocesses per variant and
    makes the guard slower than the sync it protects.
    """
    key = (base, variant)
    if key in _CORPUS_CACHE:
        return _CORPUS_CACHE[key]

    listing = git("ls-tree", "-r", base, "--", f"{DATA_PREFIX}/{variant}/transcriptions/")
    blobs: list[str] = []
    for line in listing.splitlines():
        meta, _, path = line.partition("\t")
        if not TRANSCRIPTION_RE.match(path.strip().strip('"')):
            continue
        parts = meta.split()
        if len(parts) >= 3:
            blobs.append(parts[2])

    total = 0
    if blobs:
        # Byte mode is required: git reports the blob size in bytes, and these
        # transcriptions carry multibyte characters, so slicing a decoded str
        # by that size silently misreads the stream.
        result = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=ROOT,
            input=("\n".join(blobs) + "\n").encode("ascii"),
            capture_output=True,
            check=False,
        )
        stream = result.stdout
        pos = 0
        for _ in blobs:
            header_end = stream.find(b"\n", pos)
            if header_end == -1:
                break
            header = stream[pos:header_end].split()
            if len(header) < 3:
                break
            size = int(header[2])
            body = stream[header_end + 1 : header_end + 1 + size]
            total += len(transcription_body(body.decode("utf-8", errors="replace")))
            pos = header_end + 1 + size + 1  # trailing newline after the blob

    _CORPUS_CACHE[key] = total
    return total


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

    # Transcribed text must not shrink materially, measured per variant against
    # everything that variant holds -- not just the pages this sync touched.
    per_variant: dict[str, list[int]] = {}
    emptied: dict[str, list[int]] = {}
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

        # A page that held real text and is now blank is the wipe signature.
        if before_len >= args.emptied_page_chars and after_len == 0:
            emptied.setdefault(variant, []).append(page_number(path))

    for variant, page_numbers in sorted(emptied.items()):
        preview = ", ".join(str(n) for n in sorted(page_numbers)[:8])
        errors.append(
            f"{variant}: {len(page_numbers)} page(s) that held text are now empty "
            f"(pages {preview})"
        )

    for variant, (before_len, after_len, n_files) in sorted(per_variant.items()):
        delta = after_len - before_len
        corpus = variant_corpus_size(args.base, variant)
        summary = (
            f"{variant}: {n_files} changed page(s), transcribed text "
            f"{before_len} -> {after_len} chars ({delta:+d})"
        )
        if delta < 0 and corpus > 0:
            fraction = -delta / corpus
            summary += f", {fraction:.1%} of the variant's {corpus} chars"
            if fraction > args.max_text_loss:
                errors.append(summary + f" exceeds the {args.max_text_loss:.1%} limit")
                continue
        notes.append(summary)

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
