# Berner Reformation - Digitale Edition

Web-Prototyp fuer eine digitale Edition zur Berner Reformation (1528) mit Fokus auf **Predigten** und **Disputation**.
Die Anwendung kombiniert:
- IIIF-Faksimile (OpenSeadragon, seitenbasiert)
- Textspalte fuer Transkription (mit optionalem Named-Entity-Linking)
- Textspalte fuer moderne deutsche Uebersetzung aus lokalen Markdown-Dateien

## Aktueller Stand

Implementiert:
- Single-Page-Webapp in [`index.html`](index.html)
- Navigation zwischen vier Bereichen: Startseite, Predigten, Disputation, Ressourcen
- Predigten-Viewer mit OpenSeadragon (Canvas-Wechsel pro Seite aus IIIF-Manifest)
- Disputation-Viewer mit OpenSeadragon und Variantenumschaltung
- Disputation kann pro Variante aus lokalem `viewer_manifest.json` gespeist werden (Transkribus-Export)
- Seitennavigation fuer Bild + Transkription + Uebersetzung (beide Bereiche)
- Laden der Uebersetzungen aus `data/predigten/translations/`
- Optionales Laden von Transkriptionen aus `data/predigten/transcriptions/`
- Optionales Named-Entity-Linking via `data/predigten/entities/named_entities.json`
- Disputations-Ansichten:
  - Druck von 1528
  - A V 1447: Schlussredaktion
  - A V 1443: Hertwig
  - A V 1444: Cyro
  - A V 1445: Schoeni
  - A V 1446: Ruemlang

In Vorbereitung:
- Vollstaendige Befuellung der Disputations-Manifeste fuer alle Handschriften
- Personen-/Institutionsregister
- Vollstaendige Transkriptionsspalten

## Projektstruktur

```text
reformation/
├── index.html
├── README.md
├── PROJEKTPLAN.md
├── scripts/
│   └── sync_disputation_transkribus.py
├── config/
│   └── disputation_transkribus.example.json
├── docs/
│   └── named-entity-linking.md
└── data/
    ├── predigten/
    │   ├── entities/
    │   │   └── named_entities.json
    │   ├── transcriptions/
    │   │   └── page_<n>.md
    │   └── translations/
    │       ├── page_1.md
    │       ├── page_2.md
    │       └── ...
    └── disputation/
        ├── druck_1528/
        ├── a_v_1447_schlussredaktion/
        ├── a_v_1443_hertwig/
        ├── a_v_1444_cyro/
        ├── a_v_1445_schoeni/
        └── a_v_1446_ruemlang/
```

Wichtige Dateien:
- [`index.html`](index.html): komplette Frontend-Logik (HTML, CSS, JavaScript)
- [`scripts/sync_disputation_transkribus.py`](scripts/sync_disputation_transkribus.py): Sync von Bildern + PAGE XML + Zeilenkoordinaten aus Transkribus
- [`config/disputation_transkribus.example.json`](config/disputation_transkribus.example.json): Vorlage fuer Collection-/Document-IDs
- [`data/predigten/translations/`](data/predigten/translations): Uebersetzungsdateien als Markdown
- [`data/predigten/entities/named_entities.json`](data/predigten/entities/named_entities.json): Alias- und Link-Index fuer Entitaeten
- [`data/disputation/`](data/disputation): Variantenordner fuer die sechs Disputationsfassungen
- [`docs/named-entity-linking.md`](docs/named-entity-linking.md): Vorgehen fuer Vollabdeckung aller Entitaeten
- [`docs/disputation-transkribus-setup.md`](docs/disputation-transkribus-setup.md): Credential- und Sync-Setup fuer Transkribus
- [`PROJEKTPLAN.md`](PROJEKTPLAN.md): Projektplanung und Roadmap

## Lokale Ausfuehrung

Da Uebersetzungen via `fetch(...)` geladen werden, muss die Seite ueber einen lokalen Webserver laufen (nicht via `file://`).

1. Im Projektverzeichnis starten:

```bash
cd /Users/TH_1/Documents/Repo/reformation
python3 -m http.server 8000
```

2. Im Browser oeffnen:

```text
http://localhost:8000
```

Hinweis: Fuer OpenSeadragon und Manifest-Zugriff ist Internetzugang erforderlich (CDN + e-rara).

## Datenformate (Text)

Dateinamen:
- Uebersetzung: `data/predigten/translations/page_<nummer>.md`
- Transkription: `data/predigten/transcriptions/page_<nummer>.md`
- Disputation pro Variante analog:
  - `data/disputation/<variante>/translations/page_<nummer>.md`
  - `data/disputation/<variante>/transcriptions/page_<nummer>.md`
  - `data/disputation/<variante>/line_coords/page_<nummer>.json` (Zeilenkoordinaten)

Einfaches Markdown-Schema:
- Zeilen mit `# ` werden als Abschnittstitel dargestellt
- Alle anderen Zeilen werden als Fliesstext mit Zeilenumbruechen ausgegeben

Beispiel:

```md
# Seite 1

Kurzer Abschnittstitel

Lauftext der Uebersetzung...
```

## Technische Hinweise

- Die Konstante `PREDIGTEN_DEFAULT_TOTAL_PAGES` in [`index.html`](index.html) definiert den Fallback, bis die Seitenzahl aus dem Manifest geladen ist.
- Predigten nutzt `PREDIGTEN_MANIFEST_URL`, `PREDIGTEN_TRANSLATION_BASE_PATH`, `PREDIGTEN_TRANSCRIPTION_BASE_PATH`.
- Disputation wird ueber `DISPUTATION_VARIANTS` konfiguriert (Manifest + Datenpfade je Variante).
- Named-Entity-Linking nutzt pro Bereich eine `named_entities.json` (mit `label`, `aliases`, `url`).
- Bei Varianten ohne IIIF-Manifest laedt das Frontend `data/disputation/<variante>/viewer_manifest.json`.

## Bekannte Einschraenkungen

- Fuer Seiten ohne Datei in `data/predigten/transcriptions/` wird ein Platzhalter angezeigt.
- Der Predigten-Bereich erwartet numerische Seiten (`page_1.md` bis `page_224.md`). Zusaetzliche Dateien mit roemischen Seitenbezeichnungen werden derzeit nicht automatisch verwendet.
- Fuer Varianten ohne IIIF-Manifest ist ein vorheriger Transkribus-Sync notwendig.
- Keine Build-Pipeline, Tests oder Linting eingerichtet (statischer Prototyp).

## Transkribus-Sync (Disputation)

Details: [`docs/disputation-transkribus-setup.md`](docs/disputation-transkribus-setup.md)

Kurzfassung:
1. `pip install requests`
2. `cp config/disputation_transkribus.example.json config/disputation_transkribus.json`
3. IDs je Variante setzen (`collection_id`, `document_id`)
4. Credentials setzen (`TRANSKRIBUS_USER`, `TRANSKRIBUS_PASSWORD`)
5. `python3 scripts/sync_disputation_transkribus.py --config config/disputation_transkribus.json`

## Quellen

- Predigten (DOI): [10.3931/e-rara-3026](https://doi.org/10.3931/e-rara-3026)
- Disputation (DOI): [10.3931/e-rara-47098](https://doi.org/10.3931/e-rara-47098)
- OpenSeadragon: [openseadragon.github.io](https://openseadragon.github.io/)

## Weiterentwicklung

Konzeptionelle und organisatorische Details stehen in [`PROJEKTPLAN.md`](PROJEKTPLAN.md).
