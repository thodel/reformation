# Plan: E-Periodica Integration für Swiss History Bot

## Zusammenfassung

E-Periodica (ETH-Bibliothek) bietet programmatischen Zugang via **OAI-PMH** und direkten PDF-Download. Dieser Plan beschreibt, wie wir Artikel für den Swiss History Bot nutzen können – ohne das PDF selbst zu speichern.

---

## Technische Möglichkeiten

### 1. OAI-PMH Interface
- **Endpoint:** `https://www.e-periodica.ch/oai/dataprovider`
- **Metadaten-Format:** `oai_dc` (Dublin Core)
- **Verfügbare Sets:** DDC-Kategorien (z.B. `ddc:940` für Geschichte Europas)

### 2. Erhältliche Metadaten
- Titel
- Autor/Creator
- Datum/Jahr
- Zeitschrift/Journal
- DOI
- PDF-Direktlink: `https://www.e-periodica.ch/cntmng?type=pdf&pid={identifier}`
- IIIF-Bildlink

### 3. Rechtliche Einschränkungen
- **Terms of Use:** "Systematic storage of any part or all of the content on other servers is generally not permitted"
- **Aber:** Für Forschungszwecke und mit korrekter Zitation kann eine Ausnahme gelten
- **Empfehlung:** Wir speichern KEINE PDFs, nur Metadaten + Embeddings

---

## Implementation Plan

### Phase 1: Metadaten-Harvesting
1. **OAI-PMH Client** erstellen (Python `oai-pmh` oder `polymatheia`)
2. **Sets durchsuchen:** Relevante Kategorien für Schweizer Geschichte (`ddc:940`)
3. **Metadaten extrahieren:** Titel, Autor, Jahr, DOI, Journal, PDF-URL

### Phase 2: Text-Extraktion (ohne Speicherung)
1. **PDF herunterladen** (temporär)
2. **Text extrahieren** (PyMuPDF / pdfplumber)
3. **Chunking:** In sinnvolle Textabschnitte teilen
4. **Embedding generieren:** OpenAI text-embedding-3-small
5. **Temporäre Dateien löschen**

### Phase 3: Speicherung (nur Metadaten + Embeddings)
1. **Metadaten speichern:** SQLite (wie bestehende Pipeline)
2. **Embeddings speichern:** FAISS Index
3. **Verweis auf Original:** DOI + E-Periodica URL (kein PDF auf unserem Server)

### Phase 4: RAG-Integration
1. Query-Routing: Welche Quelle (HLS, SSRQ, E-Periodica)
2. Zitationsformat: "E-Periodica: {Titel}, {Jahr}"

---

## Architektur

```
E-Periodica OAI-PMH
        │
        ▼
┌───────────────────┐
│  Metadata Harvest  │ ──► Metadaten (SQLite)
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Temp PDF Download │ ──► Löschen nach Extraktion
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Text Extraction  │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│   Chunking        │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Embedding (API)  │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ FAISS + SQLite    │ (NUR Metadaten + Embeddings)
└───────────────────┘
```

---

## Script-Struktur (Vorschlag)

```bash
scripts/
├── ingest_eperiodica.py    # Main ingestion script
├── oai_client.py           # OAI-PMH wrapper
└── pdf_processor.py         # Temp download → extract → delete
```

---

## Offene Fragen

1. **Rechtliche Absicherung:** Klären, ob temporäre Extraktion für Embedding-Zwecke unter die Ausnahme fällt
2. **Rate Limiting:** Wie viele Requests pro Minute sind erlaubt?
3. **Umfang:** Welche DDC-Kategorien sind relevant?
   - ddc:940 – Geschichte Europas
   - ddc:948 – Geschichte einzelner Länder (Schweiz: ddc:949.4?)

---

## Nächste Schritte

1. Rechtliche Klärung mit ETH-Bibliothek oder Rechtsabteilung
2. PoC: Einen einzelnen Artikel harvesten und embedden
3. Test-RAG-Query gegen E-Periodica-Daten

---

*Erstellt: 2026-03-18*
