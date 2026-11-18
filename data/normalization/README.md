# Normalisierungs-Entscheidungen

Menschenentscheidungen, gegen die die Skripte nie entscheiden (#46).
Diese Verzeichnis ist der Ort, an dem die Skripte vorschlagen und Menschen
entscheiden: die Tabellen werden im Spreadsheet oder im Editor gepflegt und
mit der Recherche versioniert — ein PR gegen `decisions.tsv` ist eine
Normalisierungs-Entscheidung.

## decisions.tsv

| Spalte | Bedeutung |
|---|---|
| `kind` | `orthography` \| `person` \| `bible` |
| `from` | die beobachtete Form (im normalisierten, kleingeschriebenen Vergleichsformat abgeglichen — Gross-/Kleinschreibung und Schreibvarianten sind egal) |
| `to` | die entschiedene Form; **leer** = «keine Zusammenführung» bzw. «passt nicht» |
| `scope` | `global` (Standard) oder ein Zeugenschlüssel wie `a_v_1443_hertwig`; zeugenspezifische Einträge schlagen globale |
| `decided_by` | wer entschieden hat (Name oder `dh-bot`) |
| `decided_on` | Datum, JJJJ-MM-TT |
| `note` | Begründung in einem Satz |

Ein unbekanntes `kind` oder ein leeres `from` ist ein Fehler: die Skripte
versagen laut, statt die Tabelle still zu ignorieren.
Prüfen mit `python3 scripts/normalization_decisions.py --check`.

**Anwendung nach Stand dieses PR:** `bible` ist voll verdrahtet
(`recognize_bible_refs.py`: Einträge schlagen den Fuzzy-Schwellwert, ein
leeres `to` verweigert das Match). `person` (Register) und `orthography`
folgen als Teil 2 von #46 — Zeilen dieser Art werden geladen und validiert,
aber noch nicht angewendet.

## open.tsv

Wird von den Skripten bei jedem Lauf geschrieben: die noch **offenen** Fälle,
nach Häufigkeit sortiert — die Arbeitsliste, die ein Mensch von oben
durcharbeitet. Ein Lauf ersetzt nur die Zeilen seiner eigenen Art und
liest Fälle, die in `decisions.tsv` stehen, nicht mehr. Pro Art landen
höchstens die 50 häufigsten Fälle in der Liste — eine Display-Grenze gegen
Rauschen, keine Entscheidung: nichts wird dadurch zusammengeführt oder
weggelassen.
