#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from template import EMPTY_STATE, ITEM_CARD, NAV_LINK, PAGE, TABLE_ROW, TEXT_ROW, TOOLBAR_PILL

DB_PATH = os.environ.get("INTEL_DB_PATH", "/opt/miniflux-rsshub/intel/intel.db")
OUT_DIR = os.environ.get("SITE_OUT_DIR", os.path.join(os.path.dirname(__file__), "..", "docs"))

# Only verified or daily-worthy records are public. Crawler candidates stay private.
PUBLISH_STATUSES = ("publish_ready", "processed", "published")


def fetch_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        f"""
        SELECT * FROM intelligence_items
        WHERE status IN ({','.join('?' * len(PUBLISH_STATUSES))})
        ORDER BY final_score DESC, published_at DESC
        LIMIT 100
        """,
        PUBLISH_STATUSES,
    ).fetchall()


def generate(db_path: str = DB_PATH, out_dir: str = OUT_DIR) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = fetch_items(conn)
    conn.close()

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "topics"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "sources"), exist_ok=True)

    context = build_context(rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    write_page(
        out_dir,
        "index.html",
        render_page(
            rows=rows,
            context=context,
            generated_at=now,
            page_title="AI 行业情报日报",
            eyebrow="Daily Brief",
            headline="今日高价值 AI 行业情报",
            intro="从 RSS、Miniflux 和 crawler 候选中筛选出已确认可公开的情报，聚焦价格、政策、工具变更和可执行影响。",
            active="latest",
            toolbar=[
                ("/topics/", "专题索引"),
                ("/sources/", "信息源"),
            ],
        ),
    )

    write_page(
        out_dir,
        os.path.join("topics", "index.html"),
        render_topic_index(rows, context, now),
    )
    write_page(
        out_dir,
        os.path.join("sources", "index.html"),
        render_sources_index(rows, context, now),
    )

    page_count = 3
    for category, category_rows in context["topics"].items():
        slug = context["topic_slugs"][category]
        write_page(
            out_dir,
            os.path.join("topics", f"{slug}.html"),
            render_page(
                rows=category_rows,
                context=context,
                generated_at=now,
                page_title=f"{display_label(category)} - AI 行业情报日报",
                eyebrow="Topic",
                headline=display_label(category),
                intro="该专题聚合已确认可公开的情报条目，适合用于专题数据库、邮件栏目和后续 crawler 关键词反馈。",
                active=f"topic:{category}",
                toolbar=[
                    ("/", "返回最新"),
                    ("/topics/", "全部专题"),
                ],
            ),
        )
        page_count += 1

    return {"items": len(rows), "pages": page_count}


def build_context(rows: list[sqlite3.Row]) -> dict[str, object]:
    topics: dict[str, list[sqlite3.Row]] = defaultdict(list)
    sources: dict[str, list[sqlite3.Row]] = defaultdict(list)

    for row in rows:
        topics[category_for(row)].append(row)
        sources[source_for(row)].append(row)

    ordered_topics = dict(sorted(topics.items(), key=lambda item: (-len(item[1]), display_label(item[0]))))
    ordered_sources = dict(sorted(sources.items(), key=lambda item: (-len(item[1]), item[0])))
    taken_slugs: set[str] = set()
    topic_slugs = {name: unique_slug(name, taken=taken_slugs) for name in ordered_topics}
    source_counts = Counter(source_for(row) for row in rows)

    return {
        "topics": ordered_topics,
        "sources": ordered_sources,
        "topic_slugs": topic_slugs,
        "source_counts": source_counts,
        "total_items": len(rows),
        "top_score": max((int(row_value(row, "final_score") or 0) for row in rows), default=0),
    }


def render_page(
    *,
    rows: list[sqlite3.Row],
    context: dict[str, object],
    generated_at: str,
    page_title: str,
    eyebrow: str,
    headline: str,
    intro: str,
    active: str,
    toolbar: list[tuple[str, str]],
) -> str:
    content = '<section class="feed">' + ("".join(render_item(row) for row in rows) if rows else EMPTY_STATE) + "</section>"
    return PAGE.format(
        page_title=escape(page_title),
        primary_nav=render_primary_nav(active, context),
        topic_nav=render_topic_nav(active, context),
        eyebrow=escape(eyebrow),
        headline=escape(headline),
        intro=escape(intro),
        toolbar=render_toolbar(toolbar),
        content=content,
        generated_at=escape(generated_at),
        total_items=context["total_items"],
        top_score=context["top_score"],
        topic_count=len(context["topics"]),
        source_count=len(context["sources"]),
        recent_sources=render_recent_sources(context),
    )


def render_topic_index(rows: list[sqlite3.Row], context: dict[str, object], generated_at: str) -> str:
    topic_rows = []
    for category, category_rows in context["topics"].items():
        latest = first_date(category_rows)
        slug = context["topic_slugs"][category]
        topic_rows.append(
            TABLE_ROW.format(
                href=escape_attr(f"/topics/{slug}.html"),
                title=escape(display_label(category)),
                subtitle=escape("专题情报流"),
                meta=escape(latest),
                count=escape(f"{len(category_rows)} 条"),
            )
        )
    content = '<section class="table-list">' + ("".join(topic_rows) if topic_rows else EMPTY_STATE) + "</section>"
    return PAGE.format(
        page_title="专题索引 - AI 行业情报日报",
        primary_nav=render_primary_nav("topics", context),
        topic_nav=render_topic_nav("topics", context),
        eyebrow="Topics",
        headline="专题索引",
        intro="按业务用途聚合公开情报，后续可反向沉淀 crawler 关键词、RSS 源优先级和邮件栏目。",
        toolbar=render_toolbar([("/", "返回最新"), ("/sources/", "信息源")]),
        content=content,
        generated_at=escape(generated_at),
        total_items=context["total_items"],
        top_score=context["top_score"],
        topic_count=len(context["topics"]),
        source_count=len(context["sources"]),
        recent_sources=render_recent_sources(context),
    )


def render_sources_index(rows: list[sqlite3.Row], context: dict[str, object], generated_at: str) -> str:
    source_rows = []
    for source, source_items in context["sources"].items():
        sample = source_items[0]
        feed_url = safe_url(row_value(sample, "feed_url"))
        href = feed_url if feed_url != "#" else safe_url(row_value(sample, "url"))
        source_rows.append(
            TABLE_ROW.format(
                href=escape_attr(href),
                title=escape(source),
                subtitle=escape(category_for(sample)),
                meta=escape(first_date(source_items)),
                count=escape(f"{len(source_items)} 条"),
            )
        )
    content = '<section class="table-list">' + ("".join(source_rows) if source_rows else EMPTY_STATE) + "</section>"
    return PAGE.format(
        page_title="信息源 - AI 行业情报日报",
        primary_nav=render_primary_nav("sources", context),
        topic_nav=render_topic_nav("sources", context),
        eyebrow="Sources",
        headline="公开信息源",
        intro="这里展示已产出公开情报的信息源，后续作为 RSS 反馈和 industry-crawler 源发现的交互界面。",
        toolbar=render_toolbar([("/", "返回最新"), ("/topics/", "专题索引")]),
        content=content,
        generated_at=escape(generated_at),
        total_items=context["total_items"],
        top_score=context["top_score"],
        topic_count=len(context["topics"]),
        source_count=len(context["sources"]),
        recent_sources=render_recent_sources(context),
    )


def render_primary_nav(active: str, context: dict[str, object]) -> str:
    links = [
        ("latest", "/", "最新", context["total_items"]),
        ("topics", "/topics/", "专题", len(context["topics"])),
        ("sources", "/sources/", "信息源", len(context["sources"])),
    ]
    return "".join(
        NAV_LINK.format(
            active="active" if key == active else "",
            href=escape_attr(href),
            label=escape(label),
            count=escape(str(count)),
        )
        for key, href, label, count in links
    )


def render_topic_nav(active: str, context: dict[str, object]) -> str:
    rendered = []
    for category, rows in list(context["topics"].items())[:8]:
        key = f"topic:{category}"
        slug = context["topic_slugs"][category]
        rendered.append(
            NAV_LINK.format(
                active="active" if key == active else "",
                href=escape_attr(f"/topics/{slug}.html"),
                label=escape(display_label(category)),
                count=escape(str(len(rows))),
            )
        )
    if not rendered:
        rendered.append(TEXT_ROW.format(text="暂无专题"))
    return "".join(rendered)


def render_toolbar(links: list[tuple[str, str]]) -> str:
    return "".join(
        TOOLBAR_PILL.format(href=escape_attr(href), label=escape(label))
        for href, label in links
    )


def render_recent_sources(context: dict[str, object]) -> str:
    rows = []
    for source, count in context["source_counts"].most_common(5):
        rows.append(TEXT_ROW.format(text=escape(f"{source} · {count} 条")))
    return "".join(rows) if rows else TEXT_ROW.format(text="暂无来源")


def render_item(row: sqlite3.Row) -> str:
    return ITEM_CARD.format(
        final_score=escape(str(row_value(row, "final_score") or 0)),
        category=escape(display_label(category_for(row))),
        source=escape(source_for(row)),
        title=escape(row_value(row, "title")),
        one_sentence=escape(row_value(row, "ai_summary")),
        what_happened=escape(row_value(row, "what_happened")),
        who_is_affected=escape(row_value(row, "who_is_affected")),
        business_impact=escape(row_value(row, "business_impact")),
        recommended_action=escape(row_value(row, "recommended_action")),
        url=escape_attr(safe_url(row_value(row, "url"))),
        published_at=escape((row_value(row, "published_at") or "")[:10]),
    )


def first_date(rows: list[sqlite3.Row]) -> str:
    for row in rows:
        value = row_value(row, "published_at")
        if value:
            return value[:10]
    return "未标注"


def category_for(row: sqlite3.Row) -> str:
    return row_value(row, "source_category") or "未分类"


def source_for(row: sqlite3.Row) -> str:
    return row_value(row, "feed_title") or "Unknown Source"


def display_label(value: str) -> str:
    label = re.sub(r"^\d+[_-]+", "", value or "").replace("_", " ").strip()
    return label or "未分类"


def unique_slug(value: str, taken: set[str]) -> str:
    base = slugify(value)
    slug = base
    idx = 2
    while slug in taken:
        slug = f"{base}-{idx}"
        idx += 1
    taken.add(slug)
    return slug


def slugify(value: str) -> str:
    normalized = display_label(value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    if slug:
        return slug[:64]
    digest = hashlib.sha1((value or "topic").encode("utf-8")).hexdigest()[:10]
    return f"topic-{digest}"


def row_value(row: sqlite3.Row, key: str) -> str:
    try:
        return row[key]
    except (IndexError, KeyError):
        return ""


def escape(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def escape_attr(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def safe_url(value: object) -> str:
    url = str(value or "").strip()
    if not url.lower().startswith(("http://", "https://", "/")):
        return "#"
    return url


def write_page(out_dir: str, relative_path: str, html_text: str) -> None:
    path = os.path.join(out_dir, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_text)


def main() -> None:
    result = generate()
    print(f"generated {result['items']} item(s), {result['pages']} page(s) -> {OUT_DIR}")


if __name__ == "__main__":
    main()
