#!/usr/bin/env python3
"""Resolve e-rara digitisations to page image URLs over IIIF.

Images are never stored in the repository (see issue #7): the published Pages
artifact is already 2 GB against a 1 GB limit, and the four prints would add up
to 2.6 GB more. Pages are fetched transiently for recognition and only the text
is kept.

Note that the number in an e-rara DOI is NOT the IIIF identifier. 
10.3931/e-rara-141267 is served under IIIF id 30973277, which has to be read
off the DOI landing page.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_URL = "https://www.e-rara.ch/i3f/v20/{id}/manifest"
MANIFEST_ID_RE = re.compile(r"e-rara\.ch/i3f/v20/(\d+)/manifest")
USER_AGENT = "reformation-research/1.0 (+https://github.com/thodel/reformation)"


@dataclass(frozen=True)
class Page:
    page_nr: int
    canvas_id: str
    image_service: str
    label: str

    def image_url(self, size: str = "!2000,2000") -> str:
        return f"{self.image_service}/full/{size}/0/default.jpg"


def fetch(url: str, timeout: int = 60, retries: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Could not fetch {url}: {last}")


def resolve_manifest_id(doi: str) -> str:
    """Read the IIIF id off the DOI landing page."""
    html = fetch(f"https://doi.org/{doi}").decode("utf-8", "replace")
    match = MANIFEST_ID_RE.search(html)
    if not match:
        raise RuntimeError(f"No IIIF manifest id found on the landing page for {doi}")
    return match.group(1)


def load_manifest(erara_id: str) -> dict[str, Any]:
    return json.loads(fetch(MANIFEST_URL.format(id=erara_id)).decode("utf-8", "replace"))


def pages_from_manifest(manifest: dict[str, Any]) -> list[Page]:
    sequences = manifest.get("sequences") or [{}]
    canvases = sequences[0].get("canvases") or []
    pages: list[Page] = []
    for index, canvas in enumerate(canvases, start=1):
        images = canvas.get("images") or []
        if not images:
            continue
        resource = images[0].get("resource") or {}
        service = (resource.get("service") or {}).get("@id")
        if not service:
            continue
        pages.append(
            Page(
                page_nr=index,
                canvas_id=str(canvas.get("@id", "")),
                image_service=str(service),
                label=str(canvas.get("label", "")),
            )
        )
    return pages


def load_witnesses(config_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return [w for w in payload.get("witnesses", []) if not w.get("skip")]


def default_iiif_size(config_path: Path) -> str:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return str(payload.get("iiif_size", "!2000,2000"))
