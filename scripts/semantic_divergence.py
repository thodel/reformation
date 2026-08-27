#!/usr/bin/env python3
"""Typed divergence between witnesses: shifts, additions, omissions.

Why the similarity numbers mislead
----------------------------------
The sentence aligner pairs on character similarity, strictly 1:1. Two
sentences saying the same thing in different orthography fail to pair, and
both get reported as "only in A" / "only in B" - for druck_1528 against
druck_1701 that is 58% of all sentence rows. Real additions and omissions
drown in manufactured ones, and every small spelling difference in a matched
pair drags the similarity score down as if it were divergence.

What this script does instead
-----------------------------
1. Re-pair. The character-matched pairs stay as anchors (they are monotone by
   construction). Between consecutive anchors, the leftover only_a / only_b
   runs are aligned monotonically on embedding cosine (Needleman-Wunsch with
   a gap penalty), on ORTHOGRAPHICALLY NORMALIZED text. A pair beats two gaps
   exactly when its cosine exceeds the pairing threshold.
2. Classify by meaning. For every pair - anchored or rescued - the divergence
   signal is the embedding cosine alone. Character similarity is demoted to a
   display detail (verbatim vs reworded). Below the shift threshold a pair is
   a semantic-shift candidate; unpaired sentences are omission (only_a,
   measured from the base witness) or addition (only_b) candidates.
3. Calibrate on the control. druck_1608_bern and druck_1608_zuerich are the
   same edition (#17), so every shift or addition flagged between them is
   noise by construction. --calibrate sweeps both thresholds on that pair and
   reports the noise floor each choice buys.

The thresholds below were chosen from that sweep; rerun --calibrate after any
model or normalization change.
"""

from __future__ import annotations

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_orthography import normalize_text  # noqa: E402
from embed_sentences import MODEL_NAME, load_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COMPARISON = ROOT / "data" / "comparison"

CONTROL_PAIR = "druck_1608_bern__druck_1608_zuerich"

# A rescued pair must reach this cosine (normalized text) to count as a pair;
# the NW gap penalty is half of it, so pairing beats gapping exactly here.
PAIR_FLOOR = 0.70
# Below this cosine a pair is a semantic-shift candidate. Set from the control
# pair: same-edition pairs essentially never score this low.
SHIFT_CEILING = 0.55
# Above this character similarity a same-content pair is "verbatim" rather
# than "reworded". Display detail only - it never makes divergence.
VERBATIM_FLOOR = 0.80
# An unpaired row whose characters are this well covered by the other side's
# full unit text is segmentation spill, not an omission: the ~20-word grouping
# fell differently and a neighbouring matched group absorbed the content. On
# the control pair, 100% of clean unpaired rows are of this kind. Measured
# cross-edition: content known present has p10 coverage 0.84, content known
# absent has p90 coverage 0.73 - the threshold sits between them.
SPILL_COVERAGE = 0.78


