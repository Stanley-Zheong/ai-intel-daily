from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import publish_to_chatweb, sync_miniflux
from tests.test_yuan_shan_export import make_minimal_chatweb


def miniflux_entry(entry_id: int, title: str, url: str, category: str = "01_AI技术") -> dict:
    return {
        "id": entry_id,
        "title": title,
        "url": url,
        "published_at": "2026-07-05T08:00:00Z",
        "content": f"<p>{title} 正文</p>",
        "feed": {
            "title": "Miniflux Test Feed",
            "feed_url": "https://example.com/feed.xml",
            "category": {"title": category},
        },
    }


class FakeResponse:
    def __init__(self, entries: list[dict]) -> None:
        self.entries = entries

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"entries": self.entries}


class TestSyncMiniflux(unittest.TestCase):
    def test_starred_entries_are_pending_ai(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            entries = [
                miniflux_entry(1, "AI 发布样例", "https://example.com/ai"),
                miniflux_entry(2, "数据政策样例", "https://example.com/data", "08_CDO中央数据组织"),
            ]

            summary = sync_miniflux.sync_entries(db, entries, "AI")

            self.assertEqual(summary, {"fetched": 2, "inserted": 2, "updated": 0})
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT title, source_category, status FROM intelligence_items ORDER BY id"
            ).fetchall()
            conn.close()

            self.assertEqual([row["status"] for row in rows], ["starred_pending_ai", "starred_pending_ai"])
            self.assertEqual(rows[1]["source_category"], "08_CDO中央数据组织")

    def test_existing_published_row_is_not_downgraded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            entry = miniflux_entry(1, "AI 发布样例", "https://example.com/ai")
            sync_miniflux.sync_entries(db, [entry], "AI")

            conn = sqlite3.connect(db)
            conn.execute("UPDATE intelligence_items SET status = 'published' WHERE miniflux_entry_id = 1")
            conn.commit()
            conn.close()

            sync_miniflux.sync_entries(db, [entry], "AI")

            conn = sqlite3.connect(db)
            status = conn.execute(
                "SELECT status FROM intelligence_items WHERE miniflux_entry_id = 1"
            ).fetchone()[0]
            conn.close()
            self.assertEqual(status, "published")

    def test_publish_to_chatweb_can_sync_then_export_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            chatweb = Path(td) / "chatweb"
            make_minimal_chatweb(chatweb)
            entries = [miniflux_entry(1, "AI 发布样例", "https://example.com/ai")]

            def fake_enrich(db_path, api_key, base_url, model, limit, timeout):
                conn = sqlite3.connect(db_path)
                conn.execute(
                    """
                    UPDATE intelligence_items
                    SET status = 'publish_ready',
                        ai_summary = 'AI 摘要',
                        title_en = 'AI sample',
                        summary_en = 'AI summary',
                        body_zh = '## 背景\n\nAI 生成中文正文。',
                        body_en = '## Background\n\nAI generated English body.',
                        tags = 'AI,测试',
                        tags_zh = 'AI,测试',
                        tags_en = 'AI,Test',
                        final_score = 90
                    """
                )
                conn.commit()
                conn.close()
                return {"pending": 1, "ready": 1, "needs_review": 0, "skipped": 0}

            with (
                patch.object(sync_miniflux.requests, "get", return_value=FakeResponse(entries)),
                patch.object(publish_to_chatweb.ai_enrich, "enrich_pending", side_effect=fake_enrich),
            ):
                rc = publish_to_chatweb.main(
                    [
                        "--db",
                        str(db),
                        "--chatweb-repo",
                        str(chatweb),
                        "--sync-miniflux",
                        "--miniflux-url",
                        "https://miniflux.example",
                        "--miniflux-token",
                        "test-token",
                        "--enrich-pending",
                    ]
                )

            self.assertEqual(rc, 0)
            manifest = json.loads(
                (chatweb / "src" / "generated" / "content-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(manifest), 1)
            self.assertEqual(manifest[0]["meta"]["section"], "yuan-shan")
            self.assertEqual(manifest[0]["meta"]["title"], "AI 发布样例")
            self.assertEqual(manifest[0]["meta"]["title_en"], "AI sample")


if __name__ == "__main__":
    unittest.main()
