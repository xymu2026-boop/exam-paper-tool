"""M2 Data Layer — dataclass models for Paper, Mistake, and ExportLog.

All field names and types match INTERFACE-CONTRACT.md Section 4.2 exactly.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Paper:
    """A scanned exam paper uploaded by the user.

    Maps to the ``paper`` table.  Every field corresponds one-to-one
    with a SQLite column — see contract Section 3.1 for the DDL.
    """

    id: int
    child_id: str
    subject: str
    paper_type: str
    title: Optional[str]
    original_path: str
    processed_path: Optional[str]
    cleaned_path: Optional[str]
    upload_time: str
    status: str
    quality_score: Optional[float]
    error_message: Optional[str]


@dataclass
class Mistake:
    """A cropped mistake region extracted from a paper.

    Maps to the ``mistake`` table.  The ``crop_*`` fields record the
    bounding-box in the original (or processed) image pixel coordinates.
    """

    id: int
    paper_id: int
    child_id: str
    subject: str
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    mistake_image_path: Optional[str]
    clean_mistake_image_path: Optional[str]
    note: Optional[str]
    error_type: Optional[str]
    status: str
    created_at: str
    reviewed_at: Optional[str]


@dataclass
class ExportLog:
    """A record of a PDF export operation.

    Maps to the ``export_log`` table.  The ``mistake_ids`` field is
    stored as JSON text in the database but materialised as ``list[int]``
    in Python.
    """

    id: int
    child_id: str
    subject: Optional[str]
    mistake_ids: list[int]
    pdf_path: str
    created_at: str
