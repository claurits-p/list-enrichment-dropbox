"""Persistent storage for submissions + approval queue.

Uses Supabase Postgres when DATABASE_URL is set, otherwise falls back to
local SQLite (useful for dev only; data does NOT persist on Streamlit Cloud).
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DATA_DIR, DB_PATH


def _database_url() -> str | None:
    url = os.getenv("DATABASE_URL", "").strip()
    return url or None


def _is_postgres() -> bool:
    return _database_url() is not None


# ---------------------------------------------------------------------------
# Postgres backend
# ---------------------------------------------------------------------------


_PG_SCHEMA_CREATED = False


def _pg_ensure_schema() -> None:
    global _PG_SCHEMA_CREATED
    if _PG_SCHEMA_CREATED:
        return
    import psycopg

    with psycopg.connect(_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS counter (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_list_id INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS submissions (
                    list_id TEXT PRIMARY KEY,
                    row_count INTEGER NOT NULL,
                    filename TEXT,
                    list_name TEXT,
                    submitted_by TEXT,
                    submitted_by_email TEXT,
                    list_type TEXT,
                    record_type TEXT,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    error_message TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_approvals (
                    queue_id BIGSERIAL PRIMARY KEY,
                    submitted_by TEXT NOT NULL,
                    submitted_by_email TEXT,
                    list_name TEXT NOT NULL,
                    list_type TEXT,
                    record_type TEXT,
                    row_count INTEGER NOT NULL,
                    filename TEXT,
                    csv_bytes BYTEA NOT NULL,
                    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    status TEXT NOT NULL DEFAULT 'pending'
                )
                """
            )
            # Migrations for pre-existing deployments (idempotent)
            cur.execute(
                "ALTER TABLE submissions "
                "ADD COLUMN IF NOT EXISTS submitted_by_email TEXT"
            )
            cur.execute(
                "ALTER TABLE submissions "
                "ADD COLUMN IF NOT EXISTS list_type TEXT"
            )
            cur.execute(
                "ALTER TABLE pending_approvals "
                "ADD COLUMN IF NOT EXISTS submitted_by_email TEXT"
            )
            cur.execute(
                "ALTER TABLE pending_approvals "
                "ADD COLUMN IF NOT EXISTS list_type TEXT"
            )
            cur.execute(
                """
                INSERT INTO counter (id, last_list_id)
                VALUES (1, 0)
                ON CONFLICT (id) DO NOTHING
                """
            )
        conn.commit()
    _PG_SCHEMA_CREATED = True


@contextmanager
def _pg_conn():
    import psycopg

    _pg_ensure_schema()
    conn = psycopg.connect(_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _pg_next_list_id() -> str:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO counter (id, last_list_id) VALUES (1, 1)
                ON CONFLICT (id) DO UPDATE
                  SET last_list_id = counter.last_list_id + 1
                RETURNING last_list_id
                """
            )
            row = cur.fetchone()
    return f"{row[0]:06d}"


def _pg_record_submission(
    list_id: str,
    row_count: int,
    filename: str | None,
    status: str,
    list_name: str | None,
    submitted_by: str | None,
    submitted_by_email: str | None,
    list_type: str | None,
    record_type: str | None,
    error_message: str | None,
) -> None:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO submissions
                (list_id, row_count, filename, list_name, submitted_by,
                 submitted_by_email, list_type, record_type, status,
                 created_at, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (list_id) DO UPDATE SET
                  row_count = EXCLUDED.row_count,
                  filename = EXCLUDED.filename,
                  list_name = EXCLUDED.list_name,
                  submitted_by = EXCLUDED.submitted_by,
                  submitted_by_email = EXCLUDED.submitted_by_email,
                  list_type = EXCLUDED.list_type,
                  record_type = EXCLUDED.record_type,
                  status = EXCLUDED.status,
                  created_at = EXCLUDED.created_at,
                  error_message = EXCLUDED.error_message
                """,
                (
                    list_id,
                    row_count,
                    filename,
                    list_name,
                    submitted_by,
                    submitted_by_email,
                    list_type,
                    record_type,
                    status,
                    datetime.now(timezone.utc),
                    error_message,
                ),
            )


def _pg_recent_submissions(limit: int) -> list[dict]:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT list_id, list_name, submitted_by, submitted_by_email,
                       list_type, record_type, row_count, status, created_at,
                       filename, error_message
                FROM submissions
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [c.name for c in cur.description]
            rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        out.append(d)
    return out


def _pg_clear_history(reset_counter: bool) -> int:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM submissions")
            before = int(cur.fetchone()[0])
            cur.execute("DELETE FROM submissions")
            if reset_counter:
                cur.execute("UPDATE counter SET last_list_id = 0 WHERE id = 1")
    return before


def _pg_add_to_queue(
    submitted_by: str,
    submitted_by_email: str | None,
    list_name: str,
    list_type: str | None,
    row_count: int,
    filename: str | None,
    csv_bytes: bytes,
    record_type: str | None,
) -> int:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pending_approvals
                (submitted_by, submitted_by_email, list_name, list_type,
                 record_type, row_count, filename, csv_bytes, submitted_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING queue_id
                """,
                (
                    submitted_by,
                    submitted_by_email,
                    list_name,
                    list_type,
                    record_type,
                    row_count,
                    filename,
                    csv_bytes,
                    datetime.now(timezone.utc),
                ),
            )
            row = cur.fetchone()
    return int(row[0])


def _pg_list_pending() -> list[dict]:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT queue_id, submitted_by, submitted_by_email, list_name,
                       list_type, record_type, row_count, filename, submitted_at
                FROM pending_approvals
                WHERE status = 'pending'
                ORDER BY submitted_at ASC
                """
            )
            cols = [c.name for c in cur.description]
            rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(zip(cols, r))
        if isinstance(d.get("submitted_at"), datetime):
            d["submitted_at"] = d["submitted_at"].isoformat()
        out.append(d)
    return out


