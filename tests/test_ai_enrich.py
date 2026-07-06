from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import ai_enrich, sync_miniflux
from tests.test_sync_miniflux import miniflux_entry


def ai_result() -> dict:
    return {
        "title_zh": "AI 价格变化影响开发预算",
        "title_en": "AI Pricing Change Affects Developer Budgets",
        "summary_zh": "这次变化会影响团队的成本假设。",
        "summary_en": "The change affects team cost assumptions.",
        "body_zh": "## 背景\n\n这是 AI 生成的中文情报。",
        "body_en": "## Background\n\nThis is AI-generated English intelligence.",
        "context_zh": "历史上同类价格变化会影响选型。",
        "context_en": "Similar pricing changes have affected vendor choices.",
        "background_zh": "供应商更新了价格相关信息。",
        "background_en": "The vendor updated pricing-related information.",
        "purpose_zh": "帮助读者判断是否需要复核预算。",
        "purpose_en": "Help readers decide whether to review budgets.",
        "impact_zh": "影响 API 成本、毛利和产品定价。",
        "impact_en": "It affects API cost, margin, and product pricing.",
        "recommended_action_zh": "复核调用量和成本告警。",
        "recommended_action_en": "Review usage and cost alerts.",
        "tags": ["ai-pricing", "budget"],
        "tags_zh": ["AI价格", "预算"],
        "tags_en": ["AI Pricing", "Budget"],
        "source_type": "rss",
        "impact_score": 88,
        "urgency_score": 72,
        "confidence_score": 86,
        "final_score": 84,
    }


class TestAiEnrich(unittest.TestCase):
    def test_pending_starred_row_becomes_publish_ready_with_bilingual_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            sync_miniflux.sync_entries(
                db,
                [miniflux_entry(1, "AI price update", "https://example.com/pricing")],
                "AI",
            )

            with patch.object(ai_enrich, "call_openai_compatible", return_value=ai_result()):
                summary = ai_enrich.enrich_pending(
                    db_path=db,
                    api_key="test-key",
                    base_url="https://api.example/v1",
                    model="test-model",
                    limit=10,
                    timeout=5,
                )

            self.assertEqual(summary["ready"], 1)
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM intelligence_items WHERE miniflux_entry_id = 1").fetchone()
            conn.close()
            self.assertEqual(row["status"], "publish_ready")
            self.assertEqual(row["title_en"], "AI Pricing Change Affects Developer Budgets")
            self.assertEqual(row["tags_en"], "AI Pricing,Budget")
            self.assertEqual(row["final_score"], 84)

    def test_missing_api_key_moves_pending_row_to_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "intel.db"
            sync_miniflux.sync_entries(
                db,
                [miniflux_entry(2, "AI price update", "https://example.com/pricing-2")],
                "AI",
            )

            summary = ai_enrich.enrich_pending(
                db_path=db,
                api_key=None,
                base_url="https://api.example/v1",
                model="test-model",
                limit=10,
                timeout=5,
            )

            self.assertEqual(summary["needs_review"], 1)
            conn = sqlite3.connect(db)
            status = conn.execute(
                "SELECT status FROM intelligence_items WHERE miniflux_entry_id = 2"
            ).fetchone()[0]
            conn.close()
            self.assertEqual(status, "needs_review")


if __name__ == "__main__":
    unittest.main()
