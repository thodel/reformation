#!/usr/bin/env python3
"""Validate repository data and static app invariants."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPUTATION_ROOT = ROOT / "data" / "disputation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate repository data files")
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Exit with a non-zero status code when warnings are present",
    )
    return parser.parse_args()


def find_json_errors() -> list[str]:
    errors: list[str] = []
    for path in sorted(ROOT.rglob("*.json")):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"Invalid JSON: {path.relative_to(ROOT)} ({exc})")
    return errors


def find_ds_store_files() -> list[str]:
    return [str(path.relative_to(ROOT)) for path in sorted(ROOT.rglob(".DS_Store"))]


def validate_viewer_manifests() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    missing_translations: dict[str, list[int]] = defaultdict(list)

    for manifest_path in sorted(DISPUTATION_ROOT.glob("*/viewer_manifest.json")):
        variant_dir = manifest_path.parent
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages = payload.get("pages") or []
        page_count = payload.get("page_count")
        if page_count != len(pages):
            errors.append(
                f"{manifest_path.relative_to(ROOT)} declares page_count={page_count} but contains {len(pages)} page entries"
            )

        for page in pages:
            page_nr = int(page.get("page_nr", 0))
            for key in ("transcription", "line_coords", "pagexml", "image"):
                value = page.get(key)
                if not isinstance(value, str) or not value or value.startswith(("http://", "https://")):
                    continue
                if not (variant_dir / value).exists():
                    errors.append(
                        f"{manifest_path.relative_to(ROOT)} page {page_nr} references missing {key}: {value}"
                    )

            translation = page.get("translation")
            if isinstance(translation, str) and translation and not translation.startswith(("http://", "https://")):
                if not (variant_dir / translation).exists():
                    missing_translations[str(manifest_path.relative_to(ROOT))].append(page_nr)

        has_local_content = any(
            (variant_dir / directory).exists() and any((variant_dir / directory).glob("page_*"))
            for directory in ("transcriptions", "pagexml", "line_coords", "images")
        )
        if not pages and not has_local_content:
            warnings.append(
                f"{manifest_path.relative_to(ROOT)} has no page entries and no local synced content yet"
            )

    for manifest, page_numbers in sorted(missing_translations.items()):
        preview = ", ".join(str(page_nr) for page_nr in page_numbers[:5])
        warnings.append(
            f"{manifest} references {len(page_numbers)} missing translation file(s)"
            + (f" (first pages: {preview})" if preview else "")
        )

    return errors, warnings


def main() -> int:
    args = parse_args()
    errors = []
    warnings = []

    errors.extend(find_json_errors())

    ds_store_files = find_ds_store_files()
    if ds_store_files:
        errors.extend([f"Remove macOS metadata file: {path}" for path in ds_store_files])

    manifest_errors, manifest_warnings = validate_viewer_manifests()
    errors.extend(manifest_errors)
    warnings.extend(manifest_warnings)

    if errors:
        print("Validation failed:")
        for item in errors:
            print(f"  ERROR: {item}")
    else:
        print("Validation passed without errors.")

    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"  WARN: {item}")

    if errors:
        return 1
    if args.strict_warnings and warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
