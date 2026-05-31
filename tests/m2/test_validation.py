"""Tests for application-layer input validation.

All write operations that accept constrained string values (child_id,
subject, status, error_type, paper_type) must reject illegal inputs at
the Python level — returning ``None`` or ``False`` — before any SQL is
executed.
"""


# ======================================================================
# Paper validation
# ======================================================================

class TestPaperCreateValidation:
    def test_invalid_child_id(self, db):
        assert (
            db.create_paper(
                child_id="K3", subject="数学", original_path="/tmp/a.jpg"
            )
            is None
        )

    def test_invalid_subject(self, db):
        assert (
            db.create_paper(
                child_id="K1", subject="物理", original_path="/tmp/a.jpg"
            )
            is None
        )

    def test_invalid_paper_type(self, db):
        assert (
            db.create_paper(
                child_id="K1",
                subject="数学",
                original_path="/tmp/a.jpg",
                paper_type="期中卷",
            )
            is None
        )

    def test_valid_inputs_succeed(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert pid is not None


class TestPaperUpdateValidation:
    def test_invalid_status(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert pid is not None
        assert (
            db.update_paper_status(pid, "invalid_status") is False
        )

    def test_valid_status_succeeds(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert db.update_paper_status(pid, "processing") is True


class TestPaperListValidation:
    def test_invalid_child_id_filter_ignored(self, db):
        """If a list filter value is invalid, we simply don't filter
        by it — the query succeeds and returns all rows."""
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        db.create_paper(
            child_id="K2", subject="英语", original_path="/tmp/b.jpg"
        )
        # K3 is invalid → filter ignored → both papers returned
        papers = db.list_papers(child_id="K3")
        assert len(papers) == 2

    def test_invalid_subject_filter_ignored(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        papers = db.list_papers(subject="物理")
        assert len(papers) == 1  # all papers returned

    def test_invalid_status_filter_ignored(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        papers = db.list_papers(status="done")
        assert len(papers) == 1


# ======================================================================
# Mistake validation
# ======================================================================

class TestMistakeCreateValidation:
    def test_invalid_child_id(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert pid is not None
        result = db.create_mistake(
            paper_id=pid,
            child_id="K3",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
        assert result is None

    def test_invalid_subject(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert pid is not None
        result = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="物理",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
        assert result is None

    def test_invalid_error_type(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert pid is not None
        result = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
            error_type="笔误",
        )
        assert result is None

    def test_none_error_type_is_valid(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        result = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
            error_type=None,
        )
        assert result is not None


class TestMistakeUpdateValidation:
    def test_invalid_status(self, db):
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
        assert mid is not None
        assert db.update_mistake_status(mid, "unknown") is False

    def test_valid_status_succeeds(self, db):
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
        assert db.update_mistake_status(mid, "practiced") is True


class TestMistakeListValidation:
    def test_invalid_child_id_filter_ignored(self, db):
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
        )
        # K3 invalid → filter ignored → mistake returned
        assert len(db.list_mistakes(child_id="K3")) == 1

    def test_invalid_status_filter_ignored(self, db):
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
        )
        assert len(db.list_mistakes(status="complete")) == 1


# ======================================================================
# Export Log validation
# ======================================================================

class TestExportLogValidation:
    def test_invalid_child_id(self, db):
        assert (
            db.create_export_log(
                child_id="K3", mistake_ids=[1], pdf_path="/tmp/e.pdf"
            )
            is None
        )

    def test_invalid_subject(self, db):
        assert (
            db.create_export_log(
                child_id="K1",
                mistake_ids=[1],
                pdf_path="/tmp/e.pdf",
                subject="物理",
            )
            is None
        )

    def test_none_subject_is_valid(self, db):
        """subject=None means 'all subjects' — must be accepted."""
        eid = db.create_export_log(
            child_id="K1", mistake_ids=[], pdf_path="/tmp/e.pdf", subject=None
        )
        assert eid is not None

    def test_list_invalid_child_id_filter_ignored(self, db):
        db.create_export_log(
            child_id="K1", mistake_ids=[1], pdf_path="/tmp/e.pdf"
        )
        logs = db.list_export_logs(child_id="K3")
        assert len(logs) == 1
