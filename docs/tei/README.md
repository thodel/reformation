# TEI-P5-Export

Maschinell erzeugter TEI-P5-Export der Edition. **Nicht von Hand bearbeiten** —
die Dateien werden von `scripts/export_tei.py` aus den Quelldaten des
Repositorys erzeugt und bei jeder Datenänderung neu geschrieben. Eine von Hand
gepflegte Kopie wäre eine zweite Wahrheit und würde innerhalb eines Monats von
der Edition abweichen.

## Dateien

| Datei | Inhalt |
|---|---|
| `druck_1528.xml` … `druck_1701.xml` | die fünf Drucke, Sigle D1–D5 |
| `a_v_1443_hertwig.xml` … `a_v_1447_schlussredaktion.xml` | die fünf Handschriften, Sigle H43–H47 |
| `apparatus.xml` | der berechnete Variantenapparat als `<app>`/`<rdg>`, Lesarten auf die Sigla bezogen |
| `register.xml` | `<listPerson>` mit HLS-Verknüpfung, `<listBibl>` der Bibelstellen |

Jedes Zeugendokument enthält `<pb n="…" facs="…"/>` je Seite — `@facs` verweist
auf die zitierfähige Seiten-URL der Website — und `<lb/>` je Zeile, wo die
PAGE-XML Zeilenumbrüche liefert.

## Was der Export über sich selbst sagt

Zwei Angaben stehen in **jedem** `teiHeader`, nicht nur auf der Website: dass
der Text maschinell erkannt und **nicht ediert** ist, und dass die Digitalisate
unter der Public Domain Mark bei den besitzenden Institutionen liegen. Ein
TEI-Dokument wird geerntet und weiterverwendet, weit weg von der Seite, auf der
sonst jeder Vorbehalt steht.

Der Apparat ist maschinell berechnet, keine Kollation von Hand. Ein Teil seiner
Lesarten geht auf Erkennungsfehler zurück; die typisierte Auswertung auf der
Website (`#/vergleich/<a>__<b>/typ`) trennt diese von inhaltlichen Abweichungen.

## Erzeugen und prüfen

```bash
python3 scripts/export_tei.py
python3 -m pytest tests/test_tei_export.py
```

Die Tests validieren jede Datei gegen `tei_all.rng` (einmal geladen, danach in
`.cache/` zwischengespeichert). Ist das Schema weder erreichbar noch im Cache,
überspringt der Test mit sichtbarem Grund — er meldet nie Erfolg für einen
Export, den niemand validiert hat.
