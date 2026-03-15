#!/usr/bin/env python3
"""Auto-translate new transcription files using Gemini 2.5.

Scans transcription directories for pages that have no translation yet,
calls the Gemini API, writes the result, and pushes a single commit.

Usage:
 python3 scripts/auto_translate.py [--repo-root /path/to/repo] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    import google.generativeai as genai
except ModuleNotFoundError:
    genai = None

TRANSLATION_PROMPT_TEMPLATE = """\
Du bist ein wissenschaftlicher Übersetzer für frühneuzeitliche Texte.
Übersetze den folgenden mittelhochdeutschen bzw. frühneuhochdeutschen Text \
aus der Berner Reformation (1528) ins moderne Deutsch.

Anforderungen:
- Behalte den sachlichen, theologischen Charakter des Originals bei.
- Verwende wissenschaftliche Standardsprache.
- Behalte die Absatzstruktur und Markdown-Überschriften (# Titel) exakt bei.
- Übersetze nur den Fließtext, keine Metadaten.
- Gib ausschließlich den übersetzten Markdown-Text zurück, ohne Erläuterungen.

Original:
{transcription}
"""

SCAN_PATHS = [
    # (transcriptions_dir, translations_dir)
    ("data/predigten/transcriptions", "data/predigten/translations"),
    ("data/disputation/druck_1528/transcriptions", "data/disputation/druck_1528/translations"),
    ("data/disputation/a_v_1447_schlussredaktion/transcriptions", "data/disputation/a_v_1447_schlussredaktion/translations"),
    ("data/disputation/a_v_1443_hertwig/transcriptions", "data/disputation/a_v_1443_hertwig/translations"),
    ("data/disputation/a_v_1444_cyro/transcriptions", "data/disputation/a_v_1444_cyro/translations"),
    ("data/disputation/a_v_1445_schoeni/transcriptions", "data/disputation/a_v_1445_schoeni/translations"),
    ("data/disputation/a_v_1446_ruemlang/transcriptions", "data/disputation/a_v_1446_ruemlang/translations"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-translate transcription files via Gemini")
    parser.add_argument("--repo-root", default=".", help="Path to repo root (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be translated without writing or pushing")
    parser.add_argument("--model", default="gemini-2.5-pro-preview-05-06", help="Gemini model name")
    return parser.parse_args()


def git_pull(repo_root: Path) -> None:
    result = subprocess.run(["git", "pull", "--ff-only"], cwd=repo_root, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[WARN] git pull failed: {result.stderr}")
        # Try with rebase as fallback
        result = subprocess.run(["git", "pull", "--rebase"], cwd=repo_root, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[WARN] git pull --rebase also failed: {result.stderr}")


def git_commit_and_push(repo_root: Path, files: list[Path]) -> None:
    rel_files = [str(f.relative_to(repo_root)) for f in files]
    subprocess.run(["git", "add", "--"] + rel_files, cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Auto-translate {len(rel_files)} page(s) via Gemini"],
        cwd=repo_root, check=True,
    )
    subprocess.run(["git", "push"], cwd=repo_root, check=True)


def translate(model, transcription_text: str) -> str:
    prompt = TRANSLATION_PROMPT_TEMPLATE.format(transcription=transcription_text)
    response = model.generate_content(prompt)
    return response.text.strip()


def find_untranslated(repo_root: Path) -> list[tuple[Path, Path]]:
    """Return list of (transcription_path, target_translation_path) pairs."""
    pairs: list[tuple[Path, Path]] = []
    for trans_dir_rel, transl_dir_rel in SCAN_PATHS:
        trans_dir = repo_root / trans_dir_rel
        transl_dir = repo_root / transl_dir_rel
        if not trans_dir.exists():
            continue
        for src in sorted(trans_dir.glob("page_*.md")):
            dst = transl_dir / src.name
            if dst.exists() and dst.read_text(encoding="utf-8").strip():
                continue  # already translated
            pairs.append((src, dst))
    return pairs


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()

    if genai is None:
        print("[ERROR] google-generativeai not installed. Run: pip install google-generativeai", file=sys.stderr)
        return 2

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[ERROR] GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        return 2

    print("[INFO] Pulling latest changes...")
    git_pull(repo_root)

    pairs = find_untranslated(repo_root)
    if not pairs:
        print("[INFO] No untranslated pages found. Nothing to do.")
        return 0

    print(f"[INFO] Found {len(pairs)} page(s) to translate.")
    if args.dry_run:
        for src, dst in pairs:
            print(f" would translate: {src.relative_to(repo_root)} → {dst.relative_to(repo_root)}")
        return 0

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(args.model)

    written: list[Path] = []
    for src, dst in pairs:
        print(f"[INFO] Translating {src.relative_to(repo_root)} ...")
        transcription = src.read_text(encoding="utf-8")
        try:
            translation = translate(model, transcription)
        except Exception as exc:
            print(f"[WARN] Gemini error for {src.name}: {exc} — skipping.", file=sys.stderr)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(translation, encoding="utf-8")
        written.append(dst)
        print(f" → wrote {dst.relative_to(repo_root)}")

    if written:
        print(f"[INFO] Committing and pushing {len(written)} translation(s)...")
        git_commit_and_push(repo_root, written)
        print("[INFO] Done.")
    else:
        print("[INFO] No translations written (all skipped due to errors).")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
