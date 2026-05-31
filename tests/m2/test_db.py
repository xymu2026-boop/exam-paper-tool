"""Comprehensive CRUD tests for the Database class.

Every method in the ``Database`` public API is exercised with valid
inputs to verify correct behaviour.
"""

from src.m2_data_layer import Database, Paper, Mistake


# ======================================================================
# Paper CRUD
# ======================================================================

class TestPaperCreate:
    def test_create_returns_positive_int(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert pid is not None
        assert isinstance(pid, int)
        assert pid > 0

    def test_create_with_all_optional_fields(self, db):
        pid = db.create_paper(
            child_id="K2",
            subject="英语",
            original_path="/tmp/b.jpg",
            paper_type="考试卷",
            title="月考卷",
        )
        assert pid is not None
        assert isinstance(pid, int)

    def test_create_increments_id(self, db):
        pid1 = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/1.jpg"
        )
        pid2 = db.create_paper(
            child_id="K2", subject="语文", original_path="/tmp/2.jpg"
        )
        assert pid2 > pid1

    def test_create_default_paper_type(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        paper = db.get_paper(pid)
        assert paper.paper_type == "其他"

    def test_create_default_status(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        paper = db.get_paper(pid)
        assert paper.status == "pending"

    def test_create_upload_time_is_set(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        paper = db.get_paper(pid)
        assert paper.upload_time is not None
        assert len(paper.upload_time) > 0


class TestPaperGet:
    def test_get_returns_correct_fields(self, db):
        pid = db.create_paper(
            child_id="K1",
            subject="数学",
            original_path="/tmp/test.jpg",
        )
        paper = db.get_paper(pid)
        assert isinstance(paper, Paper)
        assert paper.id == pid
        assert paper.child_id == "K1"
        assert paper.subject == "数学"
        assert paper.original_path == "/tmp/test.jpg"

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_paper(99999) is None


class TestPaperUpdate:
    def test_update_status_only(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert db.update_paper_status(pid, "processing") is True
        assert db.get_paper(pid).status == "processing"

    def test_update_all_fields(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert db.update_paper_status(
            pid,
            "processed",
            processed_path="/tmp/p.jpg",
            cleaned_path="/tmp/c.jpg",
            quality_score=0.92,
            error_message=None,
        ) is True
        paper = db.get_paper(pid)
        assert paper.status == "processed"
        assert paper.processed_path == "/tmp/p.jpg"
        assert paper.cleaned_path == "/tmp/c.jpg"
        assert paper.quality_score == 0.92

    def test_update_failed_with_error(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        assert db.update_paper_status(
            pid, "failed", error_message="内存不足"
        ) is True
        paper = db.get_paper(pid)
        assert paper.status == "failed"
        assert paper.error_message == "内存不足"

    def test_update_nonexistent_returns_false(self, db):
        assert (
            db.update_paper_status(99999, "processing") is False
        )


class TestPaperList:
    def test_list_all(self, db):
        for i in range(5):
            db.create_paper(
                child_id="K1", subject="数学", original_path=f"/tmp/{i}.jpg"
            )
        papers = db.list_papers()
        assert len(papers) == 5

    def test_list_filter_by_child(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/1.jpg"
        )
        db.create_paper(
            child_id="K2", subject="英语", original_path="/tmp/2.jpg"
        )
        papers = db.list_papers(child_id="K1")
        assert len(papers) == 1
        assert papers[0].child_id == "K1"

    def test_list_filter_multi(self, db):
        db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/1.jpg"
        )
        db.create_paper(
            child_id="K1", subject="语文", original_path="/tmp/2.jpg"
        )
        db.create_paper(
            child_id="K2", subject="数学", original_path="/tmp/3.jpg"
        )
        papers = db.list_papers(child_id="K1", subject="数学")
        assert len(papers) == 1

    def test_list_pagination(self, db):
        for i in range(10):
            db.create_paper(
                child_id="K1",
                subject="数学",
                original_path=f"/tmp/{i}.jpg",
            )
        page1 = db.list_papers(limit=3, offset=0)
        assert len(page1) == 3
        page2 = db.list_papers(limit=3, offset=3)
        assert len(page2) == 3
        # ensure distinct sets
        assert {p.id for p in page1} != {p.id for p in page2}

    def test_list_order_desc(self, db):
        pid1 = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/1.jpg"
        )
        pid2 = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/2.jpg"
        )
        papers = db.list_papers()
        # most recent first
        assert papers[0].id == pid2
        assert papers[1].id == pid1


# ======================================================================
# Mistake CRUD
# ======================================================================

class TestMistakeCreate:
    def test_create_returns_positive_int(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        mid = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=100,
            crop_height=200,
        )
        assert mid is not None
        assert isinstance(mid, int)
        assert mid > 0

    def test_create_with_all_fields(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        mid = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=10,
            crop_y=20,
            crop_width=300,
            crop_height=400,
            mistake_image_path="/tmp/m.jpg",
            clean_mistake_image_path="/tmp/mc.jpg",
            note="进位错",
            error_type="粗心",
        )
        assert mid is not None

    def test_create_default_status(self, db):
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
        mistake = db.get_mistake(mid)
        assert mistake.status == "new"


class TestMistakeGet:
    def test_get_returns_correct_fields(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        mid = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=5,
            crop_y=15,
            crop_width=200,
            crop_height=300,
            note="test",
        )
        m = db.get_mistake(mid)
        assert isinstance(m, Mistake)
        assert m.id == mid
        assert m.paper_id == pid
        assert m.crop_x == 5
        assert m.crop_width == 200
        assert m.note == "test"

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_mistake(99999) is None


class TestMistakeUpdate:
    def test_update_status(self, db):
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
        assert db.update_mistake_status(mid, "printed") is True
        assert db.get_mistake(mid).status == "printed"

    def test_update_status_nonexistent(self, db):
        assert db.update_mistake_status(99999, "printed") is False

    def test_update_paths_mistake_image(self, db):
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
        assert (
            db.update_mistake_paths(mid, mistake_image_path="/tmp/m.jpg")
            is True
        )
        m = db.get_mistake(mid)
        assert m.mistake_image_path == "/tmp/m.jpg"
        assert m.clean_mistake_image_path is None

    def test_update_paths_clean_image(self, db):
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
        assert (
            db.update_mistake_paths(
                mid, clean_mistake_image_path="/tmp/mc.jpg"
            )
            is True
        )
        m = db.get_mistake(mid)
        assert m.clean_mistake_image_path == "/tmp/mc.jpg"

    def test_update_paths_both(self, db):
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
        assert db.update_mistake_paths(
            mid,
            mistake_image_path="/tmp/m.jpg",
            clean_mistake_image_path="/tmp/mc.jpg",
        ) is True
        m = db.get_mistake(mid)
        assert m.mistake_image_path == "/tmp/m.jpg"
        assert m.clean_mistake_image_path == "/tmp/mc.jpg"

    def test_update_paths_both_none(self, db):
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
        assert db.update_mistake_paths(mid) is False

    def test_update_paths_nonexistent(self, db):
        assert (
            db.update_mistake_paths(99999, mistake_image_path="/tmp/m.jpg")
            is False
        )


class TestMistakeList:
    def test_list_all(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        for _ in range(4):
            db.create_mistake(
                paper_id=pid,
                child_id="K1",
                subject="数学",
                crop_x=0,
                crop_y=0,
                crop_width=10,
                crop_height=10,
            )
        assert len(db.list_mistakes()) == 4

    def test_list_filter_by_child(self, db):
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
        db.create_mistake(
            paper_id=pid,
            child_id="K2",
            subject="英语",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
        assert len(db.list_mistakes(child_id="K1")) == 1

    def test_list_filter_by_paper_id(self, db):
        pid1 = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/1.jpg"
        )
        pid2 = db.create_paper(
            child_id="K2", subject="英语", original_path="/tmp/2.jpg"
        )
        db.create_mistake(
            paper_id=pid1,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
        db.create_mistake(
            paper_id=pid2,
            child_id="K2",
            subject="英语",
            crop_x=0,
            crop_y=0,
            crop_width=20,
            crop_height=20,
        )
        assert len(db.list_mistakes(paper_id=pid1)) == 1

    def test_list_filter_multi(self, db):
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
        result = db.list_mistakes(child_id="K1", subject="数学")
        assert len(result) == 2

    def test_list_pagination(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        for i in range(10):
            db.create_mistake(
                paper_id=pid,
                child_id="K1",
                subject="数学",
                crop_x=i,
                crop_y=0,
                crop_width=10,
                crop_height=10,
            )
        page1 = db.list_mistakes(limit=3, offset=0)
        assert len(page1) == 3
        page2 = db.list_mistakes(limit=3, offset=3)
        assert len(page2) == 3


class TestMistakeDelete:
    def test_delete_existing(self, db):
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
        assert db.delete_mistake(mid) is True
        assert db.get_mistake(mid) is None

    def test_delete_nonexistent(self, db):
        assert db.delete_mistake(99999) is False

    def test_delete_reduces_list(self, db):
        pid = db.create_paper(
            child_id="K1", subject="数学", original_path="/tmp/a.jpg"
        )
        m1 = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=10,
            crop_height=10,
        )
        m2 = db.create_mistake(
            paper_id=pid,
            child_id="K1",
            subject="数学",
            crop_x=0,
            crop_y=0,
            crop_width=20,
            crop_height=20,
        )
        assert len(db.list_mistakes()) == 2
        db.delete_mistake(m1)
        assert len(db.list_mistakes()) == 1
        assert db.list_mistakes()[0].id == m2

    def test_double_delete(self, db):
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
        assert db.delete_mistake(mid) is True
        assert db.delete_mistake(mid) is False


# ======================================================================
# Export Log CRUD
# ======================================================================

class TestExportLogCreate:
    def test_create_returns_positive_int(self, db):
        eid = db.create_export_log(
            child_id="K1", mistake_ids=[1, 2], pdf_path="/tmp/e.pdf"
        )
        assert eid is not None
        assert isinstance(eid, int)
        assert eid > 0

    def test_create_with_subject(self, db):
        eid = db.create_export_log(
            child_id="K1",
            mistake_ids=[1],
            pdf_path="/tmp/e.pdf",
            subject="数学",
        )
        assert eid is not None

    def test_create_empty_ids(self, db):
        eid = db.create_export_log(
            child_id="K1", mistake_ids=[], pdf_path="/tmp/e.pdf"
        )
        assert eid is not None


class TestExportLogList:
    def test_list_all(self, db):
        db.create_export_log(
            child_id="K1", mistake_ids=[1], pdf_path="/tmp/a.pdf"
        )
        db.create_export_log(
            child_id="K2", mistake_ids=[2], pdf_path="/tmp/b.pdf"
        )
        logs = db.list_export_logs()
        assert len(logs) == 2

    def test_list_filter_by_child(self, db):
        db.create_export_log(
            child_id="K1", mistake_ids=[1], pdf_path="/tmp/a.pdf"
        )
        db.create_export_log(
            child_id="K2", mistake_ids=[2], pdf_path="/tmp/b.pdf"
        )
        logs = db.list_export_logs(child_id="K1")
        assert len(logs) == 1
        assert logs[0]["child_id"] == "K1"

    def test_list_returns_dicts_with_all_keys(self, db):
        eid = db.create_export_log(
            child_id="K1",
            mistake_ids=[1, 3],
            pdf_path="/tmp/test.pdf",
            subject="数学",
        )
        logs = db.list_export_logs()
        assert len(logs) == 1
        log = logs[0]
        assert log["id"] == eid
        assert log["child_id"] == "K1"
        assert log["subject"] == "数学"
        assert log["pdf_path"] == "/tmp/test.pdf"
        assert "created_at" in log

    def test_list_limit(self, db):
        for i in range(5):
            db.create_export_log(
                child_id="K1",
                mistake_ids=[i],
                pdf_path=f"/tmp/{i}.pdf",
            )
        logs = db.list_export_logs(limit=2)
        assert len(logs) == 2

    def test_list_ordered_desc(self, db):
        eid1 = db.create_export_log(
            child_id="K1", mistake_ids=[1], pdf_path="/tmp/a.pdf"
        )
        eid2 = db.create_export_log(
            child_id="K1", mistake_ids=[2], pdf_path="/tmp/b.pdf"
        )
        logs = db.list_export_logs()
        assert logs[0]["id"] == eid2
        assert logs[1]["id"] == eid1
