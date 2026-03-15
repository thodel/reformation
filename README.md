# Berner Reformation - Digitale Edition

Web-Prototyp fuer eine digitale Edition zur Berner Reformation (1528) mit Fokus auf den Bereich **Predigten**.
Die Anwendung kombiniert:
- IIIF-Faksimile (Mirador)
- Textspalte fuer Transkription (Platzhalter)
- Textspalte fuer moderne deutsche Uebersetzung aus lokalen Markdown-Dateien

## Aktueller Stand

Implementiert:
- Single-Page-Webapp in [`index.html`](index.html)
- Navigation zwischen vier Bereichen: Startseite, Predigten, Disputation, Ressourcen
- Predigten-Viewer mit Mirador (Manifest von e-rara)
- Seitennavigation fuer 224 Seiten (`page_1.md` bis `page_224.md`)
- Laden der Uebersetzungen aus `data/predigten/translations/`

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
└── data/
    └── predigten/
        └── translations/
            ├── page_1.md
            ├── page_2.md
            └── ...
```

Wichtige Dateien:
- [`index.html`](index.html): komplette Frontend-Logik (HTML, CSS, JavaScript)
- [`data/predigten/translations/`](data/predigten/translations): Uebersetzungsdateien als Markdown
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

Hinweis: Fuer Mirador und Manifest-Zugriff ist Internetzugang erforderlich (CDN + e-rara).

## Datenformat der Uebersetzungen

Dateinamen:
- `page_<nummer>.md` (z. B. `page_1.md`, `page_224.md`)

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

- Die Konstante `TOTAL_PAGES` in [`index.html`](index.html) steuert die Seitenanzahl im Viewer.
- Der Manifest-Link ist in `PREDIGTEN_MANIFEST_URL` zentral konfiguriert.
- Der Pfad zu den Uebersetzungen ist in `TRANSLATION_BASE_PATH` zentral konfiguriert.

## Bekannte Einschraenkungen

- Die Transkriptionsspalte wird aktuell noch nicht aus Dateien befuellt.
- Der Predigten-Bereich erwartet numerische Seiten (`page_1.md` bis `page_224.md`). Zusaetzliche Dateien mit roemischen Seitenbezeichnungen werden derzeit nicht automatisch verwendet.
- Keine Build-Pipeline, Tests oder Linting eingerichtet (statischer Prototyp).

## Quellen

- Predigten (IIIF Manifest): [e-rara.ch](https://www.e-rara.ch/i3f/v20/935411/manifest)
- Disputation (IIIF Manifest): [e-rara.ch](https://www.e-rara.ch/i3f/v20/13106447/manifest)
- Mirador: [mirador.dev](https://mirador.dev/)

## Weiterentwicklung

Konzeptionelle und organisatorische Details stehen in [`PROJEKTPLAN.md`](PROJEKTPLAN.md).
