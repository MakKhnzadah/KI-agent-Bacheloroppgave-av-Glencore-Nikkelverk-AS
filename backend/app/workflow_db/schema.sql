PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  file_name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('Sikkerhet','Vedlikehold','Miljø','Kvalitet','Prosedyre','Annet')),
  status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected')),
  uploaded_by TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  original_content TEXT NOT NULL,
  revised_content TEXT NOT NULL,
  approved_content TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activities (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('document_approved','document_uploaded','ai_suggestion','document_rejected','system_update')),
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  user TEXT NOT NULL,
  time TEXT NOT NULL,
  document_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS document_audits (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('created','approved','rejected','deleted')),
  from_status TEXT CHECK (from_status IN ('pending','approved','rejected')),
  to_status TEXT CHECK (to_status IN ('pending','approved','rejected')),
  performed_by TEXT NOT NULL,
  comment TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

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
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_activities_document_id ON activities(document_id);
CREATE INDEX IF NOT EXISTS idx_document_audits_document_id ON document_audits(document_id);
CREATE INDEX IF NOT EXISTS idx_suggestions_upload_id ON suggestions(upload_id);
CREATE INDEX IF NOT EXISTS idx_reviews_suggestion_id ON reviews(suggestion_id);
