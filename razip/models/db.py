import sqlite3
import os
import re
from config import Config

DB_PATH = Config.DB_PATH


def get_db():
    """Open a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _adapt_sql(sql):
    """Convert MySQL-style SQL to SQLite-compatible SQL."""
    sql = sql.replace('%s', '?')
    sql = re.sub(r'\bNOW\(\)', "datetime('now')", sql, flags=re.IGNORECASE)
    return sql


def query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    """
    Convenience wrapper around SQLite.
    Returns:
      - lastrowid  if commit=True
      - one dict   if fetchone=True
      - list[dict] if fetchall=True
      - None       otherwise
    """
    sql = _adapt_sql(sql)
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())

        if commit:
            conn.commit()
            return cursor.lastrowid

        if fetchone:
            row = cursor.fetchone()
            return dict(row) if row else None

        if fetchall:
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

        return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def create_tables():
    """Create all tables if they don't already exist (runs on app startup)."""
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name    TEXT    NOT NULL,
        last_name     TEXT    NOT NULL,
        email         TEXT    NOT NULL UNIQUE,
        password_hash TEXT    NOT NULL,
        created_at    DATETIME DEFAULT (datetime('now')),
        last_login    DATETIME
    );

    CREATE TABLE IF NOT EXISTS resumes (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id          INTEGER NOT NULL,
        filename         TEXT    NOT NULL,
        stored_path      TEXT    NOT NULL,
        raw_text         TEXT,
        skills_extracted TEXT,
        job_title        TEXT,
        industry         TEXT,
        job_description  TEXT,
        upload_date      DATETIME DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS analysis_results (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_id         INTEGER NOT NULL,
        ats_score         INTEGER DEFAULT 0,
        readability_score INTEGER DEFAULT 0,
        keyword_score     INTEGER DEFAULT 0,
        ai_summary        TEXT,
        ai_suggestions    TEXT,
        ai_strengths      TEXT    DEFAULT '[]',
        ai_weaknesses     TEXT    DEFAULT '[]',
        ai_suitable_roles TEXT    DEFAULT '[]',
        present_skills    TEXT,
        missing_skills    TEXT,
        score_breakdown   TEXT,
        analyzed_at       DATETIME DEFAULT (datetime('now')),
        FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS applications (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        resume_id   INTEGER,
        job_title   TEXT    NOT NULL,
        company     TEXT    NOT NULL,
        job_url     TEXT,
        location    TEXT,
        salary      TEXT,
        match_score INTEGER DEFAULT 0,
        source      TEXT    DEFAULT 'manual',
        status      TEXT    DEFAULT 'pending'
                    CHECK(status IN ('pending','applied','viewed','interview','rejected','failed')),
        applied_at  DATETIME DEFAULT (datetime('now')),
        updated_at  DATETIME DEFAULT (datetime('now')),
        FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
        FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS site_settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS resume_builder_drafts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        name       TEXT    DEFAULT 'My Resume',
        data       TEXT    NOT NULL DEFAULT '{}',
        template   TEXT    DEFAULT 'professional',
        created_at DATETIME DEFAULT (datetime('now')),
        updated_at DATETIME DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_resumes_user        ON resumes(user_id);
    CREATE INDEX IF NOT EXISTS idx_analysis_resume     ON analysis_results(resume_id);
    CREATE INDEX IF NOT EXISTS idx_applications_user   ON applications(user_id);
    CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
    CREATE INDEX IF NOT EXISTS idx_builder_user        ON resume_builder_drafts(user_id);
    """
    conn = get_db()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def migrate_tables():
    """
    Add columns introduced after initial schema creation.
    Safely skips columns that already exist.
    """
    new_columns = [
        ("analysis_results", "ai_strengths",      "TEXT DEFAULT '[]'"),
        ("analysis_results", "ai_weaknesses",     "TEXT DEFAULT '[]'"),
        ("analysis_results", "ai_suitable_roles", "TEXT DEFAULT '[]'"),
    ]
    conn = get_db()
    try:
        for table, col, definition in new_columns:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            except Exception:
                pass  # column already exists — safe to ignore
        conn.commit()
    finally:
        conn.close()
