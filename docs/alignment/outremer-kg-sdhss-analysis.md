# Outremer KG → SDHSS Ontology: Migration Feasibility Analysis

**Date:** 2026-03-09  
**Prepared by:** cl-bot  
**Ontology source:** https://ontome.net/namespace/365 (downloaded 2026-03-09)  
**Data source:** `/home/th/repos/outremer/data/unified_kg.json` + `unified_kg.ttl`

---

## 1. Current State of the Data

### Corpus
| Metric | Value |
|---|---|
| Total persons | 19,085 |
| From own authority file (AUTH:CRx) | 126 |
| From Wikidata | 18,359 |
| With bio data (birth/death/gender) | 18,959 (99%) |
| With relationships | 18,332 (96%) |
| With roles/titles | 2,729 (14%) |
| With place data | 86 (0.5%) |

### Relationship network (dense)
- Child relations: 51,160
- Parent relations: 35,591
- Spouse relations: 20,135

### Existing TTL format (problem)
The current `unified_kg.ttl` already uses an `sdhss:` prefix — but **it is NOT the real SDHSS ontology**. It uses flat, custom properties like `sdhss:Person`, `sdhss:preferredLabel`, `sdhss:variantName`, `sdhss:title_seatPlace`, etc. These are local inventions that borrow the SDHSS name without following the actual ontome.net/365 model. This is the core issue to fix.

---

## 2. The Real SDHSS Ontology (ontome.net/365)

SDHSS is a **layered ontology** combining:
- **CIDOC-CRM** (E-classes) — the event-centric cultural heritage standard
- **FRBRoo** (F-classes) — bibliographic model
- **CRMdig** (D-classes) — digital provenance
- **CRMsci** (S-classes) — scientific observation
- **SDHSS core** — social history extensions (C-classes, e.g. C38 Person Appellation, C75 Person Classification)
- **SDHSS crm-supplement** — additional social science concepts

Key design principle: **everything is an event**. Persons don't simply "have" attributes — attributes are assigned through events with time-spans, sources, and epistemic qualifiers.

---

## 3. Migration Mapping

### 3.1 Persons

| Current (flat) | SDHSS/CRM mapping | Class/Property |
|---|---|---|
| `sdhss:Person` | `crm:E21_Person` | ✅ direct |
| `sdhss:preferredLabel` | `C38 Person Appellation in a Language` + `C39 type = "preferred"` | via appellation event |
| `sdhss:variantName` | `C38 Person Appellation in a Language` + `C39 type = "variant"` | multiple instances |
| `sdhss:outremerAuthorityId` | `crm:E42_Identifier` assigned via `crm:E15_Identifier_Assignment` | |
| `wikidata_qid` | `owl:sameAs <http://www.wikidata.org/entity/Qxxx>` or `crm:E42_Identifier` | ✅ simple |

### 3.2 Biographical data

| Current | SDHSS/CRM mapping | Notes |
|---|---|---|
| `bio.birth.date` | `crm:E67_Birth` → `crm:P4_has_time-span` → `crm:E52_Time-Span` | ✅ |
| `bio.death.date` | `crm:E69_Death` → `crm:P4_has_time-span` → `crm:E52_Time-Span` | ✅ |
| `bio.floruit` | `crm:E52_Time-Span` on an `E7_Activity` or `C3_Epistemic_Situation` | approximate; less obvious |
| `bio.gender` | `crm:E55_Type` or `C6_Social_Quality` referenced from the person | commonly modeled as E55 |

### 3.3 Relationships (most complex)

CIDOC-CRM is deliberately **event-centric** for family relations:

| Relationship | SDHSS/CRM event-based approach |
|---|---|
| `parent` / `child` | `E67_Birth` with `P96_by_mother (E21)` and `P97_from_father (E21)` → `P98_brought_into_life (E21)` |
| `spouse` | `E85_Joining` into a `E74_Group` (family group), or custom `C25_Intentional_Collective` |
| Alternative simpler approach | `crm:P152_has_parent` (CRM shortcut property, available in CRM v7.1+) |

**Recommendation:** Use `crm:P152_has_parent` shortcuts for parent-child (avoids creating ~50K birth event nodes), and model marriages as `E85_Joining` a family group only for the 126 authority-file persons where source evidence matters. For the Wikidata bulk data, shortcuts are pragmatic and standard.

### 3.4 Roles / Titles

| Current | SDHSS/CRM mapping |
|---|---|
| `roles[].type = "title"` + label | `E85_Joining` → `E74_Group` (the title/office as a group) with `C75_Person_Classification` typing |
| Title label | `E74_Group` carrying an `E35_Title` appellation |

Example: "member of the House of Lords" → person `E85_Joining` → `E74_Group` (House of Lords) typed as `C9_Group_Type`.

### 3.5 Places

