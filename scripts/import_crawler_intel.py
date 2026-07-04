#!/usr/bin/env python3
"""导入 industry-crawler -> rss-daily 的 crawler_to_intel.1 batch。"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


FORBIDDEN_FIELDS = {
    "lead_score", "conversion_stage", "attribution", "sales_owner",
    "deal_result", "lead_status", "intent_score",
}


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def _validate(batch: Dict[str, Any]) -> None:
    if batch.get("schema_version") != "crawler_to_intel.1":
        raise ValueError("schema_version must be crawler_to_intel.1")
    if not isinstance(batch.get("items"), list):
        raise ValueError("items must be a list")
    forbidden = sorted({k for k in _walk_keys(batch) if k.lower() in FORBIDDEN_FIELDS})
    if forbidden:
        raise ValueError("forbidden conversion fields: %s" % forbidden)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS crawler_intel_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      record_id TEXT NOT NULL UNIQUE,
      title TEXT NOT NULL,
      url TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'candidate',
      topic TEXT,
      publish_time TEXT,
      source_name TEXT,
      source_payload TEXT,
      matched_keywords TEXT,
      body_excerpt TEXT,
      extraction_confidence REAL DEFAULT 0,
      evidence_url TEXT,
      raw_snapshot_path TEXT,
      crawler_batch_id TEXT,
      crawler_fingerprint TEXT,
      imported_at TEXT
    )
    """)


def import_batch(conn: sqlite3.Connection, batch: Dict[str, Any]) -> int:
    _validate(batch)
    _ensure_schema(conn)
    imported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    count = 0
    for item in batch.get("items") or []:
        if item.get("record_type") not in ("verified_record", "candidate_source", "crawl_gap"):
            continue
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        cur = conn.execute("""
            INSERT OR IGNORE INTO crawler_intel_candidates
            (record_id, title, url, status, topic, publish_time, source_name,
             source_payload, matched_keywords, body_excerpt, extraction_confidence,
             evidence_url, raw_snapshot_path, crawler_batch_id, crawler_fingerprint,
             imported_at)
            VALUES (?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.get("record_id") or "",
            item.get("title") or "",
            item.get("url") or "",
            batch.get("topic") or "",
            item.get("publish_time") or "",
            source.get("name") or "",
            json.dumps(source, ensure_ascii=False, sort_keys=True),
            json.dumps(item.get("matched_keywords") or [], ensure_ascii=False),
            item.get("body_excerpt") or "",
            item.get("extraction_confidence") or 0,
            item.get("evidence_url") or "",
            item.get("raw_snapshot_path") or "",
            batch.get("batch_id") or "",
            batch.get("fingerprint") or "",
            imported_at,
        ))
        count += cur.rowcount
    conn.commit()
    return count


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="import crawler_to_intel.1 as candidates")
    ap.add_argument("--db", required=True)
    ap.add_argument("--batch", required=True)
    args = ap.parse_args(argv)
    with open(args.batch, "r", encoding="utf-8") as fh:
        batch = json.load(fh)
    conn = sqlite3.connect(args.db)
    try:
        count = import_batch(conn, batch)
    finally:
        conn.close()
    print("imported %d crawler candidate(s)" % count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
