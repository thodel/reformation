# Projekt: Swiss History Bot (ch-h-bot)

**Kurzname:** Swiss History Bot  
**Kalender-Stichwort:** `Swiss History Bot` · `infoclio` · `ch-h-bot`  
**Link:** https://cloud.hodelweb.ch/index.php/apps/files/files/730?dir=/Documents/projects&editing=false&openfile=true

---

## Status

**Phase:** Alpha / Proof of Concept — live und aktiv in Nutzung  
**URL:** <https://chat.hodelweb.ch> (Caddy → Docker, VM 194.13.80.183)  
**Repository:** <https://github.com/thodel/ch-h-bot>  
**Deployment:** `/opt/ch-h-bot/` auf VM  
**Konzept-Dokument:** [Google Doc](https://docs.google.com/document/d/1yBZj8Q4ATAF6_H941XYq97zQUdAMDSl3gItKaHK7QHY/edit)

---

## Architektur (aktuell)

```
Browser
  └─ Streamlit (app/app.py)  :8501
       ├─ POST /chat   ──► FastAPI (api/main.py)  :8000
       └─ POST /search ──►     ├─ OpenAI Embeddings (text-embedding-3-small)
                               ├─ FAISS index (IndexFlatIP, 310 MB, 52.799 Einträge)
                               ├─ Weaviate (Metadaten-Store, :8081)
                               ├─ SQLite (documents + chunks + audit_log)
                               └─ Gemini 2.0 Flash (LLM)
```

**Deployment:** 3 Docker-Container (api, app, weaviate) — alle laufend und gesund

---

## Indiziertes Korpus

| Quelle | Dokumente | Typ |
|--------|-----------|-----|
| **HLS** — Historisches Lexikon der Schweiz | 33.506 | Referenzartikel |
| **Archive** — Argovia + SZG (Schweizerische Zeitschrift für Geschichte) | 29.317 | Fachaufsätze (PDF) |
| **SSRQ** — Schweizerische Rechtsquellen | 1.217 | TEI-XML Editionen |
| **Königsfelden** | 634 | TEI-XML Urkundeneditionen |
| **RSS** — infoclio.ch Feeds | 178 | Aktuelle Artikel |
| **PDF** — manuelle Uploads | 21 | Diverses |
| **Total** | **64.873 Dokumente · 84.133 Chunks · 52.799 im FAISS-Index** | |

---

## Features (implementiert)

- **Chat** — Natürlichsprachige Fragen mit Inline-Zitaten (`[n]`-Superscripts, verlinkt auf Quellen)
- **References-Panel** — Vollständige akademische Zitierungen mit DOI-Badges
- **Evidence-Panel** — Aufklappbare Quell-Chunks neben jeder Antwort
- **Semantic Search** — Bedeutungsbasierte Suche (kein LLM, nur FAISS), Relevanz-Scores
- **PDF-Export** — Antwort + vollständige Referenzen als PDF
- **Partners-Tab** — Übersicht der indizierten Quellen
- **About-Tab** — Pipeline-Erklärung und Limitierungen
- **Mehrsprachig** — DE und FR aktiv genutzt

---

## Tech Stack

| Komponente | Tool |
|------------|------|
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector Index | FAISS `IndexFlatIP` (Cosine Similarity, L2-normalisiert) |
| Metadaten | Weaviate + SQLite (`documents`, `chunks`, `faiss_lookup`, `audit_log`) |
| LLM | Gemini 2.0 Flash (Standard) / GPT-4o-mini (Fallback) |
| Backend | FastAPI |
| Frontend | Streamlit |
| PDF | FPDF2 |
| Deployment | Docker Compose + Caddy Reverse Proxy |

---

## Deployment & Betrieb

- **Aktive Entwicklungsphase** (bis 09.03.2026): stündlicher Auto-Deploy-Cron (08:00–22:00 CET)
- **Ab 10.03.2026**: täglicher Health-Check-Cron (06:00 CET)
- **Auto-Deploy:** `git pull` → rebuild API container → Health-Check
- **Logs:** `/var/log/ch-h-bot/deploy.log`, `/var/log/ch-h-bot/daily_check.log`

---

## Datenpartner

| Partner | Inhalt | Status |
|---------|--------|--------|
| **HLS** — Historisches Lexikon der Schweiz | Enzyklopädische Referenzartikel | ✅ indiziert |
| **SZG** — Schweizerische Zeitschrift für Geschichte | Peer-reviewed Fachaufsätze | ✅ indiziert |
| **Argovia** — Hist. Gesellschaft Kanton Aargau | Jahresschrift | ✅ indiziert |
| **SSRQ** — Schweizerische Rechtsquellen | TEI-XML Editionen (Zenodo) | ✅ indiziert |
| **Königsfelden** | TEI-XML Urkundenedition | ✅ indiziert |
| **infoclio.ch** | RSS-Feeds (aktuelle Forschung) | ✅ indiziert |
| **e-rara / e-periodica** | Digitalisierte Bücher + Journals | 📋 geplant |
| **Nationalbibliothek** | Katalog + Authority Records | 📋 geplant |

---

## Roadmap / Offene Punkte

- [ ] **Knowledge Graph Layer** (Entity-aware Retrieval / GraphRAG) — Weaviate-Infrastruktur vorhanden
- [ ] **e-rara / e-periodica** — OAI-PMH Ingestion (Metadaten + Links)
- [ ] **Nationalbibliothek** — OAI-PMH (auf Anfrage)
- [ ] **BibTeX / RIS Export** — Zitier-Export für Forschende
- [ ] **Evaluations-Harness** — 50 Test-Fragen, Zitier-Integrität ≥90%, Halluzination ≤5%
- [ ] **GPUStack UNIBE** — Migration von API-Inferenz auf In-House-Modell
- [ ] **Volltext-Filter in Search** — Datum, Quellentyp, Sprache
- [ ] **chat.hodelweb.ch** — DNS / HTTPS vollständig konfiguriert ✅ (Caddy läuft)

---

## Meeting-Historie

| Datum | Event | Notizen |
|-------|-------|---------|
| 09.03.2026, 13:00 | Austausch infoclio: Swiss History Bot | Hosting-Optionen, Partnerschaft |

---

*Aktualisiert am 08.03.2026 — basierend auf Repository, Live-Deployment und Datenbank-Stand.*
