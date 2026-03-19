# Projekt: Introduction to Humanities Data Science

**Kurzname:** Intro HDS  
**Kalender-Stichwort:** `Intro HDS` · `Humanities Data Science` · `Einführung Data Science`

## Projektübersicht

Hands-on Reader/Einführung in Data Science für Geisteswissenschaftler:innen. Ziel ist es, Studierenden praktische Kompetenzen im Umgang mit digitalen Methoden und Datenanalyse zu vermitteln — angewendet auf geisteswissenschaftliche Fragestellungen.

**Format:** Reader (Beitragssammlung) statt modularer Kurs  
**Sprache:** Deutsch  
**Programmiersprache:** Python

## Zielgruppe

- BA-Studierende Geisteswissenschaften (ab 2. Semester)
- MA-Studierende ohne Vorkenntnisse in Data Science
- Doktorierende, die digitale Methoden erlernen möchten

## Lernziele

Nach Arbeit mit dem Reader können die Teilnehmenden:

1. **Daten erfassen und aufbereiten**
   - Strukturierte vs. unstrukturierte Daten
   - Datenbereinigung und -transformation
   - Metadaten-Standards (TEI-XML, CSV, JSON)

2. **Daten analysieren und visualisieren**
   - Explorative Datenanalyse (EDA)
   - Statistische Grundbegriffe
   - Visualisierung mit Python (Matplotlib, Seaborn)

3. **Textanalyse-Methoden anwenden**
   - Tokenisierung, Stemming, Lemmatisierung
   - Häufigkeitsanalysen, Kookkurrenzen
   - Topic Modeling (LDA)
   - Named Entity Recognition (NER)

4. **Reproduzierbar arbeiten**
   - Versionskontrolle mit Git
   - Jupyter Notebooks
   - Dokumentation und Datenmanagement

## Reader-Konzept

Statt eines modularen Kurses entsteht eine **Beitragssammlung (Reader)** mit dedizierten Kapiteln zu spezifischen Methoden und Anwendungsfällen. Jeder Beitrag behandelt einen in sich geschlossenen Ansatz mit:

- Theoretische Einführung (kurz, praxisorientiert)
- Python-Codebeispiele (Jupyter Notebook)
- Geisteswissenschaftliches Anwendungsbeispiel
- Weiterführende Literatur

### Mögliche Themen/Beiträge (strukturiert nach Oberthemen)

#### 1. Data/Capta → Epistemologie
*Grundlagen: Was sind geisteswissenschaftliche Daten? Wie entstehen sie? Welche erkenntnistheoretischen Implikationen hat die Datifizierung?*

| Unterkapitel | Inhalt | Mögliche Autor:innen | Status |
|--------------|--------|---------------------|--------|
| 1.1 Daten vs. Capta | Druckers Unterscheidung: Daten sind nicht "gegeben", sondern "genommen" (konstruiert) | TBD | Brainstorming |
| 1.2 Hermeneutik und Algorithmus | Verhältnis von interpretativer und quantitativer Erkenntnis | TBD | Brainstorming |
| 1.3 Bias in Daten und Modellen | Kritische Reflexion von Trainingsdaten, Kategorien, Klassifikationen | TBD | Brainstorming |
| 1.4 Digitale Quellenkritik | Wie bewertet man digital aufbereitete Quellen? Metadaten, Provenienz, Versionierung | TBD | Brainstorming |
| 1.5 Ethik der Digital Humanities | Datenschutz, Urheberrecht, faire Nutzung, Dekolonisierung digitaler Sammlungen | TBD | Brainstorming |

#### 2. Korpusbildung → Heuristik
*Grundlagen: Wie entsteht ein digitales Korpus? Welche Entscheidungen treffen wir bei der Zusammenstellung, Aufbereitung und Annotation?*

| Unterkapitel | Inhalt | Mögliche Autor:innen | Status |
|--------------|--------|---------------------|--------|
| 2.1 Korpusdesign | Repräsentativität, Sampling, Abgrenzung eines Korpus | TBD | Brainstorming |
| 2.2 Digitalisierung und OCR/HTR | Von der analogen Quelle zum digitalen Text (Transkribus, eScriptorium) | TBD | Brainstorming |
| 2.3 Datenbereinigung mit Pandas | Umgang mit fehlenden Werten, Duplikaten, Inkonsistenzen | TBD | Brainstorming |
| 2.4 Metadaten-Standards | TEI-XML, Dublin Core, CIDOC-CRM — wann welcher Standard? | TBD | Brainstorming |
| 2.5 Annotation und Tagging | Manuelle vs. automatische Annotation, Inter-Annotator-Agreement | TBD | Brainstorming |
| 2.6 API-Zugriffe | Daten sammeln von Zotero, Europeana, HLS, SSRQ, GitHub | TBD | Brainstorming |

#### 3. Algorithmisierung → Methodologie
*Grundlagen: Welche Methoden stehen zur Verfügung? Wie funktionieren sie? Wann sind sie angemessen?*

