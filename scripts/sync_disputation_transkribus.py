#!/usr/bin/env python3
"""Sync Disputation material from Transkribus into local viewer files.

This script downloads page images + latest PAGE XML transcript per page,
extracts line text and line coordinates, and writes a local viewer manifest.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import requests
except ModuleNotFoundError:
    requests = None

BASE_REST_URL = "https://transkribus.eu/TrpServer/rest"
LOGIN_URL = f"{BASE_REST_URL}/auth/login"
FULLDOC_URL_TEMPLATE = f"{BASE_REST_URL}/collections/{{col_id}}/{{doc_id}}/fulldoc"

VARIANT_DIR_MAP = {
    "druck-1528": "druck_1528",
    "a-v-1447": "a_v_1447_schlussredaktion",
    "a-v-1443": "a_v_1443_hertwig",
    "a-v-1444": "a_v_1444_cyro",
    "a-v-1445": "a_v_1445_schoeni",
    "a-v-1446": "a_v_1446_ruemlang",
}


@dataclass(frozen=True)
class VariantConfig:
    variant_id: str
    collection_id: int
    document_id: int
    status_preference: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync disputation data from Transkribus")
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
    return parser.parse_args()


def load_config(path: Path) -> list[VariantConfig]:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Copy config/disputation_transkribus.example.json "
            "to config/disputation_transkribus.json and fill IDs."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    variants = payload.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("Config must contain a non-empty 'variants' array.")

    parsed: list[VariantConfig] = []
    for item in variants:
        if not isinstance(item, dict):
            raise ValueError("Each variant entry must be an object.")

        variant_id = str(item.get("id", "")).strip()
        if variant_id not in VARIANT_DIR_MAP:
            raise ValueError(
                f"Unknown variant id '{variant_id}'. Valid values: {', '.join(VARIANT_DIR_MAP.keys())}"
            )

        collection_id = int(item.get("collection_id"))
        document_id = int(item.get("document_id"))
        status_preference = item.get("status_preference") or []
        if not isinstance(status_preference, list):
            raise ValueError(f"status_preference of {variant_id} must be a list")

        parsed.append(
            VariantConfig(
                variant_id=variant_id,
                collection_id=collection_id,
                document_id=document_id,
                status_preference=[str(s) for s in status_preference],
            )
        )

    return parsed


def require_credentials() -> tuple[str, str]:
    user = os.environ.get("TRANSKRIBUS_USER", "").strip()
    password = os.environ.get("TRANSKRIBUS_PASSWORD", "")
    if not user or not password:
        raise RuntimeError(
            "Missing credentials. Please set TRANSKRIBUS_USER and TRANSKRIBUS_PASSWORD."
        )
    return user, password


def login(session: requests.Session, user: str, password: str) -> str:
    response = session.post(LOGIN_URL, data={"user": user, "pw": password}, timeout=60)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    sid = root.findtext("sessionId")
    if not sid:
        raise RuntimeError("Login succeeded but no sessionId found in response.")
    return sid


def fetch_document_content(session: requests.Session, sid: str, col_id: int, doc_id: int) -> dict[str, Any]:
    url = FULLDOC_URL_TEMPLATE.format(col_id=col_id, doc_id=doc_id)
    response = session.get(url, params={"JSESSIONID": sid}, timeout=60)
    response.raise_for_status()
    return response.json()


def pick_latest_transcript(page: dict[str, Any], status_preference: list[str]) -> dict[str, Any] | None:
    transcripts = (((page.get("tsList") or {}).get("transcripts")) or [])
    if not transcripts:
        return None

    preference = [s.upper() for s in status_preference]
    if preference:
        preferred = [
            ts for ts in transcripts
            if str(ts.get("status", "")).upper() in preference
        ]
        if preferred:
            return max(preferred, key=lambda ts: int(ts.get("timestamp", 0)))

    return max(transcripts, key=lambda ts: int(ts.get("timestamp", 0)))


def parse_points(points_text: str) -> list[list[float]]:
    points: list[list[float]] = []
    for token in points_text.strip().split():
        if "," not in token:
            continue
        x_str, y_str = token.split(",", 1)
        try:
            x = float(x_str)
            y = float(y_str)
        except ValueError:
            continue
        points.append([x, y])
    return points


def points_to_bbox(points: list[list[float]]) -> dict[str, float] | None:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return None
    return {"x": min_x, "y": min_y, "w": width, "h": height}


def parse_pagexml(pagexml_text: str) -> tuple[int | None, int | None, list[dict[str, Any]]]:
    root = ET.fromstring(pagexml_text)

    page_node = root.find(".//{*}Page")
    image_width = None
    image_height = None
    if page_node is not None:
        try:
            image_width = int(page_node.attrib.get("imageWidth", ""))
        except ValueError:
            image_width = None
        try:
            image_height = int(page_node.attrib.get("imageHeight", ""))
        except ValueError:
            image_height = None

    lines: list[dict[str, Any]] = []
    for index, line_node in enumerate(root.findall(".//{*}TextLine"), start=1):
        line_id = str(line_node.attrib.get("id") or f"line-{index}")
        coords_node = line_node.find("./{*}Coords")
        points = parse_points(coords_node.attrib.get("points", "")) if coords_node is not None else []
        bbox = points_to_bbox(points)

        unicode_node = line_node.find(".//{*}TextEquiv/{*}Unicode")
        text = (unicode_node.text or "") if unicode_node is not None else ""
        text = text.strip()

        lines.append(
            {
                "id": line_id,
                "text": text,
                "points": points,
                "bbox": bbox,
            }
        )

    return image_width, image_height, lines


def write_binary(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sync_variant(
    session: requests.Session,
    sid: str,
    variant: VariantConfig,
    output_root: Path,
    overwrite: bool,
) -> None:
    variant_dir = output_root / VARIANT_DIR_MAP[variant.variant_id]
    images_dir = variant_dir / "images"
    transcriptions_dir = variant_dir / "transcriptions"
    line_coords_dir = variant_dir / "line_coords"
    pagexml_dir = variant_dir / "pagexml"

    for directory in [images_dir, transcriptions_dir, line_coords_dir, pagexml_dir, variant_dir / "translations", variant_dir / "entities"]:
        directory.mkdir(parents=True, exist_ok=True)

    document = fetch_document_content(session, sid, variant.collection_id, variant.document_id)
    pages = (((document.get("pageList") or {}).get("pages")) or [])
    pages = sorted(pages, key=lambda page: int(page.get("pageNr", 0)))

    viewer_pages: list[dict[str, Any]] = []

    for page in pages:
        page_nr = int(page.get("pageNr", len(viewer_pages) + 1))
        transcript = pick_latest_transcript(page, variant.status_preference)
        if transcript is None:
            print(f"[WARN] No transcript for {variant.variant_id} page {page_nr}; skipping page")
            continue

        pagexml_url = str(transcript.get("url", "")).strip()
        if not pagexml_url:
            print(f"[WARN] Missing pagexml URL for {variant.variant_id} page {page_nr}; skipping page")
            continue

        pagexml_target = pagexml_dir / f"page_{page_nr}.xml"
        if overwrite or not pagexml_target.exists():
            pagexml_response = session.get(pagexml_url, timeout=60)
            pagexml_response.raise_for_status()
            write_text(pagexml_target, pagexml_response.text)
        pagexml_text = pagexml_target.read_text(encoding="utf-8")

        image_width, image_height, lines = parse_pagexml(pagexml_text)

        image_url = str(page.get("url", "")).strip()
        image_name = str(page.get("imgFileName", "")).strip()
        image_ext = Path(image_name).suffix.lower() if image_name else ".jpg"
        if not image_ext:
            image_ext = ".jpg"
        image_rel = f"images/page_{page_nr}{image_ext}"
        image_target = variant_dir / image_rel
        if image_url:
            if overwrite or not image_target.exists():
                image_response = session.get(image_url, timeout=120)
                image_response.raise_for_status()
                write_binary(image_target, image_response.content)

        transcription_md = "# Seite {0}\n\n{1}\n".format(
            page_nr,
            "\n".join(line["text"] for line in lines if line.get("text")),
        )
        transcription_rel = f"transcriptions/page_{page_nr}.md"
        write_text(variant_dir / transcription_rel, transcription_md)

        line_coords_payload = {
            "page_nr": page_nr,
            "image": {
                "width": image_width,
                "height": image_height,
                "url": image_url,
                "file": image_rel,
            },
            "lines": lines,
        }
        line_coords_rel = f"line_coords/page_{page_nr}.json"
        write_text(variant_dir / line_coords_rel, json.dumps(line_coords_payload, ensure_ascii=False, indent=2))

        viewer_pages.append(
            {
                "page_nr": page_nr,
                "image": image_rel if image_target.exists() else None,
                "transcription": transcription_rel,
                "translation": f"translations/page_{page_nr}.md",
                "line_coords": line_coords_rel,
                "pagexml": f"pagexml/page_{page_nr}.xml",
            }
        )

    viewer_manifest = {
        "variant_id": variant.variant_id,
        "source": "transkribus",
        "collection_id": variant.collection_id,
        "document_id": variant.document_id,
        "page_count": len(viewer_pages),
        "pages": viewer_pages,
    }
    write_text(variant_dir / "viewer_manifest.json", json.dumps(viewer_manifest, ensure_ascii=False, indent=2))

    entities_path = variant_dir / "entities" / "named_entities.json"
    if not entities_path.exists():
        write_text(entities_path, json.dumps({"entities": []}, ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()

    if requests is None:
        print(
            "[ERROR] Python package 'requests' is required. Install with: pip install requests",
            file=sys.stderr,
        )
        return 2

    config_path = Path(args.config)
    output_root = Path(args.output_root)

    variants = load_config(config_path)
    user, password = require_credentials()

    session = requests.Session()
    sid = login(session, user, password)

    for variant in variants:
        print(
            f"[INFO] Sync {variant.variant_id}: collection={variant.collection_id}, document={variant.document_id}"
        )
        sync_variant(session, sid, variant, output_root, overwrite=args.overwrite)

    print("[INFO] Disputation sync completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
