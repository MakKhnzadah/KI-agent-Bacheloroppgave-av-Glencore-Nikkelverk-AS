PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS uploads (
  upload_id TEXT PRIMARY KEY,
  original_filename TEXT NOT NULL,
  content_type TEXT,
  size_bytes INTEGER,
  sha256 TEXT NOT NULL,
  stored_path TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS normalized_documents (
  normalized_id TEXT PRIMARY KEY,
  upload_id TEXT NOT NULL,
  text TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (upload_id) REFERENCES uploads(upload_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS suggestions (
  suggestion_id TEXT PRIMARY KEY,
  upload_id TEXT NOT NULL,
  target_kb_path TEXT,
  suggestion_json TEXT NOT NULL,
  model TEXT,
  prompt_version TEXT,
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','rejected','applied')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (upload_id) REFERENCES uploads(upload_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reviews (
  review_id TEXT PRIMARY KEY,
  suggestion_id TEXT NOT NULL,
  reviewer TEXT,
  decision TEXT NOT NULL CHECK (decision IN ('approved','rejected')),
  comment TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (suggestion_id) REFERENCES suggestions(suggestion_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applied_changes (
  change_id TEXT PRIMARY KEY,
  suggestion_id TEXT NOT NULL,
  kb_path TEXT NOT NULL,
  applied_at TEXT NOT NULL DEFAULT (datetime('now')),
  notes TEXT,
  FOREIGN KEY (suggestion_id) REFERENCES suggestions(suggestion_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_uploads_sha256 ON uploads(sha256);
CREATE INDEX IF NOT EXISTS idx_suggestions_upload_id ON suggestions(upload_id);
CREATE INDEX IF NOT EXISTS idx_reviews_suggestion_id ON reviews(suggestion_id);
