# P3 — Pilotmessung der druckgestützten Lesung: NICHT BESTANDEN

*30. August 2026. Teil von #75. Schwelle und Konsequenz waren VOR der
Messung festgelegt (docs/print-support-plan.md): Wortübereinstimmung
≥ 0,85 auf treuen Kopierpassagen, sonst publiziert Phase 5 nicht.*

## Ergebnis

**Median 0,60 auf 17 treuen Kopierpassagen — die Schwelle ist deutlich
verfehlt. Phase 5 (gestützte Batch-Lesung als publizierter Text) entfällt.**

| Sicht | n | Median |
|---|---:|---:|
| treue Kopierpassagen (Drucktreue ≥ 0,5) | 17 | **0,60** |
| ohne Schöni (dessen Referenztext selbst schwach ist) | 13 | 0,67 |
| nur Hertwig (sauberste Hand) | 6 | 0,74 |
| bestes Einzelblatt (Hertwig S. 55) | 1 | 0,83 |
| freie Protokollpassagen (Rümlang Notizen) | 3 | 0,27 |

Kein ehrlicher Zuschnitt rettet das Verdikt: selbst die sauberste Hand
allein bleibt elf Punkte unter der Schwelle, und das beste Einzelblatt
erreicht sie nicht.

## Methode

20 Seiten, seeded gezogen (seed 75, `docs/p3/selection.json`) über die vier
Hände, proportional zum transkribierten Bestand; die eingebundenen
Druckblätter von A V 1444 ausgeschlossen (Druckschrift, teils eigene
P0-Transkription). Stützpakete wie in Produktion: Ankerbereiche künstlich
um ±3 Seiten aufgeweitet, damit die Messung nicht von alignment-exakten
Ankern profitiert, die unerschlossene Seiten nicht haben. Lesung
ausschliesslich aus Bild + Druckpassage; der Transkribus-Bestand wurde
während des Lesens nicht geöffnet. Metrik: SequenceMatcher über
normalisierte Wortfolgen (Nasalstrich aufgelöst, ſ gefaltet,
Interpunktion entfernt); Drucktreue = Anteil der Bestandswörter, die in
der Druckpassage vorkommen. Rohwerte: `docs/p3/scores.json`.

## Warum der Fünf-Seiten-Test 0,88–0,96 zeigte und diese Messung 0,60

Der frühere Test lag nicht falsch — er mass eine andere Bedingung, und die
Differenz ist selbst der Befund:

1. **Parallelabschrift ≠ Druckpassage.** Im Fünf-Seiten-Test trugen drei
   Seiten dieselbe Vadian-Rede in zwei weiteren Abschriften — wortnah,
   zeilennah. Der Druck überliefert denselben *Inhalt*, aber redigiert:
   Wortstellung, Auslassungen, Zusätze. Die Stütze liefert die Richtung,
   diktiert aber nicht den Wortlaut — und genau der wird gemessen.
2. **Die Pilotseiten sind der Normalfall, nicht der Schaufall.** Konzepte
   mit Streichungen und Interlinear-Einfügungen (Hertwig 37, 39),
   verblasste Entwürfe (Schöni durchgängig), freie Protokollnotizen
   (Rümlang 5, 18). Der Fünf-Seiten-Test traf Reinschrift-Eröffnungsseiten.
3. **Der Referenztext misst mit.** Wo der Transkribus-Bestand selbst schwach
   ist (Schöni), misst die Übereinstimmung auch dessen Fehler. Das drückt
   die Zahl — hebt sie aber selbst im günstigsten Zuschnitt nicht über die
   Schwelle.

## Was aus dem Scheitern folgt — und was bestehen bleibt

- **P5 entfällt.** Es wird kein druckgestützt gelesener Handschriftentext
  publiziert. Der Plan hat diesen Ausgang vorgesehen; die ehrliche Lücke
  bleibt Lücke.
- **P4 (Lesehilfe im Viewer) bleibt sinnvoll und wird gebaut**: die
  Druckpassage als *Hypothese neben dem Faksimile* für menschliche Leser
  ist genau das, was die Messung stützt — die Passage traf in 17 von 20
  Fällen den Inhalt (Drucktreue ≥ 0,5), sie taugt als Wegweiser, nicht als
  Diktat.
- **P6 (Transkribus Text2Image) wird wichtiger, nicht unwichtiger**: der
  Weg zu publizierbarem Text führt über ein auf diese Hände trainiertes
  Modell, nicht über gestütztes Ablesen.
- Die Ankerkarte (P1) hat sich getragen: die Passagen lagen inhaltlich
  richtig; verfehlt wurde die Buchstabentreue, nicht die Verortung.