| Unterkapitel | Inhalt | Mögliche Autor:innen | Status |
|--------------|--------|---------------------|--------|
| 3.1 Python-Grundlagen für Geisteswissenschaftler:innen | Variablen, Schleifen, Funktionen, Libraries (Pandas, NLTK, spaCy) | TBD | Brainstorming |
| 3.2 Textvorverarbeitung | Tokenisierung, Stemming, Lemmatisierung, Stopwords | TBD | Brainstorming |
| 3.3 Explorative Datenanalyse (EDA) | Deskriptive Statistik, Verteilungen, Ausreisser | TBD | Brainstorming |
| 3.4 Topic Modeling (LDA, BERTopic) | Unsupervised Learning für Textkorpora | TBD | Brainstorming |
| 3.5 Named Entity Recognition (NER) | Personen, Orte, Organisationen automatisch erkennen | TBD | Brainstorming |
| 3.6 Netzwerkanalyse für Historiker:innen | Graphen, Zentralitätsmaße, Community Detection (NetworkX) | TBD | Brainstorming |
| 3.7 Maschinelles Lernen im Überblick | Supervised vs. Unsupervised, Klassifikation, Clustering | TBD | Brainstorming |

#### 4. Auswertung/Visualisierung → Kommunikation
*Grundlagen: Wie werden Ergebnisse aufbereitet, visualisiert und kommuniziert?*

| Unterkapitel | Inhalt | Mögliche Autor:innen | Status |
|--------------|--------|---------------------|--------|
| 4.1 Visualisierung mit Matplotlib/Seaborn | Grundprinzipien guter Datenvisualisierung | TBD | Brainstorming |
| 4.2 Interaktive Visualisierung | Plotly, Altair, Observable — wenn Statik nicht reicht | TBD | Brainstorming |
| 4.3 Karten und Geovisualisierung | GIS für Geisteswissenschaftler:innen (QGIS, Folium, Leaflet) | TBD | Brainstorming |
| 4.4 Narration mit Daten | Vom Befund zur Geschichte — Ergebnisse erzählen | TBD | Brainstorming |
| 4.5 Reproduzierbare Publikation | Jupyter Books, RMarkdown, Versionierung mit Git/GitHub | TBD | Brainstorming |
| 4.6 Public Humanities | Wie kommuniziert man DH-Ergebnisse ausserhalb der Wissenschaft? | TBD | Brainstorming |

## Technische Infrastruktur

- **Programmiersprache:** Python
- **Umgebung:** JupyterHub (Uni Bern) oder Google Colab
- **Versionskontrolle:** GitHub (Education Account)
- **Daten:** Open-Access-Datensätze (HLS, SSRQ, e-periodica)
- **Sprache:** Deutsch

## Materialien

- **Reader:** Dieses Dokument + begleitende Jupyter Notebooks
- **Übungsdaten:** `/data/` Ordner mit Beispiel-Datensätzen

### Literatur (aus Zotero-Bibliothek)

#### Grundlagen & Einführung
- Fitzpatrick, K. (2011). *Debates in the Digital Humanities*
- Svensson, P. (2016). *Big Digital Humanities. Imagining a meeting place for the humanities and the digital*
- Drucker, J. (2019). *The Digital Humanities Coursebook: Applied Concepts and Critical Approaches*
- Gold, M. K., & Klein, L. F. (2018). *Debates in the Digital Humanities*

#### Epistemologie & Theorie
- Drucker, J. (2011). "Humanistic Theory and Digital Scholarship" — *Data as Capta*
- Geyrhalter, L. et al. (2021). *Digital Humanities im deutschsprachigen Raum*
- "Ground Truth: Grundwahrheit oder Ad-Hoc-Lösung? Wo stehen die Digital Humanities"
- "Theorie und Digital Humanities – Eine Bestandsaufnahme"

#### Methoden & Praxis
- *Digital Methods in the Humanities. Challenges, Ideas, Perspectives*
- "Fünf Herausforderungen digitaler Methoden, oder: Ranke re-visited"
- "Text‐Mining the Humanities"
- "Inducing linguistic networks from historical corpora. Towards a new method in history"
- "Usability-Analyse von digitalen Tools und Methoden in den Geisteswissenschaften"

#### Digitale Infrastrukturen
- "If you build it, will we come? Large scale digital infrastructures as a dead end"
- *The Routledge Companion to Digital Humanities and Art History*
- "Communities of practice, the methodological commons, and digital self-determination"

### Open Educational Resources (OER) & Initiativen

#### Europäische Infrastrukturen
| Initiative | Angebot | Link |
|------------|---------|------|
| **DARIAH Campus** | OER-Plattform für Digital Humanities, Kurse zu Digital Cultural Heritage, Data Modelling, Europeana APIs | https://campus.dariah.eu/ |
| **CLARIN Learning Hub** | Sprachressourcen, Online-Trainingsmodule, Materialien für DH-Kurse | https://www.clarin.eu/content/learning-hub |
| **CLARIN-DARIAH Course Registry** | Globale Übersicht über DH-Lehrveranstaltungen (nach Disziplin, Ort, ECTS, TaDiRAH-Taxonomie) | https://www.clarin.eu/content/digital-humanities-course-registry |
| **SSH Open Marketplace** | Training-Materialien zu Social Sciences & Humanities | https://marketplace.sshopencloud.eu/training-material |

