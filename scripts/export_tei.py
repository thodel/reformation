#!/usr/bin/env python3
"""Export the edition as TEI P5 (issue #64).

Everything here is DERIVED. The sources of truth stay where they are - the
per-page markdown, the PAGE XML, the computed apparatus, the registers - and
this script reads them and writes TEI. Nothing in docs/tei/ is ever edited by
hand; a second, hand-maintained copy of the edition would be a second truth,
and the two would diverge within a month.

What is written
---------------
  docs/tei/<witness>.xml   one TEI document per witness: teiHeader with
                           provenance and rights, body with <pb/> per page and
                           <lb/> per line where PAGE XML has line breaks
  docs/tei/apparatus.xml   the computed variants as <app>/<rdg> keyed to the
                           sigla (D1-D5, H43-H47)
  docs/tei/register.xml    <listPerson> with @ref to HLS, <listBibl> for the
                           biblical references

Two things a reader of the TEI must not have to guess, so both are stated in
every teiHeader rather than only on the website: the text is machine-produced
and not editorially established, and the facsimiles belong to the holding
institutions under the Public Domain Mark.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DISPUTATION = ROOT / "data" / "disputation"
PRINTS = ROOT / "data" / "prints"
REGISTER = ROOT / "data" / "register"
APPARATUS = ROOT / "data" / "apparatus"
OUT = ROOT / "docs" / "tei"

TEI_NS = "http://www.tei-c.org/ns/1.0"
SITE = "https://thodel.github.io/reformation/"

# Sigla, provenance and imprint per witness. Mirrors WITNESS_SIGIL and
# WITNESS_METADATA in index.html; the imprints come from the e-rara manifests'
# Impressum lines - both 1528 printings are Zurich (Froschauer), both 1608
# copies are Bern (Le Preux), 1701 is Bern (Huegenet).
WITNESSES = {
    "druck_1528": {
        "sigil": "D1", "kind": "print", "base": "data/disputation/druck_1528",
        "label": "Druck, 23. März 1528", "short": "Zürich, März 1528",
        "pub_place": "Zürich", "printer": "Christoffel Froschouer", "date": "1528-03-23",
        "institution": "Universitätsbibliothek Bern", "shelfmark": "MUE AD 124 : 2",
        "doi": "10.3931/e-rara-141267", "variant": "druck-1528", "section": "drucke",
    },
    "druck_1528_04": {
        "sigil": "D2", "kind": "print", "base": "data/prints/druck_1528_04",
        "label": "Druck, 23. April 1528", "short": "Zürich, April 1528",
        "pub_place": "Zürich", "printer": "Christoffel Froschouer", "date": "1528-04-23",
        "institution": "Universitätsbibliothek Bern", "shelfmark": "MUE H X 83 : 1",
        "doi": "10.3931/e-rara-127203", "variant": "druck-1528-04", "section": "drucke",
    },
    "druck_1608_bern": {
        "sigil": "D3", "kind": "print", "base": "data/prints/druck_1608_bern",
        "label": "Druck 1608 (Bern)", "short": "Bern 1608 (Ex. UB Bern)",
        "pub_place": "Bern", "printer": "Johannes Le Preux", "date": "1608",
        "institution": "Universitätsbibliothek Bern", "shelfmark": "MUE H IV 206 a : 1",
        "doi": "10.3931/e-rara-5557", "variant": "druck-1608-bern", "section": "drucke",
    },
    "druck_1608_zuerich": {
        "sigil": "D4", "kind": "print", "base": "data/prints/druck_1608_zuerich",
        "label": "Druck 1608 (Zürich)", "short": "Bern 1608 (Ex. ZB Zürich)",
        "pub_place": "Bern", "printer": "Johannes Le Preux", "date": "1608",
        "institution": "Zentralbibliothek Zürich", "shelfmark": "7.487",
        "doi": "10.3931/e-rara-80702", "variant": "druck-1608-zuerich", "section": "drucke",
    },
    "druck_1701": {
        "sigil": "D5", "kind": "print", "base": "data/prints/druck_1701",
        "label": "Druck 1701", "short": "Bern 1701",
        "pub_place": "Bern", "printer": "Andreas Hügenet", "date": "1701",
        "institution": "Universitätsbibliothek Bern", "shelfmark": "MUE H IV 47",
        "doi": "10.3931/e-rara-47098", "variant": "druck-1701", "section": "drucke",
    },
    "a_v_1447_schlussredaktion": {
        "sigil": "H47", "kind": "ms", "base": "data/disputation/a_v_1447_schlussredaktion",
        "label": "A V 1447: Schlussredaktion", "short": "Schlussredaktion",
        "institution": "Staatsarchiv des Kantons Bern", "shelfmark": "A V 1447",
        "variant": "a-v-1447", "section": "disputation",
    },
    "a_v_1443_hertwig": {
        "sigil": "H43", "kind": "ms", "base": "data/disputation/a_v_1443_hertwig",
        "label": "A V 1443: Hertwig", "short": "Hertwig", "scribe": "Hertwig",
        "institution": "Staatsarchiv des Kantons Bern", "shelfmark": "A V 1443",
        "variant": "a-v-1443", "section": "disputation",
    },
    "a_v_1444_cyro": {
        "sigil": "H44", "kind": "ms", "base": "data/disputation/a_v_1444_cyro",
        "label": "A V 1444: Cyro", "short": "Cyro", "scribe": "Cyro",
        "institution": "Staatsarchiv des Kantons Bern", "shelfmark": "A V 1444",
        "variant": "a-v-1444", "section": "disputation",
    },
    "a_v_1445_schoeni": {
        "sigil": "H45", "kind": "ms", "base": "data/disputation/a_v_1445_schoeni",
        "label": "A V 1445: Schöni", "short": "Schöni", "scribe": "Schöni",
        "institution": "Staatsarchiv des Kantons Bern", "shelfmark": "A V 1445",
        "variant": "a-v-1445", "section": "disputation",
    },
    "a_v_1446_ruemlang": {
        "sigil": "H46", "kind": "ms", "base": "data/disputation/a_v_1446_ruemlang",
        "label": "A V 1446: Rümlang", "short": "Rümlang", "scribe": "Rümlang",
        "institution": "Staatsarchiv des Kantons Bern", "shelfmark": "A V 1446",
        "variant": "a-v-1446", "section": "disputation",
    },
}

PDM = "https://creativecommons.org/publicdomain/mark/1.0/"

# The caveat that must survive extraction into any other system.
RECOGNITION_NOTE = (
    "Der Text ist maschinell erkannt beziehungsweise maschinell transkribiert "
    "und nicht ediert. Er ist als Arbeitsgrundlage zu verstehen, nicht als "
    "kritisch hergestellter Text."
)


@lru_cache(maxsize=1)
def publication_date() -> str:
    """The date the SOURCES last changed, not today.

    A today() stamp would rewrite all twelve files on every scheduled run and
    commit ~20 MB of new blobs for a corpus that had not moved - the export
    would churn the repository exactly as the page images once did, and the
    refresh workflow's "nothing changed, commit nothing" rule would never
    trigger. Falling back to today only outside a git checkout.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", "data/"],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        stamp = out.stdout.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stamp):
            return stamp
    except Exception:  # noqa: BLE001 - not a git checkout, or no git
        pass
    return date.today().isoformat()


