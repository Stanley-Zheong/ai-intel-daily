#!/usr/bin/env python3
from __future__ import annotations

"""Export publishable RSS intelligence rows into dia-for Yuan Shan Markdown files.

This exporter is cumulative by design: it writes one Markdown file per source
item and never deletes old articles from the destination directory.
"""

import argparse
import hashlib
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


DB_PATH = os.environ.get("INTEL_DB_PATH", "/opt/miniflux-rsshub/intel/intel.db")
DEFAULT_CHATWEB_REPO = os.environ.get(
    "CHATWEB_REPO_PATH",
    "/Users/laosanzheong/Documents/codebases/chatweb",
)
OUT_DIR = os.environ.get(
    "YUAN_SHAN_OUT_DIR",
    str(Path(DEFAULT_CHATWEB_REPO) / "content" / "yuan-shan"),
)

PUBLISH_STATUSES = ("starred_for_daily", "processed", "published")

CATEGORY_MAP = {
    "ai": "AI",
    "ai技术": "AI",
    "ai产品": "AI",
    "人工智能": "AI",
    "数据": "数据",
    "data": "数据",
    "cdo": "数据",
    "新能源": "新能源",
    "new-energy": "新能源",
    "传统ai+": "传统AI+",
    "传统ai": "传统AI+",
    "制造业": "传统AI+",
    "教育ai+": "教育AI+",
    "教育ai": "教育AI+",
    "高等教育": "教育AI+",
}


def fetch_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    placeholders = ",".join("?" * len(PUBLISH_STATUSES))
    return conn.execute(
        f"""
        SELECT *
        FROM intelligence_items
        WHERE status IN ({placeholders})
        ORDER BY published_at DESC, final_score DESC, id DESC
        """,
        PUBLISH_STATUSES,
    ).fetchall()


def normalize_category(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "AI"

    lowered = raw.lower()
    for key, mapped in CATEGORY_MAP.items():
        if key in lowered:
            return mapped

    return "AI"


def row_get(row: sqlite3.Row, key: str, default: object = None) -> object:
    if key not in row.keys():
        return default
    return row[key]


def date_part(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return value[:10]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def stable_slug(row: sqlite3.Row) -> str:
    url = str(row_get(row, "url", "") or "")
    source_key = str(
        row_get(row, "miniflux_entry_id")
        or url
        or row_get(row, "title")
        or row_get(row, "id")
    )
    digest = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:8]
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    host_part = slugify(host.split(":")[0]) if host else "rss"
    return f"{date_part(str(row_get(row, 'published_at', '') or ''))}-{host_part}-{digest}"


def yaml_scalar(value: object) -> str:
    text = "" if value is None else str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_array(values: Iterable[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return "[]"
    return "[" + ", ".join(yaml_scalar(value) for value in cleaned) + "]"


def body_field(label: str, value: str | None) -> str:
    if not value:
        return ""
    return f"## {label}\n\n{value.strip()}\n\n"


def render_markdown(row: sqlite3.Row) -> str:
    category = normalize_category(str(row_get(row, "source_category", "") or ""))
    title = str(row_get(row, "title", "") or "未命名情报").strip()
    summary = str(row_get(row, "ai_summary") or row_get(row, "what_happened") or "").strip()
    source_name = str(
        row_get(row, "feed_title")
        or row_get(row, "source_name")
        or row_get(row, "source_category")
        or "RSS"
    ).strip()
    source_url = str(row_get(row, "url", "") or "")
    created = date_part(str(row_get(row, "published_at", "") or ""))
    tags = ["远山", category]

    frontmatter = "\n".join(
        [
            "---",
            f"title: {yaml_scalar(title)}",
            'section: "yuan-shan"',
            f"category: {yaml_scalar(category)}",
            f"topic: {yaml_scalar('远山')}",
            f"source_name: {yaml_scalar(source_name)}",
            f"source_url: {yaml_scalar(source_url)}",
            f"canonical_url: {yaml_scalar(source_url)}",
            f"summary: {yaml_scalar(summary)}",
            "published: true",
            f"created: {yaml_scalar(created)}",
            f"tags: {yaml_array(tags)}",
            f"rss_source: {yaml_scalar(source_name)}",
            f"score: {int(row_get(row, 'final_score', 0) or 0)}",
            f"impact_score: {int(row_get(row, 'impact_score', 0) or 0)}",
            f"urgency_score: {int(row_get(row, 'urgency_score', 0) or 0)}",
            f"confidence_score: {int(row_get(row, 'confidence_score', 0) or 0)}",
            "---",
            "",
        ]
    )

    body = ""
    body += body_field("一句话结论", row_get(row, "ai_summary"))
    body += body_field("发生了什么", row_get(row, "what_happened"))
    body += body_field("影响谁", row_get(row, "who_is_affected"))
    body += body_field("为什么重要", row_get(row, "business_impact"))
    body += body_field("建议动作", row_get(row, "recommended_action"))

    if source_url:
        body += f"## 原始来源\n\n[{source_name}]({source_url})\n\n"

    return frontmatter + (body.strip() or summary or title) + "\n"


def export_rows(rows: list[sqlite3.Row], out_dir: Path, dry_run: bool) -> tuple[int, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    unchanged = 0

    for row in rows:
        target = out_dir / f"{stable_slug(row)}.md"
        content = render_markdown(row)
        if target.exists() and target.read_text(encoding="utf-8") == content:
            unchanged += 1
            continue

        written += 1
        if not dry_run:
            target.write_text(content, encoding="utf-8")

    return written, unchanged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = fetch_items(conn)
    conn.close()

    written, unchanged = export_rows(rows, Path(args.out_dir), args.dry_run)
    mode = "would write" if args.dry_run else "wrote"
    print(
        f"{mode} {written} Yuan Shan markdown file(s), "
        f"{unchanged} unchanged, from {len(rows)} publishable row(s)"
    )


if __name__ == "__main__":
    main()
