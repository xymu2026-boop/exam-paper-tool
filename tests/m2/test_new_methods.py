"""Tests for the M2 methods added to remove M4's private-attribute access
and to replace its O(N) total-count hack:

- ``count_papers``           — fast COUNT(*) for paper list pagination.
- ``count_mistakes``         — fast COUNT(*) for mistake list pagination.
- ``update_mistake_fields``  — note / error_type updater used by M4.
- ``update_export_log_path`` — pdf_path backfill used by M4 export flow.
"""

from src.m2_data_layer import Database


# ======================================================================
# count_papers
# ======================================================================

class TestCountPapers:
    def test_empty_db_returns_zero(self, db):
        assert db.count_papers() == 0

    def test_total_after_inserts(self, db):
        for _ in range(3):
            db.create_paper(
                child_id="K1", subject="数学", original_path="/tmp/a.jpg"
            )
        assert db.count_papers() == 3

    def test_count_filtered_by_child_id(self, db):
        db.create_paper(child_id="K1", subject="数学", original_path="/x")
        db.create_paper(child_id="K1", subject="数学", original_path="/y")
        db.create_paper(child_id="K2", subject="数学", original_path="/z")
        assert db.count_papers(child_id="K1") == 2
        assert db.count_papers(child_id="K2") == 1

    def test_count_filtered_by_subject(self, db):
        db.create_paper(child_id="K1", subject="数学", original_path="/x")
        db.create_paper(child_id="K1", subject="语文", original_path="/y")
        assert db.count_papers(subject="数学") == 1
        assert db.count_papers(subject="语文") == 1

    def test_count_filtered_by_status(self, db):
        pid1 = db.create_paper(
            child_id="K1", subject="数学", original_path="/a"
        )
        db.create_paper(child_id="K1", subject="数学", original_path="/b")
        db.update_paper_status(pid1, "processed")
        assert db.count_papers(status="pending") == 1
        assert db.count_papers(status="processed") == 1

    def test_count_combined_filters(self, db):
        db.create_paper(child_id="K1", subject="数学", original_path="/a")
        db.create_paper(child_id="K1", subject="语文", original_path="/b")
        db.create_paper(child_id="K2", subject="数学", original_path="/c")
        assert db.count_papers(child_id="K1", subject="数学") == 1

    def test_count_invalid_filter_silently_ignored(self, db):
        db.create_paper(child_id="K1", subject="数学", original_path="/a")
        db.create_paper(child_id="K2", subject="数学", original_path="/b")
        # Invalid child_id should be ignored (matches list_papers behaviour).
        assert db.count_papers(child_id="BAD") == 2

    def test_count_matches_list_total(self, db):
        for i in range(7):
            db.create_paper(
                child_id="K1", subject="数学", original_path=f"/{i}"
            )
        listed = db.list_papers(limit=1_000_000)
        assert db.count_papers() == len(listed)


# ======================================================================
# count_mistakes
# ======================================================================

class TestCountMistakes:
    def _make_paper(self, db, child="K1", subject="数学"):
        return db.create_paper(
            child_id=child, subject=subject, original_path="/p.jpg"
        )

    def test_empty_db_returns_zero(self, db):
        assert db.count_mistakes() == 0

    def test_total_after_inserts(self, db):
        pid = self._make_paper(db)
        for _ in range(4):
            db.create_mistake(
                paper_id=pid, child_id="K1", subject="数学",
                crop_x=0, crop_y=0, crop_width=10, crop_height=10,
            )
        assert db.count_mistakes() == 4

    def test_count_filtered_by_paper_id(self, db):
        pid1 = self._make_paper(db)
        pid2 = self._make_paper(db)
        db.create_mistake(
            paper_id=pid1, child_id="K1", subject="数学",
            crop_x=0, crop_y=0, crop_width=10, crop_height=10,
        )
        db.create_mistake(
            paper_id=pid2, child_id="K1", subject="数学",
            crop_x=0, crop_y=0, crop_width=10, crop_height=10,
        )
        assert db.count_mistakes(paper_id=pid1) == 1
        assert db.count_mistakes(paper_id=pid2) == 1

    def test_count_filtered_by_child_subject_status(self, db):
        pid = self._make_paper(db)
        mid = db.create_mistake(
            paper_id=pid, child_id="K1", subject="数学",
            crop_x=0, crop_y=0, crop_width=10, crop_height=10,
        )
        db.create_mistake(
            paper_id=pid, child_id="K1", subject="数学",
            crop_x=0, crop_y=0, crop_width=10, crop_height=10,
        )
        db.update_mistake_status(mid, "passed")
        assert db.count_mistakes(child_id="K1") == 2
        assert db.count_mistakes(subject="数学") == 2
        assert db.count_mistakes(status="new") == 1
        assert db.count_mistakes(status="passed") == 1

    def test_count_invalid_filter_silently_ignored(self, db):
        pid = self._make_paper(db)
        db.create_mistake(
            paper_id=pid, child_id="K1", subject="数学",
            crop_x=0, crop_y=0, crop_width=10, crop_height=10,
        )
        assert db.count_mistakes(subject="不存在") == 1

    def test_count_matches_list_total(self, db):
        pid = self._make_paper(db)
        for _ in range(6):
            db.create_mistake(
                paper_id=pid, child_id="K1", subject="数学",
                crop_x=0, crop_y=0, crop_width=10, crop_height=10,
            )
        listed = db.list_mistakes(limit=1_000_000)
        assert db.count_mistakes() == len(listed)


