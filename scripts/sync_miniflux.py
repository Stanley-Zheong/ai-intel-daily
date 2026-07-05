#!/usr/bin/env python3
"""Sync selected Miniflux entries into the RSS intelligence database.

The public site only receives rows whose status is publishable. Miniflux
starred entries are therefore stored as `starred_for_daily` so the next
publish step can export them into chatweb's Yuan Shan content directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = os.environ.get("INTEL_DB_PATH", "/opt/miniflux-rsshub/intel/intel.db")
DEFAULT_SCHEMA = REPO_ROOT / "db" / "schema.sql"
PUBLISH_STATUS = "starred_for_daily"
PROTECTED_STATUSES = {"processed", "published", "newsletter", "paid", "archived"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn: sqlite3.Connection, schema_path: Path = DEFAULT_SCHEMA) -> None:
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(intelligence_items)").fetchall()
    }
    migrations = {
        "updated_at": "ALTER TABLE intelligence_items ADD COLUMN updated_at TEXT",
        "raw_payload": "ALTER TABLE intelligence_items ADD COLUMN raw_payload TEXT",
    }
    for column, statement in migrations.items():
        if column not in existing:
            conn.execute(statement)


def miniflux_headers(token: str) -> dict[str, str]:
    return {"X-Auth-Token": token}


def fetch_starred_entries(
    miniflux_url: str,
    token: str,
    limit: int,
    timeout: int,
) -> list[dict[str, Any]]:
    response = requests.get(
        f"{miniflux_url.rstrip('/')}/v1/entries",
        headers=miniflux_headers(token),
        params={
            "starred": "true",
            "limit": limit,
            "order": "published_at",
            "direction": "desc",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return list(payload.get("entries", []))


def category_from_entry(entry: dict[str, Any], default_category: str) -> str:
    feed = entry.get("feed") or {}
    category = feed.get("category") or {}
    if isinstance(category, dict):
        title = category.get("title") or category.get("name")
        if title:
            return str(title)
    return str(feed.get("category_title") or default_category)


def upsert_entry(
    conn: sqlite3.Connection,
    entry: dict[str, Any],
    default_category: str,
) -> str:
    feed = entry.get("feed") or {}
    now = utc_now()
    miniflux_entry_id = entry.get("id")
    url = entry.get("url") or entry.get("external_url") or ""
    title = entry.get("title") or "未命名情报"

    existing = conn.execute(
        """
        SELECT id, status
        FROM intelligence_items
        WHERE miniflux_entry_id = ? OR url = ?
        LIMIT 1
        """,
        (miniflux_entry_id, url),
    ).fetchone()

    next_status = PUBLISH_STATUS
    if existing and existing["status"] in PROTECTED_STATUSES:
        next_status = existing["status"]

    values = {
        "miniflux_entry_id": miniflux_entry_id,
        "title": title,
        "url": url,
        "feed_title": feed.get("title"),
        "feed_url": feed.get("feed_url") or feed.get("site_url"),
        "source_category": category_from_entry(entry, default_category),
        "published_at": entry.get("published_at"),
        "saved_at": now,
        "updated_at": now,
        "raw_content": entry.get("content"),
        "raw_payload": json.dumps(entry, ensure_ascii=False, sort_keys=True),
        "status": next_status,
    }

    if existing:
        conn.execute(
            """
            UPDATE intelligence_items
            SET title = :title,
                url = :url,
                feed_title = :feed_title,
                feed_url = :feed_url,
                source_category = :source_category,
                published_at = :published_at,
                saved_at = :saved_at,
                updated_at = :updated_at,
                raw_content = :raw_content,
                raw_payload = :raw_payload,
                status = :status
            WHERE id = :id
            """,
            {**values, "id": existing["id"]},
        )
        return "updated"

    conn.execute(
        """
        INSERT INTO intelligence_items
        (miniflux_entry_id, title, url, feed_title, feed_url, source_category,
         published_at, saved_at, updated_at, raw_content, raw_payload, status)
        VALUES
        (:miniflux_entry_id, :title, :url, :feed_title, :feed_url, :source_category,
         :published_at, :saved_at, :updated_at, :raw_content, :raw_payload, :status)
        """,
        values,
    )
    return "inserted"


def sync_entries(
    db_path: Path,
    entries: list[dict[str, Any]],
    default_category: str,
) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        inserted = 0
        updated = 0
        for entry in entries:
            result = upsert_entry(conn, entry, default_category)
            if result == "inserted":
                inserted += 1
            else:
                updated += 1
        conn.commit()
        return {"fetched": len(entries), "inserted": inserted, "updated": updated}
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync Miniflux starred entries into intelligence_items.",
    )
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--miniflux-url", default=os.environ.get("MINIFLUX_URL"))
    parser.add_argument("--miniflux-token", default=os.environ.get("MINIFLUX_TOKEN"))
    parser.add_argument("--limit", type=int, default=int(os.environ.get("MINIFLUX_SYNC_LIMIT", "100")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("MINIFLUX_TIMEOUT", "20")))
    parser.add_argument("--default-category", default=os.environ.get("MINIFLUX_DEFAULT_CATEGORY", "AI"))
    args = parser.parse_args(argv)

    if not args.miniflux_url:
        raise RuntimeError("MINIFLUX_URL is required")
    if not args.miniflux_token:
        raise RuntimeError("MINIFLUX_TOKEN is required")

    entries = fetch_starred_entries(
        miniflux_url=args.miniflux_url,
        token=args.miniflux_token,
        limit=args.limit,
        timeout=args.timeout,
    )
    summary = sync_entries(Path(args.db).expanduser().resolve(), entries, args.default_category)
    print(f"synced Miniflux starred entries: {summary}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
