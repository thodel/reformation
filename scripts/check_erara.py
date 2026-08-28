#!/usr/bin/env python3
"""Check that the facsimiles the site links to are still served (issue #62).

Since #57 the edition mirrors no page images at all: every facsimile of all
five prints is fetched from e-rara at view time. That is the right arrangement
for rights and repository size, and it makes the site's most visible component
depend on a service nobody here operates. If e-rara renumbers an object or has
an outage, the viewer degrades silently - a dark pane, no error - and the first
to notice would be a reader.

Availability is expected to be high; this exists so that the rare failure is
reported rather than discovered. It therefore checks the two things that would
actually break the page, and nothing else:

  1. the IIIF image service answers for one page per witness, and
  2. its native pixel dimensions still match what the manifest recorded -
     which is what catches a silent renumbering, where a URL keeps working but
     now serves a different object.

Five requests per run, one per witness: enough to detect an outage or a
renumbering, light enough to be a good citizen on someone else's service.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# One probe page per witness. Not page 1: leading blanks and title pages are
# the most likely to be re-scanned or re-ordered, so a page from the body is
# the more honest canary.
MANIFESTS = {
    "druck_1528 (Zürich, März 1528)": ("data/disputation/druck_1528/viewer_manifest.json", 20),
    "druck_1528_04 (Zürich, April 1528)": ("data/prints/druck_1528_04/viewer_manifest.json", 20),
    "druck_1608_bern (Bern 1608, UB)": ("data/prints/druck_1608_bern/viewer_manifest.json", 20),
    "druck_1608_zuerich (Bern 1608, ZB)": ("data/prints/druck_1608_zuerich/viewer_manifest.json", 20),
    "druck_1701 (Bern 1701)": ("data/prints/druck_1701/viewer_manifest.json", 20),
}

TIMEOUT = 45

# Recorded native dimensions of each probe page. Without this only druck_1528
# (which keeps line_coords) could be checked for renumbering; the other four
# would answer 200 for a URL now serving a different object and the check
# would call that healthy. Written by --update-baseline.
BASELINE_PATH = ROOT / "config" / "erara_baseline.json"


def service_base(image_url: str) -> str:
    """The IIIF service root behind either manifest style.

    druck_1528 stores .../<id>/info.json (deep zoom); the other four store a
    sized JPEG .../<id>/full/!1600,1600/0/default.jpg. Both reduce to the same
    service root.
    """
    marker = "/i3f/v20/"
    if marker not in image_url:
        return ""
    tail = image_url.split(marker, 1)[1]
    return f"https://www.e-rara.ch{marker}{tail.split('/', 1)[0]}"


def load_baseline() -> dict:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("pages", {})
    return {}


def expected_dims(witness_dir: Path, page_nr: int, name: str, baseline: dict):
    """Native dimensions this page is expected to have.

    Prefers the recorded baseline; falls back to line_coords, which only
    druck_1528 keeps.
    """
    entry = baseline.get(name)
    if entry and entry.get("width") and entry.get("height"):
        return int(entry["width"]), int(entry["height"])
    coords = witness_dir / "line_coords" / f"page_{page_nr}.json"
    if coords.exists():
        try:
            img = json.loads(coords.read_text(encoding="utf-8")).get("image", {})
            if img.get("width") and img.get("height"):
                return int(img["width"]), int(img["height"])
        except (ValueError, KeyError):
            pass
    return None


def check(name: str, manifest_path: Path, page_nr: int, baseline: dict) -> tuple[bool, str]:
    if not manifest_path.exists():
        return False, f"{name}: Manifest fehlt ({manifest_path})"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = payload.get("pages", [])
    entry = next((p for p in pages if p.get("page_nr") == page_nr), None) or (pages[0] if pages else None)
    if not entry:
        return False, f"{name}: Manifest enthält keine Seiten"
    base = service_base(entry.get("image", "") or "")
    if not base:
        return False, f"{name}: Seite {entry.get('page_nr')} verweist nicht auf e-rara"

    try:
        with urllib.request.urlopen(f"{base}/info.json", timeout=TIMEOUT) as resp:
            info = json.load(resp)
    except urllib.error.HTTPError as exc:
        return False, f"{name}: info.json HTTP {exc.code} ({base})"
    except Exception as exc:  # noqa: BLE001 - network, DNS, timeout
        return False, f"{name}: info.json nicht erreichbar - {exc} ({base})"

    got = (info.get("width"), info.get("height"))
    if not all(got):
        return False, f"{name}: info.json ohne Bildmasse ({base})"

    want = expected_dims(manifest_path.parent, entry["page_nr"], name, baseline)
    if want and tuple(want) != got:
        return False, (f"{name}: Seite {entry['page_nr']} misst jetzt {got[0]}x{got[1]}, "
                       f"erwartet {want[0]}x{want[1]} - moegliche Umnummerierung ({base})")

    suffix = " (Masse geprueft)" if want else " (keine lokalen Masse hinterlegt)"
    return True, f"{name}: OK {got[0]}x{got[1]}{suffix}"


def write_baseline() -> int:
    """Record today's dimensions as the expectation. Run deliberately, never
    from the scheduled check - a baseline that updates itself would ratify the
    very change it exists to detect."""
    pages = {}
    for name, (rel, page_nr) in MANIFESTS.items():
        manifest_path = ROOT / rel
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = payload.get("pages", [])
        entry = next((p for p in entries if p.get("page_nr") == page_nr), None) or entries[0]
        base = service_base(entry.get("image", "") or "")
        with urllib.request.urlopen(f"{base}/info.json", timeout=TIMEOUT) as resp:
            info = json.load(resp)
        pages[name] = {"page_nr": entry["page_nr"], "service": base,
                       "width": info["width"], "height": info["height"]}
        print(f"  {name}: {info['width']}x{info['height']}")
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(
        {"note": "Erwartete native Bildmasse der Stichprobenseiten je Zeuge; "
                 "geschrieben von scripts/check_erara.py --update-baseline.",
         "pages": pages}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nBasislinie geschrieben: {BASELINE_PATH.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true",
                    help="only print failures")
    ap.add_argument("--update-baseline", action="store_true",
                    help="record the current dimensions as the expected ones")
    args = ap.parse_args()

    if args.update_baseline:
        return write_baseline()

    baseline = load_baseline()
    failures = []
    for name, (rel, page_nr) in MANIFESTS.items():
        ok, message = check(name, ROOT / rel, page_nr, baseline)
        if ok:
            if not args.quiet:
                print(f"  {message}")
        else:
            failures.append(message)
            print(f"  FEHLER {message}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)} von {len(MANIFESTS)} Zeugen nicht erreichbar "
              "oder veraendert.", file=sys.stderr)
        return 1
    print(f"\nAlle {len(MANIFESTS)} Zeugen erreichbar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
