#!/usr/bin/python3
"""
Normalize entity names using Gemini API.
Converts historical names to modern German.
"""

import json
import time
import requests
from pathlib import Path
import re

ENTITIES_FILE = Path("/home/th/repos/reformation/data/entities/named_entities.json")
BATCH_SIZE = 10
DELAY = 1.0

def load_api_key():
    env_path = Path("/home/th/repos/outremer/.env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("GOOGLE_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return None

def normalize_name(api_key, name):
    """Normalize a historical name to modern German."""
    prompt = f"""Normalisiere den historischen Namen "{name}" auf moderne deutsche Schreibweise.
Gib nur den modernen Namen zurück, ohne Erklärung.
Beispiele:
- "Zwingkl" → "Ulrich Zwingli"
- "Hallerus" → "Berchtold Haller"  
- "Capito" → "Wolfgang Capito"
- "Joachim von Watt" → "Joachim von Watt"
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 50}
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            # Clean up the response
            text = text.strip().strip('"').strip()
            # Remove any explanation
            if '\n' in text:
                text = text.split('\n')[0]
            return text if text else name
        return name
    except Exception as e:
        print(f"Error normalizing {name}: {e}")
        return name

def main():
    api_key = load_api_key()
    if not api_key:
        print("ERROR: No API key found")
        return
    
    with open(ENTITIES_FILE, 'r') as f:
        entities = json.load(f)
    
    # Get persons that need normalization
    persons = [e for e in entities if e.get("type") == "PERSON"]
    # Normalize all persons (overwrite existing)
    to_normalize = persons
    
    print(f"Found {len(persons)} persons, {len(to_normalize)} need normalization")
    
    # Normalize in batches
    for i, person in enumerate(to_normalize):
        original = person.get("name", "")
        if len(original) < 3:  # Skip very short names
            continue
            
        print(f"[{i+1}/{len(to_normalize)}] Normalizing: {original}")
        normalized = normalize_name(api_key, original)
        
        if normalized and normalized != original:
            person["normalized_name"] = normalized
            print(f"  -> {normalized}")
        
        # Rate limiting
        time.sleep(DELAY)
        
        # Save progress periodically
        if (i + 1) % 50 == 0:
            with open(ENTITIES_FILE, 'w') as f:
                json.dump(entities, f, ensure_ascii=False, indent=2)
            print(f"Progress saved at {i+1}")
    
    # Final save
    with open(ENTITIES_FILE, 'w') as f:
        json.dump(entities, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Normalized {len(to_normalize)} names")

if __name__ == "__main__":
    main()