def esc(text) -> str:
    return escape(str(text if text is not None else ""))


def page_body(text: str) -> str:
    """Page text without the markdown heading line."""
    return re.sub(r"^#.*$", "", text, flags=re.M).strip()


def pagexml_lines(path: Path) -> list[str] | None:
    """Line texts from PAGE XML, in reading order, or None if it has none."""
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    if "<TextLine" not in raw:
        return None
    lines = []
    for block in re.findall(r"<TextLine\b.*?</TextLine>", raw, re.S):
        found = re.findall(r"<Unicode>(.*?)</Unicode>", block, re.S)
        if found:
            value = found[-1].strip()
            if value:
                lines.append(value)
    return lines or None


def iter_pages(base: Path):
    """(page number, transcription text) for pages that carry text."""
    src = base / "transcriptions"
    if not src.exists():
        return
    for path in sorted(src.glob("page_*.md"),
                       key=lambda p: int(re.search(r"\d+", p.name).group())):
        if not re.fullmatch(r"page_\d+\.md", path.name):
            continue
        nr = int(re.search(r"\d+", path.name).group())
        body = page_body(path.read_text(encoding="utf-8"))
        if body:
            yield nr, body


def header(key: str, meta: dict, page_count: int, translated: int) -> str:
    """teiHeader: who holds it, who printed it, how the text was made."""
    title = f"Handlung oder Acta gehaltner Disputation zu Bern ({meta['label']})"
    if meta["kind"] == "print":
        # idno belongs inside monogr and BEFORE imprint - after it, tei_all
        # rejects it. The holding copy is a second sourceDesc member rather
        # than a note: a printed edition and the exemplar in hand are two
        # different things, and only the exemplar carries the shelfmark.
        source = f"""      <biblStruct>
        <monogr>
          <title>{esc(title)}</title>
          <idno type="DOI">{esc(meta['doi'])}</idno>
          <imprint>
            <pubPlace>{esc(meta['pub_place'])}</pubPlace>
            <publisher>{esc(meta['printer'])}</publisher>
            <date when="{esc(meta['date'])}">{esc(meta['date'])}</date>
          </imprint>
        </monogr>
      </biblStruct>
      <msDesc>
        <msIdentifier>
          <country>Schweiz</country>
          <repository>{esc(meta['institution'])}</repository>
          <idno>{esc(meta['shelfmark'])}</idno>
        </msIdentifier>
        <msContents><summary>Benutztes Exemplar des Drucks.</summary></msContents>
      </msDesc>"""
    else:
        scribe = (f"\n          <msItem><respStmt><resp>Schreiber</resp>"
                  f"<persName>{esc(meta['scribe'])}</persName></respStmt></msItem>"
                  if meta.get("scribe") else "")
        source = f"""      <msDesc>
        <msIdentifier>
          <country>Schweiz</country>
          <settlement>Bern</settlement>
          <repository>{esc(meta['institution'])}</repository>
          <idno>{esc(meta['shelfmark'])}</idno>
        </msIdentifier>
        <msContents>
          <summary>{esc(title)}</summary>{scribe}
        </msContents>
      </msDesc>"""

    translation_note = (
        f"<p>{translated} Seiten liegen zusätzlich in moderner deutscher "
        "Übersetzung vor (maschinell erzeugt).</p>" if translated else "")

    return f"""  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>{esc(title)}</title>
        <title type="sub">Berner Reformation — Digitale Edition, Zeuge {esc(meta['sigil'])}</title>
        <respStmt>
          <resp>Digitale Edition, Datenaufbereitung und maschinelle Texterkennung</resp>
          <name>Tobias Hodel</name>
        </respStmt>
      </titleStmt>
      <publicationStmt>
        <publisher>Berner Reformation — Digitale Edition</publisher>
        <distributor><ref target="{SITE}">{SITE}</ref></distributor>
        <date when="{publication_date()}"/>
        <availability status="free">
          <licence target="{PDM}">Public Domain Mark 1.0 — Digitalisate,
            bereitgestellt durch {esc(meta['institution'])}</licence>
        </availability>
      </publicationStmt>
      <sourceDesc>
{source}
      </sourceDesc>
    </fileDesc>
    <encodingDesc>
      <projectDesc>
        <p>Abgeleiteter Export aus der digitalen Edition; die Quelldaten liegen
          im Repository thodel/reformation. Diese Datei wird erzeugt, nicht von
          Hand gepflegt.</p>
      </projectDesc>
      <editorialDecl>
        <p>{esc(RECOGNITION_NOTE)}</p>
        <p>Wiedergegeben sind {page_count} Seiten mit Text. Seiten ohne
          erkannten Text sind nicht als leere Elemente enthalten.</p>
        {translation_note}
      </editorialDecl>
    </encodingDesc>
    <profileDesc>
      <langUsage><language ident="gmh">Frühneuhochdeutsch</language></langUsage>
      <textClass>
        <keywords scheme="local">
          <term>Berner Disputation 1528</term>
          <term>Reformation</term>
        </keywords>
      </textClass>
    </profileDesc>
  </teiHeader>"""


