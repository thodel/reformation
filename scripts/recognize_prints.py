#!/usr/bin/env python3
"""Recognise the text of the printed Disputation editions with Gemini (issue #8).

Page images are streamed from e-rara over IIIF and never stored (issue #7).
Only the recognised text is written, to data/prints/<key>/transcriptions/.

Modes:
  --list-models        report the model ids this API key may call
  --sample N           recognise N pages per witness across a model/size matrix
                       and report output plus token usage, to choose a tier
  (default)            recognise every page that has no text yet

Recognition state lives in data/prints/<key>/recognition_state.json and records
the model and prompt version each page was produced with, so changing either
marks pages for redoing without re-recognising everything by accident.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import erara  # noqa: E402
import gemini_client as gc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRINTS_ROOT = ROOT / "data" / "prints"
CONFIG = ROOT / "config" / "prints.json"

# Bump when the prompt changes; pages recorded under an older version can then
# be re-recognised deliberately with --refresh.
PROMPT_VERSION = 1

SYSTEM_INSTRUCTION = """\
Du transkribierst frühneuzeitliche deutsche Drucke (Fraktur, 16.–18. Jahrhundert).

Regeln:
- Diplomatische Transkription: Schreibung des Originals unverändert übernehmen.
- Nicht modernisieren, nicht normalisieren, nicht korrigieren, nicht übersetzen.
- u/v, i/j, langes ſ und übergeschriebene Vokale (uͦ, aͤ, oͤ) so wiedergeben,
  wie sie dastehen.
- Zeilenumbrüche des Drucks beibehalten.
- Kolumnentitel, Seitenzahlen und Marginalien mit aufnehmen, Marginalien am
  Ende unter der Zeile "## Marginalien".
- Unleserliche Stellen als [unleserlich] markieren.
- Ausschliesslich den Text ausgeben, keine Einleitung, keine Erklärung,
  keine Code-Zäune.
