# Berner Reformation - Digitale Edition

Web-Prototyp fuer eine digitale Edition zur Berner Reformation (1528) mit Fokus auf den Bereich **Predigten**.
Die Anwendung kombiniert:
- IIIF-Faksimile (OpenSeadragon, seitenbasiert)
- Textspalte fuer Transkription (mit optionalem Named-Entity-Linking)
- Textspalte fuer moderne deutsche Uebersetzung aus lokalen Markdown-Dateien

## Aktueller Stand

Implementiert:
- Single-Page-Webapp in [`index.html`](index.html)
- Navigation zwischen vier Bereichen: Startseite, Predigten, Disputation, Ressourcen
- Predigten-Viewer mit OpenSeadragon (Canvas-Wechsel pro Seite aus IIIF-Manifest)
- Seitennavigation fuer Bild + Transkription + Uebersetzung
- Laden der Uebersetzungen aus `data/predigten/translations/`
- Optionales Laden von Transkriptionen aus `data/predigten/transcriptions/`
- Optionales Named-Entity-Linking via `data/predigten/entities/named_entities.json`

In Vorbereitung:
- Disputation-Viewer
- Personen-/Institutionsregister
- Vollstaendige Transkriptionsspalte

## Projektstruktur

```text
reformation/
├── index.html
├── README.md
├── PROJEKTPLAN.md
├── docs/
│   └── named-entity-linking.md
└── data/
    └── predigten/
        ├── entities/
        │   └── named_entities.json
        ├── transcriptions/
        │   └── page_<n>.md
        └── translations/
            ├── page_1.md
            ├── page_2.md
            └── ...
```

Wichtige Dateien:
- [`index.html`](index.html): komplette Frontend-Logik (HTML, CSS, JavaScript)
- [`data/predigten/translations/`](data/predigten/translations): Uebersetzungsdateien als Markdown
- [`data/predigten/entities/named_entities.json`](data/predigten/entities/named_entities.json): Alias- und Link-Index fuer Entitaeten
- [`docs/named-entity-linking.md`](docs/named-entity-linking.md): Vorgehen fuer Vollabdeckung aller Entitaeten
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

- Die Konstante `DEFAULT_TOTAL_PAGES` in [`index.html`](index.html) definiert den Fallback, bis die Seitenzahl aus dem Manifest geladen ist.
- Der Manifest-Link ist in `PREDIGTEN_MANIFEST_URL` zentral konfiguriert.
- Der Pfad zu den Uebersetzungen ist in `TRANSLATION_BASE_PATH` zentral konfiguriert.
- Der Pfad zu Transkriptionen ist in `TRANSCRIPTION_BASE_PATH` konfiguriert.
- Named-Entity-Linking nutzt `ENTITY_INDEX_PATH` (JSON mit `label`, `aliases`, `url`).

## Bekannte Einschraenkungen

- Fuer Seiten ohne Datei in `data/predigten/transcriptions/` wird ein Platzhalter angezeigt.
- Der Predigten-Bereich erwartet numerische Seiten (`page_1.md` bis `page_224.md`). Zusaetzliche Dateien mit roemischen Seitenbezeichnungen werden derzeit nicht automatisch verwendet.
- Keine Build-Pipeline, Tests oder Linting eingerichtet (statischer Prototyp).

## Quellen

- Predigten (DOI): [10.3931/e-rara-3026](https://doi.org/10.3931/e-rara-3026)
- Disputation (DOI): [10.3931/e-rara-47098](https://doi.org/10.3931/e-rara-47098)
- OpenSeadragon: [openseadragon.github.io](https://openseadragon.github.io/)

## Weiterentwicklung

Konzeptionelle und organisatorische Details stehen in [`PROJEKTPLAN.md`](PROJEKTPLAN.md).
