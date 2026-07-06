#!/usr/bin/env python3
"""Export publishable RSS intelligence into chatweb and verify the handoff.

This is the bridge between the RSS/Miniflux pipeline and the public
`dia-for/chatweb` site. It intentionally fails if a publishable database row
does not appear in chatweb's generated manifest.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from generator import export_yuan_shan_markdown
from scripts import ai_enrich
from scripts import sync_miniflux


DEFAULT_DB = os.environ.get("INTEL_DB_PATH", "/opt/miniflux-rsshub/intel/intel.db")
DEFAULT_CHATWEB_REPO = os.environ.get(
    "CHATWEB_REPO_PATH",
    "/Users/laosanzheong/Documents/codebases/chatweb",
)
DEFAULT_OBSIDIAN_RAW_DIR = os.environ.get("OBSIDIAN_RAW_DIR", "")


def publishable_rows(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return export_yuan_shan_markdown.fetch_items(conn)
    finally:
        conn.close()


def run(command: list[str], cwd: Path) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def load_manifest(chatweb_repo: Path) -> list[dict]:
    manifest_path = chatweb_repo / "src" / "generated" / "content-manifest.json"
    with manifest_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def verify_manifest(rows: list[sqlite3.Row], chatweb_repo: Path) -> dict[str, int]:
    manifest = load_manifest(chatweb_repo)
    yuan_shan = [item for item in manifest if item.get("meta", {}).get("section") == "yuan-shan"]
    manifest_titles = {item.get("meta", {}).get("title") for item in yuan_shan}
    manifest_source_urls = {
        item.get("meta", {}).get("source_url")
        or item.get("meta", {}).get("canonical_url")
        for item in yuan_shan
    }
    markdown_source_urls = {
        export_yuan_shan_markdown.source_url_from_markdown(path)
        for path in (chatweb_repo / "content" / "yuan-shan").glob("*.md")
    }

    missing: list[str] = []
    for row in rows:
        title = str(export_yuan_shan_markdown.row_get(row, "title", "") or "")
        source_url = str(export_yuan_shan_markdown.row_get(row, "url", "") or "")
        slug = export_yuan_shan_markdown.stable_slug(row)
        markdown_path = chatweb_repo / "content" / "yuan-shan" / f"{slug}.md"
        if not markdown_path.exists() and source_url not in markdown_source_urls:
            missing.append(f"missing markdown: {markdown_path}")
        if title not in manifest_titles and source_url not in manifest_source_urls:
            missing.append(f"missing manifest row: {title or source_url or slug}")

    if missing:
        detail = "\n".join(f"- {item}" for item in missing)
        raise RuntimeError(f"Yuan Shan handoff verification failed:\n{detail}")

    return {
        "publishable_rows": len(rows),
        "manifest_yuan_shan": len(yuan_shan),
        "manifest_total": len(manifest),
    }


def mark_published(db_path: Path, rows: list[sqlite3.Row]) -> int:
    ids = [row["id"] for row in rows if export_yuan_shan_markdown.row_get(row, "status") == "publish_ready"]
    if not ids:
        return 0

    placeholders = ",".join("?" * len(ids))
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            f"""
            UPDATE intelligence_items
            SET status = 'published',
                updated_at = datetime('now')
            WHERE id IN ({placeholders})
            """,
            ids,
        )
        conn.commit()
        return conn.total_changes
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export RSS intelligence to chatweb/content/yuan-shan and verify manifest ingestion.",
    )
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--chatweb-repo", default=DEFAULT_CHATWEB_REPO)
    parser.add_argument("--min-publishable", type=int, default=1)
    parser.add_argument("--skip-manifest", action="store_true")
    parser.add_argument(
        "--sync-miniflux",
        action="store_true",
        help="Fetch Miniflux starred entries into the DB before exporting Yuan Shan markdown.",
    )
    parser.add_argument("--miniflux-url", default=os.environ.get("MINIFLUX_URL"))
    parser.add_argument("--miniflux-token", default=os.environ.get("MINIFLUX_TOKEN"))
    parser.add_argument("--miniflux-limit", type=int, default=int(os.environ.get("MINIFLUX_SYNC_LIMIT", "100")))
    parser.add_argument("--miniflux-timeout", type=int, default=int(os.environ.get("MINIFLUX_TIMEOUT", "20")))
    parser.add_argument("--default-category", default=os.environ.get("MINIFLUX_DEFAULT_CATEGORY", "AI"))
    parser.add_argument(
        "--enrich-pending",
        action="store_true",
        help="Run AI enrichment for starred_pending_ai rows before export.",
    )
    parser.add_argument("--ai-api-key", default=os.environ.get("AI_ENRICH_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))
    parser.add_argument("--ai-base-url", default=os.environ.get("AI_ENRICH_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
    parser.add_argument("--ai-model", default=os.environ.get("AI_ENRICH_MODEL") or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
    parser.add_argument("--ai-limit", type=int, default=int(os.environ.get("AI_ENRICH_LIMIT", "10")))
    parser.add_argument("--ai-timeout", type=int, default=int(os.environ.get("AI_ENRICH_TIMEOUT", "90")))
    parser.add_argument("--obsidian-raw-dir", default=DEFAULT_OBSIDIAN_RAW_DIR)
    parser.add_argument("--skip-obsidian", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--qa-live", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    db_path = Path(args.db).expanduser().resolve()
    chatweb_repo = Path(args.chatweb_repo).expanduser().resolve()
    out_dir = chatweb_repo / "content" / "yuan-shan"

    if not db_path.exists():
        if not args.sync_miniflux:
            raise FileNotFoundError(f"database not found: {db_path}")
    if not chatweb_repo.exists():
        raise FileNotFoundError(f"chatweb repo not found: {chatweb_repo}")

    if args.sync_miniflux:
        if not args.miniflux_url:
            raise RuntimeError("MINIFLUX_URL is required when --sync-miniflux is used")
        if not args.miniflux_token:
            raise RuntimeError("MINIFLUX_TOKEN is required when --sync-miniflux is used")
        entries = sync_miniflux.fetch_starred_entries(
            miniflux_url=args.miniflux_url,
            token=args.miniflux_token,
            limit=args.miniflux_limit,
            timeout=args.miniflux_timeout,
        )
        sync_summary = sync_miniflux.sync_entries(db_path, entries, args.default_category)
        print(f"synced Miniflux before publish: {sync_summary}", flush=True)

    if args.enrich_pending:
        enrich_summary = ai_enrich.enrich_pending(
            db_path=db_path,
            api_key=args.ai_api_key,
            base_url=args.ai_base_url,
            model=args.ai_model,
            limit=args.ai_limit,
            timeout=args.ai_timeout,
        )
        print(f"enriched pending rows before publish: {enrich_summary}", flush=True)

    rows = publishable_rows(db_path)
    if len(rows) < args.min_publishable:
        raise RuntimeError(
            f"only {len(rows)} publishable row(s), below --min-publishable={args.min_publishable}"
        )

    written, unchanged = export_yuan_shan_markdown.export_rows(rows, out_dir, args.dry_run)
    print(
        f"exported {len(rows)} publishable row(s): {written} written, {unchanged} unchanged -> {out_dir}",
        flush=True,
    )

    if args.obsidian_raw_dir and not args.skip_obsidian:
        obs_written, obs_unchanged = export_yuan_shan_markdown.export_obsidian_rows(
            rows,
            Path(args.obsidian_raw_dir).expanduser().resolve(),
            args.dry_run,
        )
        print(
            f"exported Obsidian raw RSS notes: {obs_written} written, {obs_unchanged} unchanged -> {args.obsidian_raw_dir}",
            flush=True,
        )

    if args.dry_run:
        return 0

    if not args.skip_manifest:
        run(["npm", "run", "content:manifest"], cwd=chatweb_repo)
        summary = verify_manifest(rows, chatweb_repo)
        print(f"verified handoff: {summary}", flush=True)

    if args.build:
        run(["npm", "run", "build:cloudflare"], cwd=chatweb_repo)

    if args.deploy:
        run(["npm", "run", "deploy"], cwd=chatweb_repo)

    if args.qa_live:
        run(["npm", "run", "qa:live"], cwd=chatweb_repo)

    marked = mark_published(db_path, rows)
    if marked:
        print(f"marked {marked} publish-ready row(s) as published", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
