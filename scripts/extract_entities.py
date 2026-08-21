#!/usr/bin/env python3
"""Extract named entities from the recognised texts.

Replaces ner_extraction.py, which could not run here: it carried absolute paths
from another machine, named only the six original documents, called an outdated
model through raw REST, and truncated every page at 1,500 characters - roughly
the median page length in this corpus, so it silently dropped the tail of half
the pages it read.

The prompt also encodes what building the register taught us. The previous pass
counted Bible books as people - "Mathei" 33 times, "Johannis" 34, "Esa" 17 -
and kept bare titles like "Doctor" as names. Both are excluded here, because a
citation belongs in the scripture register (recognize_bible_refs.py) and a title
is not a person.

Incremental: a page already extracted under the same prompt and model is not
sent again, so a re-run costs only what changed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini_client as gc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "entities"
MERGED = OUT_DIR / "named_entities.json"
PAGE_RE = re.compile(r"page_(\d+)\.md$")

PROMPT_VERSION = 2
BATCH_PAGES = 6
MAX_CHARS_PER_PAGE = 6000

SYSTEM = """\
Du erschliesst Quellen zur Berner Disputation von 1528 (frühneuhochdeutsch,
maschinell erkannt, daher fehlerhaft).

Erfasse benannte Entitäten:
- PERSON: wirkliche Personen mit Namen
- ORG: Institutionen, Orden, Räte, Ämter als Körperschaft
- LOC: Orte, Städte, Dörfer, Länder

**Nicht erfassen:**
- Biblische Bücher und Verweise (Matthäus, Johannis, Esaie, Corinth …) — das
  sind Stellenangaben, keine Personen.
- Biblische und göttliche Gestalten (Christus, Gott, Paulus, Petrus, Moses …).
- Blosse Titel und Rollen ohne Namen (Doctor, Pfarrer, Meister, Bischof).
- Wörter, die nur wegen eines Erkennungsfehlers wie ein Name aussehen.

Gib den Namen so wieder, wie er dasteht — nicht normalisiert.

