#!/usr/bin/env python3
"""Translate witness transcriptions to modern German via GPUStack (issue #61).

The same route the druck_1528 translations took, but pointed at the four
remaining Staatsarchiv manuscripts and driven from this machine rather than a
notebook: GPUStack's gpt-oss-120b, temperature 0, one call per page, written
straight to translations/page_N.md.

What it refuses to do
---------------------
Send an empty page to the model. Most of these manuscripts are not
transcribed - of a_v_1444_cyro's 839 pages, 13 carry text; the PAGE XML for
the rest holds zero Unicode elements, so the blankness is real and not a sync
artifact. Pages under --min-chars are skipped and counted, never translated:
handing "# Seite 300" to a translator is how page 496 of druck_1528 ended up
with the model addressing the operator instead of translating (#43).

Resumable by construction: a page whose translation file already exists is
skipped unless --force. Interrupt it freely.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"

BASE_URL = os.environ.get("GPUSTACK_BASE_URL", "https://gpustack.unibe.ch/v1")
MODEL = os.environ.get("TRANSLATION_MODEL", "gpt-oss-120b")

# The four manuscripts of #61. druck_1528 and a_v_1447 are already translated.
DEFAULT_WITNESSES = [
    "a_v_1443_hertwig",
    "a_v_1444_cyro",
    "a_v_1445_schoeni",
    "a_v_1446_ruemlang",
]

WITNESS_LABEL = {
    "a_v_1443_hertwig": "A V 1443, Abschrift Hertwig",
    "a_v_1444_cyro": "A V 1444, Abschrift Cyro",
    "a_v_1445_schoeni": "A V 1445, Abschrift Schöni",
    "a_v_1446_ruemlang": "A V 1446, Abschrift Rümlang",
    "a_v_1447_schlussredaktion": "A V 1447, Schlussredaktion",
}

PROMPT = """\
Du bist ein wissenschaftlicher Übersetzer für frühneuzeitliche Texte.
Übersetze die folgende Seite aus einer Handschrift der Berner Disputation von \
1528 ({witness}) ins moderne Deutsch.

Der Text ist maschinell erkannt. Er kann lückenhaft sein, aus einzelnen \
Wörtern, Spaltenresten oder Randnotizen bestehen.

Anforderungen:
- Behalte den sachlichen, theologischen Charakter des Originals bei.
- Behalte die Zeilen- und Absatzstruktur sowie Markdown-Überschriften (# Titel) bei.
- Übersetze auch Bruchstücke, so weit sie sich deuten lassen; gib ein \
unverständliches Bruchstück unverändert wieder, statt es zu erfinden.
- Kommentiere nicht, entschuldige dich nicht und wende dich nicht an den \
Benutzer. Gib ausschliesslich den übersetzten Markdown-Text zurück.

Seite:
{text}
"""

# Refusal or operator-address patterns: the failure mode from #43, where the
# model answered the operator instead of translating. Cheap to check, and a
# hit means the page is left untranslated rather than published as chatter.
CHATTER = re.compile(
    r"bitte stellen sie|kann keine übersetzung|als sprachmodell|"
    r"ich kann diesen text nicht|kein text (vorhanden|zum übersetzen)|"
    r"please provide|as an ai",
    re.IGNORECASE)


def body_of(text: str) -> str:
    """Page text without the markdown heading line."""
    return re.sub(r"^#.*$", "", text, flags=re.M).strip()


def call_llm(api_key: str, prompt: str, retries: int = 4) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 4000,
    }).encode("utf-8")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/chat/completions", data=body,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                out = json.load(resp)
            return out["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001 - retry, then surface
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {retries} attempts: {last}")


def pages_to_do(witness: str, min_chars: int, force: bool):
    src = DISPUTATION / witness / "transcriptions"
    dst = DISPUTATION / witness / "translations"
    todo, skipped_empty, skipped_done = [], 0, 0
    for path in sorted(src.glob("page_*.md"),
                       key=lambda p: int(re.search(r"\d+", p.name).group())):
        if not re.fullmatch(r"page_\d+\.md", path.name):
            continue  # _gemini variants duplicate the page the viewer reads
        nr = int(re.search(r"\d+", path.name).group())
        text = path.read_text(encoding="utf-8")
        if len(body_of(text)) < min_chars:
            skipped_empty += 1
            continue
        if not force and (dst / path.name).exists():
            skipped_done += 1
            continue
        todo.append((nr, text))
    return todo, skipped_empty, skipped_done


def run_witness(witness: str, api_key: str, workers: int, min_chars: int,
                force: bool, dry_run: bool) -> dict:
    dst = DISPUTATION / witness / "translations"
    todo, empty, done = pages_to_do(witness, min_chars, force)
    label = WITNESS_LABEL.get(witness, witness)
    print(f"{witness}: {len(todo)} zu übersetzen, {empty} leer (übersprungen), "
          f"{done} bereits vorhanden")
    if dry_run or not todo:
        return {"witness": witness, "translated": 0, "empty": empty,
                "already": done, "failed": 0, "chatter": 0}

    dst.mkdir(parents=True, exist_ok=True)

    def work(item):
        nr, text = item
        out = call_llm(api_key, PROMPT.format(witness=label, text=text))
        if not out.strip():
            return nr, None, "leer"
        if CHATTER.search(out):
            return nr, None, "modellrede"
        return nr, out, None

    written = failed = chatter = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(work, item): item[0] for item in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            nr = futures[fut]
            try:
                nr, out, problem = fut.result()
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  FEHLER Seite {nr}: {exc}", file=sys.stderr)
                continue
            if problem:
                chatter += 1
                print(f"  ÜBERSPRUNGEN Seite {nr}: {problem}", file=sys.stderr)
                continue
            (dst / f"page_{nr}.md").write_text(
                out.rstrip() + "\n", encoding="utf-8")
            written += 1
            if i % 25 == 0:
                print(f"  {witness}: {i}/{len(todo)}")
    print(f"  -> {written} geschrieben, {chatter} wegen Modellrede verworfen, "
          f"{failed} fehlgeschlagen")
    return {"witness": witness, "translated": written, "empty": empty,
            "already": done, "failed": failed, "chatter": chatter}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("witnesses", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--min-chars", type=int, default=20,
                    help="pages with less transcription than this are skipped")
    ap.add_argument("--force", action="store_true",
                    help="retranslate pages that already have a translation")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("GPUSTACK_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        print("GPUSTACK_API_KEY ist nicht gesetzt", file=sys.stderr)
        return 1

    witnesses = args.witnesses or DEFAULT_WITNESSES
    results = [run_witness(w, api_key, args.workers, args.min_chars,
                           args.force, args.dry_run) for w in witnesses]
    print("\nGesamt:")
    for r in results:
        print(f"  {r['witness']:28} +{r['translated']:4} übersetzt, "
              f"{r['empty']:4} leer, {r['failed']} Fehler, {r['chatter']} verworfen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
