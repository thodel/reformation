#!/usr/bin/env python3
"""LLM adjudication of divergence candidates (stage 4 of the typed comparison).

semantic_divergence.py reduces each witness pair to a few hundred candidate
rows - semantic shifts, omissions, additions - after calibrating away
orthography, segmentation, and recognition debris on the same-edition control
pair. This script has an LLM read exactly those survivors and say what each
one IS, in the categories a historian of the Disputation cares about.

The two known error modes of the candidate stage both err toward flagging too
much: badly recognised passages depress the embedding cosine, and pure
modernisation occasionally lands under the shift threshold. The typology
therefore includes explicit "not a real difference" categories, so the LLM
can retire false candidates instead of inventing meaning for them.

Runs against GPUStack (UniBE network / VPN required). Credentials via
GPUSTACK_API_KEY; endpoint via GPUSTACK_BASE_URL. Results are written
incrementally to a JSONL work file, so an interrupted run resumes instead of
re-spending calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BASE_URL = os.environ.get("GPUSTACK_BASE_URL", "https://gpustack.unibe.ch/v1")
MODEL = os.environ.get("TYPOLOGY_MODEL", "gpt-oss-120b")

SHIFT_CATEGORIES = """\
- "erkennungsfehler": die Unterschiede stammen aus fehlerhafter Texterkennung, nicht aus dem Druck (verstümmelte Wörter, Zeichensalat); inhaltlich dieselbe Stelle
- "modernisierung": gleicher Inhalt, nur jüngere Sprache/Orthographie (z. B. dhein→kein, sye→seye)
- "umformulierung": gleicher Inhalt, erkennbar andere Formulierung
- "abschwaechung": B mildert eine Aussage von A ab (Ton, Verbindlichkeit, Urteil)
- "verschaerfung": B verschärft eine Aussage von A
- "ersetzung": ein Name, eine Bibelstelle, Zahl oder Instanz wurde ersetzt
- "zusatz_im_satz": B fügt innerhalb der Stelle inhaltlich Neues hinzu
- "auslassung_im_satz": B lässt innerhalb der Stelle Inhalt von A weg
- "inhaltlich_anders": anderweitig echte inhaltliche Differenz (kurz begründen)"""

SINGLE_CATEGORIES = """\
- "erkennungsfehler": der Text ist so verstümmelt, dass kein Inhalt beurteilbar ist
- "paratext": Titelblatt, Kolophon, Druckvermerk, Überschrift, Bogensignatur, Register - Beiwerk des Drucks, kein Text der Disputation
- "echter_inhalt": tatsächlicher Disputationstext, der im anderen Zeugen fehlt (kurz zusammenfassen, was er sagt)"""

PROMPT_SHIFT = """\
Du vergleichst zwei Fassungen einer Stelle aus den Akten der Berner \
Disputation von 1528. A ist der Druck vom 23. März 1528 (Basistext), B der \
Gegenzeuge {witness_b}. Beide Texte sind maschinell erkannt und können \
Erkennungsfehler enthalten.

A: {a}

B: {b}

Ordne den Unterschied GENAU EINER Kategorie zu:
{categories}

Antworte NUR mit einem JSON-Objekt:
{{"kategorie": "...", "begruendung": "<ein Satz>", "stelle": "<die entscheidend abweichenden Worte, oder leer>"}}"""

PROMPT_SINGLE = """\
Die folgende Stelle steht {direction} der Akten der Berner Disputation von \
1528. Der Text ist maschinell erkannt und kann Erkennungsfehler enthalten.

Text: {text}

Ordne die Stelle GENAU EINER Kategorie zu:
{categories}

