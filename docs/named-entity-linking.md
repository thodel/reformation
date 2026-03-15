# Named-Entity Linking Approach (Transkription)

## Ziel
Alle benannten Entitaeten in der Transkription (Personen, Orte, Institutionen, Werke/Bibelstellen) auf stabile Referenzen verlinken.

## Datenmodell
Die Web-App nutzt `data/predigten/entities/named_entities.json` als Laufzeit-Index.

Schema pro Entitaet:
- `id`: stabiler interner oder externer Identifier
- `label`: kanonische Namensform
- `type`: z. B. `person`, `place`, `institution`, `work`
- `url`: Zielseite (Wikidata, GND, lokales Register)
- `aliases`: historische Schreibvarianten fuer das Matching

## Pipeline (empfohlen)
1. Transkriptionen strukturieren:
- Ziel: pro Seite `data/predigten/transcriptions/page_<n>.md` oder TEI-XML mit Entitaetsmarkup.

2. Kanonische Register aufbauen:
- Personen/Orte/Institutionen mit stabilen IDs.
- Bevorzugt: Wikidata/GND + lokale Projekt-IDs.

3. Varianten sammeln:
- Historische Orthographien als `aliases` erfassen.
- Beispiele: `Bern`/`Bernn`, `Zwingli`/`Zuingli`.

4. Entitaeten annotieren:
- Goldstandard: TEI (`<persName ref=...>`, `<placeName ref=...>`).
- Fallback: regelbasiertes Alias-Matching gegen den JSON-Index.

5. QA vor Veröffentlichung:
- Precision/Recall auf Stichprobe je Predigt.
- Kollisionspruefung bei mehrdeutigen Namen.
- Sichtpruefung auf der Seite mit Kontext.

## Frontend-Verhalten (implementiert)
- Beim Laden der Transkription wird `named_entities.json` geladen.
- Treffer werden als Links mit Klasse `.entity-link` gerendert.
- Matching ist wortgrenzenbasiert und alias-laengenpriorisiert (lange Aliases zuerst).

## Skalierung auf "alle" Entitaeten
- Kurzfristig: Alias-Index manuell erweitern.
- Mittelfristig: halbautomatische Extraktion (NER + Normalisierung + Review-UI).
- Langfristig: Entitaetsverweise direkt im TEI-Quelltext pflegen und daraus JSON ableiten.

## Nächste konkrete Schritte
1. `data/predigten/transcriptions/` mit Seiten-Dateien befuellen.
2. `named_entities.json` auf Vollabdeckung erweitern.
3. Ambiguitaetsregeln definieren (z. B. kontextabhaengige Zuordnung).
4. Optional: lokales Register mit Detailseiten statt externer URLs.
