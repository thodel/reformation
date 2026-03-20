#!/usr/bin/python3
"""
Metagrid linker for extracted Named Entities.
Queries Metagrid API for persons found in named_entities.json.
"""

import json
import time
import requests
from pathlib import Path

ENTITIES_FILE = Path("/home/th/repos/reformation/data/entities/named_entities.json")

def call_metagrid(name):
    """Search Metagrid for a person name."""
    # We might need to handle name splitting or variations later, 
    # but for now we search the exact string or words.
    url = f"https://api.metagrid.ch/search?q={name}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return {}
    except Exception as e:
        print(f"Metagrid error for {name}: {e}")
        return {}

def main():
    if not ENTITIES_FILE.exists():
        print("named_entities.json not found!")
        return

    with open(ENTITIES_FILE, 'r') as f:
        entities = json.load(f)

    persons = [e for e in entities if e.get("type") == "PERSON"]
    print(f"Found {len(persons)} persons to check against Metagrid.")

    updates = 0
    for i, person in enumerate(persons):
        if person.get("metagrid_id"):
            continue  # Already linked
        
        name = person.get("normalized_name") or person.get("name", "")
        if not name or len(name) < 4:
            continue
            
        print(f"[{i+1}/{len(persons)}] Checking Metagrid for: {name} (original: {person.get('name')})")
        result = call_metagrid(name)
        
        if result and result.get("resources"):
            matched = False
            for res in result["resources"][:5]:
                meta = res.get("metadata", {})
                first_name = meta.get("first_name", "").lower()
                last_name = meta.get("last_name", "").lower()
                search_name = name.lower()
                
                if search_name in f"{first_name} {last_name}" or last_name in search_name:
                    if len(last_name) > 3:
                        person["metagrid_id"] = res.get("identifier")
                        person["normalized_name"] = f"{meta.get('first_name','')} {meta.get('last_name','')}".strip()
                        print(f"  -> Linked to: {person['normalized_name']} ({person['metagrid_id']})")
                        updates += 1
                        matched = True
                        break
            
            if not matched:
                print(f"  -> No good match found")
        
        time.sleep(0.5)

    if updates > 0:
        print(f"Updated {updates} entities with Metagrid IDs. Saving...")
        with open(ENTITIES_FILE, 'w') as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)
    else:
        print("No new Metagrid links found.")

if __name__ == "__main__":
    main()
