from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import load_workflow_db_config


def _read_schema_sql() -> str:
    schema_path = Path(__file__).with_name("schema.sql")
    return schema_path.read_text(encoding="utf-8")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    cfg = load_workflow_db_config()
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(cfg.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_users_table_for_expert_role(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()

    if row is None:
        return

    create_sql = (row["sql"] or "").lower()
    if "'expert'" in create_sql:
        return

    conn.execute("PRAGMA foreign_keys = OFF;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users_new (
          id TEXT PRIMARY KEY,
          username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          display_name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'expert' CHECK (role IN ('admin','reviewer','user','expert','employee')),
          is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        INSERT INTO users_new (id, username, password_hash, display_name, role, is_active, created_at, updated_at)
        SELECT id, username, password_hash, display_name, role, is_active, created_at, updated_at
        FROM users
        """
    )
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    conn.execute("PRAGMA foreign_keys = ON;")


def _ensure_suggestions_generation_columns(conn: sqlite3.Connection) -> None:
    # SQLite supports ADD COLUMN, but not adding CHECK constraints post-hoc.
    # We keep this as best-effort to enable explicit generation status/diagnostics.
    cols = conn.execute("PRAGMA table_info('suggestions')").fetchall()
    existing = {str(c[1]) for c in cols}  # column name is index 1

    def add(name: str, ddl: str) -> None:
        if name in existing:
            return
        conn.execute(f"ALTER TABLE suggestions ADD COLUMN {ddl}")

    add("generation_status", "generation_status TEXT NOT NULL DEFAULT 'unknown'")
    add("generation_fallback_used", "generation_fallback_used INTEGER NOT NULL DEFAULT 0")
    add("generation_attempts", "generation_attempts INTEGER NOT NULL DEFAULT 0")
    add("generation_started_at", "generation_started_at TEXT")
    add("generation_finished_at", "generation_finished_at TEXT")
    add("generation_reason", "generation_reason TEXT")
    add("generation_error", "generation_error TEXT")

    # Index is optional; create if missing.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_suggestions_generation_status ON suggestions(generation_status)"
    )


def init_db() -> None:
    schema_sql = _read_schema_sql()
    with get_connection() as conn:
        conn.executescript(schema_sql)
        _migrate_users_table_for_expert_role(conn)
        _ensure_suggestions_generation_columns(conn)
