# Projektplan: Berner Reformation Digitale Edition

## 1. Zielsetzung

Eine digitale Edition zur Berner Reformation erstellen mit:
- **Predigten** (Sermons)
- **Disputation** (Disputation documents)
- **Weitere Ressourcen** (Further Resources)

Jeder Hauptbereich bietet einen 3-Spalten-Viewer:
1. **Bilder** — Faksimile der Originalquelle (Druck/ Handschrift)
2. **Transkription** — Textuelle Wiedergabe
3. **Übersetzung** — Moderne deutsche Übersetzung

## 2. Technische Architektur

### 2.1 Verzeichnisstruktur
```
reformation/
├── site/                    # GitHub Pages Output
│   ├── index.html          # Startseite
│   ├── predigten/         # Predigten-Sektion
│   ├── disputation/       # Disputation-Sektion
│   └── ressourcen/        # Weitere Ressourcen
├── data/                   # Quelldaten
│   ├── predigten/         # Bilder, Transkriptionen, Übersetzungen
│   ├── disputation/       # Bilder, Transkriptionen, Übersetzungen
│   ├── institutionen/     # Metadaten zu Institutionen
│   ├── personen/          # Metadaten zu Personen
│   └── register/          # Generierte Indizes
├── scripts/               # Verarbeitungsskripte
│   ├── generate_indices.py
│   └── build_site.py
├── content/               # Markdown/Inhaltsseiten
└── REAME.md
```

### 2.2 Technologie-Stack
- **Hosting:** GitHub Pages (aus `site/` Verzeichnis)
- **Frontend:** Vanilla HTML/CSS/JS oder leichtgewichtiges Static Site Generator
- **Datenformat:** 
  - TEI-XML für Transkriptionen (standardisiert)
  - JSON für Metadaten und Indizes
- **Bildbetrachter:** IIIF-kompatibler Viewer (z.B. Mirador oder Leaflet)
- **Übersetzungen:** Markdown-Dateien

## 3. Hauptkomponenten

### 3.1 Dreispalten-Viewer (für Predigten + Disputation)

**Layout:**
```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│     BILD-QUELLE     │    TRANSKRIPTION   │    ÜBERSETZUNG     │
│   (Faksimile/Scan)  │   (TEI-XML/MD)     │  (ModernesDeutsch) │
├─────────────────────┴─────────────────────┴─────────────────────┤
│ [Navigation: prev / title / next]                                │
└──────────────────────────────────────────────────────────────────┘
```

**Features:**
- Synchronisiertes Scrollen (optional)
- Zoom für Bilder
- Textauswahl in Transkription/Übersetzung
- Responsives Design (Mobile: Stapelansicht statt 3 Spalten)

### 3.2 Register-System

**Personenregister:**
- ID, Name, Lebensdaten, Rolle, Quelle(n)
- Verknüpfung mit transkribierten Dokumenten

**Organisationsregister:**
- ID, Name, Zeitraum, Ort, Verknüpfungen

**Suchfunktion:**
- Facettensuche nach Person, Institution, Datum

## 4. Open Questions / Unsicherheiten

### 4.1 Inhaltliche Fragen
1. **Welche spezifischen Predigten?** — 
   - Sind die "Bernerpredigten" (1528) gemeint?
   - Welche weiteren Predigten sollen integriert werden?

2. **Welche Disputations-Dokumente?** — 
   - Die Berner Disputation 1528?
   - Weitere synodale Dokumente?

3. **Bestehende Digitalisate?** — 
   - Existieren bereits gescannte Versionen (e-rara.ch, e-manuscripta.ch)?
   - Wer hält die Rechte an den Digitalisaten?

4. **Transkriptionen vorhanden?** — 
   - Liegen bereits TEI-XML Transkriptionen vor?
   - Falls nicht: OCR/HTR erforderlich? (→ Königsfelden-Modell?)

5. **Übersetzungen vorhanden?** — 
   - Gibt es bestehende Übersetzungen ins Deutsche?
   - Falls nicht: Wer übersetzt? (KI-Unterstützung?)

### 4.2 Technische Fragen
1. **IIIF-Server?** — 
   - Eigener Server oder Drittanbieter?
   - Eigene Bilder hosten oder extern verlinken?

2. **Rechte/Lizenzen?** — 
   - CC-Lizenz für Inhalte?
   - Besitzrechte für Digitalisate geklärt?

3. **Hochskalierbarkeit?** — 
   - Wie viele Seiten/Dokumente erwartet?
   - Performance bei grossen Bildmengen?

### 4.3 Organisatorische Fragen
1. **Wer liefert Inhalte?** — 
   - Wer stellt Transkriptionen bereit?
   - Wer macht die Übersetzungen?

2. **Wer pflegt?** — 
   - Langzeitwartung?
   - Wer aktualisiert bei Fehlern?

## 5. Umsetzungsschritte

### Phase 1: Konzept & Prototype (1-2 Wochen)
- [ ] Ordnerstruktur anlegen
- [ ] Basis-HTML mit 3-Spalten-Viewer erstellen
- [ ] Beispieldaten (1 Predigt, 1 Disputation) mocken
- [ ] Design-Prototyp prüfen

### Phase 2: Datensammlung (2-4 Wochen)
- [ ] Quellen identifizieren (Archive, Bibliotheken)
- [ ] Rechte klären
- [ ] Digitalisate beschaffen
- [ ] Transkriptionen erstellen (oder bestehende importieren)
- [ ] Übersetzungen erstellen

### Phase 3: Datenaufbereitung (1-2 Wochen)
- [ ] Bilder optimieren (WebP, thumbnails)
- [ ] TEI-XML/JSON Struktur definieren
- [ ] Metadaten erfassen
- [ ] Indizes generieren

### Phase 4: Entwicklung (2-4 Wochen)
- [ ] Viewer fertigstellen (Zoom, Navigation)
- [ ] Suchfunktion integrieren
- [ ] Register-Seiten erstellen
- [ ] Responsive Design

### Phase 5: Launch & Testing (1 Woche)
- [ ] Auf GitHub Pages deployen
- [ ] Testen mit echten Daten
- [ ] Feedback einarbeiten

## 6. Geschätzter Aufwand

| Phase | Aufwand (geschätzt) |
|-------|---------------------|
| Konzept | 1-2 Wochen |
| Datensammlung | 2-4 Wochen (abhängig von Vorhandensein) |
| Datenaufbereitung | 1-2 Wochen |
| Entwicklung | 2-4 Wochen |
| Launch | 1 Woche |
| **Total** | **7-15 Wochen** |

## 7. Nächste Schritte

1. **Bestandsaufnahme:** Vorhandene Digitalisate, Transkriptionen, Übersetzungen identifizieren
2. **Rechte klären:** Urheberrechte für Bilder und Texte klären
3. **Pilotprojekt:** Eine Predigt komplett durch den 3-Spalten-Viewer

---

*Erstellt: 2026-03-15*
