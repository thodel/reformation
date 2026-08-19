# Drucke vergleichen — Plan

Synoptischer Vergleich der gedruckten Fassungen der Berner Disputation (1528–1701).

## Korpus

| Schlüssel | Ausgabe | DOI | e-rara ID | Seiten | Stand |
|---|---|---|---|---|---|
| `druck_1528_03` | Druck, 23. März 1528 (UB Bern) | [10.3931/e-rara-141267](https://doi.org/10.3931/e-rara-141267) | 30973277 | 496 | **liegt vor** als `druck_1528` |
| `druck_1528_04` | Druck, 23. April 1528 (UB Bern) | [10.3931/e-rara-127203](https://doi.org/10.3931/e-rara-127203) | 29725665 | 570 | zu beschaffen |
| `druck_1608_bern` | Druck 1608 (UB Bern) | [10.3931/e-rara-5557](https://doi.org/10.3931/e-rara-5557) | 1703316 | 568 | zu beschaffen |
| `druck_1608_zuerich` | Druck 1608 (ZB Zürich) | [10.3931/e-rara-80702](https://doi.org/10.3931/e-rara-80702) | 22785862 | 836 | zu beschaffen |
| `druck_1701` | Druck 1701 (UB Bern) | [10.3931/e-rara-47098](https://doi.org/10.3931/e-rara-47098) | 13106447 | 672 | zu beschaffen |

Der März-Druck 1528 ist bereits vollständig transkribiert und übersetzt; er ist im
Repository als `data/disputation/druck_1528` abgelegt (vgl.
`docs/alignment/druck_1528_page-alignment.md`, dasselbe IIIF-Manifest 30973277).
Neu zu erkennen sind daher **2 646 Seiten**.

Die beiden 1608er Exemplare unterscheiden sich um 268 Seiten. Ob es sich um
dieselbe Ausgabe in zwei Exemplaren oder um zwei Drucke handelt, ist eine
fachliche Frage und muss vor der Kollation geklärt werden.

## Phasen

### 1 — Beschaffung
DOI auflösen, IIIF-Manifest lesen (`https://www.e-rara.ch/i3f/v20/<id>/manifest`),
Seitenbilder herunterladen nach `data/prints/<key>/images/page_N.jpg`.
Jede Ausgabe erhält `provenance.json` mit DOI, e-rara-ID, besitzender Bibliothek,
Manifest-URL und Lizenzangabe. Der Lauf ist wiederaufnehmbar und ratenbegrenzt.

### 2 — Texterkennung (Gemini)
Seitenbild an die Gemini-API, Prompt auf frühneuhochdeutschen Fraktursatz
abgestimmt. Ausgabe nach `data/prints/<key>/transcriptions/page_N.md`.
Inkrementell über eine Zustandsdatei nach dem Muster von `sync_state.json`:
erkannt wird nur, was fehlt oder dessen Quellbild sich geändert hat. Obergrenze
pro Lauf, damit ein Fehler keine Rechnung über tausende Aufrufe erzeugt.

### 3 — Normalisierung
Ohne Normalisierung besteht jeder Vergleich aus orthographischem Rauschen.
Zu behandeln: u/v, i/j, langes ſ, übergeschriebene Vokale (uͦ, aͤ), Abbreviaturen,
Trennungen am Zeilenende, Interpunktion. Die Normalisierung ist eine eigene
Schicht; Original und normalisierte Form bleiben beide erhalten.

### 4 — Alignment
Zwei Granularitäten, wie gewünscht auf Seitenebene verankert (keine Zeilenbezüge):

- **grob** — Absatz- bzw. Segmentebene. Ankerpunkte sind die nummerierten
  Schlussreden und Abschnittsüberschriften, die über alle Ausgaben stabil sind;
  dazwischen Fuzzy-Matching.
- **fein** — Wort- und Zeichenebene innerhalb einer ausgerichteten Einheit.

Ergebnis: `data/prints/alignment.json` — Einheiten mit `{witness: [Seiten]}`.

### 5 — Vergleichsdaten
Vorberechnete Diffs als JSON, damit die statische Seite ohne Server auskommt.
Pro Einheit: Übereinstimmung, Zusätze, Auslassungen, Ersetzungen je Zeugenpaar.

### 6 — Viewer: Tab „Vergleich“
Synoptische Spalten (2–4 Zeugen nebeneinander), scrollsynchron, Umschalter
zwischen Absatz- und Wortansicht, Variantenapparat je Einheit, Deep Links
`#/vergleich/<einheit>`.

## Visualisierungen

1. **Synoptische Spalten** — die eigentliche Leseansicht, Einfügung/Auslassung/
   Ersetzung farbcodiert. Kern der Funktion.
2. **Divergenz-Heatmap** — Matrix Zeuge × Abschnitt, eingefärbt nach Dichte der
   Abweichungen. Zeigt auf einen Blick, wo 1701 den Text von 1528 umschreibt.
3. **Ähnlichkeitsmatrix** — 5 × 5 Wärmekarte der Gesamtdistanz; gruppiert die
   Zeugen und stützt eine Stemma-Diskussion.
4. **Divergenz-Verlaufsband** — schmaler Streifen längs des Textes, der zeigt,
   wo die Zeugen zusammengehen und wo sie auseinanderlaufen.
5. **Alignment-Bogendiagramm** — Seitenkorrespondenz zweier Zeugen, macht
   Umstellungen und Lücken sichtbar. Aufwendig, daher später.
6. **Variantentypologie** — Aufschlüsselung orthographisch vs. substanziell;
   trennt Druckvarianten von inhaltlichen Eingriffen.

Empfehlung: zuerst 1, 2 und 3; 4 als kleine Ergänzung; 5 und 6 später.