def export_witness(key: str, meta: dict) -> tuple[Path, int]:
    base = ROOT / meta["base"]
    pages = list(iter_pages(base))
    translations = base / "translations"
    translated = len(list(translations.glob("page_*.md"))) if translations.exists() else 0

    body = []
    for nr, text in pages:
        facs = f"{SITE}#/{meta['section']}/{meta['variant']}/{nr}"
        body.append(f'      <pb n="{nr}" facs="{esc(facs)}"/>')
        lines = pagexml_lines(base / "pagexml" / f"page_{nr}.xml")
        if lines:
            # <lb/> before each line but the first: the break precedes the line
            # it starts, and a leading break would assert one before the page.
            rendered = "<lb/>".join(esc(line) for line in lines)
            body.append(f"      <p>{rendered}</p>")
        else:
            for para in [p for p in re.split(r"\n\s*\n", text) if p.strip()]:
                inner = "<lb/>".join(esc(line) for line in para.splitlines() if line.strip())
                if inner:
                    body.append(f"      <p>{inner}</p>")

    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI_NS}" xml:id="{esc(meta['sigil'])}" xml:lang="de">
{header(key, meta, len(pages), translated)}
  <text>
    <body>
      <div type="edition" n="{esc(key)}">
{chr(10).join(body)}
      </div>
    </body>
  </text>
