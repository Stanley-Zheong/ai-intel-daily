#!/usr/bin/env python3
"""Create bilingual publish-ready intelligence articles from starred RSS rows."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from scripts.sync_miniflux import ensure_schema


DEFAULT_DB = os.environ.get("INTEL_DB_PATH", "/opt/miniflux-rsshub/intel/intel.db")
DEFAULT_MODEL = os.environ.get("AI_ENRICH_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
DEFAULT_BASE_URL = os.environ.get(
    "AI_ENRICH_BASE_URL",
    os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
)
DEFAULT_API_KEY = os.environ.get("AI_ENRICH_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")

PENDING_STATUS = "starred_pending_ai"
READY_STATUS = "publish_ready"
REVIEW_STATUS = "needs_review"

REQUIRED_TEXT_FIELDS = [
    "title_zh",
    "title_en",
    "summary_zh",
    "summary_en",
    "body_zh",
    "body_en",
    "context_zh",
    "context_en",
    "background_zh",
    "background_en",
    "purpose_zh",
    "purpose_en",
    "impact_zh",
    "impact_en",
    "recommended_action_zh",
    "recommended_action_en",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def strip_html(value: str | None, limit: int = 6000) -> str:
    text = re.sub(r"<(script|style).*?</\1>", " ", value or "", flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    if key not in row.keys():
        return default
    return row[key]


def pending_rows(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT *
        FROM intelligence_items
        WHERE status = ?
        ORDER BY saved_at DESC, published_at DESC, id DESC
        LIMIT ?
        """,
        (PENDING_STATUS, limit),
    ).fetchall()


def context_rows(conn: sqlite3.Connection, row: sqlite3.Row, limit: int = 5) -> list[sqlite3.Row]:
    source_category = str(row_get(row, "source_category", "") or "")
    feed_title = str(row_get(row, "feed_title", "") or "")
    return conn.execute(
        """
        SELECT title, ai_summary, what_happened, business_impact, recommended_action,
               tags, feed_title, source_category, published_at
        FROM intelligence_items
        WHERE id != ?
          AND status IN ('publish_ready', 'processed', 'published')
          AND (
            source_category = ?
            OR feed_title = ?
          )
        ORDER BY published_at DESC, final_score DESC
        LIMIT ?
        """,
        (row["id"], source_category, feed_title, limit),
    ).fetchall()


def build_context(context: list[sqlite3.Row]) -> str:
    blocks: list[str] = []
    for item in context:
        blocks.append(
            "\n".join(
                [
                    f"- title: {row_get(item, 'title', '')}",
                    f"  summary: {row_get(item, 'ai_summary', '') or row_get(item, 'what_happened', '')}",
                    f"  impact: {row_get(item, 'business_impact', '')}",
                    f"  action: {row_get(item, 'recommended_action', '')}",
                    f"  tags: {row_get(item, 'tags', '')}",
                ]
            )
        )
    return "\n".join(blocks) or "No related historical items found."


