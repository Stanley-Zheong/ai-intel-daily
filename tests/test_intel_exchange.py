"""rss-daily 情报交换脚本测试。"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest

from scripts import export_source_feedback, import_crawler_intel


def _make_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("""
    CREATE TABLE intelligence_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT,
      url TEXT UNIQUE,
      feed_title TEXT,
      feed_url TEXT,
      source_category TEXT,
      published_at TEXT,
      ai_summary TEXT,
      final_score INTEGER,
      tags TEXT,
      status TEXT
    )
    """)
    conn.execute("""
    INSERT INTO intelligence_items
    (title, url, feed_title, feed_url, source_category, published_at,
     ai_summary, final_score, tags, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "OpenAI API pricing update",
        "https://openai.example/pricing",
        "OpenAI Changelog",
        "https://openai.example/feed.xml",
        "official",
        "2026-07-04T12:00:00Z",
        "pricing changed",
        88,
        "OpenAI,API pricing,model price",
        "processed",
    ))
    conn.commit()
    conn.close()


def _crawler_batch():
    return {
        "schema_version": "crawler_to_intel.1",
        "batch_id": "crawler-ai-api-20260704-001",
        "source_system": "industry-crawler:ai-tools-api",
        "topic": "ai-tools-api",
        "created_at": "2026-07-04T14:00:00Z",
        "watermark_from": "2026-07-04",
        "watermark_to": "2026-07-04",
        "items": [
            {
                "record_id": "rec-openai-pricing",
                "record_type": "verified_record",
                "fingerprint": "sha256:item",
                "title": "OpenAI updates API pricing page",
                "url": "https://openai.example/pricing",
                "publish_time": "2026-07-04",
                "source": {
                    "name": "OpenAI Pricing",
                    "url": "https://openai.example/pricing",
                    "source_type": "pricing_page",
                    "provenance": {"discovery": "rss_daily_feedback"},
                },
                "matched_keywords": ["OpenAI API pricing"],
                "body_excerpt": "Pricing page changed.",
                "extraction_confidence": 0.86,
                "evidence_url": "https://openai.example/pricing",
                "raw_snapshot_path": "",
                "warnings": [],
            }
        ],
        "counts": {"items": 1, "verified_records": 1, "candidate_sources": 0, "crawl_gaps": 0},
        "fingerprint": "sha256:batch",
    }


class TestExportSourceFeedback(unittest.TestCase):
    def test_exports_intel_source_feedback_batch(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "intel.db")
            out = os.path.join(td, "feedback.json")
            _make_db(db)

            rc = export_source_feedback.main([
                "--db", db,
                "--out", out,
                "--batch-id", "rss-ai-api-20260704-001",
                "--topic", "ai-tools-api",
                "--watermark-from", "2026-07-04T00:00:00Z",
                "--watermark-to", "2026-07-04T13:30:00Z",
            ])

            self.assertEqual(rc, 0)
            with open(out, encoding="utf-8") as fh:
                batch = json.load(fh)
            self.assertEqual(batch["schema_version"], "intel_source_feedback.1")
            self.assertEqual(batch["counts"]["items"], 1)
            item = batch["items"][0]
            self.assertEqual(item["source_name"], "OpenAI Changelog")
            self.assertIn("API pricing", item["keyword_candidates"])
            self.assertTrue(item["rss_signals"]["published"])
            self.assertEqual(item["rss_signals"]["final_score"], 88)


class TestImportCrawlerIntel(unittest.TestCase):
    def test_imports_crawler_batch_as_candidate_idempotently(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "intel.db")
            batch_path = os.path.join(td, "crawler.json")
            _make_db(db)
            with open(batch_path, "w", encoding="utf-8") as fh:
                json.dump(_crawler_batch(), fh, ensure_ascii=False)

            self.assertEqual(import_crawler_intel.main(["--db", db, "--batch", batch_path]), 0)
            self.assertEqual(import_crawler_intel.main(["--db", db, "--batch", batch_path]), 0)

            conn = sqlite3.connect(db)
            rows = conn.execute("SELECT title, status, crawler_batch_id FROM crawler_intel_candidates").fetchall()
            conn.close()

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "OpenAI updates API pricing page")
            self.assertEqual(rows[0][1], "candidate")
            self.assertEqual(rows[0][2], "crawler-ai-api-20260704-001")


if __name__ == "__main__":
    unittest.main()
