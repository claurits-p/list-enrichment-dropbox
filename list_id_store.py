from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from config import DATA_DIR, DB_PATH


def _ensure_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counter (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_list_id INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                list_id TEXT PRIMARY KEY,
                row_count INTEGER NOT NULL,
                filename TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                error_message TEXT
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO counter (id, last_list_id) VALUES (1, 0)"
        )


def next_list_id() -> str:
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE counter SET last_list_id = last_list_id + 1 WHERE id = 1")
        row = conn.execute("SELECT last_list_id FROM counter WHERE id = 1").fetchone()
        return f"{row[0]:06d}"


def record_submission(
    list_id: str,
    row_count: int,
    filename: str | None,
    status: str,
    error_message: str | None = None,
) -> None:
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO submissions
            (list_id, row_count, filename, status, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                list_id,
                row_count,
                filename,
                status,
                datetime.now(timezone.utc).isoformat(),
                error_message,
            ),
        )


def recent_submissions(limit: int = 10) -> list[dict]:
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT list_id, row_count, filename, status, created_at, error_message
            FROM submissions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