</TEI>
"""
    out = OUT / f"{key}.xml"
    out.write_text(doc, encoding="utf-8")
    return out, len(pages)


def export_register() -> tuple[Path, int, int]:
    persons, bible = [], []

    ptsv = REGISTER / "persons.tsv"
    if ptsv.exists():
        with ptsv.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                ident = re.sub(r"[^A-Za-z0-9_.-]", "_", row.get("key") or "")
                if not ident or ident[0].isdigit():
                    ident = f"p_{ident}"
                # <person> takes no @ref in TEI; the authority link is an
                # <idno>. Also carried as @sameAs so a harvester sees it
                # without reading the children.
                hls = (f'https://hls-dhs-dss.ch/de/articles/{row["hls_id"]}/'
                       if row.get("hls_id") else "")
                same = f' sameAs="{esc(hls)}"' if hls else ""
                idno = f'<idno type="HLS">{esc(hls)}</idno>' if hls else ""
                forms = [f.strip() for f in (row.get("forms") or "").split("|") if f.strip()]
                # The first surface form is the register's display name; the
                # rest are recorded so a reader can trace why a mention was
                # clustered here.
                names = "".join(f"<persName type=\"variant\">{esc(f)}</persName>"
                                for f in forms[1:12])
                years = (f'<note type="lifespan">{esc(row["hls_years"])}</note>'
                         if row.get("hls_years") else "")
                title = (f'<note type="hls">{esc(row["hls_title"])}</note>'
                         if row.get("hls_title") else "")
                persons.append(
                    f'      <person xml:id="{esc(ident)}"{same}>\n'
                    f'        <persName type="preferred">{esc(row.get("label"))}</persName>'
                    f'{names}\n        {idno}{years}{title}'
                    f'<note type="mentions">{esc(row.get("mentions") or 0)}</note>\n'
                    f'      </person>')

    btsv = REGISTER / "bible_refs.tsv"
    if btsv.exists():
        with btsv.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                ident = re.sub(r"[^A-Za-z0-9_.-]", "_", row.get("reference") or "")
                bible.append(
                    f'      <bibl xml:id="b_{esc(ident)}" type="biblical">\n'
                    f'        <title>{esc(row.get("book"))}</title>'
                    f'<biblScope unit="chapter">{esc(row.get("chapter"))}</biblScope>\n'
                    f'        <note type="citations">{esc(row.get("count") or 0)}</note>\n'
                    f'      </bibl>')

    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI_NS}" xml:id="register" xml:lang="de">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Register der Berner Reformation — Digitale Edition</title>
        <respStmt><resp>Maschinelle Erkennung und Verknüpfung</resp>
          <name>Tobias Hodel</name></respStmt>
      </titleStmt>
      <publicationStmt>
        <publisher>Berner Reformation — Digitale Edition</publisher>
        <distributor><ref target="{SITE}">{SITE}</ref></distributor>
        <date when="{publication_date()}"/>
        <availability status="free"><licence target="{PDM}">Public Domain Mark 1.0</licence></availability>
      </publicationStmt>
      <sourceDesc><p>Abgeleitet aus data/register/ der digitalen Edition.</p></sourceDesc>
    </fileDesc>
    <encodingDesc>
      <editorialDecl>
        <p>{esc(RECOGNITION_NOTE)}</p>
        <p>Personen sind maschinell erkannt und geclustert; die Verknüpfung mit
          dem Historischen Lexikon der Schweiz ist vorgeschlagen und nicht
          bestätigt. Sie liegt nur für einen Teil der Personen vor: die übrigen
          sind verzeichnet, aber nicht identifiziert. Bibelstellen sind
          regelbasiert erkannt.</p>
      </editorialDecl>
    </encodingDesc>
  </teiHeader>
  <text>
    <body>
      <div type="register">
        <listPerson>
{chr(10).join(persons)}
        </listPerson>
        <listBibl>
{chr(10).join(bible)}
        </listBibl>
      </div>
    </body>
  </text>
</TEI>
"""
    out = OUT / "register.xml"
    out.write_text(doc, encoding="utf-8")
    return out, len(persons), len(bible)