# ======================================================================
# update_mistake_fields
# ======================================================================

class TestUpdateMistakeFields:
    def _make_mistake(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/p.jpg"
        )
        return db.create_mistake(
            paper_id=pid, child_id="K1", subject="数学",
            crop_x=0, crop_y=0, crop_width=10, crop_height=10,
        )

    def test_update_note_only(self, db):
        mid = self._make_mistake(db)
        assert db.update_mistake_fields(mid, note="忘记进位") is True
        assert db.get_mistake(mid).note == "忘记进位"

    def test_update_error_type_only(self, db):
        mid = self._make_mistake(db)
        assert db.update_mistake_fields(mid, error_type="粗心") is True
        assert db.get_mistake(mid).error_type == "粗心"

    def test_update_both_fields(self, db):
        mid = self._make_mistake(db)
        ok = db.update_mistake_fields(
            mid, note="加法错", error_type="计算错误"
        )
        assert ok is True
        m = db.get_mistake(mid)
        assert m.note == "加法错"
        assert m.error_type == "计算错误"

    def test_no_fields_returns_false(self, db):
        mid = self._make_mistake(db)
        assert db.update_mistake_fields(mid) is False

    def test_invalid_error_type_returns_false(self, db):
        mid = self._make_mistake(db)
        assert db.update_mistake_fields(mid, error_type="不在枚举里") is False
        # Note must not have been written either.
        assert db.get_mistake(mid).error_type is None

    def test_nonexistent_id_returns_false(self, db):
        assert db.update_mistake_fields(99999, note="x") is False

    def test_does_not_touch_other_fields(self, db):
        mid = self._make_mistake(db)
        before = db.get_mistake(mid)
        db.update_mistake_fields(mid, note="只改备注")
        after = db.get_mistake(mid)
        assert after.status == before.status
        assert after.crop_x == before.crop_x
        assert after.error_type == before.error_type


# ======================================================================
# update_export_log_path
# ======================================================================

class TestUpdateExportLogPath:
    def test_updates_existing_row(self, db):
        eid = db.create_export_log(
            child_id="K1",
            mistake_ids=[1, 2],
            pdf_path="/tmp/pending.pdf",
        )
        assert db.update_export_log_path(eid, "/tmp/exports/42.pdf") is True
        logs = db.list_export_logs()
        assert logs[0]["pdf_path"] == "/tmp/exports/42.pdf"

    def test_nonexistent_id_returns_false(self, db):
        assert db.update_export_log_path(99999, "/tmp/x.pdf") is False

    def test_preserves_other_columns(self, db):
        eid = db.create_export_log(
            child_id="K1",
            mistake_ids=[7, 8, 9],
            pdf_path="/tmp/pending.pdf",
            subject="数学",
        )
        db.update_export_log_path(eid, "/tmp/final.pdf")
        log = db.list_export_logs()[0]
        assert log["child_id"] == "K1"
        assert log["subject"] == "数学"
        assert log["mistake_ids"] == [7, 8, 9]
