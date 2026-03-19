#!/usr/bin/env python3
"""
Transcribe druck_1528 using Gemini 2.5
Downloads pages from e-rara and transcribes them
"""

import os
import json
import requests
import time
from pathlib import Path

# Config
MANIFEST_URL = "https://www.e-rara.ch/i3f/v20/30973277/manifest"
DATA_DIR = Path("/home/th/repos/reformation/data/disputation/druck_1528")
IMAGE_DIR = DATA_DIR / "images_temp"
TRANSCRIPTION_DIR = DATA_DIR / "transcriptions"
GEMINI_MODEL = "gemini-2.0-flash"

# Use Google Genai SDK
import google.generativeai as genai

def get_canvases():
    """Get canvas URLs from IIIF manifest."""
    resp = requests.get(MANIFEST_URL, timeout=30)
    manifest = resp.json()
    
    sequences = manifest.get("sequences", [])
    if not sequences:
        return []
    
    canvases = sequences[0].get("canvases", [])
    result = []
    
    for i, canvas in enumerate(canvases):
        images = canvas.get("images", [])
        if images:
            resource = images[0].get("resource", {})
            svc = resource.get("service", {})
            if svc:
                id_url = svc.get("@id") or svc.get("id")
                if id_url:
                    # Get full resolution
                    full_url = f"{id_url}/full/1000,/0/default.jpg"
                    result.append({
                        "page_num": i + 1,
                        "url": full_url,
                    })
    
    return result

def download_image(url, page_num):
    """Download a single image."""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    img_path = IMAGE_DIR / f"page_{page_num:04d}.jpg"
    if img_path.exists():
        print(f"  Page {page_num} already exists")
        return img_path
    
    print(f"  Downloading page {page_num}...")
    try:
        resp = requests.get(url, timeout=120)
        if resp.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(resp.content)
            print(f"    Saved: {img_path.stat().st_size / 1024:.1f} KB")
            return img_path
    except Exception as e:
        print(f"    Error: {e}")
    return None

def transcribe_image(image_path, page_num):
    """Transcribe a single image using Gemini 2.5."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        return None
    
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    
    print(f"    Transcribing page {page_num}...")
    
    try:
        # Upload image
        uploaded = genai.upload_file(path=image_path)
        
        prompt = """Transcribe this historical text from a 1528 print.
        Preserve ALL original characters, spelling, and punctuation.
        Maintain line breaks as in the original.
        Return ONLY the transcription, nothing else.
        If the page is blank or mostly blank, say 'BLANK PAGE'."""
        
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content([prompt, uploaded])
        return response.text
    
    except Exception as e:
        print(f"    Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def transcribe_page(page_num, canvases):
    """Transcribe a single page."""
    # Find the canvas
    canvas = None
    for c in canvases:
        if c["page_num"] == page_num:
            canvas = c
            break
    
    if not canvas:
        print(f"  Page {page_num} not found in manifest")
        return None
    
    # Check if already transcribed
    trans_path = TRANSCRIPTION_DIR / f"page_{page_num}.md"
    if trans_path.exists():
        print(f"  Page {page_num} already transcribed")
        with open(trans_path) as f:
            return f.read()
    
    # Download image
    img_path = download_image(canvas["url"], page_num)
    if not img_path:
        return None
    
    # Transcribe
    text = transcribe_image(img_path, page_num)
    
    if text:
        # Save
        with open(trans_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"    Saved transcription ({len(text)} chars)")
    
    return text

def main(start_page=1, end_page=50):
    print("=" * 60)
    print("Transcription: Berner Disputation 1528")
    print(f"Model: {GEMINI_MODEL}")
    print(f"Pages: {start_page}-{end_page}")
    print("=" * 60)
    
    # Get canvases
    print("\n1. Loading IIIF manifest...")
    canvases = get_canvases()
    print(f"   Found {len(canvases)} pages")
    
    # Transcribe pages
    TRANSCRIPTION_DIR.mkdir(parents=True, exist_ok=True)
    
    for page_num in range(start_page, min(end_page + 1, len(canvases) + 1)):
        print(f"\n[{page_num}/{end_page}]")
        result = transcribe_page(page_num, canvases)
        
        if result:
            print(f"   ✅ {len(result)} chars")
        
        time.sleep(1)  # Rate limiting
    
    print("\nDone!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=50)
    args = parser.parse_args()
    
    main(args.start, args.end)
