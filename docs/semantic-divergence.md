# Typisierte Divergenz statt Ähnlichkeitsprozente

`scripts/semantic_divergence.py` ersetzt die Frage „wie ähnlich?" durch die
Frage „was ist anders?": **Verschiebung** (gleiche Stelle, anderer Inhalt),
**Auslassung**, **Zusatz** — alles andere ist *gleich* (wörtlich, umformuliert
oder anders segmentiert) oder Beiwerk (Marginalien, Schadstellen, Zeilensalat
der Erkennung).

## Warum die bisherigen Zahlen irreführten

Der Satz-Aligner paart zeichenbasiert und strikt 1:1. Für 1528↔1701 blieben so
**58 % aller Satzzeilen ungepaart** und erschienen als „nur in A / nur in B" —
fabrizierte Auslassungen und Zusätze, in denen die echten untergingen. Drei
Mechanismen stellten sich als verantwortlich heraus, jeder einzeln gemessen:

1. **Orthographie:** gleicher Inhalt, andere Schreibung → Paarung scheitert.
   Behoben durch Wiederpaarung über Einbettungen (monoton, Needleman-Wunsch)
   auf normalisiertem Text.
2. **Segmentierung:** die ~20-Wort-Gruppen schneiden in jedem Zeugen anders;
   Inhalt wird von Nachbargruppen absorbiert oder liegt eine Einheit weiter.
   Auf dem Kontrollpaar waren **100 % der „Auslassungen" von dieser Art**.
   Behoben durch eine zweite, globale monotone Paarung über alle Einheiten
   hinweg plus Abdeckungstest (±4 Einheiten) für den Rest.
3. **Beiwerk:** Marginalienblöcke, `[unleserlich]`-Fragmente, Spaltensalat.
   607 „Zusätze" des Zürcher 1608ers gegen seine eigene Ausgabe bestanden
   daraus. Wird vor der Zählung ausgefiltert.

## Kalibrierung am Kontrollpaar

Die beiden 1608er sind dieselbe Ausgabe (#17): jede gemeldete Differenz
zwischen ihnen ist per Konstruktion Rauschen. Nach den drei Korrekturen:

| Kontrollpaar 1608 B↔Z | Wert |
|---|---:|
| Auslassungen | **0** |
| Zusätze | **1** |
| Verschiebungen (Schwelle 0,55) | 41 = **0,8 %** |
| Verschiebungen (Schwelle 0,45) | 14 = 0,27 % |

Das Rauschniveau der Methode ist damit beziffert, nicht geschätzt.
`--calibrate` wiederholt den Sweep nach jeder Modell- oder
Normalisierungsänderung.

## Ergebnis (Basis: Druck 23. März 1528)

| Gegenzeuge | Zeilen | gleich | Verschiebung | Auslassung | Zusatz | inhaltlich verschieden |
|---|---:|---:|---:|---:|---:|---:|
| 1608 B↔Z (Kontrolle) | 5 229 | 99,2 % | 41 | 0 | 1 | **0,8 %** |
| Druck 23. April 1528 | 5 265 | 94,7 % | 126 | 140 | 13 | **5,3 %** |
| Druck 1608 (Bern) | 5 367 | 94,5 % | 143 | 127 | 25 | **5,5 %** |
| Druck 1608 (Zürich) | 5 295 | 94,4 % | 144 | 129 | 26 | **5,6 %** |
| Druck 1701 | 6 158 | 92,5 % | 270 | 92 | 101 | **7,5 %** |

Zum Vergleich: die zeichenbasierte Ähnlichkeit derselben Paare liegt bei
42–53 % — die Methode bestätigt quantitativ, dass davon der weitaus grösste
Teil Schreibung und Segmentierung ist, nicht Inhalt.

## Stichprobenbefund

Echte Funde unter den Verschiebungen und Zusätzen (1528↔1701):

- der Nachdruck-Kolophon 1701: *„Auffs newe widerum gedruckt … Gedruckt zu
  Bern"* an der Stelle des alten Explicit
- die **umadressierte Zielgruppe** des Mandats: 1528 an Amtsträger
  (Schultheissen, Tschachtlan, Vögte…), 1701 an *„Einwohneren/Hindersässen…"*
- Titelblatt und erweitertes Vorwerk 1701 als Zusätze; 1528-04 mit hebräischer
  Holzschnitt-Beischrift (Prov. 30) als Zusatz

Bekannte Fehlerquellen, beide in Richtung *Übervorsicht* (falsche Kandidaten,
keine verpassten): stark verlesene Stellen des Basiszeugen (Gemini-Erkennung)
drücken die Kosinus-Werte; reine Modernisierung (*dhein → kein*) landet
vereinzelt knapp unter der Verschiebungsschwelle. Beides ist genau das, was
die geplante LLM-Typisierung der überlebenden Kandidaten (wenige hundert pro
Paar) adjudizieren soll.
