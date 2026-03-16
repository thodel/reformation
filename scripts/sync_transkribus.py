#!/usr/bin/env python3
"""Compatibility wrapper for the canonical disputation sync script.

This script keeps the older entrypoint name but delegates all real work to
``sync_disputation_transkribus.py`` so the repository has a single sync
implementation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import sync_disputation_transkribus as sync_impl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync disputation data from Transkribus (compatibility wrapper)"
    )
    parser.add_argument(
        "--config",
        default="config/disputation_transkribus.json",
        help="Path to config JSON (default: config/disputation_transkribus.json)",
    )
    parser.add_argument(
        "--output-root",
        default="data/disputation",
        help="Output root directory (default: data/disputation)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing downloaded image/pagexml files",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image download and keep external image URLs in the viewer manifest",
    )
    parser.add_argument(
        "--variant",
        action="append",
        dest="variant_ids",
        help="Sync only the given variant id (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which variants would be synced without downloading files",
    )
    return parser.parse_args()


def select_variants(
    variants: list[sync_impl.VariantConfig],
    requested_variant_ids: list[str] | None,
) -> list[sync_impl.VariantConfig]:
    if not requested_variant_ids:
        return variants

    requested = {variant_id.strip() for variant_id in requested_variant_ids if variant_id.strip()}
    if not requested:
        return variants

    selected = [variant for variant in variants if variant.variant_id in requested]
    missing = sorted(requested - {variant.variant_id for variant in selected})
    if missing:
        valid_values = ", ".join(sorted(sync_impl.VARIANT_DIR_MAP.keys()))
        raise ValueError(f"Unknown variant id(s): {', '.join(missing)}. Valid values: {valid_values}")
    return selected


def main() -> int:
    args = parse_args()

    variants = sync_impl.load_config(Path(args.config))
    selected_variants = select_variants(variants, args.variant_ids)
    output_root = Path(args.output_root)
    download_images = not args.no_images

    if args.dry_run:
        print("[INFO] Dry run: no files will be written.")
        for variant in selected_variants:
            target_dir = output_root / sync_impl.VARIANT_DIR_MAP[variant.variant_id]
            print(
                "[INFO] Would sync "
                f"{variant.variant_id}: collection={variant.collection_id}, "
                f"document={variant.document_id}, output={target_dir}"
            )
        return 0

    if sync_impl.requests is None:
        print(
            "[ERROR] Python package 'requests' is required. Install with: pip install requests",
            file=sys.stderr,
        )
        return 2

    session = sync_impl.requests.Session()
    auth = sync_impl.resolve_auth(session)
    print(f"[INFO] Auth OK ({auth.source})")
    if not download_images:
        print("[INFO] Image download disabled (--no-images); external URLs will be stored in viewer manifest.")

    for variant in selected_variants:
        print(
            f"[INFO] Sync {variant.variant_id}: collection={variant.collection_id}, "
            f"document={variant.document_id}"
        )
        sync_impl.sync_variant(
            session,
            auth,
            variant,
            output_root,
            overwrite=args.overwrite,
            download_images=download_images,
        )

    print("[INFO] Disputation sync completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
