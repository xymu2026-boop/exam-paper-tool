"""M2 Database class — single entry point for all SQLite operations.

``Database`` encapsulates the connection, schema initialisation, and every
CRUD operation defined in INTERFACE-CONTACT.md Section 4.2.  All SQL is
parameterised; writes are protected by a ``threading.Lock`` for safe use
with FastAPI's thread pool.
"""

import json
import os
import sqlite3
import threading
from typing import Any, Optional

from .models import Paper, Mistake, ExportLog
from .migrations import run_migrations
from .utils import row_to_paper, row_to_mistake, row_to_export_log, build_where

# ---------------------------------------------------------------------------
# Validation sets — application-level checks before SQL execution
# ---------------------------------------------------------------------------

VALID_CHILD_IDS: frozenset[str] = frozenset({'K1', 'K2'})
VALID_SUBJECTS: frozenset[str] = frozenset(
    {'数学', '语文', '英语', '科学', '其他'}
)
VALID_PAPER_STATUSES: frozenset[str] = frozenset(
    {'pending', 'processing', 'processed', 'failed'}
)
VALID_MISTAKE_STATUSES: frozenset[str] = frozenset(
    {'new', 'printed', 'practiced', 'passed', 'retry'}
)
VALID_ERROR_TYPES: frozenset[Optional[str]] = frozenset(
    {'粗心', '概念不清', '计算错误', '不会做', '其他', None}
)
VALID_PAPER_TYPES: frozenset[str] = frozenset(
    {'作业', '单元卷', '考试卷', '练习册', '其他'}
)


