#!/usr/bin/env python3
"""导出 rss-daily -> industry-crawler 的 intel_source_feedback.1 batch。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


PUBLISH_STATUSES = {"starred_for_daily", "processed", "published"}


def _stable_sha(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _split_tags(value: str) -> List[str]:
    out, seen = [], set()
    for part in (value or "").replace("，", ",").split(","):
        part = part.strip()
        if part and part not in seen:
            seen.add(part)
            out.append(part)
    return out


def _source_trust(category: str) -> int:
    category = (category or "").lower()
    if "official" in category or "官方" in category:
        return 95
    if "github" in category:
        return 85
    if "community" in category or "社区" in category:
        return 65
    return 75


def _rows(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute("""
        SELECT title, url, feed_title, feed_url, source_category, published_at,
               ai_summary, final_score, tags, status
        FROM intelligence_items
        WHERE status IN ('starred_for_daily', 'processed', 'published')
        ORDER BY published_at DESC, final_score DESC
        LIMIT 200
    """).fetchall()


def build_batch(conn: sqlite3.Connection, *, batch_id: str, topic: str,
                watermark_from: str = "", watermark_to: str = "") -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for row in _rows(conn):
        tags = _split_tags(row["tags"] or "")
        keyword_candidates = tags[:8]
        if not keyword_candidates and row["title"]:
            keyword_candidates = [row["title"]]
        signal = {
            "signal_id": _stable_sha({"url": row["url"], "title": row["title"]}),
            "signal_type": "published_item" if row["status"] in PUBLISH_STATUSES else "rss_source",
            "title": row["title"] or "",
            "url": row["url"] or "",
            "feed_url": row["feed_url"] or "",
            "source_name": row["feed_title"] or "",
            "source_category": row["source_category"] or "",
            "source_trust": _source_trust(row["source_category"] or ""),
            "keyword_candidates": keyword_candidates,
            "entity_candidates": [],
            "rss_signals": {
                "saved": row["status"] in PUBLISH_STATUSES,
                "starred": row["status"] == "starred_for_daily",
                "published": row["status"] in PUBLISH_STATUSES,
                "final_score": row["final_score"] or 0,
            },
            "notes": row["ai_summary"] or "",
        }
        items.append(signal)
    batch = {
        "schema_version": "intel_source_feedback.1",
        "batch_id": batch_id,
        "source_system": "rss-daily",
        "topic": topic,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "watermark_from": watermark_from,
        "watermark_to": watermark_to,
        "items": items,
        "counts": {"items": len(items)},
    }
    batch["fingerprint"] = _stable_sha({
        "schema_version": batch["schema_version"],
        "topic": batch["topic"],
        "watermark_from": batch["watermark_from"],
        "watermark_to": batch["watermark_to"],
        "items": batch["items"],
    })
    return batch


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="export intel_source_feedback.1")
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--topic", required=True)
    ap.add_argument("--watermark-from", default="")
    ap.add_argument("--watermark-to", default="")
    args = ap.parse_args(argv)

    conn = sqlite3.connect(args.db)
    try:
        batch = build_batch(conn, batch_id=args.batch_id, topic=args.topic,
                            watermark_from=args.watermark_from,
                            watermark_to=args.watermark_to)
    finally:
        conn.close()
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(batch, fh, ensure_ascii=False, indent=2)
    print("exported %d feedback item(s) -> %s" % (batch["counts"]["items"], args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
