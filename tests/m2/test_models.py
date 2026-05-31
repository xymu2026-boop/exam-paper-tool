"""Tests for the dataclass models (Paper, Mistake, ExportLog).

Verifies that instances can be constructed with the expected field names,
types, and default behaviours.
"""

from src.m2_data_layer import Paper, Mistake, ExportLog


class TestPaperDataclass:
    """Paper construction and field access."""

    def test_minimal_construction(self):
        p = Paper(
            id=1,
            child_id="K1",
            subject="数学",
            paper_type="其他",
            title=None,
            original_path="/tmp/test.jpg",
            processed_path=None,
            cleaned_path=None,
            upload_time="2026-05-31 12:00:00",
            status="pending",
            quality_score=None,
            error_message=None,
        )
        assert p.id == 1
        assert p.child_id == "K1"
        assert p.title is None
        assert p.original_path == "/tmp/test.jpg"

    def test_full_construction(self):
        p = Paper(
            id=42,
            child_id="K2",
            subject="英语",
            paper_type="考试卷",
            title="期中测试",
            original_path="/tmp/original.jpg",
            processed_path="/tmp/processed.jpg",
            cleaned_path="/tmp/cleaned.jpg",
            upload_time="2026-05-31 14:30:00",
            status="processed",
            quality_score=0.87,
            error_message=None,
        )
        assert p.id == 42
        assert p.quality_score == 0.87
        assert p.processed_path == "/tmp/processed.jpg"
        assert p.status == "processed"

    def test_optional_fields_default_to_none(self):
        p = Paper(
            id=1,
            child_id="K1",
            subject="数学",
            paper_type="其他",
            title=None,
            original_path="/tmp/test.jpg",
            processed_path=None,
            cleaned_path=None,
            upload_time="2026-05-31 12:00:00",
            status="pending",
            quality_score=None,
            error_message=None,
        )
        assert p.processed_path is None
        assert p.cleaned_path is None
        assert p.quality_score is None
        assert p.error_message is None
        assert p.title is None


class TestMistakeDataclass:
    """Mistake construction and field access."""

    def test_minimal_construction(self):
        m = Mistake(
            id=1,
            paper_id=2,
            child_id="K1",
            subject="数学",
            crop_x=10,
            crop_y=20,
            crop_width=100,
            crop_height=200,
            mistake_image_path=None,
            clean_mistake_image_path=None,
            note=None,
            error_type=None,
            status="new",
            created_at="2026-05-31 12:00:00",
            reviewed_at=None,
        )
        assert m.id == 1
        assert m.paper_id == 2
        assert m.crop_x == 10
        assert m.crop_height == 200
        assert m.error_type is None
        assert m.status == "new"

    def test_full_construction(self):
        m = Mistake(
            id=5,
            paper_id=1,
            child_id="K2",
            subject="英语",
            crop_x=0,
            crop_y=0,
            crop_width=300,
            crop_height=400,
            mistake_image_path="/tmp/mistake.jpg",
            clean_mistake_image_path="/tmp/mistake_clean.jpg",
            note="第三人称单数",
            error_type="粗心",
            status="printed",
            created_at="2026-05-31 10:00:00",
            reviewed_at="2026-05-31 15:00:00",
        )
        assert m.note == "第三人称单数"
        assert m.error_type == "粗心"
        assert m.mistake_image_path == "/tmp/mistake.jpg"
        assert m.reviewed_at == "2026-05-31 15:00:00"


class TestExportLogDataclass:
    """ExportLog construction and field access."""

    def test_minimal_construction(self):
        e = ExportLog(
            id=1,
            child_id="K1",
            subject=None,
            mistake_ids=[1, 2, 3],
            pdf_path="/tmp/export.pdf",
            created_at="2026-05-31 12:00:00",
        )
        assert e.id == 1
        assert e.mistake_ids == [1, 2, 3]
        assert e.subject is None

    def test_empty_mistake_ids(self):
        e = ExportLog(
            id=2,
            child_id="K2",
            subject="数学",
            mistake_ids=[],
            pdf_path="/tmp/empty.pdf",
            created_at="2026-05-31 13:00:00",
        )
        assert e.mistake_ids == []
        assert e.subject == "数学"
