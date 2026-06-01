"""Database schema migrations — centralised DDL for the M2 data layer.

All ``CREATE TABLE`` and ``CREATE INDEX`` statements live here so that
schema changes require editing only one file.  The ``run_migrations``
function is idempotent (``IF NOT EXISTS``) and safe to call on every
application startup.
"""

import sqlite3

# ---------------------------------------------------------------------------
# Schema DDL — matches INTERFACE-CONTRACT.md Section 3.1 exactly.
# Every CHECK constraint, default value, and column type is preserved.
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS paper (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT NOT NULL CHECK(child_id IN ('K1', 'K2')),
    subject TEXT NOT NULL CHECK(subject IN ('数学','语文','英语','科学','其他')),
    paper_type TEXT DEFAULT '其他' CHECK(paper_type IN ('作业','单元卷','考试卷','练习册','其他')),
    title TEXT,
    original_path TEXT NOT NULL,
    processed_path TEXT,
    cleaned_path TEXT,
    red_mask_path TEXT,
    handwriting_mask_path TEXT,
    combined_mask_path TEXT,
    upload_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','processed','failed')),
    quality_score REAL,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS mistake (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES paper(id),
    child_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    crop_x INTEGER NOT NULL,
    crop_y INTEGER NOT NULL,
    crop_width INTEGER NOT NULL,
    crop_height INTEGER NOT NULL,
    mistake_image_path TEXT,
    clean_mistake_image_path TEXT,
    note TEXT,
    error_type TEXT CHECK(error_type IN ('粗心','概念不清','计算错误','不会做','其他',NULL)),
    status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','printed','practiced','passed','retry')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS export_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT NOT NULL,
    subject TEXT,
    mistake_ids TEXT NOT NULL,  -- JSON array of mistake IDs
    pdf_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_paper_child_id ON paper(child_id);
CREATE INDEX IF NOT EXISTS idx_paper_subject ON paper(subject);
CREATE INDEX IF NOT EXISTS idx_paper_status ON paper(status);

CREATE INDEX IF NOT EXISTS idx_mistake_child_id ON mistake(child_id);
CREATE INDEX IF NOT EXISTS idx_mistake_subject ON mistake(subject);
CREATE INDEX IF NOT EXISTS idx_mistake_status ON mistake(status);
CREATE INDEX IF NOT EXISTS idx_mistake_paper_id ON mistake(paper_id);

CREATE INDEX IF NOT EXISTS idx_export_log_child_id ON export_log(child_id);
"""


def run_migrations(conn: sqlite3.Connection) -> None:
    """Execute all ``CREATE TABLE IF NOT EXISTS`` and ``CREATE INDEX``
    statements against *conn*.

    This function is idempotent — it is safe to call on every startup.
    """
    conn.executescript(SCHEMA_SQL)
    # V2 新增列: 对已有数据库做 ALTER TABLE ADD COLUMN (忽略"已存在"错误)
    _add_column_if_missing(conn, "paper", "red_mask_path", "TEXT")
    _add_column_if_missing(conn, "paper", "handwriting_mask_path", "TEXT")
    _add_column_if_missing(conn, "paper", "combined_mask_path", "TEXT")


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_type: str
) -> None:
    """Add a column if it doesn't already exist (idempotent)."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    except sqlite3.OperationalError:
        pass  # column already exists


def get_schema_sql() -> str:
    """Return the full schema DDL for reference / debugging."""
    return SCHEMA_SQL
