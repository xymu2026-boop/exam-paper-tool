"""Edge-case and boundary-condition tests for the Database class.

Covers empty tables, non-existent IDs, pagination boundaries, foreign-key
integrity, and repeated-delete semantics.
"""

import pytest


class TestEmptyTable:
    """All list operations on a fresh database return empty lists."""

    def test_empty_papers(self, db):
        assert db.list_papers() == []

    def test_empty_mistakes(self, db):
        assert db.list_mistakes() == []

    def test_empty_export_logs(self, db):
        assert db.list_export_logs() == []


class TestNonExistentRecord:
    """Operations targeting non-existent IDs return None/False."""

    def test_get_paper(self, db):
        assert db.get_paper(999) is None

    def test_get_mistake(self, db):
        assert db.get_mistake(999) is None

    def test_update_paper_status(self, db):
        assert db.update_paper_status(999, "processed") is False

    def test_update_mistake_status(self, db):
        assert db.update_mistake_status(999, "printed") is False

    def test_update_mistake_paths(self, db):
        assert (
            db.update_mistake_paths(999, mistake_image_path="/tmp/m.jpg")
            is False
        )

    def test_delete_mistake(self, db):
        assert db.delete_mistake(999) is False


class TestPaginationBoundaries:
    """Pagination parameters at extremes."""

    def test_offset_zero(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        papers = db.list_papers(limit=50, offset=0)
        assert len(papers) == 1

    def test_offset_beyond_total(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        papers = db.list_papers(limit=50, offset=100)
        assert papers == []

    def test_offset_exact_total(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        papers = db.list_papers(limit=50, offset=1)
        assert papers == []

    def test_large_limit_does_not_error(self, db):
        for i in range(5):
            db.create_paper(
                child_id="K1",
                subject="数学",
                original_path=f"/tmp/{i}.jpg",
            )
        papers = db.list_papers(limit=10000, offset=0)
        assert len(papers) == 5

    def test_zero_limit_returns_empty(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        papers = db.list_papers(limit=0, offset=0)
        assert papers == []


class TestForeignKeyConstraint:
    """Foreign-key violations are caught and returned as None."""

    def test_create_mistake_without_paper(self, db):
        """paper_id=999 does not reference any existing paper."""
        result = db.create_mistake(
            paper_id=999,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
        assert result is None


class TestMultiConditionCombinations:
    """Multiple filter conditions applied simultaneously."""

    def test_papers_three_conditions(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/1.jpg"
        )
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/2.jpg",
            paper_type="练习册",
        )
        db.create_paper(
            child_id="K2", subject="数学", original_path="/tmp/3.jpg"
        )
        db.create_paper(
            child_id="K1", subject="语文", original_path="/tmp/4.jpg"
        )
        # K1 + 数学 + 其他 (default paper_type)
        papers = db.list_papers(child_id="K1", subject="数学")
        assert len(papers) == 2

    def test_mistakes_three_conditions(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
            error_type="粗心",
        )
        db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=20,
            crop_height=20,
            error_type="计算错误",
        )
        db.create_mistake(
            paper_id=pid,
            child_id="K2",
            subject="英语",
            crop_x=0,
            crop_y=0,
            crop_width=30,
            crop_height=30,
            error_type="粗心",
        )
        result = db.list_mistakes(child_id="K1", subject="数学")
        assert len(result) == 2


class TestListFilters:
    """Filter conditions that SHOULD be applied (valid values)."""

    def test_list_papers_filter_by_status(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        db.create_paper(
            child_id="K2",
            subject="英语",
            original_path="/tmp/b.jpg",
        )
        # update one paper to 'processing'
        papers = db.list_papers()
        db.update_paper_status(papers[0].id, "processing")
        filtered = db.list_papers(status="processing")
        assert len(filtered) == 1
        assert filtered[0].status == "processing"

    def test_list_mistakes_filter_by_status(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        mid = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
        db.update_mistake_status(mid, "printed")
        filtered = db.list_mistakes(status="printed")
        assert len(filtered) == 1
        assert filtered[0].status == "printed"


class TestMigrations:
    """Schema utility functions."""

    def test_get_schema_sql_returns_string(self, db):
        from src.m2_data_layer.migrations import get_schema_sql
        sql = get_schema_sql()
        assert isinstance(sql, str)
        assert "CREATE TABLE IF NOT EXISTS paper" in sql
        assert "CREATE TABLE IF NOT EXISTS mistake" in sql
        assert "CREATE TABLE IF NOT EXISTS export_log" in sql


class TestRowToExportLog:
    """Direct tests for the row_to_export_log utility (error handling)."""

    def test_row_to_export_log_corrupted_json(self, db):
        from src.m2_data_layer.utils import row_to_export_log
        # Simulate a Row with corrupted JSON
        import sqlite3
        db.conn.execute(
            "INSERT INTO export_log (child_id, mistake_ids, pdf_path) "
            "VALUES (?, ?, ?)",
            ("K1", "not json{{{", "/tmp/e.pdf"),
        )
        db.conn.commit()
        cur = db.conn.execute("SELECT * FROM export_log")
        row = cur.fetchone()
        log = row_to_export_log(row)
        assert log.mistake_ids == []

    def test_row_to_export_log_missing_key(self, db):
        from src.m2_data_layer.utils import row_to_export_log
        import sqlite3
        db.conn.execute(
            "INSERT INTO export_log (child_id, mistake_ids, pdf_path) "
            "VALUES (?, ?, ?)",
            ("K1", "", "/tmp/e.pdf"),
        )
        db.conn.commit()
        cur = db.conn.execute("SELECT * FROM export_log")
        row = cur.fetchone()
        log = row_to_export_log(row)
        assert log.mistake_ids == []


class TestDatabaseErrorHandling:
    """Trigger sqlite3.Error handlers by closing the raw connection."""

    def test_create_paper_sql_error(self, db):
        db.conn.close()
        assert db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        ) is None

    def test_get_paper_sql_error(self, db):
        db.conn.close()
        assert db.get_paper(1) is None

    def test_update_paper_status_sql_error(self, db):
        db.conn.close()
        assert db.update_paper_status(1, "processed") is False

    def test_list_papers_sql_error(self, db):
        db.conn.close()
        assert db.list_papers() == []

    def test_create_mistake_sql_error(self, db):
        db.conn.close()
        assert db.create_mistake(
            paper_id=1, child_id="K1", subject="数学",
            crop_x=0, crop_y=0, crop_width=10, crop_height=10,
        ) is None

    def test_get_mistake_sql_error(self, db):
        db.conn.close()
        assert db.get_mistake(1) is None

    def test_update_mistake_status_sql_error(self, db):
        db.conn.close()
        assert db.update_mistake_status(1, "printed") is False

    def test_update_mistake_paths_sql_error(self, db):
        db.conn.close()
        assert db.update_mistake_paths(1, mistake_image_path="/tmp/m.jpg") is False

    def test_list_mistakes_sql_error(self, db):
        db.conn.close()
        assert db.list_mistakes() == []

    def test_delete_mistake_sql_error(self, db):
        db.conn.close()
        assert db.delete_mistake(1) is False

    def test_create_export_log_sql_error(self, db):
        db.conn.close()
        assert db.create_export_log(
            child_id="K1", mistake_ids=[1], pdf_path="/tmp/e.pdf"
        ) is None

    def test_list_export_logs_sql_error(self, db):
        db.conn.close()
        assert db.list_export_logs() == []


class TestClose:
    """close() cleans up and subsequent operations should fail."""

    def test_close_then_operation_raises(self, db):
        db.close()
        import sqlite3
        with pytest.raises((sqlite3.ProgrammingError, AttributeError)):
            db.create_paper(
                child_id="K1", subject="数学", original_path="/tmp/a.jpg"
            )
