"""Static site generation tests."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from generator import generate_site


def _make_site_db(path: str) -> None:
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
      what_happened TEXT,
      who_is_affected TEXT,
      business_impact TEXT,
      recommended_action TEXT,
      final_score INTEGER,
      tags TEXT,
      status TEXT
    )
    """)
    rows = [
        (
            "OpenAI API pricing update",
            "https://openai.example/pricing",
            "OpenAI Changelog",
            "https://openai.example/feed.xml",
            "01_official",
            "2026-07-04T12:00:00Z",
            "API pricing changed",
            "The pricing page changed.",
            "AI app builders",
            "Budget assumptions may need review.",
            "Review API cost alerts.",
            91,
            "OpenAI,API pricing",
            "processed",
        ),
        (
            "Crawler-only candidate should stay private",
            "https://candidate.example/item",
            "Candidate Source",
            "https://candidate.example/feed.xml",
            "07_opportunity",
            "2026-07-04T10:00:00Z",
            "Unverified crawler item",
            "A crawler candidate was imported.",
            "Operators",
            "Unverified.",
            "Verify first.",
            81,
            "candidate",
            "candidate",
        ),
        (
            "<script>alert(1)</script>",
            "javascript:alert(1)",
            "Unsafe Feed",
            "https://unsafe.example/feed.xml",
            "03_pricing",
            "2026-07-03T10:00:00Z",
            "<b>unsafe summary</b>",
            "A potentially unsafe item.",
            "Readers",
            "Escaping matters.",
            "Keep HTML escaped.",
            72,
            "security",
            "published",
        ),
    ]
    conn.executemany("""
    INSERT INTO intelligence_items
    (title, url, feed_title, feed_url, source_category, published_at,
     ai_summary, what_happened, who_is_affected, business_impact,
     recommended_action, final_score, tags, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()


class TestSiteGeneration(unittest.TestCase):
    def test_generates_chatweb_style_shell_and_filters_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "intel.db")
            out_dir = os.path.join(td, "site")
            _make_site_db(db)

            generated = generate_site.generate(db_path=db, out_dir=out_dir)

            self.assertEqual(generated["items"], 2)
            with open(os.path.join(out_dir, "index.html"), encoding="utf-8") as fh:
                html = fh.read()

            self.assertIn('class="app-shell"', html)
            self.assertIn('class="sidebar"', html)
            self.assertIn('class="content-panel"', html)
            self.assertIn('class="context-panel"', html)
            self.assertIn("OpenAI API pricing update", html)
            self.assertNotIn("Crawler-only candidate should stay private", html)
            self.assertIn("/topics/", html)
            self.assertIn("/sources/", html)

    def test_generates_topic_and_source_pages(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "intel.db")
            out_dir = os.path.join(td, "site")
            _make_site_db(db)

            generate_site.generate(db_path=db, out_dir=out_dir)

            self.assertTrue(os.path.exists(os.path.join(out_dir, "topics", "index.html")))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "sources", "index.html")))
            topic_files = [
                name
                for name in os.listdir(os.path.join(out_dir, "topics"))
                if name.endswith(".html") and name != "index.html"
            ]
            self.assertGreaterEqual(len(topic_files), 2)

    def test_escapes_html_and_blocks_unsafe_urls(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "intel.db")
            out_dir = os.path.join(td, "site")
            _make_site_db(db)

            generate_site.generate(db_path=db, out_dir=out_dir)

            with open(os.path.join(out_dir, "index.html"), encoding="utf-8") as fh:
                html = fh.read()

            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
            self.assertIn("&lt;b&gt;unsafe summary&lt;/b&gt;", html)
            self.assertNotIn("javascript:alert", html)
            self.assertIn('href="#"', html)


if __name__ == "__main__":
    unittest.main()