def char_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def coverage(needle: str, haystack: str) -> float:
    """Fraction of needle's characters found in order inside haystack."""
    sm = SequenceMatcher(None, needle, haystack, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / max(len(needle), 1)


def is_noise(text: str) -> bool:
    """Recognition and layout debris, not textual content.

    Learned from the control pair, where every unmatched row is noise by
    construction: marginalia blocks, damage fragments in editorial brackets,
    and column salad - a misread layout emitting one or two words per line.
    Counting these as additions is how the Zurich copy came to show 607
    'additions' against its own edition.
    """
    if "## Marginalien" in text or "[unleserlich]" in text or "[..." in text:
        return True
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 4:
        words_per_line = sum(len(ln.split()) for ln in lines) / len(lines)
        if words_per_line < 3.0:
            return True
    return False


def unit_blocks(pairs):
    """Anchored pairs, plus the only_a/only_b runs between consecutive anchors.

    The pairs list is in document order, so everything between two matches is
    co-located material the character matcher could not pair.
    """
    anchors = []
    blocks = []
    run_a, run_b = [], []
    for p in pairs:
        if p.get("op") == "match" and p.get("a") and p.get("b"):
            if run_a or run_b:
                blocks.append((run_a, run_b))
                run_a, run_b = [], []
            anchors.append(p)
        elif p.get("op") == "only_a" and p.get("a"):
            run_a.append(p)
        elif p.get("op") == "only_b" and p.get("b"):
            run_b.append(p)
    if run_a or run_b:
        blocks.append((run_a, run_b))
    return anchors, blocks


def nw_align(sim, gap):
    """Monotone alignment maximizing cosine sum with per-gap penalty.

    Returns index pairs (i, j). With gap = PAIR_FLOOR / 2, a pair is chosen
    over gapping both sides exactly when its cosine exceeds PAIR_FLOOR.
    """
    n, m = len(sim), len(sim[0]) if sim else 0
    H = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        H[i][0] = i * gap
    for j in range(1, m + 1):
        H[0][j] = j * gap
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            H[i][j] = max(
                H[i - 1][j - 1] + sim[i - 1][j - 1],
                H[i - 1][j] + gap,
                H[i][j - 1] + gap,
            )
    out = []
    i, j = n, m
    while i > 0 and j > 0:
        if H[i][j] == H[i - 1][j - 1] + sim[i - 1][j - 1]:
            out.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif H[i][j] == H[i - 1][j] + gap:
            i -= 1
        else:
            j -= 1
    return out[::-1]


# Embeddings do not depend on the thresholds, so the calibration sweep reuses
# them instead of re-encoding eleven thousand sentences per grid point.
_VEC_CACHE: dict[str, object] = {}


def analyse_pair(pair_dir: Path, model, pair_floor: float, shift_ceiling: float):
    """Count typed differences for one witness pair."""
    import numpy as np

    units = sorted(pair_dir.glob("unit_*.json"),
                   key=lambda p: int(p.stem.split("_")[1]))
    texts = []
    parsed = []
    unit_nrs = []
    for uf in units:
        d = json.loads(uf.read_text(encoding="utf-8"))
        unit_nrs.append(d.get("unit"))
        anchors, blocks = unit_blocks(d.get("sentences", {}).get("pairs", []))
        # Unmatched rows are re-paired across the whole unit, not per
        # inter-anchor gap: on the control pair only 13 of 692 gaps had rows
        # on both sides - the leftovers of A and B sit between different
        # anchors, and gap-local alignment never sees them. Unit-level
        # alignment stays monotone, which is the constraint that matters.
        run_a = [p for ra, _ in blocks for p in ra]
        run_b = [p for _, rb in blocks for p in rb]
        pairs = d.get("sentences", {}).get("pairs", [])
        a_full = normalize_text(" ".join(p["a"] for p in pairs if p.get("a")))
        b_full = normalize_text(" ".join(p["b"] for p in pairs if p.get("b")))
        parsed.append((anchors, run_a, run_b, a_full, b_full))
        for p in anchors:
            texts.append(normalize_text(p["a"]))
            texts.append(normalize_text(p["b"]))
        for p in run_a:
            texts.append(normalize_text(p["a"]))
        for p in run_b:
            texts.append(normalize_text(p["b"]))

    if pair_dir.name in _VEC_CACHE:
        vectors = _VEC_CACHE[pair_dir.name]
    else:
        vectors = model.encode(texts, batch_size=64, show_progress_bar=False,
                               normalize_embeddings=True)
        _VEC_CACHE[pair_dir.name] = vectors

    counts = {"verbatim": 0, "reworded": 0, "shift": 0,
              "omission": 0, "addition": 0, "rescued": 0, "noise": 0,
              "spill": 0}
    examples = {"shift": [], "omission": [], "addition": []}
    candidates = []  # every shift/omission/addition row, in full, for the
                     # LLM typology stage

    def note(kind, **fields):
        if kind in examples and len(examples[kind]) < 12:
            examples[kind].append(fields)

    cursor = 0
    # Rows still unpaired after the per-unit pass, in document order. The
    # segment boundaries fall differently between editions, so content
    # regularly sits one or two units away from its counterpart - the sampled
    # "omissions" of the first version had 0.91-1.00 coverage in the OTHER
    # witness taken as a whole. A second, global monotone pass catches these;
    # what it cannot pair is checked against a window of neighbouring units
    # before it may count as an omission or addition.
    leftover_a, leftover_b = [], []  # (unit_idx, row, norm_text, vector)
    unit_a_texts, unit_b_texts = [], []
    for ui, (anchors, run_a, run_b, a_full, b_full) in enumerate(parsed):
        for p in anchors:
            va, vb = vectors[cursor], vectors[cursor + 1]
            ta, tb = texts[cursor], texts[cursor + 1]
            cursor += 2
            # A matched pair where either side is debris cannot witness a
            # semantic shift - the model is comparing prose against salad.
            if is_noise(p["a"]) or is_noise(p["b"]):
                counts["noise"] += 1
                continue
            cos = float(np.dot(va, vb))
            kind = classify_pair_at(cos, char_similarity(ta, tb), shift_ceiling)
            counts[kind] += 1
            if kind == "shift":
                note("shift", cosine=round(cos, 3), a=p["a"][:160], b=p["b"][:160])
                candidates.append({"kind": "shift", "unit": unit_nrs[ui],
                                   "cosine": round(cos, 3),
                                   "a": p["a"], "b": p["b"]})

        na, nb = len(run_a), len(run_b)
        va = vectors[cursor:cursor + na]
        ta = texts[cursor:cursor + na]
        cursor += na
        vb = vectors[cursor:cursor + nb]
        tb = texts[cursor:cursor + nb]
        cursor += nb

        # Debris is taken out before alignment so it cannot occupy a slot a
        # real sentence should get.
        clean_a = [i for i, p in enumerate(run_a) if not is_noise(p["a"])]
        clean_b = [j for j, p in enumerate(run_b) if not is_noise(p["b"])]
        counts["noise"] += (na - len(clean_a)) + (nb - len(clean_b))

        paired_a, paired_b = set(), set()
        if clean_a and clean_b:
            sim = [[float(np.dot(va[i], vb[j])) for j in clean_b] for i in clean_a]
            for ci, cj in nw_align(sim, pair_floor / 2):
                cos = sim[ci][cj]
                if cos < pair_floor:
                    continue
                i, j = clean_a[ci], clean_b[cj]
                paired_a.add(i)
                paired_b.add(j)
                counts["rescued"] += 1
                kind = classify_pair_at(cos, char_similarity(ta[i], tb[j]),
                                        shift_ceiling)
                counts[kind] += 1
                if kind == "shift":
                    note("shift", cosine=round(cos, 3),
                         a=run_a[i]["a"][:160], b=run_b[j]["b"][:160])
                    candidates.append({"kind": "shift", "unit": unit_nrs[ui],
                                       "cosine": round(cos, 3),
                                       "a": run_a[i]["a"], "b": run_b[j]["b"]})
        unit_a_texts.append(a_full)
        unit_b_texts.append(b_full)
        for i in clean_a:
            if i not in paired_a:
                leftover_a.append((ui, run_a[i], ta[i], va[i]))
        for j in clean_b:
            if j not in paired_b:
                leftover_b.append((ui, run_b[j], tb[j], vb[j]))

    # Second pass: global monotone re-pairing of everything still unpaired.
    g_paired_a, g_paired_b = set(), set()
    if leftover_a and leftover_b:
        va = np.stack([x[3] for x in leftover_a])
        vb = np.stack([x[3] for x in leftover_b])
        sim = np.matmul(va, np.transpose(vb)).tolist()
        for i, j in nw_align(sim, pair_floor / 2):
            cos = sim[i][j]
            if cos < pair_floor:
                continue
            g_paired_a.add(i)
            g_paired_b.add(j)
            counts["rescued"] += 1
            kind = classify_pair_at(cos, char_similarity(leftover_a[i][2],
                                                         leftover_b[j][2]),
                                    shift_ceiling)
            counts[kind] += 1
            if kind == "shift":
                note("shift", cosine=round(cos, 3),
                     a=leftover_a[i][1]["a"][:160],
                     b=leftover_b[j][1]["b"][:160])
                candidates.append({"kind": "shift",
                                   "unit": unit_nrs[leftover_a[i][0]],
                                   "cosine": round(cos, 3),
                                   "a": leftover_a[i][1]["a"],
                                   "b": leftover_b[j][1]["b"]})

    # Last resort: character containment in the other witness's neighbouring
    # units. Only what fails this too is an omission or addition.
    def window(units_texts, ui):
        lo, hi = max(0, ui - 4), min(len(units_texts), ui + 5)
        return " ".join(units_texts[lo:hi])

    for i, (ui, row, tnorm, _v) in enumerate(leftover_a):
        if i in g_paired_a:
            continue
        if coverage(tnorm, window(unit_b_texts, ui)) >= SPILL_COVERAGE:
            counts["spill"] += 1
        else:
            counts["omission"] += 1
            note("omission", a=row["a"][:160])
            candidates.append({"kind": "omission", "unit": unit_nrs[ui],
                               "a": row["a"], "b": None})
    for j, (ui, row, tnorm, _v) in enumerate(leftover_b):
        if j in g_paired_b:
            continue
        if coverage(tnorm, window(unit_a_texts, ui)) >= SPILL_COVERAGE:
            counts["spill"] += 1
        else:
            counts["addition"] += 1
            note("addition", b=row["b"][:160])
            candidates.append({"kind": "addition", "unit": unit_nrs[ui],
                               "a": None, "b": row["b"]})

    total_rows = (counts["verbatim"] + counts["reworded"] + counts["shift"]
                  + counts["omission"] + counts["addition"] + counts["spill"])
    return {"pair": pair_dir.name, "units": len(units), "rows": total_rows,
            "counts": counts, "examples": examples, "candidates": candidates}


def classify_pair_at(cosine: float, char: float, shift_ceiling: float) -> str:
    if cosine < shift_ceiling:
        return "shift"
    return "verbatim" if char >= VERBATIM_FLOOR else "reworded"


def print_report(r):
    c = r["counts"]
    content = c["shift"] + c["omission"] + c["addition"]
    same = c["verbatim"] + c["reworded"] + c["spill"]
    print(f"\n{r['pair']}  ({r['units']} Einheiten, {r['rows']} Satzzeilen)")
    print(f"  gleich        : {same:5d}  (woertlich {c['verbatim']}, umformuliert {c['reworded']}, Segmentierungsrest {c['spill']})")
    print(f"    davon durch Einbettung gerettet: {c['rescued']}")
    print(f"  Verschiebung  : {c['shift']:5d}")
    print(f"  Auslassung    : {c['omission']:5d}  (in Basis, fehlt im Vergleichszeugen)")
    print(f"  Zusatz        : {c['addition']:5d}  (nur im Vergleichszeugen)")
    print(f"  Beiwerk/Rauschen ausgefiltert: {c['noise']}")
    pct = 100.0 * content / r["rows"] if r["rows"] else 0.0
    print(f"  inhaltlich verschieden: {content} von {r['rows']} = {pct:.1f}%")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*", help="pair directory names")
    ap.add_argument("--calibrate", action="store_true",
                    help="sweep thresholds on the control pair")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--candidates-dir", type=Path, default=None,
                    help="write <pair>.candidates.json with every flagged row")
    args = ap.parse_args()

    model = load_model()

    if args.calibrate:
        pair_dir = COMPARISON / CONTROL_PAIR
        print(f"Kalibrierung auf {CONTROL_PAIR} (gleiche Ausgabe: alles ist Rauschen)")
        print(f"{'pair_floor':>10} {'shift_ceil':>10} {'shift%':>8} {'omit%':>8} {'add%':>8} {'spill':>6} {'rescued':>8} {'noise':>7}")
        for pf in (0.60, 0.65, 0.70, 0.75):
            for sc in (0.45, 0.50, 0.55, 0.60):
                r = analyse_pair(pair_dir, model, pf, sc)
                c, rows = r["counts"], r["rows"]
                print(f"{pf:>10.2f} {sc:>10.2f} "
                      f"{100*c['shift']/rows:>7.2f}% {100*c['omission']/rows:>7.2f}% "
                      f"{100*c['addition']/rows:>7.2f}% {c['spill']:>6d} {c['rescued']:>8d} {c['noise']:>7d}")
        return 0

    names = args.pairs or [p.name for p in sorted(COMPARISON.iterdir())
                           if p.is_dir() and "__" in p.name]
    results = []
    for name in names:
        r = analyse_pair(COMPARISON / name, model, PAIR_FLOOR, SHIFT_CEILING)
        if args.candidates_dir:
            args.candidates_dir.mkdir(parents=True, exist_ok=True)
            (args.candidates_dir / f"{name}.candidates.json").write_text(
                json.dumps(r["candidates"], ensure_ascii=False, indent=1),
                encoding="utf-8")
        r.pop("candidates")
        results.append(r)
        print_report(r)
    if args.json_out:
        args.json_out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
