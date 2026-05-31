"""Tests for JSON serialisation / deserialisation of export_log.mistake_ids.

The ``mistake_ids`` column is stored as JSON text in SQLite but should
be transparently serialised on write and deserialised on read.
"""

import json


class TestExportLogJSONRoundtrip:
    """Verify that list[int] survives a write-then-read cycle."""

    def test_simple_list(self, db):
        eid = db.create_export_log(
            child_id="K1", mistake_ids=[1, 2, 3], pdf_path="/tmp/e.pdf"
        )
        logs = db.list_export_logs()
        assert len(logs) == 1
        assert logs[0]["mistake_ids"] == [1, 2, 3]

    def test_sorted_storage(self, db):
        """IDs should be sorted before being written to the database."""
        eid = db.create_export_log(
            child_id="K1",
            mistake_ids=[5, 2, 8, 1, 3],
            pdf_path="/tmp/e.pdf",
        )
        logs = db.list_export_logs()
        assert logs[0]["mistake_ids"] == [1, 2, 3, 5, 8]

    def test_empty_list(self, db):
        eid = db.create_export_log(
            child_id="K1", mistake_ids=[], pdf_path="/tmp/e.pdf"
        )
        logs = db.list_export_logs()
        assert logs[0]["mistake_ids"] == []

    def test_single_element(self, db):
        eid = db.create_export_log(
            child_id="K2", mistake_ids=[42], pdf_path="/tmp/e.pdf"
        )
        logs = db.list_export_logs()
        assert logs[0]["mistake_ids"] == [42]

    def test_duplicate_ids(self, db):
        """Duplicates are preserved (no de-duplication)."""
        eid = db.create_export_log(
            child_id="K1",
            mistake_ids=[3, 3, 1, 1],
            pdf_path="/tmp/e.pdf",
        )
        logs = db.list_export_logs()
        # Sorting keeps duplicates adjacent: [1, 1, 3, 3]
        assert logs[0]["mistake_ids"] == [1, 1, 3, 3]

    def test_multiple_logs_independent(self, db):
        """Multiple export logs each have their own independent JSON."""
        eid1 = db.create_export_log(
            child_id="K1", mistake_ids=[10, 20], pdf_path="/tmp/a.pdf"
        )
        eid2 = db.create_export_log(
            child_id="K1", mistake_ids=[30], pdf_path="/tmp/b.pdf"
        )
        logs = db.list_export_logs(child_id="K1")
        ids_set = {frozenset(log["mistake_ids"]) for log in logs}
        assert frozenset({10, 20}) in ids_set
        assert frozenset({30}) in ids_set

    def test_corrupted_json_returns_empty_list(self, db):
        """If raw JSON is corrupt, the error handler should return []."""
        db.create_export_log(
            child_id="K1", mistake_ids=[1], pdf_path="/tmp/e.pdf"
        )
        # Directly corrupt the JSON in the database
        db.conn.execute(
            "UPDATE export_log SET mistake_ids = ? WHERE child_id = ?",
            ("not valid json[[", "K1"),
        )
        db.conn.commit()
        logs = db.list_export_logs()
        assert len(logs) == 1
        assert logs[0]["mistake_ids"] == []

    def test_raw_storage_is_json(self, db):
        """Peek at the raw SQLite value to confirm it's actually JSON."""
        db.create_export_log(
            child_id="K1",
            mistake_ids=[1, 2, 3],
            pdf_path="/tmp/e.pdf",
        )
        # Access the raw connection to inspect stored value
        cur = db.conn.execute(
            "SELECT mistake_ids FROM export_log WHERE child_id = ?",
            ("K1",),
        )
        row = cur.fetchone()
        raw = row["mistake_ids"]
        assert isinstance(raw, str)
        assert json.loads(raw) == [1, 2, 3]

    def test_mistake_ids_type_in_dict(self, db):
        """Ensure the deserialised field is actually list[int]."""
        db.create_export_log(
            child_id="K1",
            mistake_ids=[4, 5, 6],
            pdf_path="/tmp/e.pdf",
        )
        logs = db.list_export_logs()
        ids = logs[0]["mistake_ids"]
        assert isinstance(ids, list)
        assert all(isinstance(x, int) for x in ids)