def prompt_for(row: sqlite3.Row, related_context: str) -> str:
    source_text = strip_html(row_get(row, "raw_content", ""))
    raw_payload = row_get(row, "raw_payload")
    feed_meta = ""
    if raw_payload:
        try:
            payload = json.loads(raw_payload)
            feed_meta = json.dumps(payload.get("feed", {}), ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            feed_meta = ""

    return f"""
You are a B2B intelligence analyst. Turn one starred RSS item into a publishable bilingual intelligence article.

Rules:
- Do not republish or lightly rewrite the original text.
- Add context, background, purpose, cross-industry/business impact, and recommended actions.
- If the source is thin or uncertain, lower confidence_score.
- Use only the RSS item, feed metadata, source URL, and historical context below. Do not invent facts.
- Output strict JSON only. No Markdown fences.
- tags must be stable short tags. tags_zh and tags_en must be localized display tags.

Required JSON fields:
{", ".join(REQUIRED_TEXT_FIELDS)}, tags, tags_zh, tags_en, source_type,
impact_score, urgency_score, confidence_score, final_score.

Scoring:
impact_score: 0-100, money/risk/opportunity impact.
urgency_score: 0-100, whether readers should act soon.
confidence_score: 0-100, source reliability and completeness.
final_score: weighted practical publishing value.

RSS item:
title: {row_get(row, "title", "")}
url: {row_get(row, "url", "")}
feed_title: {row_get(row, "feed_title", "")}
feed_url: {row_get(row, "feed_url", "")}
category: {row_get(row, "source_category", "")}
published_at: {row_get(row, "published_at", "")}
feed_meta: {feed_meta}
content_text: {source_text}

Historical context:
{related_context}
""".strip()


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def call_openai_compatible(
    prompt: str,
    api_key: str,
    base_url: str,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You return strict JSON for bilingual B2B intelligence publishing.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return extract_json(content)


def normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,，\n]", value) if item.strip()]
    return []


def validate_result(result: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_TEXT_FIELDS if not str(result.get(field, "")).strip()]
    if missing:
        raise ValueError(f"missing required AI fields: {', '.join(missing)}")
    if not normalize_list(result.get("tags")):
        raise ValueError("missing tags")
    if not normalize_list(result.get("tags_zh")):
        raise ValueError("missing tags_zh")
    if not normalize_list(result.get("tags_en")):
        raise ValueError("missing tags_en")


def update_ready(conn: sqlite3.Connection, row_id: int, result: dict[str, Any], model: str) -> None:
    tags = normalize_list(result.get("tags"))
    tags_zh = normalize_list(result.get("tags_zh"))
    tags_en = normalize_list(result.get("tags_en"))
    conn.execute(
        """
        UPDATE intelligence_items
        SET title = ?,
            title_en = ?,
            ai_summary = ?,
            summary_en = ?,
            body_zh = ?,
            body_en = ?,
            context_zh = ?,
            context_en = ?,
            background_zh = ?,
            background_en = ?,
            purpose_zh = ?,
            purpose_en = ?,
            business_impact = ?,
            impact_en = ?,
            recommended_action = ?,
            action_en = ?,
            what_happened = ?,
            who_is_affected = ?,
            tags = ?,
            tags_zh = ?,
            tags_en = ?,
            impact_score = ?,
            urgency_score = ?,
            confidence_score = ?,
            final_score = ?,
            ai_model = ?,
            ai_enriched_at = ?,
            updated_at = ?,
            status = ?
        WHERE id = ?
        """,
        (
            str(result["title_zh"]).strip(),
            str(result["title_en"]).strip(),
            str(result["summary_zh"]).strip(),
            str(result["summary_en"]).strip(),
            str(result["body_zh"]).strip(),
            str(result["body_en"]).strip(),
            str(result["context_zh"]).strip(),
            str(result["context_en"]).strip(),
            str(result["background_zh"]).strip(),
            str(result["background_en"]).strip(),
            str(result["purpose_zh"]).strip(),
            str(result["purpose_en"]).strip(),
            str(result["impact_zh"]).strip(),
            str(result["impact_en"]).strip(),
            str(result["recommended_action_zh"]).strip(),
            str(result["recommended_action_en"]).strip(),
            str(result.get("what_happened_zh") or result["summary_zh"]).strip(),
            str(result.get("who_is_affected_zh") or result["impact_zh"]).strip(),
            ",".join(tags),
            ",".join(tags_zh),
            ",".join(tags_en),
            int(result.get("impact_score") or 0),
            int(result.get("urgency_score") or 0),
            int(result.get("confidence_score") or 0),
            int(result.get("final_score") or 0),
            model,
            utc_now(),
            utc_now(),
            READY_STATUS,
            row_id,
        ),
    )


def update_review(conn: sqlite3.Connection, row_id: int, reason: str) -> None:
    conn.execute(
        """
        UPDATE intelligence_items
        SET status = ?, updated_at = ?, ai_summary = ?
        WHERE id = ?
        """,
        (REVIEW_STATUS, utc_now(), f"AI enrichment failed: {reason[:500]}", row_id),
    )


def enrich_pending(
    db_path: Path,
    api_key: str | None,
    base_url: str,
    model: str,
    limit: int,
    timeout: int,
) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        rows = pending_rows(conn, limit)
        ready = 0
        review = 0
        skipped = 0

        for row in rows:
            if not api_key:
                update_review(conn, row["id"], "missing AI_ENRICH_API_KEY or DEEPSEEK_API_KEY")
                review += 1
                continue

            try:
                related = build_context(context_rows(conn, row))
                result = call_openai_compatible(
                    prompt_for(row, related),
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    timeout=timeout,
                )
                validate_result(result)
                update_ready(conn, row["id"], result, model)
                ready += 1
            except Exception as exc:  # noqa: BLE001 - keep cron resilient per item.
                update_review(conn, row["id"], str(exc))
                review += 1

        conn.commit()
        return {"pending": len(rows), "ready": ready, "needs_review": review, "skipped": skipped}
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI-enrich starred RSS rows into bilingual publish-ready articles.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=int(os.environ.get("AI_ENRICH_LIMIT", "10")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("AI_ENRICH_TIMEOUT", "90")))
    args = parser.parse_args(argv)

    summary = enrich_pending(
        db_path=Path(args.db).expanduser().resolve(),
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        limit=args.limit,
        timeout=args.timeout,
    )
    print(f"AI enrichment summary: {summary}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
