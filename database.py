"""
database.py — SQLite data layer for StudyTracker
All database access goes through this module.
study_tracker.py and analysis.py import from here — never touch sqlite3 directly.
"""

import os
import sqlite3

DB_PATH = os.path.join("data", "study_tracker.db")


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """
    Open and return a connection to the SQLite database.
    - Row factory set to sqlite3.Row so rows behave like dicts.
    - Foreign key enforcement enabled on every connection.
    Caller is responsible for closing the connection.
    """
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS study_entries (
    id             TEXT PRIMARY KEY,
    date           TEXT NOT NULL,
    start_time     TEXT NOT NULL DEFAULT '',
    end_time       TEXT NOT NULL DEFAULT '',
    subject        TEXT NOT NULL,
    hours          REAL DEFAULT 0,
    accomplished   TEXT DEFAULT '',
    next_goal      TEXT DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS study_plans (
    id             TEXT PRIMARY KEY,
    subject        TEXT NOT NULL,
    target_hours   REAL DEFAULT 0,
    goal           TEXT DEFAULT '',
    due_date       TEXT DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'pending',
    completed_date TEXT DEFAULT ''
);
"""

def _migrate_schema(conn: sqlite3.Connection):
    """
    Add columns introduced after initial schema creation.
    Checks existing columns first — no-op if columns already exist.
    """
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(study_entries)").fetchall()
    }

    additions = {
        "start_time" : "ALTER TABLE study_entries ADD COLUMN start_time TEXT NOT NULL DEFAULT ''",
        "end_time"   : "ALTER TABLE study_entries ADD COLUMN end_time   TEXT NOT NULL DEFAULT ''",
        "created_at" : "ALTER TABLE study_entries ADD COLUMN created_at TEXT NOT NULL DEFAULT ''",
    }

    for col, sql in additions.items():
        if col not in existing:
            conn.execute(sql)

    conn.commit()


def init_db():
    """Create tables if they don't exist, then apply any schema migrations."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_schema(conn)
    finally:
        conn.close()


# ── ID generation ─────────────────────────────────────────────────────────────

def next_entry_id() -> str:
    """
    Return the next E-prefixed ID using COUNT(*)+1 inside a single transaction.
    Safer than reading MAX(id) separately — avoids race conditions under
    concurrent Streamlit sessions.
    """
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM study_entries"
        ).fetchone()[0]
        return f"E{count + 1:03d}"
    finally:
        conn.close()


def next_plan_id() -> str:
    """Return the next P-prefixed ID using COUNT(*)+1."""
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM study_plans"
        ).fetchone()[0]
        return f"P{count + 1:03d}"
    finally:
        conn.close()


# ── Study entries — CRUD ──────────────────────────────────────────────────────

def insert_entry(entry: dict):
    """Insert a single study entry dict into the database."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO study_entries
               (id, date, start_time, end_time, subject, hours,
                accomplished, next_goal, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry["id"],
                entry["date"],
                entry["start_time"],
                entry["end_time"],
                entry["subject"],
                entry["hours"],
                entry["accomplished"],
                entry["next_goal"],
                entry["created_at"],
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_all_entries() -> list[dict]:
    """Return all study entries as a list of dicts, ordered by date and start time."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM study_entries ORDER BY date ASC, start_time ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_entries_by_date(date: str) -> list[dict]:
    """
    Return all entries for a specific date, ordered by start_time.
    Used by overlap detection before inserting a new entry.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM study_entries WHERE date = ? ORDER BY start_time ASC",
            (date,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Study plans — CRUD ────────────────────────────────────────────────────────

def insert_plan(plan: dict):
    """Insert a single study plan dict into the database."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO study_plans
               (id, subject, target_hours, goal, due_date, status, completed_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                plan["id"],
                plan["subject"],
                plan["target_hours"],
                plan["goal"],
                plan["due_date"],
                plan["status"],
                plan["completed_date"],
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_all_plans() -> list[dict]:
    """Return all study plans as a list of dicts, ordered by id."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM study_plans ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_plan_status(plan_id: str, status: str, completed_date: str = ""):
    """Flip a plan's status and optionally stamp the completed_date."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE study_plans
               SET status = ?, completed_date = ?
               WHERE id = ?""",
            (status, completed_date, plan_id)
        )
        conn.commit()
    finally:
        conn.close()


def update_plan_field(plan_id: str, field: str, value: str):
    """
    Update a single editable field on a plan.
    field must be one of: target_hours, due_date, goal.
    Allowlist prevents SQL injection via the column name,
    since parameterized queries only cover values, not column names.
    """
    ALLOWED_FIELDS = {"target_hours", "due_date", "goal"}
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"Field '{field}' is not editable.")

    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE study_plans SET {field} = ? WHERE id = ?",
            (value, plan_id)
        )
        conn.commit()
    finally:
        conn.close()
