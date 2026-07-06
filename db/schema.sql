CREATE TABLE IF NOT EXISTS intelligence_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  miniflux_entry_id INTEGER UNIQUE,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  feed_title TEXT,
  feed_url TEXT,
  source_category TEXT,

  published_at TEXT,
  saved_at TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

  raw_content TEXT,
  raw_payload TEXT,

  ai_summary TEXT,
  title_en TEXT,
  summary_en TEXT,
  body_zh TEXT,
  body_en TEXT,
  context_zh TEXT,
  context_en TEXT,
  background_zh TEXT,
  background_en TEXT,
  purpose_zh TEXT,
  purpose_en TEXT,
  impact_en TEXT,
  action_en TEXT,
  tags_zh TEXT,
  tags_en TEXT,
  ai_model TEXT,
  ai_enriched_at TEXT,
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
);

CREATE INDEX IF NOT EXISTS idx_intelligence_items_status
  ON intelligence_items(status);

CREATE INDEX IF NOT EXISTS idx_intelligence_items_published_at
  ON intelligence_items(published_at);
