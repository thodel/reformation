#!/usr/bin/env python3
"""Sync Disputation material from Transkribus into local viewer files.

This script downloads page images + latest PAGE XML transcript per page,
extracts line text and line coordinates, and writes a local viewer manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
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
OIDC_TOKEN_URL = "https://account.readcoop.eu/auth/realms/readcoop/protocol/openid-connect/token"
DEFAULT_OIDC_CLIENT_ID = "transkribus-api-client"
SYNC_STATE_FILENAME = "sync_state.json"
# Transkribus statuses, most authoritative first. Used when a variant does not
# set its own status_preference.
DEFAULT_STATUS_PREFERENCE = ["GT", "FINAL", "DONE", "IN_PROGRESS", "NEW"]

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


@dataclass(frozen=True)
class AuthContext:
    kind: str  # "sid" | "bearer"
    value: str
    source: str


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
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image download; store external image URLs in viewer manifest instead of local paths",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Re-download a page's PAGE XML when Transkribus reports a newer transcript "
            "(compared against sync_state.json). Use this for scheduled syncs: without it, "
            "pages that already exist locally are never refetched."
        ),
    )
    parser.add_argument(
        "--allow-content-loss",
        action="store_true",
        help="Permit a refreshed transcript to replace existing text with empty text (default: keep the old text and warn)",
    )
    parser.add_argument(
        "--max-page-loss",
        type=float,
        default=0.05,
        help=(
            "Abort a variant if Transkribus returns fewer pages than the existing manifest "
            "by more than this fraction (default: 0.05 = 5%%). Set to 1 to disable."
        ),
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


def oidc_password_grant(session: requests.Session, user: str, password: str) -> str:
    client_id = os.environ.get("TRANSKRIBUS_OIDC_CLIENT_ID", DEFAULT_OIDC_CLIENT_ID).strip()
    if not client_id:
        client_id = DEFAULT_OIDC_CLIENT_ID

    response = session.post(
        OIDC_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": client_id,
            "username": user,
            "password": password,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    token = str(payload.get("access_token", "")).strip()
    if not token:
        raise RuntimeError("OIDC token response did not include access_token.")
    return token


def resolve_auth(session: requests.Session) -> AuthContext:
    access_token = os.environ.get("TRANSKRIBUS_ACCESS_TOKEN", "").strip()
    if access_token:
        return AuthContext(kind="bearer", value=access_token, source="TRANSKRIBUS_ACCESS_TOKEN")

    user, password = require_credentials()

    legacy_error = None
    try:
        sid = login(session, user, password)
        return AuthContext(kind="sid", value=sid, source="legacy /auth/login")
    except Exception as exc:
        legacy_error = exc

    try:
        token = oidc_password_grant(session, user, password)
        return AuthContext(kind="bearer", value=token, source="OIDC password grant")
    except Exception as oidc_exc:
        raise RuntimeError(
            f"Legacy login failed ({legacy_error}); OIDC fallback failed ({oidc_exc})."
        ) from oidc_exc


def auth_headers(auth: AuthContext) -> dict[str, str]:
    if auth.kind == "bearer":
        return {"Authorization": f"Bearer {auth.value}"}
    return {}


def auth_params(auth: AuthContext) -> dict[str, str]:
    if auth.kind == "sid":
        return {"JSESSIONID": auth.value}
    return {}


def fetch_document_content(
    session: requests.Session,
    auth: AuthContext,
    col_id: int,
    doc_id: int,
) -> dict[str, Any]:
    url = FULLDOC_URL_TEMPLATE.format(col_id=col_id, doc_id=doc_id)
    response = session.get(
        url,
        params=auth_params(auth) or None,
        headers=auth_headers(auth) or None,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_with_auth(session: requests.Session, auth: AuthContext, url: str, timeout: int) -> requests.Response:
    response = session.get(
        url,
        params=auth_params(auth) or None,
        headers=auth_headers(auth) or None,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def status_rank(status: str, preference: list[str]) -> int:
    """Rank a transcript status; higher is more authoritative.

    Statuses outside the preference list rank below every listed one, so an
    unfamiliar status never outranks a reviewed transcript.
    """
    try:
        return len(preference) - preference.index(str(status).upper())
    except ValueError:
        return -1


def pick_latest_transcript(page: dict[str, Any], status_preference: list[str]) -> dict[str, Any] | None:
    """Choose the transcript that best represents the current state of a page.

    Ordered by editorial status first, then recency. Picking purely by
    timestamp is wrong whenever a later step reduces the editorial state of a
    page - a re-segmentation writes a fresh NEW transcript with no text, and an
    automatic HTR pass can land after a human correction. Neither should
    supersede reviewed work just for being newer.

    Transcripts that carry no transcribed line are only considered when a page
    has nothing else, so an empty re-segmentation cannot blank a page.
    """
    transcripts = (((page.get("tsList") or {}).get("transcripts")) or [])
    if not transcripts:
        return None

    preference = [str(s).upper() for s in status_preference] or DEFAULT_STATUS_PREFERENCE

    with_text = [
        ts for ts in transcripts
        if int(ts.get("nrOfTranscribedLines") or 0) > 0
    ]
    candidates = with_text or transcripts

    return max(
        candidates,
        key=lambda ts: (
            status_rank(ts.get("status", ""), preference),
            int(ts.get("timestamp", 0)),
        ),
    )


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


def load_sync_state(variant_dir: Path) -> dict[str, Any]:
    """Read the per-variant record of which Transkribus transcript each page came from."""
    state_path = variant_dir / SYNC_STATE_FILENAME
    if not state_path.exists():
        return {"pages": {}}
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        print(f"[WARN] Unreadable {state_path}; treating every page as new")
        return {"pages": {}}
    if not isinstance(payload.get("pages"), dict):
        payload["pages"] = {}
    return payload


def transcript_fingerprint(transcript: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts_id": transcript.get("tsId"),
        "timestamp": transcript.get("timestamp"),
        "status": transcript.get("status"),
        "md5": transcript.get("md5Sum"),
    }


def local_pagexml_md5(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.md5(path.read_bytes()).hexdigest()


def transcript_changed(recorded: Any, fingerprint: dict[str, Any], pagexml_target: Path) -> bool:
    """True when Transkribus holds a different transcript than the one on disk.

    Transkribus reports an md5 for the transcript XML that matches the downloaded
    file byte-for-byte, so the file itself is the source of truth. The recorded
    state is only a fast path that avoids hashing every page on every run.
    """
    remote_md5 = fingerprint.get("md5")
    if remote_md5:
        if isinstance(recorded, dict) and recorded.get("md5") == remote_md5:
            return False
        return local_pagexml_md5(pagexml_target) != remote_md5

    # No md5 from the API: fall back to the transcript id we last stored.
    if not isinstance(recorded, dict):
        return True
    return recorded.get("ts_id") != fingerprint.get("ts_id")


def transcription_body(markdown: str) -> str:
    """Strip the '# Seite N' heading so we can compare actual transcribed text."""
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# Seite"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def tracked_images(variant_dir: Path) -> set[str]:
    """Image paths git knows about, relative to the variant directory.

    The manifest must describe what the PUBLISHED SITE serves, not what
    happens to be present in this checkout. CI syncs with a sparse checkout
    that deliberately omits images/ (issue #32), so a plain exists() check
    there reports "no local image" for files that are tracked and served, and
    the manifest silently reverts to Transkribus session URLs - which is what
    undid the facsimile fix on the very next nightly run.
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--", "images"],
            cwd=variant_dir, capture_output=True, timeout=60)
        if out.returncode != 0:
            return set()
        return {name for name in out.stdout.decode("utf-8").split("\0") if name}
    except Exception:  # noqa: BLE001 - not a git checkout, or git missing
        return set()