Antworte ausschliesslich als JSON-Array, ohne weiteren Text:
[{"name": "...", "type": "PERSON|ORG|LOC", "page": 123}]
Ist auf einer Seite nichts zu finden, lass sie weg.
"""


def witness_dirs() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for root in (ROOT / "data" / "disputation", ROOT / "data" / "prints"):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if (child / "transcriptions").is_dir():
                found[child.name] = child / "transcriptions"
    return found


def load_pages(directory: Path) -> dict[int, str]:
    pages: dict[int, str] = {}
    for path in directory.glob("page_*.md"):
        m = PAGE_RE.match(path.name)
        if not m:
            continue
        body = re.sub(r"^#\s*Seite[^\n]*\n", "", path.read_text(encoding="utf-8")).strip()
        if body:
            pages[int(m.group(1))] = body[:MAX_CHARS_PER_PAGE]
    return pages


def state_path(key: str) -> Path:
    return OUT_DIR / f"{key}_state.json"


def load_state(key: str) -> dict[str, Any]:
    path = state_path(key)
    if not path.exists():
        return {"prompt_version": PROMPT_VERSION, "pages": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"prompt_version": PROMPT_VERSION, "pages": {}}
    if payload.get("prompt_version") != PROMPT_VERSION:
        return {"prompt_version": PROMPT_VERSION, "pages": {}}
    return payload


def parse_reply(reply: str) -> list[dict[str, Any]]:
    match = re.search(r"\[[\s\S]*\]", reply or "")
    if not match:
        return []
    text = match.group(0)
    for attempt in (text, re.sub(r",\s*([\]}])", r"\1", text)):
        try:
            data = json.loads(attempt)
            return [d for d in data if isinstance(d, dict) and d.get("name")]
        except json.JSONDecodeError:
            continue
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract named entities")
    parser.add_argument("--witness", action="append")
    parser.add_argument("--model", default=gc.DEFAULT_MODEL)
    parser.add_argument("--max-pages", type=int, default=0,
                        help="Stop after this many pages per witness (0 = all)")
    parser.add_argument("--merge-only", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    directories = witness_dirs()
    targets = args.witness or list(directories)

    if not args.merge_only:
        try:
            client = gc.build_client()
        except gc.GeminiUnavailable as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

        for key in targets:
            directory = directories.get(key)
            if not directory:
                print(f"  [skip] {key}: no transcriptions")
                continue
            pages = load_pages(directory)
            state = load_state(key)
            done = set(state["pages"])
            todo = [p for p in sorted(pages) if str(p) not in done]
            if args.max_pages:
                todo = todo[: args.max_pages]
            if not todo:
                print(f"  {key}: nothing to do ({len(pages)} pages already extracted)")
                continue

            print(f"  {key}: {len(todo)} page(s) to extract")
            usage = gc.Usage()
            for start in range(0, len(todo), BATCH_PAGES):
                batch = todo[start : start + BATCH_PAGES]
                joined = "\n\n---\n\n".join(f"[Seite {p}]\n{pages[p]}" for p in batch)
                try:
                    reply = gc.generate(
                        client, model=args.model,
                        parts=[gc.text_part(joined)],
                        system_instruction=SYSTEM, usage=usage, temperature=0.1,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"    [WARN] pages {batch[0]}-{batch[-1]}: {type(exc).__name__}: {exc}")
                    continue
                found = parse_reply(reply)
                by_page: dict[str, list[dict[str, Any]]] = {str(p): [] for p in batch}
                for item in found:
                    page = item.get("page")
                    if str(page) in by_page:
                        by_page[str(page)].append(
                            {"name": str(item["name"]).strip(),
                             "type": str(item.get("type", "PERSON")).upper()})
                state["pages"].update(by_page)
                state_path(key).write_text(
                    json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if (start // BATCH_PAGES) % 10 == 0:
                    print(f"    {start + len(batch)}/{len(todo)} pages", flush=True)
                time.sleep(0.2)
            print(f"    tokens in={usage.prompt_tokens} out={usage.output_tokens} "
                  f"thinking={usage.thought_tokens}")

    # Merge every witness's state into the flat file the register reads.
    #
    # Seeded from whatever is already in the merged file. The earlier extraction
    # wrote no per-witness state, so a merge that trusted state alone would
    # replace 1,396 existing entities with nothing - which is exactly what it
    # did the first time this ran.
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    if MERGED.exists():
        try:
            for entry in json.loads(MERGED.read_text(encoding="utf-8")):
                name, kind = entry.get("name", "").strip(), entry.get("type", "PERSON")
                if not name:
                    continue
                merged[(name, kind)] = {"name": name, "type": kind,
                                        "occurrences": list(entry.get("occurrences", []))}
        except Exception:
            pass

    # A witness that has its own state supersedes whatever the old file held
    # for it, so a re-extraction replaces rather than duplicates.
    restated = {k for k in directories if load_state(k).get("pages")}
    if restated:
        for entry in merged.values():
            entry["occurrences"] = [o for o in entry["occurrences"]
                                    if o.get("doc") not in restated]
        for key in list(merged):
            if not merged[key]["occurrences"]:
                del merged[key]
    for key in directories:
        state = load_state(key)
        for page, items in state.get("pages", {}).items():
            for item in items:
                name, kind = item.get("name", "").strip(), item.get("type", "PERSON")
                if not name:
                    continue
                entry = merged.setdefault((name, kind),
                                          {"name": name, "type": kind, "occurrences": []})
                entry["occurrences"].append({"doc": key, "page": int(page), "context": ""})

    out = sorted(merged.values(), key=lambda e: -len(e["occurrences"]))
    MERGED.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    docs: dict[str, int] = {}
    for entry in out:
        for occ in entry["occurrences"]:
            docs[occ["doc"]] = docs.get(occ["doc"], 0) + 1
    print(f"\nmerged {len(out)} entities, {sum(len(e['occurrences']) for e in out)} occurrences")
    for doc, n in sorted(docs.items(), key=lambda x: -x[1]):
        print(f"  {doc:30} {n}")
    print(f"wrote {MERGED.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