class Database:
    """Database access layer for the Exam Paper Tool.

    All database mutations go through this class — other modules **must
    not** import ``sqlite3`` directly.

    Usage::

        db = Database('data/exam_paper.db')
        pid = db.create_paper(...)
        paper = db.get_paper(pid)
        db.close()
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, db_path: str = 'data/exam_paper.db') -> None:
        """Initialise the database connection and auto-create tables.

        Args:
            db_path:
                Path to the SQLite database file.  Use ``':memory:'``
                for tests (no disk I/O).  Parent directories are created
                automatically for file-based paths.
        """
        self.db_path = db_path
        self._lock = threading.Lock()

        if db_path != ':memory:':
            parent = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(parent, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        with self.conn:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            run_migrations(self.conn)

    def close(self) -> None:
        """Close the underlying database connection (if open)."""
        if self.conn:
            self.conn.close()
            self.conn = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Validation helpers  (all return ``bool``)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_child_id(value: str) -> bool:
        return value in VALID_CHILD_IDS

    @staticmethod
    def _validate_subject(value: str) -> bool:
        return value in VALID_SUBJECTS

    @staticmethod
    def _validate_paper_status(value: str) -> bool:
        return value in VALID_PAPER_STATUSES

    @staticmethod
    def _validate_mistake_status(value: str) -> bool:
        return value in VALID_MISTAKE_STATUSES

    @staticmethod
    def _validate_error_type(value: Optional[str]) -> bool:
        return value in VALID_ERROR_TYPES

    @staticmethod
    def _validate_paper_type(value: str) -> bool:
        return value in VALID_PAPER_TYPES

    # ------------------------------------------------------------------
    # Paper CRUD
    # ------------------------------------------------------------------

    def create_paper(
        self,
        child_id: str,
        subject: str,
        original_path: str,
        paper_type: str = '其他',
        title: str = None,
    ) -> Optional[int]:
        """Create a paper record and return its ``id``.

        Returns ``None`` on validation failure or database error.
        """
        if not self._validate_child_id(child_id):
            return None
        if not self._validate_subject(subject):
            return None
        if not self._validate_paper_type(paper_type):
            return None

        try:
            with self._lock:
                cur = self.conn.execute(
                    "INSERT INTO paper "
                    "(child_id, subject, paper_type, title, original_path) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (child_id, subject, paper_type, title, original_path),
                )
                return cur.lastrowid
        except sqlite3.Error:
            return None

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        """Fetch a single paper by its ``id``.

        Returns ``None`` if no such record exists.
        """
        try:
            cur = self.conn.execute(
                "SELECT * FROM paper WHERE id = ?", (paper_id,)
            )
            row = cur.fetchone()
            return row_to_paper(row) if row is not None else None
        except sqlite3.Error:
            return None

    def update_paper_status(
        self,
        paper_id: int,
        status: str,
        processed_path: str = None,
        cleaned_path: str = None,
        quality_score: float = None,
        error_message: str = None,
    ) -> bool:
        """Update the processing status of a paper.

        Only the explicitly provided optional fields are written to the
        database.  Returns ``False`` on validation failure, non-existent
        record, or database error.
        """
        if not self._validate_paper_status(status):
            return False

        set_clauses: list[str] = ["status = ?"]
        params: list[Any] = [status]

        for col, val in (
            ("processed_path", processed_path),
            ("cleaned_path", cleaned_path),
            ("quality_score", quality_score),
            ("error_message", error_message),
        ):
            if val is not None:
                set_clauses.append(f"{col} = ?")
                params.append(val)

        params.append(paper_id)
        sql = f"UPDATE paper SET {', '.join(set_clauses)} WHERE id = ?"

        try:
            with self._lock:
                cur = self.conn.execute(sql, params)
                return cur.rowcount > 0
        except sqlite3.Error:
            return False

    def list_papers(
        self,
        child_id: str = None,
        subject: str = None,
        status: str = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Paper]:
        """List papers with optional filtering and pagination.

        Filters that fail validation are silently ignored (not applied).
        Returns an empty list when no records match.
        """
        conditions: dict[str, Any] = {}
        if child_id is not None and self._validate_child_id(child_id):
            conditions["child_id"] = child_id
        if subject is not None and self._validate_subject(subject):
            conditions["subject"] = subject
        if status is not None and self._validate_paper_status(status):
            conditions["status"] = status

        where_clause, params = build_where(conditions)
        params.extend([limit, offset])

        sql = f"SELECT * FROM paper{where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"

        try:
            cur = self.conn.execute(sql, params)
            return [row_to_paper(row) for row in cur.fetchall()]
        except sqlite3.Error:
            return []

    def count_papers(
        self,
        child_id: str = None,
        subject: str = None,
        status: str = None,
    ) -> int:
        """Count papers matching the given filters.

        Uses the same filter logic as :meth:`list_papers` but returns a
        single integer total via ``SELECT COUNT(*)``.  Filters that fail
        validation are silently ignored.  Returns ``0`` on database error.
        """
        conditions: dict[str, Any] = {}
        if child_id is not None and self._validate_child_id(child_id):
            conditions["child_id"] = child_id
        if subject is not None and self._validate_subject(subject):
            conditions["subject"] = subject
        if status is not None and self._validate_paper_status(status):
            conditions["status"] = status

        where_clause, params = build_where(conditions)
        sql = f"SELECT COUNT(*) FROM paper{where_clause}"

        try:
            cur = self.conn.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row is not None else 0
        except sqlite3.Error:
            return 0

    # ------------------------------------------------------------------
    # Mistake CRUD
    # ------------------------------------------------------------------

    def create_mistake(
        self,
        paper_id: int,
        child_id: str,
        subject: str,
        crop_x: int,
        crop_y: int,
        crop_width: int,
        crop_height: int,
        mistake_image_path: str = None,
        clean_mistake_image_path: str = None,
        note: str = None,
        error_type: str = None,
    ) -> Optional[int]:
        """Create a mistake record and return its ``id``.

        Returns ``None`` on validation failure, FK violation, or
        database error.
        """
        if not self._validate_child_id(child_id):
            return None
        if not self._validate_subject(subject):
            return None
        if not self._validate_error_type(error_type):
            return None

        try:
            with self._lock:
                cur = self.conn.execute(
                    "INSERT INTO mistake "
                    "(paper_id, child_id, subject, crop_x, crop_y, "
                    "crop_width, crop_height, mistake_image_path, "
                    "clean_mistake_image_path, note, error_type) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        paper_id,
                        child_id,
                        subject,
                        crop_x,
                        crop_y,
                        crop_width,
                        crop_height,
                        mistake_image_path,
                        clean_mistake_image_path,
                        note,
                        error_type,
                    ),
                )
                return cur.lastrowid
        except sqlite3.Error:
            return None

    def get_mistake(self, mistake_id: int) -> Optional[Mistake]:
        """Fetch a single mistake by its ``id``.

        Returns ``None`` if no such record exists.
        """
        try:
            cur = self.conn.execute(
                "SELECT * FROM mistake WHERE id = ?", (mistake_id,)
            )
            row = cur.fetchone()
            return row_to_mistake(row) if row is not None else None
        except sqlite3.Error:
            return None

    def update_mistake_status(self, mistake_id: int, status: str) -> bool:
        """Update the status of a mistake.

        Returns ``False`` on validation failure, non-existent record,
        or database error.
        """
        if not self._validate_mistake_status(status):
            return False

        try:
            with self._lock:
                cur = self.conn.execute(
                    "UPDATE mistake SET status = ? WHERE id = ?",
                    (status, mistake_id),
                )
                return cur.rowcount > 0
        except sqlite3.Error:
            return False

    def update_mistake_paths(
        self,
        mistake_id: int,
        mistake_image_path: str = None,
        clean_mistake_image_path: str = None,
    ) -> bool:
        """Update the image paths for a mistake (backfill after creation).

        Returns ``False`` when both path arguments are ``None``, the
        record does not exist, or a database error occurs.
        """
        set_clauses: list[str] = []
        params: list[Any] = []

        if mistake_image_path is not None:
            set_clauses.append("mistake_image_path = ?")
            params.append(mistake_image_path)
        if clean_mistake_image_path is not None:
            set_clauses.append("clean_mistake_image_path = ?")
            params.append(clean_mistake_image_path)

        if not set_clauses:
            return False

        params.append(mistake_id)
        sql = f"UPDATE mistake SET {', '.join(set_clauses)} WHERE id = ?"

        try:
            with self._lock:
                cur = self.conn.execute(sql, params)
                return cur.rowcount > 0
        except sqlite3.Error:
            return False

    def update_mistake_fields(
        self,
        mistake_id: int,
        note: str = None,
        error_type: str = None,
    ) -> bool:
        """Update free-text/category fields on a mistake (note, error_type).

        Only the explicitly provided non-``None`` fields are written.  If
        both ``note`` and ``error_type`` are ``None`` the call is a no-op
        and returns ``False``.  ``error_type`` is validated against the
        allowed enum before issuing SQL.

        Returns ``False`` on validation failure, non-existent record, or
        database error.
        """
        if error_type is not None and not self._validate_error_type(error_type):
            return False

        set_clauses: list[str] = []
        params: list[Any] = []

        if note is not None:
            set_clauses.append("note = ?")
            params.append(note)
        if error_type is not None:
            set_clauses.append("error_type = ?")
            params.append(error_type)

        if not set_clauses:
            return False

        params.append(mistake_id)
        sql = f"UPDATE mistake SET {', '.join(set_clauses)} WHERE id = ?"

        try:
            with self._lock:
                cur = self.conn.execute(sql, params)
                return cur.rowcount > 0
        except sqlite3.Error:
            return False

    def list_mistakes(
        self,
        child_id: str = None,
        subject: str = None,
        status: str = None,
        paper_id: int = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Mistake]:
        """List mistakes with optional filtering and pagination.

        Filters that fail validation are silently ignored.  ``paper_id``
        is included as-is (it is an integer FK, not a constrained enum).
        Returns an empty list when no records match.
        """
        conditions: dict[str, Any] = {}
        if child_id is not None and self._validate_child_id(child_id):
            conditions["child_id"] = child_id
        if subject is not None and self._validate_subject(subject):
            conditions["subject"] = subject
        if status is not None and self._validate_mistake_status(status):
            conditions["status"] = status
        if paper_id is not None:
            conditions["paper_id"] = paper_id

        where_clause, params = build_where(conditions)
        params.extend([limit, offset])

        sql = (
            f"SELECT * FROM mistake{where_clause} "
            "ORDER BY id DESC LIMIT ? OFFSET ?"
        )

        try:
            cur = self.conn.execute(sql, params)
            return [row_to_mistake(row) for row in cur.fetchall()]
        except sqlite3.Error:
            return []

    def count_mistakes(
        self,
        child_id: str = None,
        subject: str = None,
        status: str = None,
        paper_id: int = None,
    ) -> int:
        """Count mistakes matching the given filters.

        Uses the same filter logic as :meth:`list_mistakes` but returns a
        single integer total via ``SELECT COUNT(*)``.  Filters that fail
        validation are silently ignored.  Returns ``0`` on database error.
        """
        conditions: dict[str, Any] = {}
        if child_id is not None and self._validate_child_id(child_id):
            conditions["child_id"] = child_id
        if subject is not None and self._validate_subject(subject):
            conditions["subject"] = subject
        if status is not None and self._validate_mistake_status(status):
            conditions["status"] = status
        if paper_id is not None:
            conditions["paper_id"] = paper_id

        where_clause, params = build_where(conditions)
        sql = f"SELECT COUNT(*) FROM mistake{where_clause}"

        try:
            cur = self.conn.execute(sql, params)
            row = cur.fetchone()
            return int(row[0]) if row is not None else 0
        except sqlite3.Error:
            return 0

    def delete_mistake(self, mistake_id: int) -> bool:
        """Permanently delete a mistake record.

        Returns ``False`` if the record does not exist or a database
        error occurs.
        """
        try:
            with self._lock:
                cur = self.conn.execute(
                    "DELETE FROM mistake WHERE id = ?", (mistake_id,)
                )
                return cur.rowcount > 0
        except sqlite3.Error:
            return False

    # ------------------------------------------------------------------
    # Export Log
    # ------------------------------------------------------------------

    def create_export_log(
        self,
        child_id: str,
        mistake_ids: list[int],
        pdf_path: str,
        subject: str = None,
    ) -> Optional[int]:
        """Record a PDF export.

        The ``mistake_ids`` list is JSON-serialised (and sorted for
        consistent storage) before insertion.

        Returns ``None`` on validation failure or database error.
        """
        if not self._validate_child_id(child_id):
            return None
        if subject is not None and not self._validate_subject(subject):
            return None

        mistake_ids_json = json.dumps(sorted(mistake_ids))

        try:
            with self._lock:
                cur = self.conn.execute(
                    "INSERT INTO export_log "
                    "(child_id, subject, mistake_ids, pdf_path) "
                    "VALUES (?, ?, ?, ?)",
                    (child_id, subject, mistake_ids_json, pdf_path),
                )
                return cur.lastrowid
        except sqlite3.Error:
            return None

    def update_export_log_path(self, export_id: int, pdf_path: str) -> bool:
        """Update the ``pdf_path`` of an existing export log entry.

        Used by callers who reserve an ``export_id`` with a placeholder
        path and need to backfill the real on-disk location once it is
        known (e.g. ``data/exports/{export_id}.pdf``).

        Returns ``False`` if the record does not exist or a database
        error occurs.
        """
        try:
            with self._lock:
                cur = self.conn.execute(
                    "UPDATE export_log SET pdf_path = ? WHERE id = ?",
                    (pdf_path, export_id),
                )
                return cur.rowcount > 0
        except sqlite3.Error:
            return False

    def list_export_logs(
        self,
        child_id: str = None,
        limit: int = 20,
    ) -> list[dict]:
        """List export log entries.

        Each returned dict includes the ``mistake_ids`` field already
        deserialised from JSON to ``list[int]``.

        Returns an empty list when no records match.
        """
        conditions: dict[str, Any] = {}
        if child_id is not None and self._validate_child_id(child_id):
            conditions["child_id"] = child_id

        where_clause, params = build_where(conditions)
        params.append(limit)

        sql = (
            f"SELECT * FROM export_log{where_clause} "
            "ORDER BY id DESC LIMIT ?"
        )

        try:
            cur = self.conn.execute(sql, params)
            results: list[dict] = []
            for row in cur.fetchall():
                data = dict(row)
                try:
                    data["mistake_ids"] = json.loads(data["mistake_ids"])
                except (json.JSONDecodeError, TypeError, KeyError):
                    data["mistake_ids"] = []
                results.append(data)
            return results
        except sqlite3.Error:
            return []
