from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import load_workflow_db_config


def _read_schema_sql() -> str:
    schema_path = Path(__file__).with_name("schema.sql")
    return schema_path.read_text(encoding="utf-8")


def get_connection() -> sqlite3.Connection:
    cfg = load_workflow_db_config()
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(cfg.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    schema_sql = _read_schema_sql()
    with get_connection() as conn:
        conn.executescript(schema_sql)
