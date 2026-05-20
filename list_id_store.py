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
                list_name TEXT,
                submitted_by TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                error_message TEXT
            )
            """
        )
        # lightweight migration for older DBs
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(submissions)").fetchall()
        }
        for col in ("list_name", "submitted_by"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE submissions ADD COLUMN {col} TEXT")
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
    list_name: str | None = None,
    submitted_by: str | None = None,
    error_message: str | None = None,
) -> None:
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO submissions
            (list_id, row_count, filename, list_name, submitted_by,
             status, created_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                list_id,
                row_count,
                filename,
                list_name,
                submitted_by,
                status,
                datetime.now(timezone.utc).isoformat(),
                error_message,
            ),
        )


def clear_history(reset_counter: bool = True) -> int:
    """Delete all submissions. Returns number of rows removed.

    If reset_counter is True, the list_id counter also resets to 0
    so the next submission becomes 000001 again.
    """
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        before = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        conn.execute("DELETE FROM submissions")
        if reset_counter:
            conn.execute("UPDATE counter SET last_list_id = 0 WHERE id = 1")
    return int(before)


def recent_submissions(limit: int = 10) -> list[dict]:
    _ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT list_id, list_name, submitted_by, row_count, status,
                   created_at, filename, error_message
            FROM submissions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