def export_apparatus(limit_pages: int | None = None) -> tuple[Path, int]:
    """The computed variants as <app>/<rdg>, keyed to the sigla."""
    entries = []
    files = sorted(APPARATUS.glob("page_*.json"),
                   key=lambda p: int(re.search(r"\d+", p.name).group()))
    if limit_pages:
        files = files[:limit_pages]
    count = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        page = data.get("page")
        for wit_key, wit in (data.get("witnesses") or {}).items():
            sigil = WITNESSES.get(wit_key, {}).get("sigil", wit_key)
            for item in (wit.get("substantive") or [])[:40]:
                base_text = (item.get("base") or "").strip()
                other = (item.get("witness") or item.get("other") or "").strip()
                if not base_text and not other:
                    continue
                readings = [
                    f'          <lem wit="#D1">{esc(base_text[:600])}</lem>'
                    if base_text else '          <lem wit="#D1"/>',
                    f'          <rdg wit="#{esc(sigil)}">{esc(other[:600])}</rdg>'
                    if other else f'          <rdg wit="#{esc(sigil)}"/>',
                ]
                entries.append(
                    f'        <app type="{esc(item.get("op") or "variant")}" '
                    f'n="D1-{esc(page)}">\n' + "\n".join(readings) + "\n        </app>")
                count += 1

    wit_list = "\n".join(
        f'        <witness xml:id="{esc(m["sigil"])}">{esc(m["label"])} — '
        f'{esc(m["institution"])}, {esc(m["shelfmark"])}</witness>'
        for m in WITNESSES.values())

    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI_NS}" xml:id="apparatus" xml:lang="de">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Variantenapparat der Berner Disputation 1528</title>
        <respStmt><resp>Maschineller Vergleich</resp><name>Tobias Hodel</name></respStmt>
      </titleStmt>
      <publicationStmt>
        <publisher>Berner Reformation — Digitale Edition</publisher>
        <distributor><ref target="{SITE}">{SITE}</ref></distributor>
        <date when="{publication_date()}"/>
        <availability status="free"><licence target="{PDM}">Public Domain Mark 1.0</licence></availability>
      </publicationStmt>
      <sourceDesc>
        <listWit>
{wit_list}
        </listWit>
      </sourceDesc>
    </fileDesc>
    <encodingDesc>
      <editorialDecl>
        <p>{esc(RECOGNITION_NOTE)}</p>
        <p>Der Apparat ist maschinell berechnet: Lesarten stammen aus dem
          Zeichen- und Satzvergleich der erkannten Texte, nicht aus einer
          Kollation von Hand. Ein Teil der Differenzen geht auf Erkennungs-
          fehler zurück; die typisierte Auswertung auf der Website unterscheidet
          diese von inhaltlichen Abweichungen.</p>
      </editorialDecl>
    </encodingDesc>
  </teiHeader>
  <text>
    <body>
      <div type="apparatus">
{chr(10).join(entries)}
      </div>
    </body>
  </text>
</TEI>
"""
    out = OUT / "apparatus.xml"
    out.write_text(doc, encoding="utf-8")
    return out, count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--witnesses", nargs="*", default=None)
    ap.add_argument("--apparatus-pages", type=int, default=None,
                    help="limit the apparatus to the first N pages (for tests)")
    ap.add_argument("--skip-apparatus", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    keys = args.witnesses or list(WITNESSES)
    total = 0
    for key in keys:
        meta = WITNESSES.get(key)
        if not meta:
            print(f"  unbekannter Zeuge: {key}", file=sys.stderr)
            continue
        path, pages = export_witness(key, meta)
        total += pages
        print(f"  {path.relative_to(ROOT)}: {pages} Seiten mit Text")

    rpath, npersons, nbible = export_register()
    print(f"  {rpath.relative_to(ROOT)}: {npersons} Personen, {nbible} Bibelstellen")

    if not args.skip_apparatus:
        apath, napp = export_apparatus(args.apparatus_pages)
        print(f"  {apath.relative_to(ROOT)}: {napp} Lesarten")

    print(f"\nGesamt: {total} Seiten in {len(keys)} Zeugendokumenten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
