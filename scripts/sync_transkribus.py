#!/usr/bin/env python3
"""Sync transcriptions and pagexml from Transkribus.

Downloads the latest transcriptions (text) and pagexml files for all configured
variants from Transkribus.

Usage:
    python3 scripts/sync_transkribus.py [--dry-run]
"""

import argparse
import json
import os
import sys
import requests
import xml.etree.ElementTree as ET

# Config paths
CONFIG_PATH = "config/transkribus_config.json"
VARIANTS_CONFIG = "config/disputation_transkribus.example.json"

TRANSKRIBUS_BASE = "https://transkribus.eu/TrpServer/rest"


def load_config():
    """Load Transkribus credentials from config file."""
    config_path = os.path.join(os.path.dirname(__file__), "..", CONFIG_PATH)
    config_path = os.path.normpath(config_path)
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        return json.load(f)


def load_variants():
    """Load variant configurations."""
    variants_path = os.path.join(os.path.dirname(__file__), "..", VARIANTS_CONFIG)
    variants_path = os.path.normpath(variants_path)
    
    with open(variants_path, 'r') as f:
        data = json.load(f)
        return data.get('variants', [])


def login(email, password):
    """Login to Transkribus and return session ID."""
    r = requests.post(
        f"{TRANSKRIBUS_BASE}/auth/login",
        data={"email": email, "pw": password}
    )
    if r.status_code == requests.codes.ok:
        login_data = ET.fromstring(r.text)
        return login_data.find("sessionId").text
    else:
        raise Exception(f"Login failed: {r.status_code} - {r.text}")


def logout(sid):
    """Logout from Transkribus."""
    requests.get(f"{TRANSKRIBUS_BASE}/auth/logout?JSESSIONID={sid}")


def get_document_info(sid, doc_id):
    """Get document info including page count."""
    r = requests.get(
        f"{TRANSKRIBUS_BASE}/documents/{doc_id}",
        params={"JSESSIONID": sid}
    )
    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        raise Exception(f"Failed to get document info: {r.status_code}")


def get_page_transcription(sid, doc_id, page_nr, status_pref=None):
    """Get transcription text for a specific page.
    
    Args:
        sid: Session ID
        doc_id: Document ID
        page_nr: Page number (1-indexed)
        status_pref: List of preferred statuses, e.g. ["GT", "FINAL"]
    
    Returns:
        Tuple of (text, status) or (None, None) if not found
    """
    # First try to get the page metadata
    r = requests.get(
        f"{TRANSKRIBUS_BASE}/documents/{doc_id}/{page_nr}",
        params={"JSESSIONID": sid}
    )
    if r.status_code != 200:
        return None, None
    
    page_data = r.json()
    
    # Find the best available transcription
    if status_pref:
        for status in status_pref:
            for tr in page_data.get('transcriptions', []):
                if tr.get('status') == status:
                    # Get the actual transcription text
                    txt_id = tr.get('id')
                    r2 = requests.get(
                        f"{TRANSKRIBUS_BASE}/transcription/{doc_id}/{page_nr}/{txt_id}",
                        params={"JSESSIONID": sid}
                    )
                    if r2.status_code == 200:
                        return r2.text, status
    
    # If no preferred status found, return first available
    transcriptions = page_data.get('transcriptions', [])
    if transcriptions:
        txt_id = transcriptions[0].get('id')
        status = transcriptions[0].get('status')
        r2 = requests.get(
            f"{TRANSKRIBUS_BASE}/transcription/{doc_id}/{page_nr}/{txt_id}",
            params={"JSESSIONID": sid}
        )
        if r2.status_code == 200:
            return r2.text, status
    
    return None, None


def get_page_xml(sid, doc_id, page_nr):
    """Get page XML (pagexml) for a specific page.
    
    Returns:
        Tuple of (xml_text, img_url) or (None, None) if not found
    """
    r = requests.get(
        f"{TRANSKRIBUS_BASE}/ transcription /{doc_id}/{page_nr}",
        params={
            "JSESSIONID": sid,
            "format": "pagexml"
        }
    )
    # Try alternate endpoint
    if r.status_code != 200:
        r = requests.get(
            f"{TRANSKRIBUS_BASE}/documents/{doc_id}/{page_nr}/text",
            params={"JSESSIONID": sid, "format": "pagexml"}
        )
    
    if r.status_code == 200:
        # Extract imgUrl from XML
        try:
            root = ET.fromstring(r.text)
            img_url = None
            for elem in root.iter():
                if 'imgUrl' in elem.attrib or elem.tag.endswith('imgUrl'):
                    img_url = elem.get('imgUrl') or elem.text
                    break
            return r.text, img_url
        except:
            return r.text, None
    
    return None, None


def sync_variant(sid, variant, output_base, dry_run=False):
    """Sync all pages for a variant.
    
    Args:
        sid: Session ID
        variant: Variant config dict
        output_base: Base output directory
        dry_run: If True, only print what would be done
    
    Returns:
        Number of pages synced
    """
    doc_id = variant['document_id']
    variant_id = variant['id']
    status_pref = variant.get('status_preference', ['GT', 'FINAL'])
    
    print(f"\n=== Syncing {variant_id} (doc_id: {doc_id}) ===")
    
    # Get document info
    doc_info = get_document_info(sid, doc_id)
    page_count = doc_info.get('nrOfPages', 0)
    title = doc_info.get('title', 'Unknown')
    print(f"Document: {title}")
    print(f"Total pages: {page_count}")
    
    # Create output directories
    output_dir = os.path.join(output_base, variant_id)
    transcriptions_dir = os.path.join(output_dir, "transcriptions")
    pagexml_dir = os.path.join(output_dir, "pagexml")
    
    if not dry_run:
        os.makedirs(transcriptions_dir, exist_ok=True)
        os.makedirs(pagexml_dir, exist_ok=True)
    
    # Sync each page
    synced = 0
    for page_nr in range(1, page_count + 1):
        if page_nr % 50 == 0:
            print(f"  Processing page {page_nr}/{page_count}...")
        
        # Get transcription
        text, status = get_page_transcription(sid, doc_id, page_nr, status_pref)
        if text:
            output_file = os.path.join(transcriptions_dir, f"page_{page_nr}.txt")
            if not dry_run:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text)
            synced += 1
        else:
            print(f"  Warning: No transcription found for page {page_nr}")
        
        # Get pagexml
        xml_text, img_url = get_page_xml(sid, doc_id, page_nr)
        if xml_text:
            output_file = os.path.join(pagexml_dir, f"page_{page_nr}.xml")
            if not dry_run:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(xml_text)
    
    print(f"  Synced {synced} transcriptions, {page_count} pagexmls")
    return synced


def main():
    parser = argparse.ArgumentParser(description="Sync Transkribus transcriptions")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be synced")
    parser.add_argument("--variant", help="Only sync specific variant ID")
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    variants = load_variants()
    
    # Login
    print("Logging into Transkribus...")
    sid = login(config['email'], config['password'])
    print(f"Logged in (session: {sid[:20]}...)")
    
    try:
        output_base = os.path.join(os.path.dirname(__file__), "..", "data", "disputation")
        
        total_synced = 0
        for variant in variants:
            if args.variant and variant['id'] != args.variant:
                continue
            synced = sync_variant(sid, variant, output_base, args.dry_run)
            total_synced += synced
        
        print(f"\n=== Total: {total_synced} pages synced ===")
        
    finally:
        logout(sid)
        print("Logged out")


if __name__ == "__main__":
    main()