Antworte NUR mit einem JSON-Objekt:
{{"kategorie": "...", "begruendung": "<ein Satz>"}}"""

WITNESS_LABELS = {
    "druck_1528__druck_1528_04": "Druck vom 23. April 1528",
    "druck_1528__druck_1608_bern": "Druck von 1608 (Berner Exemplar)",
    "druck_1528__druck_1608_zuerich": "Druck von 1608 (Zürcher Exemplar)",
    "druck_1528__druck_1701": "Druck von 1701",
}

VALID = {"shift": {"erkennungsfehler", "modernisierung", "umformulierung",
                   "abschwaechung", "verschaerfung", "ersetzung",
                   "zusatz_im_satz", "auslassung_im_satz", "inhaltlich_anders"},
         "single": {"erkennungsfehler", "paratext", "echter_inhalt"}}


def call_llm(api_key: str, prompt: str, retries: int = 3) -> dict:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/chat/completions", data=body,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                out = json.load(resp)
            text = out["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.strip("`").lstrip("json").strip()
            return json.loads(text)
        except Exception as exc:  # noqa: BLE001 - retry then surface
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {retries} attempts: {last}")


def build_prompt(pair: str, cand: dict) -> tuple[str, str]:
    if cand["kind"] == "shift":
        return "shift", PROMPT_SHIFT.format(
            witness_b=WITNESS_LABELS.get(pair, pair),
            a=cand["a"][:1500], b=cand["b"][:1500],
            categories=SHIFT_CATEGORIES)
    direction = ("nur im Basistext (Druck vom 23. März 1528), nicht im "
                 f"Gegenzeugen ({WITNESS_LABELS.get(pair, pair)})"
                 if cand["kind"] == "omission"
                 else f"nur im Gegenzeugen ({WITNESS_LABELS.get(pair, pair)}), "
                      "nicht im Basistext")
    return "single", PROMPT_SINGLE.format(
        direction=direction, text=(cand["a"] or cand["b"])[:1500],
        categories=SINGLE_CATEGORIES)


def process_pair(pair: str, cands_file: Path, out_dir: Path, api_key: str,
                 workers: int) -> dict:
    cands = json.loads(cands_file.read_text(encoding="utf-8"))
    work = out_dir / f"{pair}.typology.jsonl"
    done = {}
    if work.exists():
        for line in work.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["idx"]] = rec

    todo = [(i, c) for i, c in enumerate(cands) if i not in done]
    print(f"{pair}: {len(cands)} Kandidaten, {len(done)} bereits beurteilt, "
          f"{len(todo)} offen")

    def judge(item):
        i, cand = item
        mode, prompt = build_prompt(pair, cand)
        verdict = call_llm(api_key, prompt)
        kat = str(verdict.get("kategorie", "")).strip().lower()
        if kat not in VALID[mode]:
            kat = "unklar"
        return {"idx": i, "kind": cand["kind"], "unit": cand["unit"],
                "cosine": cand.get("cosine"),
                "a": cand["a"], "b": cand["b"], "kategorie": kat,
                "begruendung": str(verdict.get("begruendung", ""))[:400],
                "stelle": str(verdict.get("stelle", "") or "")[:200]}

    failures = 0
    with work.open("a", encoding="utf-8") as fh, \
            ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(judge, item): item[0] for item in todo}
        completed = 0
        for fut in as_completed(futures):
            try:
                rec = fut.result()
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  FAIL idx={futures[fut]}: {exc}", file=sys.stderr)
                continue
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            done[rec["idx"]] = rec
            completed += 1
            if completed % 50 == 0:
                print(f"  {pair}: {completed}/{len(todo)}")

    records = [done[i] for i in sorted(done)]
    from collections import Counter
    by_cat = Counter(r["kategorie"] for r in records)
    summary = {"pair": pair, "model": MODEL, "candidates": len(cands),
               "judged": len(records), "failed": failures,
               "by_category": dict(by_cat.most_common())}
    final = out_dir / f"{pair}.typology.json"
    final.write_text(json.dumps({"summary": summary, "items": records},
                                ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"  -> {final.name}: {dict(by_cat.most_common())}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("pairs", nargs="*")
    args = ap.parse_args()

    api_key = os.environ.get("GPUSTACK_API_KEY", "").strip()
    if not api_key:
        print("GPUSTACK_API_KEY ist nicht gesetzt", file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(args.candidates_dir.glob("*.candidates.json"))
    if args.pairs:
        files = [f for f in files
                 if f.name.replace(".candidates.json", "") in args.pairs]
    for f in files:
        pair = f.name.replace(".candidates.json", "")
        process_pair(pair, f, args.out_dir, api_key, args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
