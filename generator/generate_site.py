#!/usr/bin/env python3
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from template import HEAD, ITEM, FOOT, EMPTY

DB_PATH = os.environ.get("INTEL_DB_PATH", "/opt/miniflux-rsshub/intel/intel.db")
OUT_DIR = os.environ.get("SITE_OUT_DIR", os.path.join(os.path.dirname(__file__), "..", "docs"))

# only published-worthy items make it to the site
PUBLISH_STATUSES = ("starred_for_daily", "processed", "published")


def fetch_items(conn):
    return conn.execute(
        f"""
        SELECT * FROM intelligence_items
        WHERE status IN ({','.join('?' * len(PUBLISH_STATUSES))})
        ORDER BY final_score DESC, published_at DESC
        LIMIT 100
        """,
        PUBLISH_STATUSES,
    ).fetchall()


def render_item(row):
    return ITEM.format(
        final_score=row["final_score"] or 0,
        category=row["source_category"] or "未分类",
        title=escape(row["title"]),
        one_sentence=escape(row["ai_summary"] or ""),
        what_happened=escape(row["what_happened"] or ""),
        who_is_affected=escape(row["who_is_affected"] or ""),
        business_impact=escape(row["business_impact"] or ""),
        recommended_action=escape(row["recommended_action"] or ""),
        url=row["url"],
        published_at=(row["published_at"] or "")[:10],
    )


def escape(s):
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = fetch_items(conn)
    conn.close()

    os.makedirs(OUT_DIR, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = "".join(render_item(r) for r in rows) if rows else EMPTY

    html = HEAD.format(page_title="AI 行业情报日报") + body + FOOT.format(generated_at=now)

    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    print(f"generated {len(rows)} item(s) -> {OUT_DIR}/index.html")


if __name__ == "__main__":
    main()