#### Deutschsprachige Angebote
| Initiative | Angebot | Link |
|------------|---------|------|
| **DH Lab Freiburg** | Liste kostenloser Online-Kurse (DH, Statistik, Informatik) | https://digitalhumanities.uni-freiburg.de/dh-zertifikat/links-ressources/ |
| **ACDH-OEAW (Wien)** | YouTube-Kanal mit Vorlesungen, Tool Galleries, Training Schools | https://www.oeaw.ac.at/de/acdh/wissenstransfer/online-lernmaterialien |
| **iMooX.at** | MOOC-Plattform, u.a. "Einführung in die Digital Humanities" (CC BY-SA 4.0) | https://imoox.at/ |
| **digiLL** | Lernmodul "Einführung in Open Educational Resources" (45 Min., CC BY-SA 4.0) | https://digill.de/course/einfuehrung-in-die-open-educational-resources/ |
| **TU Dresden** | Ringvorlesung "Grundlagen und anwendungsorientierte Methoden der DH" (WS 2022) | YouTube |

#### Englischsprachige Angebote
| Initiative | Angebot | Link |
|------------|---------|------|
| **Programming Historian** | Peer-reviewed Tutorials zu DH-Methoden (Python, R, Netzwerkanalyse, NLP) | https://programminghistorian.org/ |
| **The Turing Institute** | Humanities and Data Science Research Group | https://www.turing.ac.uk/research/interest-groups/humanities-and-data-science |
| **Stanford Data Science & Humanity** | Forschungsprojekte an der Schnittstelle DH/Data Science | https://datascience.stanford.edu/research/research-areas/data-science-humanity |
| **Berkeley Data Arts & Humanities** | Domain Emphasis im Data Science Major | https://cdss.berkeley.edu/degrees/domain-emphasis/data-arts-and-humanities |

#### Rezensionen & Kritische Diskussionen
- DHQ: Digital Humanities Quarterly — "Why Digital Humanists Should Emphasize Situated Knowledge"
- DHQ: "Digital Humanities and Natural Language Processing: Je t'aime... Moi non plus"
- "New methods need a new kind of conversation"
- "Toward a Critical Black Digital Humanities"
- "Bodies of Information: Intersectional Feminism and the Digital Humanities"

## Dozierende

- **Verantwortlich:** Prof. Dr. Tobias Hodel, Universität Bern, DH
- **Beitragende:** Nach Bedarf (Autor:innen für dedizierte Kapitel)

## Zeitplan & Termine

| Datum | Ereignis | Notizen |
|-------|----------|---------|
| **23. März 2026** | **Besprechung Book/Reader** | Konzept, Autor:innen, Struktur |
| TBD | Autor:innen-Anfrage | Brainstorming-Liste erstellen |
| TBD | Beitragseinreichungen | First drafts |
| TBD | Review & Überarbeitung | Peer-Review der Kapitel |
| TBD | Publikation | Online + Print? |

## Notizen & Besprechungen

### Besprechung vom 5. März 2026

**Entscheidungen:**
- Format: **Reader** (Beitragssammlung) statt modularer Kurs
- Sprache: **Deutsch** (nicht Englisch)
- Programmiersprache: **Python** (nicht Python/R parallel)
- **Nächstes Meeting:** 23. März 2026 (Book-Besprechung)

**Offene Punkte:**
- [ ] Brainstorming-Liste für potenzielle Autor:innen erstellen
- [ ] Themenstruktur für Reader festlegen
- [ ] Zielumfang klären (Anzahl Beiträge, Seitenumfang)
- [ ] Publikationsweg klären (Open Access, Verlag?)

### Nächste Schritte

1. **Vor 23. März:**
   - ✅ Literatur-Review abgeschlossen (Zotero + OER-Initiativen)
   - ✅ Themenstruktur erstellt (4 Oberthemen, 25 Unterkapitel)
   - [ ] Brainstorming-Liste potenzieller Autor:innen vorbereiten (nach Themenbereichen)
   - [ ] Zielumfang klären (Anzahl Beiträge, Seitenumfang pro Kapitel)

2. **23. März:** Konzeptbesprechung
   - Themenstruktur präsentieren
   - Autor:innen-Liste diskutieren
   - Timeline festlegen
   - Publikationsweg klären (Open Access, Verlag, Self-Publishing)

3. **Nach 23. März:**
   - Autor:innen anfragen (mit Kapitelbeschreibung)
   - Beitragsstruktur finalisieren
   - Styleguide erstellen (Zitierweise, Code-Style, Lizenzierung)

## Links

- **Nextcloud-Ordner:** https://cloud.hodelweb.ch/apps/files/?dir=/projects
- **GitHub Repo:** TBD (wird eingerichtet)
- **JupyterHub:** https://jupyterhub.unibe.ch (Zugang wird beantragt)

---

*Erstellt: 5. März 2026*  
*Letzte Aktualisierung: 5. März 2026, 20:30 UTC*  
**Updates:** Literatur-Review (Zotero + OER), Themenstruktur (4 Oberthemen, 25 Unterkapitel)
