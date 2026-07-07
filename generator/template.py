PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<style>
  :root {{
    --bg: #f6f7f4;
    --panel: #ffffff;
    --panel-soft: #fbfcf8;
    --fg: #151713;
    --muted: #62695f;
    --line: #dfe4da;
    --line-strong: #cdd5c7;
    --accent: #155eef;
    --accent-soft: #e8efff;
    --good: #12715b;
    --good-soft: #e6f4ef;
    --warn: #8a5a00;
    --shadow: 0 16px 38px rgba(32, 42, 29, 0.08);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    min-height: 100vh;
    color: var(--fg);
    background: var(--bg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    line-height: 1.55;
  }}
  a {{ color: inherit; }}
  .app-shell {{
    width: min(1440px, 100%);
    margin: 0 auto;
    display: grid;
    grid-template-columns: 248px minmax(0, 1fr) 300px;
    gap: 20px;
    padding: 20px;
  }}
  .sidebar,
  .context-panel {{
    position: sticky;
    top: 20px;
    align-self: start;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.88);
    box-shadow: var(--shadow);
  }}
  .sidebar {{ padding: 18px; }}
  .brand {{ margin-bottom: 22px; }}
  .brand-mark {{
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }}
  .brand-logo {{
    width: 44px;
    height: 44px;
    flex: 0 0 auto;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel-soft);
    object-fit: cover;
  }}
  .brand-text {{ min-width: 0; }}
  .brand strong {{ display: block; font-size: 18px; letter-spacing: 0; }}
  .brand span {{ display: block; margin-top: 4px; color: var(--muted); font-size: 12px; }}
  .nav-section {{ margin-top: 20px; }}
  .nav-title {{
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  .nav-list {{
    display: grid;
    gap: 6px;
    margin-top: 10px;
  }}
  .nav-link {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    min-height: 36px;
    padding: 8px 10px;
    border-radius: 8px;
    color: var(--muted);
    font-size: 14px;
    text-decoration: none;
  }}
  .nav-link:hover,
  .nav-link.active {{
    background: var(--accent-soft);
    color: var(--accent);
  }}
  .nav-link .count {{
    color: var(--muted);
    font-size: 12px;
  }}
  .content-panel {{ min-width: 0; }}
  .hero {{
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    padding: 26px 28px;
    box-shadow: var(--shadow);
  }}
  .eyebrow {{
    color: var(--good);
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }}
  h1 {{
    margin: 8px 0 8px;
    font-size: 30px;
    line-height: 1.18;
    letter-spacing: 0;
  }}
  .hero p {{
    max-width: 760px;
    margin: 0;
    color: var(--muted);
    font-size: 14px;
  }}
  .toolbar {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 18px;
  }}
  .pill {{
    display: inline-flex;
    align-items: center;
    min-height: 30px;
    padding: 5px 10px;
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--panel-soft);
    color: var(--muted);
    font-size: 12px;
    text-decoration: none;
  }}
  .feed {{
    display: grid;
    gap: 14px;
    margin-top: 16px;
  }}
  .item-card {{
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    padding: 18px;
    box-shadow: 0 8px 24px rgba(32, 42, 29, 0.05);
  }}
  .item-top {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }}
  .badge {{
    display: inline-flex;
    align-items: center;
    max-width: 100%;
    min-height: 26px;
    padding: 4px 8px;
    border-radius: 8px;
    background: var(--good-soft);
    color: var(--good);
    font-size: 12px;
    font-weight: 700;
  }}
  .score {{
    margin-left: auto;
    color: var(--warn);
    font-size: 12px;
    font-weight: 700;
  }}
  .item-card h2 {{
    margin: 0;
    font-size: 18px;
    line-height: 1.35;
    letter-spacing: 0;
  }}
  .one-liner {{
    margin: 8px 0 14px;
    color: #343a31;
    font-size: 14px;
    font-weight: 700;
  }}
  .intel-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }}
  .intel-field {{
    min-width: 0;
    border-top: 1px solid var(--line);
    padding-top: 10px;
    color: #33382f;
    font-size: 13px;
  }}
  .intel-field b {{
    display: block;
    margin-bottom: 3px;
    color: var(--muted);
    font-size: 11px;
    font-weight: 800;
  }}
  .meta {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
    color: var(--muted);
    font-size: 12px;
  }}
  .source-link {{
    color: var(--accent);
    font-weight: 700;
    text-decoration: none;
  }}
  .source-link:hover {{ text-decoration: underline; }}
  .context-panel {{ padding: 18px; }}
  .stat-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 12px;
  }}
  .stat {{
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel-soft);
    padding: 10px;
  }}
  .stat strong {{ display: block; font-size: 20px; }}
  .stat span {{ color: var(--muted); font-size: 12px; }}
  .context-list {{
    display: grid;
    gap: 8px;
    margin-top: 12px;
    color: var(--muted);
    font-size: 13px;
  }}
  .context-list a {{
    color: var(--accent);
    text-decoration: none;
  }}
  .table-list {{
    display: grid;
    gap: 10px;
    margin-top: 16px;
  }}
  .table-row {{
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) 120px 96px;
    gap: 12px;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    padding: 14px 16px;
    font-size: 14px;
  }}
  .table-row a {{
    color: var(--accent);
    font-weight: 700;
    text-decoration: none;
  }}
  .muted {{ color: var(--muted); }}
  .empty {{
    border: 1px dashed var(--line-strong);
    border-radius: 8px;
    background: var(--panel);
    padding: 44px 20px;
    color: var(--muted);
    text-align: center;
  }}
  footer {{
    margin-top: 18px;
    color: var(--muted);
    font-size: 12px;
    text-align: center;
  }}
  @media (max-width: 1120px) {{
    .app-shell {{ grid-template-columns: 220px minmax(0, 1fr); }}
    .context-panel {{ position: static; grid-column: 1 / -1; }}
  }}
  @media (max-width: 760px) {{
    .app-shell {{ display: block; padding: 12px; }}
    .sidebar,
    .context-panel,
    .hero,
    .item-card {{ margin-bottom: 12px; }}
    .sidebar {{ position: static; }}
    .brand-logo {{ width: 40px; height: 40px; }}
    .nav-list {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    h1 {{ font-size: 24px; }}
    .intel-grid {{ grid-template-columns: 1fr; }}
    .table-row {{ grid-template-columns: 1fr; }}
    .score {{ margin-left: 0; }}
  }}
</style>
</head>
<body>
<div class="app-shell">
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">
        <img class="brand-logo" src="/assets/erDDshui_logo.png" alt="二滴水 logo" width="44" height="44">
        <div class="brand-text">
          <strong>AI Intel Daily</strong>
          <span>公开情报 · 人工筛选 · AI 辅助评分</span>
        </div>
      </div>
    </div>
    <div class="nav-section">
      <div class="nav-title">Views</div>
      <nav class="nav-list">
        {primary_nav}
      </nav>
    </div>
    <div class="nav-section">
      <div class="nav-title">Topics</div>
      <nav class="nav-list">
        {topic_nav}
      </nav>
    </div>
  </aside>

  <main class="content-panel">
    <section class="hero">
      <div class="eyebrow">{eyebrow}</div>
      <h1>{headline}</h1>
      <p>{intro}</p>
      <div class="toolbar">{toolbar}</div>
    </section>
    {content}
    <footer>更新时间 {generated_at} · Powered by ai-intel-daily</footer>
  </main>

  <aside class="context-panel">
    <div class="nav-title">Snapshot</div>
    <div class="stat-grid">
      <div class="stat"><strong>{total_items}</strong><span>公开条目</span></div>
      <div class="stat"><strong>{top_score}</strong><span>最高评分</span></div>
      <div class="stat"><strong>{topic_count}</strong><span>专题</span></div>
      <div class="stat"><strong>{source_count}</strong><span>来源</span></div>
    </div>
    <div class="nav-section">
      <div class="nav-title">Recent Sources</div>
      <div class="context-list">
        {recent_sources}
      </div>
    </div>
  </aside>
</div>
</body>
</html>
"""

NAV_LINK = '<a class="nav-link {active}" href="{href}"><span>{label}</span><span class="count">{count}</span></a>'

TOOLBAR_PILL = '<a class="pill" href="{href}">{label}</a>'

ITEM_CARD = """<article class="item-card">
  <div class="item-top">
    <span class="badge">{category}</span>
    <span class="badge">{source}</span>
    <span class="score">Score {final_score}</span>
  </div>
  <h2>{title}</h2>
  <p class="one-liner">{one_sentence}</p>
  <div class="intel-grid">
    <div class="intel-field"><b>发生了什么</b>{what_happened}</div>
    <div class="intel-field"><b>影响谁</b>{who_is_affected}</div>
    <div class="intel-field"><b>为什么重要</b>{business_impact}</div>
    <div class="intel-field"><b>建议动作</b>{recommended_action}</div>
  </div>
  <div class="meta">
    <a class="source-link" href="{url}" target="_blank" rel="noopener">原始来源</a>
    <span>{published_at}</span>
  </div>
</article>
"""

EMPTY_STATE = '<div class="empty">当前没有符合公开发布状态的情报条目。</div>'

TABLE_ROW = """<div class="table-row">
  <div><a href="{href}">{title}</a><div class="muted">{subtitle}</div></div>
  <div class="muted">{meta}</div>
  <div class="muted">{count}</div>
</div>
"""

TEXT_ROW = '<span>{text}</span>'
