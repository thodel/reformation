#!/usr/bin/env python3
"""Validate Transkribus credentials and optional document access."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://transkribus.eu/TrpServer/rest"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Transkribus credentials")
    parser.add_argument("--collection-id", type=int, help="Optional collection id to verify")
    parser.add_argument("--document-id", type=int, help="Optional document id to verify")
    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def login(user: str, password: str) -> str:
    data = urllib.parse.urlencode({"user": user, "pw": password}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/auth/login", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Login failed ({exc.code}): {detail}") from exc

    root = ET.fromstring(body)
    sid = root.findtext("sessionId")
    if not sid:
        raise RuntimeError("Login response did not include sessionId")
    return sid


def fetch_page_count(sid: str, col_id: int, doc_id: int) -> int:
    params = urllib.parse.urlencode({"JSESSIONID": sid})
    url = f"{BASE}/collections/{col_id}/{doc_id}/fulldoc?{params}"
    req = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Document access failed ({exc.code}): {detail}") from exc

    pages = (((payload.get("pageList") or {}).get("pages")) or [])
    return len(pages)


def main() -> int:
    args = parse_args()

    user = require_env("TRANSKRIBUS_USER")
    password = require_env("TRANSKRIBUS_PASSWORD")

    sid = login(user, password)
    print("Login OK")

    if args.collection_id is not None or args.document_id is not None:
        if args.collection_id is None or args.document_id is None:
            raise RuntimeError("Provide both --collection-id and --document-id")
        count = fetch_page_count(sid, args.collection_id, args.document_id)
        print(f"Document reachable: collection={args.collection_id}, document={args.document_id}, pages={count}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
