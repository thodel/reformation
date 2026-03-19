#!/usr/bin/python3
"""
NER Extraction Script for Reformation Disputations
Extracts named entities (persons, places, organizations) from transcriptions.
Uses Gemini API for NER.
"""

import os
import json
import time
import requests
from pathlib import Path
from collections import defaultdict

# Configuration
DATA_DIR = Path("/home/th/repos/reformation/data/disputation")
OUTPUT_DIR = Path("/home/th/repos/reformation/data/entities")
BATCH_SIZE = 5  # Pages per API call
DELAY_BETWEEN_CALLS = 2.0  # Seconds

# Documents to process
DOCUMENTS = [
    "druck_1528",
    "a_v_1443_hertwig",
    "a_v_1444_cyro",
    "a_v_1445_schoeni",
    "a_v_1446_ruemlang",
    "a_v_1447_schlussredaktion"
]


def load_api_key():
    """Load Google API key from .env file"""
    env_path = Path("/home/th/repos/outremer/.env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("GOOGLE_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return None


def call_gemini(api_key, texts_with_pages):
    """Call Gemini API to extract named entities from a batch of texts."""
    # Combine texts with page context
    combined_text = "\n\n---\n\n".join([
        f"[Seite {page} von {doc_id}]\n{text[:1500]}"
        for doc_id, page, text in texts_with_pages
    ])
    
    prompt = f"""Extrahiere alle Named Entities aus dem folgenden Text der Berner Disputation von 1528.
Gib das Ergebnis als JSON-Array zurück ohne zusätzlichen Text.

JSON-Format pro Entität:
{{"name": "Name", "type": "PERSON|ORG|LOC|GPE", "doc": "dokument_id", "page": seitenzahl}}

Extrahiere: Personen (Vorname Nachname), Organisationen (Ämter, Institutionen), Orte (Städte, Dörfer), geopolitische Entitäten (Kantone, Regionen).

Text:
{combined_text}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4000
        }
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return extract_json_from_response(text)
        else:
            print(f"Error: {resp.status_code} - {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"Exception: {e}")
        return []


def extract_json_from_response(text):
    """Extract JSON array from Gemini response."""
    import re
    # Find JSON array in response
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            try:
                # Remove trailing commas
                fixed = re.sub(r',\s*]', ']', match.group(0))
                return json.loads(fixed)
            except:
                pass
    return []


def process_document(doc_id, api_key, max_pages=20, force=False):
    """Process a single document - extract entities from transcriptions."""
    doc_dir = DATA_DIR / doc_id
    transcriptions = sorted(doc_dir.glob("transcriptions/page_*.md"))
    
    print(f"Processing {doc_id}: {len(transcriptions)} transcriptions")
    
    # Load existing entities if not forcing
    output_file = OUTPUT_DIR / f"{doc_id}_entities.json"
    if output_file.exists() and not force:
        with open(output_file) as f:
            existing = json.load(f)
        processed_pages = set((e.get("doc"), e.get("page")) for e in existing)
    else:
        existing = []
        processed_pages = set()
    
    # Collect pages to process
    pages_to_process = []
    for trans_file in transcriptions[:max_pages]:  # Limit for testing
        # Handle files like page_1_gemini.md -> extract 1
        stem = trans_file.stem.replace("page_", "")
        stem = stem.replace("_gemini", "")
        page_num = int(stem)
        if (doc_id, page_num) not in processed_pages:
            with open(trans_file) as f:
                text = f.read()
            # Skip empty or placeholder pages
            if len(text.strip()) > 20:
                pages_to_process.append((doc_id, page_num, text))
    
    print(f"  Pages to process: {len(pages_to_process)}")
    
    # Process in batches
    all_entities = existing.copy()
    
    for i in range(0, len(pages_to_process), BATCH_SIZE):
        batch = pages_to_process[i:i+BATCH_SIZE]
        print(f"  Processing batch {i//BATCH_SIZE + 1}/{(len(pages_to_process)+BATCH_SIZE-1)//BATCH_SIZE}...")
        
        entities = call_gemini(api_key, batch)
        all_entities.extend(entities)
        
        # Rate limiting
        if i + BATCH_SIZE < len(pages_to_process):
            time.sleep(DELAY_BETWEEN_CALLS)
    
    # Save intermediate results
    with open(output_file, "w") as f:
        json.dump(all_entities, f, ensure_ascii=False, indent=2)
    
    print(f"  Saved {len(all_entities)} entities to {output_file}")
    return all_entities


def merge_entities(entity_lists):
    """Merge entities from multiple documents, deduplicating by name."""
    merged = defaultdict(lambda: {"name": "", "type": "", "occurrences": [], "metagrid_id": None})
    
    for entities in entity_lists:
        for ent in entities:
            name = ent.get("name", "").strip()
            if not name:
                continue
            
            # Normalize name (simple lowercase for now)
            key = name.lower()
            
            merged[key]["name"] = name
            merged[key]["type"] = ent.get("type", "PERSON")
            merged[key]["occurrences"].append({
                "doc": ent.get("doc"),
                "page": ent.get("page"),
                "context": ent.get("context", "")[:100] if ent.get("context") else ""
            })
    
    return list(merged.values())


def main():
    """Main function."""
    print("NER Extraction for Reformation Disputations")
    print("=" * 50)
    
    api_key = load_api_key()
    if not api_key:
        print("ERROR: No API key found")
        return
    
    print(f"API Key loaded: {api_key[:10]}...")
    
    # Ensure output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Process each document (limited to 20 pages each for testing)
    all_entities = []
    for doc_id in DOCUMENTS:
        print(f"\nProcessing {doc_id}...")
        entities = process_document(doc_id, api_key, max_pages=20)
        all_entities.append(entities)
    
    # Merge entities
    print("\nMerging entities...")
    merged = merge_entities(all_entities)
    
    # Save final index
    output_file = OUTPUT_DIR / "named_entities.json"
    with open(output_file, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    
    print(f"\nDone! Saved {len(merged)} unique entities to {output_file}")
    
    # Print statistics
    persons = sum(1 for e in merged if e.get("type") == "PERSON")
    orgs = sum(1 for e in merged if e.get("type") == "ORG")
    places = sum(1 for e in merged if e.get("type") in ("LOC", "GPE"))
    
    print(f"  Persons: {persons}")
    print(f"  Organizations: {orgs}")
    print(f"  Places: {places}")


if __name__ == "__main__":
    main()