def _pg_get_pending(queue_id: int) -> dict | None:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM pending_approvals WHERE queue_id = %s",
                (queue_id,),
            )
            cols = [c.name for c in cur.description]
            row = cur.fetchone()
    if row is None:
        return None
    d = dict(zip(cols, row))
    if isinstance(d.get("csv_bytes"), memoryview):
        d["csv_bytes"] = bytes(d["csv_bytes"])
    if isinstance(d.get("submitted_at"), datetime):
        d["submitted_at"] = d["submitted_at"].isoformat()
    return d


def _pg_delete_pending(queue_id: int) -> None:
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pending_approvals WHERE queue_id = %s",
                (queue_id,),
            )


# ---------------------------------------------------------------------------
# SQLite fallback (dev only)
# ---------------------------------------------------------------------------


def _sqlite_ensure_db() -> None:
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
                submitted_by_email TEXT,
                list_type TEXT,
                record_type TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                error_message TEXT
            )
            """
        )
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(submissions)").fetchall()
        }
        for col in (
            "list_name", "submitted_by", "submitted_by_email", "list_type",
            "record_type",
        ):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE submissions ADD COLUMN {col} TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_approvals (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                submitted_by TEXT NOT NULL,
                submitted_by_email TEXT,
                list_name TEXT NOT NULL,
                list_type TEXT,
                record_type TEXT,
                row_count INTEGER NOT NULL,
                filename TEXT,
                csv_bytes BLOB NOT NULL,
                submitted_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            )
            """
        )
        existing_pending_cols = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(pending_approvals)"
            ).fetchall()
        }
        for col in ("record_type", "submitted_by_email", "list_type"):
            if col not in existing_pending_cols:
                conn.execute(
                    f"ALTER TABLE pending_approvals ADD COLUMN {col} TEXT"
                )
        conn.execute(
            "INSERT OR IGNORE INTO counter (id, last_list_id) VALUES (1, 0)"
        )


# ---------------------------------------------------------------------------
# Public API (dispatches to Postgres or SQLite)
# ---------------------------------------------------------------------------


def next_list_id() -> str:
    if _is_postgres():
        return _pg_next_list_id()
    _sqlite_ensure_db()
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
    submitted_by_email: str | None = None,
    list_type: str | None = None,
    record_type: str | None = None,
    error_message: str | None = None,
) -> None:
    if _is_postgres():
        return _pg_record_submission(
            list_id, row_count, filename, status,
            list_name, submitted_by, submitted_by_email, list_type,
            record_type, error_message,
        )
    _sqlite_ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO submissions
            (list_id, row_count, filename, list_name, submitted_by,
             submitted_by_email, list_type, record_type, status, created_at,
             error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                list_id,
                row_count,
                filename,
                list_name,
                submitted_by,
                submitted_by_email,
                list_type,
                record_type,
                status,
                datetime.now(timezone.utc).isoformat(),
                error_message,
            ),
        )


def recent_submissions(limit: int = 25) -> list[dict]:
    if _is_postgres():
        return _pg_recent_submissions(limit)
    _sqlite_ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT list_id, list_name, submitted_by, submitted_by_email,
                   list_type, record_type, row_count, status, created_at,
                   filename, error_message
            FROM submissions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_history(reset_counter: bool = True) -> int:
    if _is_postgres():
        return _pg_clear_history(reset_counter)
    _sqlite_ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        before = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        conn.execute("DELETE FROM submissions")
        if reset_counter:
            conn.execute("UPDATE counter SET last_list_id = 0 WHERE id = 1")
    return int(before)


def add_to_approval_queue(
    submitted_by: str,
    list_name: str,
    row_count: int,
    filename: str | None,
    csv_bytes: bytes,
    record_type: str | None = None,
    submitted_by_email: str | None = None,
    list_type: str | None = None,
) -> int:
    if _is_postgres():
        return _pg_add_to_queue(
            submitted_by, submitted_by_email, list_name, list_type,
            row_count, filename, csv_bytes, record_type,
        )
    _sqlite_ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO pending_approvals
            (submitted_by, submitted_by_email, list_name, list_type,
             record_type, row_count, filename, csv_bytes, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                submitted_by,
                submitted_by_email,
                list_name,
                list_type,
                record_type,
                row_count,
                filename,
                csv_bytes,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return int(cur.lastrowid or 0)


def list_pending_approvals() -> list[dict]:
    if _is_postgres():
        return _pg_list_pending()
    _sqlite_ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT queue_id, submitted_by, submitted_by_email, list_name,
                   list_type, record_type, row_count, filename, submitted_at
            FROM pending_approvals
            WHERE status = 'pending'
            ORDER BY submitted_at ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_pending_approval(queue_id: int) -> dict | None:
    if _is_postgres():
        return _pg_get_pending(queue_id)
    _sqlite_ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM pending_approvals WHERE queue_id = ?",
            (queue_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_pending_approval(queue_id: int) -> None:
    if _is_postgres():
        return _pg_delete_pending(queue_id)
    _sqlite_ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM pending_approvals WHERE queue_id = ?",
            (queue_id,),
        )
