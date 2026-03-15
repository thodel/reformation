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
OIDC_TOKEN_URL = "https://account.readcoop.eu/auth/realms/readcoop/protocol/openid-connect/token"
DEFAULT_OIDC_CLIENT_ID = "transkribus-api-client"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Transkribus credentials")
    parser.add_argument("--collection-id", type=int, help="Optional collection id to verify")
    parser.add_argument("--document-id", type=int, help="Optional document id to verify")
    return parser.parse_args()


class AuthContext:
    def __init__(self, kind: str, value: str, source: str) -> None:
        self.kind = kind
        self.value = value
        self.source = source


def legacy_login(user: str, password: str) -> str:
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


def oidc_password_grant(user: str, password: str) -> str:
    client_id = os.getenv("TRANSKRIBUS_OIDC_CLIENT_ID", DEFAULT_OIDC_CLIENT_ID).strip()
    if not client_id:
        client_id = DEFAULT_OIDC_CLIENT_ID

    payload = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": client_id,
            "username": user,
            "password": password,
        }
    ).encode("utf-8")
    req = urllib.request.Request(OIDC_TOKEN_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OIDC token request failed ({exc.code}): {detail}") from exc

    access_token = str(data.get("access_token", "")).strip()
    if not access_token:
        raise RuntimeError("OIDC token response did not include access_token")
    return access_token


def resolve_auth() -> AuthContext:
    token = os.getenv("TRANSKRIBUS_ACCESS_TOKEN", "").strip()
    if token:
        return AuthContext(kind="bearer", value=token, source="TRANSKRIBUS_ACCESS_TOKEN")

    user = os.getenv("TRANSKRIBUS_USER", "").strip()
    password = os.getenv("TRANSKRIBUS_PASSWORD", "")
    if not user or not password:
        raise RuntimeError(
            "Provide TRANSKRIBUS_ACCESS_TOKEN or both TRANSKRIBUS_USER and TRANSKRIBUS_PASSWORD."
        )

    legacy_error = None
    try:
        sid = legacy_login(user, password)
        return AuthContext(kind="sid", value=sid, source="legacy /auth/login")
    except Exception as exc:
        legacy_error = exc

    try:
        token = oidc_password_grant(user, password)
        return AuthContext(kind="bearer", value=token, source="OIDC password grant")
    except Exception as oidc_exc:
        raise RuntimeError(
            f"Legacy login failed ({legacy_error}); OIDC fallback failed ({oidc_exc})."
        ) from oidc_exc


def fetch_page_count(auth: AuthContext, col_id: int, doc_id: int) -> int:
    url = f"{BASE}/collections/{col_id}/{doc_id}/fulldoc"
    headers = {}
    if auth.kind == "sid":
        query = urllib.parse.urlencode({"JSESSIONID": auth.value})
        url = f"{url}?{query}"
    elif auth.kind == "bearer":
        headers["Authorization"] = f"Bearer {auth.value}"
    else:
        raise RuntimeError(f"Unsupported auth kind: {auth.kind}")

    req = urllib.request.Request(url, headers=headers, method="GET")

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

    auth = resolve_auth()
    print(f"Auth OK ({auth.source})")

    if args.collection_id is not None or args.document_id is not None:
        if args.collection_id is None or args.document_id is None:
            raise RuntimeError("Provide both --collection-id and --document-id")
        count = fetch_page_count(auth, args.collection_id, args.document_id)
        print(f"Document reachable: collection={args.collection_id}, document={args.document_id}, pages={count}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
