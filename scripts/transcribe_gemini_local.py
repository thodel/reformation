#!/usr/bin/env python3
"""
Transcribe local images using Gemini.
"""

import os
import time
from pathlib import Path

# Config
DATA_DIR = Path("/home/th/repos/reformation/data/disputation/a_v_1446_ruemlang")
IMAGE_DIR = DATA_DIR / "images"
TRANSCRIPTION_DIR = DATA_DIR / "transcriptions"
GEMINI_MODEL = "gemini-2.5-pro" # Try 2.5-pro or fallback to 2.0-flash

def transcribe_image(image_path, page_num):
    """Transcribe a single image using Gemini."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: API_KEY not set")
        return None
    
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    
    print(f"    Transcribing page {page_num}...")
    
    try:
        # Upload image
        uploaded = genai.upload_file(path=str(image_path))
        
        prompt = """Transcribe this historical text from a 16th century manuscript/print.
        Preserve ALL original characters, spelling, and punctuation.
        Maintain line breaks as in the original.
        Return ONLY the transcription, nothing else.
        If the page is blank or mostly blank, say 'BLANK PAGE'."""
        
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content([prompt, uploaded])
        return response.text
    
    except Exception as e:
        print(f"    Error: {e}")
        # fallback to 2.0-flash if model not found
        if "models/gemini-2.5-pro" in str(e) or "not found" in str(e).lower():
             print("Falling back to gemini-2.0-flash...")
             try:
                 model = genai.GenerativeModel("gemini-2.0-flash")
                 response = model.generate_content([prompt, uploaded])
                 return response.text
             except Exception as e2:
                 print(f"    Fallback Error: {e2}")
                 return None
        return None

def main(start_page=1, end_page=50):
    print("=" * 60)
    print("Transcription: A V 1446 (Local Images)")
    print(f"Pages: {start_page}-{end_page}")
    print("=" * 60)
    
    TRANSCRIPTION_DIR.mkdir(parents=True, exist_ok=True)
    
    for page_num in range(start_page, end_page + 1):
        print(f"\n[{page_num}/{end_page}]")
        img_path = IMAGE_DIR / f"page_{page_num}.jpg"
        
        if not img_path.exists():
            print(f"  Image not found: {img_path}")
            continue
            
        trans_path = TRANSCRIPTION_DIR / f"page_{page_num}_gemini.md"
        if trans_path.exists():
            print(f"  Page {page_num} already transcribed (Gemini version)")
            continue
            
        text = transcribe_image(img_path, page_num)
        
        if text:
            # Save
            with open(trans_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"   ✅ Saved transcription ({len(text)} chars)")
        
        time.sleep(2)  # Rate limiting

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=50)
    args = parser.parse_args()
    
    main(args.start, args.end)