def existing_manifest_page_count(variant_dir: Path) -> int:
    manifest_path = variant_dir / "viewer_manifest.json"
    if not manifest_path.exists():
        return 0
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    pages = payload.get("pages")
    return len(pages) if isinstance(pages, list) else 0


def write_binary(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sync_variant(
    session: requests.Session,
    auth: AuthContext,
    variant: VariantConfig,
    output_root: Path,
    overwrite: bool,
    download_images: bool = True,
    refresh: bool = False,
    allow_content_loss: bool = False,
    max_page_loss: float = 0.05,
) -> dict[str, int]:
    variant_dir = output_root / VARIANT_DIR_MAP[variant.variant_id]
    images_dir = variant_dir / "images"
    transcriptions_dir = variant_dir / "transcriptions"
    line_coords_dir = variant_dir / "line_coords"
    pagexml_dir = variant_dir / "pagexml"

    for directory in [images_dir, transcriptions_dir, line_coords_dir, pagexml_dir, variant_dir / "translations", variant_dir / "entities"]:
        directory.mkdir(parents=True, exist_ok=True)

    document = fetch_document_content(session, auth, variant.collection_id, variant.document_id)
    pages = (((document.get("pageList") or {}).get("pages")) or [])
    pages = sorted(pages, key=lambda page: int(page.get("pageNr", 0)))

    # Guard: a partial/empty API response must never shrink an existing edition.
    previous_page_count = existing_manifest_page_count(variant_dir)
    tracked = tracked_images(variant_dir)
    if previous_page_count and max_page_loss < 1:
        allowed = previous_page_count * (1 - max_page_loss)
        if len(pages) < allowed:
            raise RuntimeError(
                f"{variant.variant_id}: Transkribus returned {len(pages)} pages but the existing "
                f"manifest has {previous_page_count}. Refusing to sync (would drop "
                f"{previous_page_count - len(pages)} pages). Re-run with --max-page-loss 1 if this "
                "shrink is intentional."
            )

    state = load_sync_state(variant_dir)
    recorded_pages: dict[str, Any] = state.get("pages", {})
    new_state_pages: dict[str, Any] = {}
    stats = {"fetched": 0, "unchanged": 0, "skipped": 0, "protected": 0}

    viewer_pages: list[dict[str, Any]] = []

    for page in pages:
        page_nr = int(page.get("pageNr", len(viewer_pages) + 1))
        pagexml_target = pagexml_dir / f"page_{page_nr}.xml"
        recorded = recorded_pages.get(str(page_nr))

        transcript = pick_latest_transcript(page, variant.status_preference)
        if transcript is None:
            # Keep whatever we already have rather than dropping the page from the edition.
            if pagexml_target.exists():
                print(f"[WARN] No remote transcript for {variant.variant_id} page {page_nr}; keeping local copy")
                if recorded is not None:
                    new_state_pages[str(page_nr)] = recorded
                stats["protected"] += 1
            else:
                print(f"[WARN] No transcript for {variant.variant_id} page {page_nr}; skipping page")
                stats["skipped"] += 1
                continue
        else:
            pagexml_url = str(transcript.get("url", "")).strip()
            if not pagexml_url:
                print(f"[WARN] Missing pagexml URL for {variant.variant_id} page {page_nr}; skipping page")
                stats["skipped"] += 1
                continue

            fingerprint = transcript_fingerprint(transcript)
            needs_fetch = (
                overwrite
                or not pagexml_target.exists()
                or (refresh and transcript_changed(recorded, fingerprint, pagexml_target))
            )

            if needs_fetch:
                pagexml_response = get_with_auth(session, auth, pagexml_url, timeout=60)
                write_text(pagexml_target, pagexml_response.text)
                stats["fetched"] += 1
            else:
                stats["unchanged"] += 1

            new_state_pages[str(page_nr)] = fingerprint

        pagexml_text = pagexml_target.read_text(encoding="utf-8")

        image_width, image_height, lines = parse_pagexml(pagexml_text)

        image_url = str(page.get("url", "")).strip()
        image_name = str(page.get("imgFileName", "")).strip()
        image_ext = Path(image_name).suffix.lower() if image_name else ".jpg"
        if not image_ext:
            image_ext = ".jpg"
        image_rel = f"images/page_{page_nr}{image_ext}"
        image_target = variant_dir / image_rel
        if download_images and image_url:
            if overwrite or not image_target.exists():
                image_response = get_with_auth(session, auth, image_url, timeout=120)
                write_binary(image_target, image_response.content)

        transcription_md = "# Seite {0}\n\n{1}\n".format(
            page_nr,
            "\n".join(line["text"] for line in lines if line.get("text")),
        )
        transcription_rel = f"transcriptions/page_{page_nr}.md"
        transcription_target = variant_dir / transcription_rel

        # Never let a page that has already been transcribed fall back to an empty
        # stub because Transkribus re-segmented it (see the pages 1-51 loss in 275dbeab).
        write_transcription = True
        if not allow_content_loss and transcription_target.exists():
            existing_body = transcription_body(transcription_target.read_text(encoding="utf-8"))
            new_body = transcription_body(transcription_md)
            if existing_body and not new_body:
                print(
                    f"[WARN] {variant.variant_id} page {page_nr}: newest Transkribus transcript has no "
                    f"text but {len(existing_body)} chars exist locally; keeping local text "
                    "(use --allow-content-loss to override)"
                )
                write_transcription = False
                stats["protected"] += 1

        if write_transcription:
            write_text(transcription_target, transcription_md)
        translation_rel = f"translations/page_{page_nr}.md"
        translation_target = variant_dir / translation_rel

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

        # Use local file if it was downloaded, otherwise fall back to external URL
        # Local path when the image is on disk OR tracked by git; only a page
        # that exists in neither falls back to the Transkribus URL. Those URLs
        # are session links to a service outside this project - fine as a last
        # resort for a page we do not have, wrong as the published source.
        have_local = image_target.exists() or image_rel in tracked
        image_manifest_value = image_rel if have_local else (image_url or None)
        viewer_pages.append(
            {
                "page_nr": page_nr,
                "image": image_manifest_value,
                "transcription": transcription_rel,
                "translation": translation_rel if translation_target.exists() else None,
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

    state["pages"] = new_state_pages
    state["variant_id"] = variant.variant_id
    state["document_id"] = variant.document_id
    state["collection_id"] = variant.collection_id
    write_text(variant_dir / SYNC_STATE_FILENAME, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True))

    return stats


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
    download_images = not args.no_images

    session = requests.Session()
    auth = resolve_auth(session)
    print(f"[INFO] Auth OK ({auth.source})")
    if not download_images:
        print("[INFO] Image download disabled (--no-images); external URLs will be stored in viewer manifest.")

    if args.refresh:
        print("[INFO] Refresh mode: pages whose Transkribus transcript changed will be re-downloaded.")

    totals = {"fetched": 0, "unchanged": 0, "skipped": 0, "protected": 0}
    for variant in variants:
        print(
            f"[INFO] Sync {variant.variant_id}: collection={variant.collection_id}, document={variant.document_id}"
        )
        stats = sync_variant(
            session,
            auth,
            variant,
            output_root,
            overwrite=args.overwrite,
            download_images=download_images,
            refresh=args.refresh,
            allow_content_loss=args.allow_content_loss,
            max_page_loss=args.max_page_loss,
        )
        print(
            f"[INFO]   {variant.variant_id}: {stats['fetched']} updated, {stats['unchanged']} unchanged, "
            f"{stats['protected']} protected, {stats['skipped']} skipped"
        )
        for key in totals:
            totals[key] += stats[key]

    print(
        f"[INFO] Disputation sync completed: {totals['fetched']} pages updated, "
        f"{totals['unchanged']} unchanged, {totals['protected']} protected, {totals['skipped']} skipped"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
