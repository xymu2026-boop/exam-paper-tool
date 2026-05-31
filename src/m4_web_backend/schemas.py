"""Pydantic request/response schemas for M4.

These models drive both runtime validation and the Swagger UI rendered at
``/docs``.  Field names match :mod:`src.m2_data_layer.models` so that
serialisation from dataclasses is a straight ``vars(...)`` call.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

# --- Enumerated value sets (single source of truth) ----------------------
ALLOWED_ERROR_TYPES: frozenset[str] = frozenset(
    {'粗心', '概念不清', '计算错误', '不会做', '其他'}
)
ALLOWED_LAYOUTS: frozenset[str] = frozenset(
    {'one_per_page', 'two_per_page', 'compact'}
)
ALLOWED_MISTAKE_STATUSES: frozenset[str] = frozenset(
    {'new', 'printed', 'practiced', 'passed', 'retry'}
)


# --- Generic envelopes ----------------------------------------------------

class ErrorResponse(BaseModel):
    """Uniform error body returned with non-2xx responses."""

    error: str


class SuccessResponse(BaseModel):
    """Uniform success envelope for mutating endpoints with no payload."""

    success: bool = True


# --- Paper schemas --------------------------------------------------------

class UploadResponse(BaseModel):
    paper_id: int
    status: str = 'pending'


class ProcessResponse(BaseModel):
    status: str
    quality_score: Optional[float] = None
    warnings: List[str] = []
    error: Optional[str] = None


class PaperOut(BaseModel):
    """Flattened view of a ``Paper`` enriched with browser-friendly URLs."""

    id: int
    child_id: str
    subject: str
    paper_type: str
    title: Optional[str] = None
    original_path: str
    processed_path: Optional[str] = None
    cleaned_path: Optional[str] = None
    upload_time: str
    status: str
    quality_score: Optional[float] = None
    error_message: Optional[str] = None
    original_url: Optional[str] = None
    processed_url: Optional[str] = None
    cleaned_url: Optional[str] = None


class PaperListResponse(BaseModel):
    papers: List[PaperOut]
    total: int


# --- Mistake schemas ------------------------------------------------------

class MistakeCreateRequest(BaseModel):
    paper_id: int
    crop_x: int = Field(..., ge=0)
    crop_y: int = Field(..., ge=0)
    crop_width: int = Field(..., gt=0)
    crop_height: int = Field(..., gt=0)
    note: Optional[str] = None
    error_type: Optional[str] = None

    @field_validator('error_type')
    @classmethod
    def _check_error_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_ERROR_TYPES:
            raise ValueError(
                f'error_type must be one of {sorted(ALLOWED_ERROR_TYPES)}'
            )
        return v


class MistakeCreateResponse(BaseModel):
    mistake_id: int


class MistakeOut(BaseModel):
    id: int
    paper_id: int
    child_id: str
    subject: str
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    mistake_image_path: Optional[str] = None
    clean_mistake_image_path: Optional[str] = None
    note: Optional[str] = None
    error_type: Optional[str] = None
    status: str
    created_at: str
    reviewed_at: Optional[str] = None
    mistake_image_url: Optional[str] = None
    clean_mistake_image_url: Optional[str] = None


class MistakeListResponse(BaseModel):
    mistakes: List[MistakeOut]
    total: int


class MistakeUpdateRequest(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None
    error_type: Optional[str] = None

    @field_validator('status')
    @classmethod
    def _check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_MISTAKE_STATUSES:
            raise ValueError(
                f'status must be one of {sorted(ALLOWED_MISTAKE_STATUSES)}'
            )
        return v

    @field_validator('error_type')
    @classmethod
    def _check_error_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_ERROR_TYPES:
            raise ValueError(
                f'error_type must be one of {sorted(ALLOWED_ERROR_TYPES)}'
            )
        return v


# --- Export schemas -------------------------------------------------------

class ExportPdfRequest(BaseModel):
    child_id: str
    mistake_ids: List[int] = Field(..., min_length=1)
    layout: str = 'one_per_page'
    title: Optional[str] = None

    @field_validator('layout')
    @classmethod
    def _check_layout(cls, v: str) -> str:
        if v not in ALLOWED_LAYOUTS:
            raise ValueError(
                f'layout must be one of {sorted(ALLOWED_LAYOUTS)}'
            )
        return v


class ExportPdfResponse(BaseModel):
    pdf_url: str
    export_id: int
    title: Optional[str] = None


class ExportHistoryItem(BaseModel):
    id: int
    child_id: str
    subject: Optional[str] = None
    mistake_ids: List[int] = []
    pdf_path: str
    created_at: str
    pdf_url: Optional[str] = None


class ExportHistoryResponse(BaseModel):
    exports: List[ExportHistoryItem]


__all__ = [
    'ALLOWED_ERROR_TYPES',
    'ALLOWED_LAYOUTS',
    'ALLOWED_MISTAKE_STATUSES',
    'ErrorResponse',
    'SuccessResponse',
    'UploadResponse',
    'ProcessResponse',
    'PaperOut',
    'PaperListResponse',
    'MistakeCreateRequest',
    'MistakeCreateResponse',
    'MistakeOut',
    'MistakeListResponse',
    'MistakeUpdateRequest',
    'ExportPdfRequest',
    'ExportPdfResponse',
    'ExportHistoryItem',
    'ExportHistoryResponse',
]
