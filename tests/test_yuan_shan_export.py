from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from generator import export_yuan_shan_markdown
from scripts import publish_to_chatweb


def make_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE intelligence_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          miniflux_entry_id INTEGER UNIQUE,
          title TEXT NOT NULL,
          url TEXT NOT NULL UNIQUE,
          feed_title TEXT,
          feed_url TEXT,
          source_category TEXT,
          published_at TEXT,
          ai_summary TEXT,
          what_happened TEXT,
          who_is_affected TEXT,
          business_impact TEXT,
          recommended_action TEXT,
          impact_score INTEGER DEFAULT 0,
          urgency_score INTEGER DEFAULT 0,
          confidence_score INTEGER DEFAULT 0,
          final_score INTEGER DEFAULT 0,
          tags TEXT,
          status TEXT DEFAULT 'candidate'
        )
        """
    )
    rows = [
        (
            1001,
            "OpenAI API 价格页更新",
            "https://openai.example/pricing",
            "OpenAI Changelog",
            "https://openai.example/feed.xml",
            "01_AI技术",
            "2026-07-04T12:00:00Z",
            "OpenAI API pricing changed.",
            "OpenAI 更新 API 价格页。",
            "AI 应用开发者。",
            "预算假设需要复核。",
            "检查成本告警。",
            90,
            70,
            95,
            88,
            "OpenAI,API",
            "processed",
        ),
        (
            1002,
            "新能源补贴窗口更新",
            "https://energy.example/policy",
            "Energy Policy",
            "https://energy.example/feed.xml",
            "07_新能源",
            "2026-07-04T11:00:00Z",
            "新能源政策窗口更新。",
            "某地更新补贴申请窗口。",
            "新能源项目团队。",
            "可能影响申报节奏。",
            "复核申报材料。",
            81,
            88,
            90,
            84,
            "新能源,补贴",
            "published",
        ),
        (
            1003,
            "未确认 crawler 候选",
            "https://candidate.example/item",
            "Crawler Candidate",
            "https://candidate.example/feed.xml",
            "candidate",
            "2026-07-04T10:00:00Z",
            "候选项。",
            "未确认。",
            "运营者。",
            "未确认。",
            "先验证。",
            60,
            60,
            50,
            55,
            "candidate",
            "candidate",
        ),
    ]
    conn.executemany(
        """
        INSERT INTO intelligence_items
        (miniflux_entry_id, title, url, feed_title, feed_url, source_category, published_at,
         ai_summary, what_happened, who_is_affected, business_impact, recommended_action,
         impact_score, urgency_score, confidence_score, final_score, tags, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def make_minimal_chatweb(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "content" / "chats").mkdir(parents=True)
    (path / "content" / "products").mkdir(parents=True)
    (path / "content" / "yuan-shan").mkdir(parents=True)
    (path / "src" / "generated").mkdir(parents=True)
    (path / "scripts").mkdir()
    shutil.copyfile(
        Path("/tmp/chatweb-work/chatweb/scripts/generate-content-manifest.mjs"),
        path / "scripts" / "generate-content-manifest.mjs",
    )
    os.symlink(Path("/tmp/chatweb-work/chatweb/node_modules"), path / "node_modules")
    (path / "package.json").write_text(
        json.dumps({"scripts": {"content:manifest": "node scripts/generate-content-manifest.mjs"}}),
        encoding="utf-8",
    )


class TestYuanShanExport(unittest.TestCase):
    def test_exporter_writes_one_markdown_per_publishable_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            out_dir = Path(td) / "yuan-shan"
            make_db(db)

            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = export_yuan_shan_markdown.fetch_items(conn)
            conn.close()
            written, unchanged = export_yuan_shan_markdown.export_rows(rows, out_dir, dry_run=False)

            self.assertEqual(len(rows), 2)
            self.assertEqual(written, 2)
            self.assertEqual(unchanged, 0)
            files = sorted(out_dir.glob("*.md"))
            self.assertEqual(len(files), 2)
            content = "\n".join(file.read_text(encoding="utf-8") for file in files)
            self.assertIn('section: "yuan-shan"', content)
            self.assertIn('category: "AI"', content)
            self.assertIn('category: "新能源"', content)
            self.assertNotIn("未确认 crawler 候选", content)

    def test_publish_to_chatweb_generates_manifest_and_verifies_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            chatweb = Path(td) / "chatweb"
            make_db(db)
            make_minimal_chatweb(chatweb)

            rc = publish_to_chatweb.main(
                [
                    "--db",
                    str(db),
                    "--chatweb-repo",
                    str(chatweb),
                    "--min-publishable",
                    "2",
                ]
            )

            self.assertEqual(rc, 0)
            manifest = json.loads(
                (chatweb / "src" / "generated" / "content-manifest.json").read_text(encoding="utf-8")
            )
            yuan_shan = [item for item in manifest if item["meta"]["section"] == "yuan-shan"]
            self.assertEqual(len(yuan_shan), 2)
            self.assertEqual(len(list((chatweb / "content" / "yuan-shan").glob("*.md"))), 2)

    def test_exporter_reuses_existing_markdown_with_same_source_url(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            out_dir = Path(td) / "yuan-shan"
            out_dir.mkdir()
            make_db(db)
            legacy = out_dir / "2026-07-04-openai-pricing.md"
            legacy.write_text(
                """---
title: 旧标题
section: yuan-shan
source_url: https://openai.example/pricing
published: true
---

旧正文
""",
                encoding="utf-8",
            )

            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            rows = export_yuan_shan_markdown.fetch_items(conn)
            conn.close()
            openai_row = next(row for row in rows if row["url"] == "https://openai.example/pricing")
            duplicate = out_dir / f"{export_yuan_shan_markdown.stable_slug(openai_row)}.md"
            duplicate.write_text(
                """---
title: 重复标题
section: yuan-shan
source_url: https://openai.example/pricing
published: true
---

重复正文
""",
                encoding="utf-8",
            )
            export_yuan_shan_markdown.export_rows(rows, out_dir, dry_run=False)

            files = sorted(path.name for path in out_dir.glob("*.md"))
            self.assertIn("2026-07-04-openai-pricing.md", files)
            self.assertNotIn(duplicate.name, files)
            self.assertEqual(
                len(
                    [
                        path
                        for path in out_dir.glob("*.md")
                        if "https://openai.example/pricing" in path.read_text(encoding="utf-8")
                    ]
                ),
                1,
            )
            self.assertIn("OpenAI API 价格页更新", legacy.read_text(encoding="utf-8"))

    def test_publish_to_chatweb_fails_when_no_publishable_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            chatweb = Path(td) / "chatweb"
            make_db(db)
            make_minimal_chatweb(chatweb)
            conn = sqlite3.connect(db)
            conn.execute("UPDATE intelligence_items SET status = 'candidate'")
            conn.commit()
            conn.close()

            with self.assertRaisesRegex(RuntimeError, "below --min-publishable"):
                publish_to_chatweb.main(["--db", str(db), "--chatweb-repo", str(chatweb)])


if __name__ == "__main__":
    unittest.main()
