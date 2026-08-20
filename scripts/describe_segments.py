#!/usr/bin/env python3
"""Give each proposed segment a title and a three-sentence summary.

Fills the title and summary columns of the segment table. Rows that already
carry a title are left alone, so a hand-written one is never overwritten by a
later run - the table is meant to be corrected by hand, and this must not undo
that work.

The text handed to the model is the recognised Early New High German, which
carries recognition errors. The summaries are therefore an orientation aid, not
an edition: they say roughly what a stretch of pages is about, and should be
read as such.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gemini_client as gc  # noqa: E402
from compare_witnesses import page_texts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = ROOT / "data" / "segments"
MAX_CHARS = 12000

SYSTEM = """\
Du erschliesst einen frühneuhochdeutschen Druck von 1528 über die Berner
Disputation für ein wissenschaftliches Publikum.

Zu einem Abschnitt lieferst du:
- einen knappen Titel (höchstens 60 Zeichen), der benennt, worum es geht
- genau drei Sätze modernes Deutsch, die den Inhalt zusammenfassen

Regeln:
- Nenne die Sprechenden, wenn sie erkennbar sind (Zwingli, Ökolampad, Haller,
  Bucer, der Pfarrer von Appenzell und andere).
- Der Text stammt aus automatischer Texterkennung und enthält Fehler. Rate
  nicht: ist eine Stelle unklar, halte die Zusammenfassung allgemeiner.
- Keine Einleitung, keine Erklärung, keine Anführungszeichen um den Titel.

Antworte ausschliesslich als JSON:
{"titel": "...", "zusammenfassung": "Satz eins. Satz zwei. Satz drei."}
"""


def load_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    return rows[0], rows[1:]


def save_rows(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        writer.writerows(rows)


def describe(client, model: str, text: str, usage: gc.Usage) -> tuple[str, str]:
    reply = gc.generate(
        client, model=model,
        parts=[gc.text_part(f"Abschnitt:\n\n{text[:MAX_CHARS]}")],
        system_instruction=SYSTEM, usage=usage, temperature=0.2,
    )
    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        start, end = reply.find("{"), reply.rfind("}")
        if start == -1 or end == -1:
            return "", ""
        try:
            data = json.loads(reply[start:end + 1])
        except json.JSONDecodeError:
            return "", ""
    title = " ".join(str(data.get("titel", "")).split())
    summary = " ".join(str(data.get("zusammenfassung", "")).split())
    return title, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Title and summarise segments")
    parser.add_argument("--witness", default="druck_1528")
    parser.add_argument("--model", default=gc.DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true",
                        help="Also redo rows that already have a title (discards hand edits)")
    args = parser.parse_args()

    table = SEGMENTS / f"{args.witness}_segments.tsv"
    if not table.exists():
        print(f"[ERROR] no segment table: {table}", file=sys.stderr)
        return 2

    header, rows = load_rows(table)
    idx = {name: i for i, name in enumerate(header)}
    texts = page_texts(args.witness)

    pending = [r for r in rows if args.overwrite or not r[idx["title"]].strip()]
    if not pending:
        print("every segment already has a title; nothing to do.")
        return 0
    if args.limit:
        pending = pending[: args.limit]

    try:
        client = gc.build_client()
    except gc.GeminiUnavailable as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    usage = gc.Usage()
    done = 0
    for row in pending:
        first, last = int(row[idx["first_page"]]), int(row[idx["last_page"]])
        body = "\n\n".join(texts[p] for p in range(first, last + 1) if p in texts)
        if not body.strip():
            continue
        try:
            title, summary = describe(client, args.model, body, usage)
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] segment {row[idx['segment']]}: {type(exc).__name__}: {exc}")
            continue
        if not title:
            print(f"  [WARN] segment {row[idx['segment']]}: no usable reply, left blank")
            continue
        row[idx["title"]] = title
        row[idx["summary"]] = summary
        done += 1
        print(f"  {row[idx['segment']]:>3}  S.{first}-{last}  {title}")
        save_rows(table, header, rows)   # written as we go, so a failure keeps progress

    print(f"\n{done} segment(s) described")
    print(f"tokens: in {usage.prompt_tokens}, out {usage.output_tokens}, "
          f"thinking {usage.thought_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
