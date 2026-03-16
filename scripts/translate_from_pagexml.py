#!/usr/bin/env python3
"""Translate transcriptions from pagexml files using Gemini.

This script extracts text from pagexml files and translates them to modern German.
"""

import os
import sys
import xml.etree.ElementTree as ET
import requests
import time

# Config
VARIANT = "a_v_1447_schlussredaktion"
BASE_PATH = "/home/th/repos/reformation/data/disputation"
VARIANT_PATH = os.path.join(BASE_PATH, VARIANT)
PAGEXML_DIR = os.path.join(VARIANT_PATH, "pagexml")
TRANSLATIONS_DIR = os.path.join(VARIANT_PATH, "translations")
GEMINI_MODEL = "gemini-2.0-flash"

# Ensure translations directory exists
os.makedirs(TRANSLATIONS_DIR, exist_ok=True)


def extract_text_from_pagexml(xml_path):
    """Extract all text lines from a pagexml file."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Get namespace
    ns = {'page': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}
    
    # Get all text lines
    text_lines = root.findall('.//page:TextLine', ns)
    
    texts = []
    for line in text_lines:
        unicode_elem = line.find('.//page:Unicode', ns)
        if unicode_elem is not None and unicode_elem.text:
            texts.append(unicode_elem.text)
    
    return texts


def translate_text(texts, api_key):
    """Translate text lines via Gemini."""
    if not texts:
        return ""
    
    # Join texts with newlines
    full_text = "\n".join(texts)
    
    # Skip if too long
    if len(full_text) > 15000:
        # Split into chunks
        chunks = [full_text[i:i+15000] for i in range(0, len(full_text), 15000)]
        translated_chunks = []
        for chunk in chunks:
            translated = translate_text([chunk], api_key)
            translated_chunks.append(translated)
        return "\n".join(translated_chunks)
    
    prompt = f"""Übersetze den folgenden frühneuhochdeutschen Text ins moderne Deutsch.
Behalte die Zeilenstruktur bei. Übersetze jede Zeile einzeln.

Text:
{full_text}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    else:
        print(f"Error: {response.status_code} - {response.text[:200]}")
        return None


def translate_page(page_num, api_key):
    """Translate a single page."""
    xml_path = os.path.join(PAGEXML_DIR, f"page_{page_num}.xml")
    output_path = os.path.join(TRANSLATIONS_DIR, f"page_{page_num}.md")
    
    # Check if already translated
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if content.strip() and len(content) > 50:
            print(f"  Page {page_num}: already translated")
            return True
    
    # Extract text
    try:
        texts = extract_text_from_pagexml(xml_path)
    except Exception as e:
        print(f"  Page {page_num}: error extracting text: {e}")
        return False
    
    if not texts:
        print(f"  Page {page_num}: no text found")
        return False
    
    # Translate
    print(f"  Page {page_num}: translating ({len(texts)} lines)...")
    translation = translate_text(texts, api_key)
    
    if translation:
        # Save
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# Seite {page_num}\n\n")
            f.write(translation)
        
        print(f"  Page {page_num}: saved")
        return True
    else:
        print(f"  Page {page_num}: translation failed")
        return False


def main():
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        print("Error: GEMINI_API_KEY not set")
        sys.exit(1)
    
    # Get list of pagexml files
    pagexml_files = sorted([f for f in os.listdir(PAGEXML_DIR) if f.endswith('.xml')])
    
    # Extract page numbers
    page_nums = sorted([int(f.replace('page_', '').replace('.xml', '')) for f in pagexml_files])
    
    print(f"Found {len(page_nums)} pages to translate")
    print(f"Variant: {VARIANT}")
    
    # Translate pages
    translated = 0
    failed = 0
    
    for i, page_num in enumerate(page_nums):
        if i > 0 and i % 10 == 0:
            print(f"\nProgress: {i}/{len(page_nums)}")
        
        success = translate_page(page_num, api_key)
        if success:
            translated += 1
        else:
            failed += 1
        
        # Rate limiting - wait between requests
        time.sleep(1)
    
    print(f"\n=== Summary ===")
    print(f"Translated: {translated}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
