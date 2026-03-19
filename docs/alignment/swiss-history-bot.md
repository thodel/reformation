# Projekt: Swiss History Bot (PoC)

**Kurzname:** Swiss History Bot  
**Kalender-Stichwort:** `Swiss History Bot` · `infoclio` · `ch-h-bot`  
**Link:** https://cloud.hodelweb.ch/index.php/apps/files/files/730?dir=/Documents/projects&editing=false&openfile=true

## Projektübersicht
Ein konversationelles Interface für präzise, quellenbasierte Informationen zur Schweizer Geschichte. Der Bot nutzt "Retrieval-Augmented Generation" (RAG), um Antworten auf Basis kuratierter Fachquellen (statt allgemeiner LLM-Daten) zu generieren.

**Ziel:** Jede Aussage ist nachvollziehbar und mit Quellen belegt (Zitationspflicht).

**Repository:** `/home/th/repos/ch-h-bot`

## Partner & Datenquellen
- **infoclio.ch:** Möglicher Host für den Bot / Projektpartner
- **HLS (Historisches Lexikon der Schweiz):** Referenzartikel (Metadaten CC0, Text)
- **SSRQ (Sammlung Schweizerischer Rechtsquellen):** TEI-XML Daten
- **Weitere (geplant):** e-rara, e-periodica, NB-Katalog, Elites Suisses

## Phasen (PoC)
1. **Phase 0 (Foundation):** Ingestion HLS-Daten, RAG-Pipeline, Vektor-DB (Chroma/Qdrant).
2. **Phase 1 (Knowledge Graph):** Entitäten-Extraktion, Graph-DB (Neo4j/Kùzu), SSRQ-Integration.
3. **Phase 2 (UI & Expansion):** Web-Interface, weitere Quellen (e-rara), Evaluation.
4. **Phase 3 (Hardening):** Deployment auf GPUStack UNIBE, Guardrails.

## Aktuelle Aufgaben / Notizen
- **Nächstes Meeting:** "Austausch infoclio: Swiss History Bot" (9. März 2026, 12:00–13:30)
- **To-Dos:**
    - HLS-Daten (CSV/BEACON) herunterladen und parsen.
    - Ingestion-Skript schreiben (Chunking -> Embedding).
    - Vektor-Store aufsetzen.
    - Erste Test-Queries ("Wer war Alfred Escher?").

## SSRQ Ingestion (Stand: 5. März 2026)
- **Script erstellt:** `swiss-history-bot/scripts/ingest_ssrq.py`
- **Datenquelle:** SSRQ TEI-XML (Sammlung Schweizerischer Rechtsquellen)
- **Extrahiert:**
    1. **Regesta/Abstract** (`<summary>` Elemente) — Kurzfassung des Dokuments
    2. **Volltext** (`<body>` Inhalt) — Vollständiger Transkriptionstext
    3. **XML-Struktur** — Komplettes TEI-XML archiviert
- **Embedding-Strategie:** Alle drei Texttypen werden separat gechunkt und eingebettet
- **Getestet mit:** FR_I_2_8 (Freiburger Hexenprozesse 15.–18. Jh.), ~500 Dokumente
- **Nächste Schritte:**
    - Embedding-API Integration (OpenAI text-embedding-3-small)
    - FAISS-Index für SSRQ-Chunks erstellen
    - Query-Routing: Welcher Chunk-Typ liefert beste Treffer?

---
*Erstellt basierend auf Repository-README am 04.03.2026.*