| Current | SDHSS/CRM mapping |
|---|---|
| `places[].type = "title_seat"` + label | `C13_Geographical_Place` (SDHSS) or `crm:E53_Place` with label + `C14_Geographical_Place_Type` |
| Link to person | via `E85_Joining` (person joins a group associated with a place) or `C75_Person_Classification` with place reference |

Note: Only 86 entries have place data — manageable as full events.

### 3.6 Provenance

| Current | SDHSS/CRM mapping |
|---|---|
| `provenance.sources[].source_file` | `crm:E13_Attribute_Assignment` with `crm:P17_was_motivated_by` → source document |
| `provenance.sources[].confidence` | `CRMsci:S4_Observation` + quantifiable quality, or custom `xsd:decimal` annotation |
| `created_at` / `updated_at` | `crm:E65_Creation` + `crm:E52_Time-Span` |

---

## 4. Data Gaps & Challenges

### 4.1 Sparse data problem
- Places: only 86 entries (0.5%) — not yet useful for spatial analysis
- Roles: only 14% have titles — mostly Wikidata-sourced, not validated
- Bio dates come from Wikidata (often approximate, formatted as year-only or `YYYY-01-01` fallback)

### 4.2 Event-centric overhead
Full SDHSS modeling of 19K persons with events for each birth, death, naming, and relationship creates **~200K–500K triples**. This is fine for a triplestore like Fuseki or GraphDB, but requires a proper conversion script. The current 8.67MB TTL would grow to ~50–150MB depending on depth of event modeling.

### 4.3 Source attribution
The 126 authority-file persons (AUTH:CRx) come from Outremer XML source files — these merit full event-based modeling with `E13_Attribute_Assignment` linking back to the source document. The 18K Wikidata persons can use shortcut properties since Wikidata itself is the source.

### 4.4 Floruit
No direct SDHSS/CRM class for "active period". Best option: a `C3_Epistemic_Situation` scoped to the person for the given time-span, or simply an `E52_Time-Span` annotation typed as "floruit". This needs a design decision.

---

## 5. Feasibility Verdict

**Migration is feasible and well-supported.** The data maps cleanly to SDHSS/CRM. 

| Aspect | Feasibility | Effort |
|---|---|---|
| Person entities | ✅ Easy | Low |
| Name appellations | ✅ Easy | Low |
| Birth/Death events | ✅ Easy | Low |
| Parent-child relationships | ✅ Easy (with P152 shortcuts) | Low |
| Spouse/family | ⚠️ Moderate (group events) | Medium |
| Roles/titles | ⚠️ Moderate (group membership model) | Medium |
| Places | ✅ Easy (few entries) | Low |
| Full event provenance | ⚠️ Complex (only justified for AUTH: 126 persons) | High |
| Wikidata provenance | ✅ Easy (owl:sameAs) | Low |

### Recommended phased approach:
1. **Phase 1 (Quick win):** Convert all 19K persons to proper `crm:E21_Person` + `C38` appellations + `E67/E69` birth/death events + `P152` parent shortcuts + `owl:sameAs` for Wikidata. Fixes the fake-SDHSS TTL, gets real CRM alignment.
2. **Phase 2 (Richer model):** Roles as group memberships, places as `C13`, full provenance for the 126 authority persons.
3. **Phase 3 (Research value):** Epistemic qualifiers (`C3 Epistemic Situation`), source criticism modeling, integration with actual crusade event timeline.

---

## 6. Key SDHSS URIs for the mapping

```
crm:E21_Person       → http://www.cidoc-crm.org/cidoc-crm/E21_Person
crm:E67_Birth        → http://www.cidoc-crm.org/cidoc-crm/E67_Birth
crm:E69_Death        → http://www.cidoc-crm.org/cidoc-crm/E69_Death
crm:E52_Time-Span    → http://www.cidoc-crm.org/cidoc-crm/E52_Time-Span
crm:E74_Group        → http://www.cidoc-crm.org/cidoc-crm/E74_Group
crm:E85_Joining      → http://www.cidoc-crm.org/cidoc-crm/E85_Joining
crm:E42_Identifier   → http://www.cidoc-crm.org/cidoc-crm/E42_Identifier
crm:P152_has_parent  → http://www.cidoc-crm.org/cidoc-crm/P152_has_parent
C38 Person Appellation in a Language → https://sdhss.org/ontology/core/1.2/C38
C75 Person Classification            → https://sdhss.org/ontology/core/1.2/C75
C13 Geographical Place               → https://sdhss.org/ontology/core/1.2/C13
```

---

## 7. Next Steps (for evening session)

- [ ] Decide modeling strategy for spouse/family relations (joint E74 group vs. custom property)
- [ ] Decide floruit encoding
- [ ] Write conversion script: `unified_kg.json` → proper SDHSS/CRM Turtle
- [ ] Test with a sample of 50 persons in Fuseki with SPARQL validation
- [ ] Check if Geovistory or nodegoat (common SDHSS-aware tools) could be a front-end target

Kalender-Stichwort: outremer-kg-sdhss-analysis
