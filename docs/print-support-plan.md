# Plan: Die Drucke als Stütze der Handschriften-Transkription

*Geschrieben am 30. August 2026. Teil der Arbeit an #70 (Handschriften sind
erst zu ~6 % transkribiert).*

## Stand der Umsetzung (1. September 2026)

Alle Phasen sind abgearbeitet oder bewusst gestrichen. Der Plan bleibt als
Begründung stehen; was daraus wurde, steht hier.

| Phase | Ausgang |
|---|---|
| P0 Thesenblätter | erledigt (#76) — S. 834–838 transkribiert und übersetzt; Nebenbefund: dieselbe zeitgenössische Handkorrektur in These VI auf beiden Blättern |
| P1 Ankerkarte | erledigt (#77, #78) — `scripts/build_print_anchors.py`, medianer Vorhersagefehler 15 Druckseiten bei zurückgehaltenen Ankern |
| P2 Stützpakete | erledigt (#79) — `scripts/build_support_bundles.py` |
| P3 Pilotmessung | **nicht bestanden** (#80) — Median 0,60 gegen die vorab festgelegte Schwelle 0,85; Bericht: [p3-pilotmessung.md](p3-pilotmessung.md) |
| P4 Lesehilfe | erledigt (#81) — unerschlossene Seiten zeigen Landmarken und Druckpassage |
| P5 Batch-Lesung | **entfällt** — genau die Folge, die P3 vorab an die Schwelle geknüpft hatte |
| P6 Text2Image | Repo-Seite erledigt (#82) — `scripts/build_t2i_packages.py`; Review und Modelltraining laufen in Transkribus |

**Was die Messung gelehrt hat.** Der Fünf-Seiten-Test (0,88–0,96) mass
Parallelabschriften derselben Rede; der Druck überliefert denselben Inhalt
*redigiert*. Er verortet also, was auf einer Handschriftenseite steht, und
diktiert nicht, wie es dort steht. Für die Publikation war das ein Nein, für
die Lesehilfe und für Text2Image ist es die richtige Erwartungshaltung.

**Was daneben entstand:** der Erschliessungsgrad steht jetzt in der
Zeugenübersicht (#83, Weg 3 aus #70), und die erfundenen Kopfzeilen des
Erkennungsmodells sind aus dem Drucktext entfernt (#84) — gefunden beim Bau
der Text2Image-Pakete.

## Die Beobachtung, aus der dieser Plan entsteht

Drei Befunde aus den letzten Arbeitstagen, alle gemessen, nicht vermutet:

1. **Allgemeine VLMs scheitern an der Kurrentschrift.** qwen3-vl-30b erreicht
   0,03–0,74 Zeichenähnlichkeit gegen den Bestand und halluziniert plausible
   deutsche Wortformen auf die Seite („Sant Gallen" → „Bern Ballen"). Weg 1
   von #70 ist damit zu — mit den verfügbaren Modellen.
2. **Lesen mit Parallelzeugen funktioniert.** Beim Fünf-Seiten-Test erreichte
   die Claude-Lesung 0,88–0,96 Übereinstimmung — aber nur, weil drei der fünf
   Seiten dieselbe Vadian-Rede tragen und die schwere Hand gegen zwei klarere
   Abschriften gelesen werden konnte. Auf den letzten 50 Seiten von A V 1443,
   **ohne** Parallele, fiel dieselbe Methode auf 5–15 Lücken pro Seite und
   unhaltbare Lesungen zurück; vier so entstandene Volltranskriptionen wurden
   bewusst wieder verworfen.
3. **Der Druck ist der Parallelzeuge, der immer da ist.** Der Basistext
   (Zürich, März 1528, 496 Seiten) ist vollständig erkannt und korrigiert;
   die Handschriften überliefern im Kern denselben Disputationstext. Was beim
   Vadian-Test die klarere Abschrift leistete, kann systematisch der Druck
   leisten.

Der Plan macht aus der Beobachtung ein System: **jede
Handschriftenseite bekommt die zugehörige Druckpassage als Lesehilfe** — für
maschinelles Lesen, für Menschen im Viewer, und als Trainingsweg in
Transkribus.

## Grundsatz, vor allem anderen

**Der Druck ist Hypothese, niemals Vorlage.** Die Handschriften sind gerade
deshalb wertvoll, weil sie vom Druck abweichen — Rümlangs Protokollnotizen,
Hertwigs Protestatio, die Reihenfolge der Voten. Ein System, das die
Transkription zum Druck hin „korrigiert", zerstört den Quellenwert, den es
erschliessen soll. Daraus folgen drei harte Regeln:

- Buchstabenbefund schlägt Drucktext. Die Stütze liefert Wort-Hypothesen;
  was der Schreiber schrieb, entscheidet die Feder.
- Abweichung vom Druck ist ein **Befund**, kein Fehler. Sie wird markiert,
  nie geglättet.
- Jede gestützt entstandene Seite trägt ihre Provenienz (`support: druck_1528`,
  Datum, Deckungsgrad) und ist im Viewer als solche gekennzeichnet.

## Architektur

```
                       ┌───────────────────────┐
                       │  druck_1528 (D1)      │  496 S., korrigiert,
                       │  Text + 83 Segmente   │  Konkordanz vorhanden
                       └──────────┬────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
   (A) Ankerkarte       (B) Stützpakete       (C) Text2Image-Paket
   ms-Seite → Druck-    Bild + Druckpassage   Drucktext, segmentweise
   Seitenbereich        (original + normali-  für Transkribus t2i
   je Handschrift       siert), pro Seite
              │                   │                   │
              ▼                   ▼                   ▼
   Viewer-Lesehilfe     gestützte Lesung      HTR-Modell auf den
   (Mensch)             (Claude, Batch)       fünf Händen (dauerhaft)
                                  │
                                  ▼
                        (D) Divergenz-QS
                        Zeichenabgleich gegen Druck;
                        Abweichungen → Befundliste,
                        Deckungsgrad → Konfidenz
```

## Phasen

### Phase 1 — Ankerkarte (`scripts/build_print_anchors.py`)

Für jede Handschrift eine Karte `ms-Seite → druck_1528-Seitenbereich`,
gespeist aus vier Quellen absteigender Härte:

1. **Vorhandene Alignments**: die Vergleichspaare `druck_1528__a_v_144x`
   liefern für transkribierte Seiten harte Anker.
2. **Struktur-Landmarken** aus dem Sichtungsbestand (finding aid): „Der Nünd
   Artickel" (Hertwig 688), „Der Zehend vnd Lest Artickell / Franciscus Kolb"
   (Hertwig 714), Sitzungsdaten („Samstag nach Vincenty", 704) — jede
   Landmarke matcht auf ein Konkordanz-Segment des Drucks. Dass das trägt,
   ist geprüft: die Segmentdaten führen ein `thesis`-Feld, und These 9 liegt
   im Druck auf S. 466–484 (Segmente 83/84) — genau dort muss Hertwig 688
   andocken. Die beiden Schwanzsegmente tragen noch keine Titel; der
   describe-Lauf ist dort nachzuziehen.
3. **Interpolation** zwischen Ankern, monoton (Blattfolge bricht die
   Reihenfolge nicht), mit ausgewiesener Unschärfe (± Seiten).
4. **Leerseitenerkennung** (Tintenanteil, bereits gebaut): Leerseiten
   unterbrechen die Interpolation nicht.

Ergebnis: `data/disputation/<ms>/print_anchors.json` mit
`{page, druck_von, druck_bis, quelle, konfidenz}`. Validierung: auf den 188
transkribierten Seiten muss die Karte die bekannten Alignments reproduzieren.

*Chicken-and-Egg offen benannt: wo weder Transkription noch Landmarke ist,
bleibt nur Interpolation. Die Karte weist das aus, statt es zu verstecken.*

### Phase 2 — Stützpakete (`scripts/build_support_bundles.py`)

Pro unerschlossener Seite ein Paket: Faksimile + Druckpassage im
Originaltext + normalisiert (Nasalstrich aufgelöst, ſ gefaltet) + Landmarken
der Nachbarseiten.

*Beim Bauen anders entschieden als hier geplant:* die Pakete liegen in
`.cache/support/` und werden **erzeugt, nicht versioniert**. Rund 2 700 JSONs,
die den Drucktext duplizieren, wären eine zweite Wahrheit mit Drift-Garantie;
sie sind vollständig aus committeten Daten ableitbar.

### Phase 3 — Pilotmessung, bevor irgendetwas publiziert wird

Auf 20 transkribierten Seiten (Stichprobe über alle vier Hände) die gestützte
Claude-Lesung gegen den Transkribus-Bestand messen — dieselbe Methodik wie
beim Fünf-Seiten-Test, jetzt mit Druckpassage statt Parallelabschrift als
Stütze. Entscheidungsschwelle vorab festgelegt:

- **Wortübereinstimmung ≥ 0,85** auf treuen Kopierpassagen → Phase 5 darf
  publizieren (mit Kennzeichnung).
- darunter → gestützte Lesung bleibt Arbeitsmaterial; nur Phase 4 und 6
  gehen weiter.

### Phase 4 — Lesehilfe im Viewer

Für Seiten ohne Transkription zeigt die Transkriptionsspalte statt „noch
nicht verfügbar": die Landmarken der Sichtung, und ausklappbar die
Druckpassage laut Ankerkarte („Der Druck überliefert an dieser Stelle: …").
Kein neuer Modus, eine Erweiterung der bestehenden Spalte. Damit wird die
Blätterei durch 2 700 unerschlossene Seiten sofort nützlich — unabhängig
davon, ob je maschinell transkribiert wird.

### Phase 5 — Gestützte Batch-Lesung (nur nach bestandener Phase 3)

Seitenweise: Lesung mit Stützpaket, dann Divergenz-QS (D): Zeichenabgleich
gegen die Druckpassage, kalibriert wie beim Zeugenvergleich. Drei Ausgänge
je Seite:

| Deckungsgrad | Behandlung |
|---|---|
| hoch (treue Kopie) | publizieren, Badge „mit Druckstütze transkribiert" |
| mittel | publizieren, Abweichungen als Befundliste angehängt |
| niedrig (freier Text, z. B. Rümlangs Notizen) | NICHT publizieren — Stütze trägt nicht, ehrliche Lücke bleibt |

Sync-Politik dazu (Verhältnis zu Transkribus): Transkribus bleibt
Quelle der Wahrheit. Gestützte Seiten tragen im Markdown einen
Provenienz-Header; der Sync-Guard wird so erweitert, dass **echter
Transkribus-Text eine gestützte Seite überschreiben darf** (das Gegenteil
der heutigen Regel, die lokalen Text schützt) — sonst sperrt die Stütze
genau die Verbesserung aus, die sie vorbereiten soll.

### Phase 6 — Transkribus-Text2Image (`scripts/build_t2i_packages.py`)

Das segmentweise Druck-Textpaket (C) ist als Referenztext für Transkribus'
Text2Image-Werkzeug gebaut: Text und Bild alignieren, Review in Transkribus,
daraus Ground Truth für ein HTR-Modell auf genau diesen fünf Händen. Das ist
Weg 2 aus #70 mit drastisch reduzierter Handarbeit — statt abzutippen wird
zugeordnet und korrigiert. Beginn bei den schwachen Händen (A V 1445 Schöni),
wo der Bestand selbst fehlerhaft ist. Dieser Teil läuft in Transkribus, nicht
in diesem Repo; das Repo liefert die Pakete und nimmt die Ergebnisse über den
bestehenden Sync zurück.

## Sonderfall, sofort erledigbar

A V 1444 (Cyro) enthält am Ende **eingebundene Druckblätter** (S. 834–838):
die Zehn Schlussreden gedruckt, deutsch und lateinisch. Das ist Druckschrift —
sicher lesbar, ohne jedes Stützsystem. Diese vier Seiten werden direkt
transkribiert und sind der erste Inhalt, der aus dieser Arbeit in die Edition
fliesst.

## Was dieser Plan nicht verspricht

- Er macht aus 6 % nicht 100 %. Rümlangs freie Protokollnotizen und alle
  Passagen, wo die Handschrift eigenständig formuliert, bleiben ohne
  tragende Stütze — dort hilft nur Phase 6 (trainiertes Modell) oder Hand.
- Die Pilotmessung kann scheitern. Dann liefert der Plan trotzdem: Ankerkarte,
  Lesehilfe im Viewer, t2i-Pakete und die vier Druckseiten.

## Reihenfolge und Abhängigkeiten

1 → 2 → 3 (Messung) → 5 nur bei Erfolg; 4 braucht nur 1; 6 braucht nur 2;
Sonderfall sofort. Phase 1–4 sind reine Repo-Arbeit; 6 braucht Transkribus-
Zugang und eine Entscheidung über Modelltraining.