"""

USER_PROMPT = "Transkribiere diese Druckseite."


def split_models(value: str) -> list[str]:
    return [m.strip() for m in value.split(",") if m.strip()]


def split_sizes(value: str) -> list[str]:
    """IIIF sizes contain commas (!2000,2000), so they are separated by ';'."""
    return [s.strip() for s in value.split(";") if s.strip()]


def state_path(key: str) -> Path:
    return PRINTS_ROOT / key / "recognition_state.json"


def load_state(key: str) -> dict[str, Any]:
    path = state_path(key)
    if not path.exists():
        return {"pages": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"pages": {}}
    if not isinstance(payload.get("pages"), dict):
        payload["pages"] = {}
    return payload


def save_state(key: str, state: dict[str, Any]) -> None:
    path = state_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def transcription_path(key: str, page_nr: int) -> Path:
    return PRINTS_ROOT / key / "transcriptions" / f"page_{page_nr}.md"


def needs_recognition(key: str, page_nr: int, state: dict, model: str, refresh: bool) -> bool:
    target = transcription_path(key, page_nr)
    if not target.exists() or not target.read_text(encoding="utf-8").strip():
        return True
    if not refresh:
        return False
    record = state.get("pages", {}).get(str(page_nr))
    if not isinstance(record, dict):
        return True
    return record.get("model") != model or record.get("prompt_version") != PROMPT_VERSION


def recognise_page(client, page: erara.Page, *, model: str, size: str, usage: gc.Usage) -> str:
    image = erara.fetch(page.image_url(size), timeout=90)
    parts = [gc.image_part(image), gc.text_part(USER_PROMPT)]
    return gc.generate(
        client,
        model=model,
        parts=parts,
        system_instruction=SYSTEM_INSTRUCTION,
        usage=usage,
    )


def cmd_list_models(client) -> int:
    names = gc.list_models(client)
    print(f"{len(names)} model(s) callable with this key:\n")
    for name in names:
        print(f"  {name}")
    return 0


def cmd_sample(client, witnesses, args) -> int:
    models = split_models(args.models)
    sizes = split_sizes(args.sizes)
    print(f"Sampling {args.sample} page(s) per witness across "
          f"{len(models)} model(s) x {len(sizes)} size(s)\n")

    out_dir = PRINTS_ROOT / "_samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for witness in witnesses:
        manifest = erara.load_manifest(witness["erara_id"])
        pages = erara.pages_from_manifest(manifest)
        if not pages:
            continue
        # Sample from the middle, where a book carries running text rather than
        # title pages and blanks.
        middle = len(pages) // 2
        chosen = pages[middle : middle + args.sample]
        for page in chosen:
            for model in models:
                for size in sizes:
                    usage = gc.Usage()
                    started = time.time()
                    try:
                        text = recognise_page(client, page, model=model, size=size, usage=usage)
                        error = ""
                    except Exception as exc:  # noqa: BLE001
                        text, error = "", f"{type(exc).__name__}: {exc}"
                    elapsed = time.time() - started
                    name = f"{witness['key']}_p{page.page_nr}_{model.replace('/', '_')}_{size.replace('!', '').replace(',', 'x')}.md"
                    (out_dir / name).write_text(
                        f"# {witness['label']} — Seite {page.page_nr}\n"
                        f"<!-- model={model} size={size} chars={len(text)} "
                        f"seconds={elapsed:.1f} -->\n\n{text or error}\n",
                        encoding="utf-8",
                    )
                    rows.append((witness["key"], page.page_nr, model, size, len(text), elapsed, error))
                    print(f"  {witness['key']:20} p{page.page_nr:<4} {model:24} {size:12} "
                          f"{len(text):5} chars {elapsed:5.1f}s {error[:40]}")

    print(f"\nWrote {len(rows)} sample(s) to {out_dir.relative_to(ROOT)}")
    summary = {}
    for key, _page, model, size, chars, seconds, error in rows:
        bucket = summary.setdefault((model, size), [0, 0, 0.0, 0])
        bucket[0] += 1
        bucket[1] += chars
        bucket[2] += seconds
        bucket[3] += 1 if error else 0
    print(f"\n{'model':26} {'size':12} {'pages':>6} {'avg chars':>10} {'avg s':>7} {'errors':>7}")
    for (model, size), (n, chars, seconds, errors) in sorted(summary.items()):
        print(f"{model:26} {size:12} {n:6} {chars // max(n, 1):10} {seconds / max(n, 1):7.1f} {errors:7}")
    return 0


def cmd_recognise(client, witnesses, args) -> int:
    size = args.size or erara.default_iiif_size(CONFIG)
    budget = args.max_pages
    total_done = 0

    for witness in witnesses:
        key = witness["key"]
        if args.witness and key not in args.witness:
            continue
        state = load_state(key)
        manifest = erara.load_manifest(witness["erara_id"])
        pages = erara.pages_from_manifest(manifest)
        pending = [p for p in pages if needs_recognition(key, p.page_nr, state, args.model, args.refresh)]
        print(f"{key}: {len(pages)} page(s), {len(pending)} to recognise")
        if args.dry_run:
            continue

        done = 0
        for page in pending:
            if budget is not None and total_done >= budget:
                print(f"  reached --max-pages {budget}; stopping")
                break
            usage = gc.Usage()
            try:
                text = recognise_page(client, page, model=args.model, size=size, usage=usage)
            except Exception as exc:  # noqa: BLE001
                print(f"  [WARN] page {page.page_nr}: {type(exc).__name__}: {exc}")
                continue

            target = transcription_path(key, page.page_nr)
            if not text.strip():
                print(f"  [WARN] page {page.page_nr}: empty response, keeping any existing text")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# Seite {page.page_nr}\n\n{text}\n", encoding="utf-8")
            state.setdefault("pages", {})[str(page.page_nr)] = {
                "model": args.model,
                "prompt_version": PROMPT_VERSION,
                "size": size,
                "chars": len(text),
            }
            done += 1
            total_done += 1

        state["witness"] = key
        state["doi"] = witness.get("doi")
        state["erara_id"] = witness.get("erara_id")
        save_state(key, state)
        print(f"  {done} page(s) recognised")

    print(f"\n{total_done} page(s) recognised in total")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recognise printed Disputation editions")
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--model", default=gc.DEFAULT_MODEL)
    parser.add_argument("--size", default=None, help="IIIF size, e.g. !2000,2000")
    parser.add_argument("--witness", action="append", help="Limit to a witness key")
    parser.add_argument("--max-pages", type=int, default=200,
                        help="Stop after this many pages in one run (default: 200)")
    parser.add_argument("--refresh", action="store_true",
                        help="Also redo pages recorded under a different model or prompt version")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--sample", type=int, default=0,
                        help="Recognise N pages per witness across the model/size matrix")
    parser.add_argument("--models", default="gemini-2.5-pro,gemini-2.5-flash",
                        help="Comma-separated models for --sample")
    parser.add_argument("--sizes", default="!1500,1500;!2500,2500",
                        help="IIIF sizes for --sample, separated by ';' (they contain commas)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    witnesses = erara.load_witnesses(Path(args.config))

    # A dry run only reads manifests, so it must work without an API key -
    # that is the whole point of being able to check the plan locally.
    if args.dry_run and not args.list_models and not args.sample:
        return cmd_recognise(None, witnesses, args)

    try:
        client = gc.build_client()
    except gc.GeminiUnavailable as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if args.list_models:
        return cmd_list_models(client)
    if args.sample:
        return cmd_sample(client, witnesses, args)
    return cmd_recognise(client, witnesses, args)


if __name__ == "__main__":
    raise SystemExit(main())
