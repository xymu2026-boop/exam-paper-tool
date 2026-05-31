"""Mistake-related API routes (``/api/mistakes/*``).

Mistakes are cropped regions of a processed paper.  The create flow:

    1. Validate the parent paper exists and is fully processed.
    2. Insert a row with NULL image paths to obtain the autoincrement id.
    3. Crop ``processed`` and ``cleaned`` images using Pillow.
    4. Backfill the image paths into the database.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.m2_data_layer import Database

from .. import config
from ..deps import get_db
from ..schemas import (
    ErrorResponse,
    MistakeCreateRequest,
    MistakeCreateResponse,
    MistakeListResponse,
    MistakeUpdateRequest,
    SuccessResponse,
)
from ..utils import crop_and_save, mistake_to_out

router = APIRouter(prefix='/api/mistakes', tags=['mistakes'])


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post(
    '',
    response_model=MistakeCreateResponse,
    responses={
        400: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        500: {'model': ErrorResponse},
    },
)
async def create_mistake(
    payload: MistakeCreateRequest,
    db: Database = Depends(get_db),
) -> MistakeCreateResponse:
    """Crop a region from a processed paper and persist it as a mistake."""

    paper = db.get_paper(payload.paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail='Paper not found')

    if paper.status != 'processed':
        raise HTTPException(
            status_code=400,
            detail=(
                f'Paper status is "{paper.status}"; '
                'must be "processed" before cropping mistakes.'
            ),
        )
    if not paper.processed_path or not paper.cleaned_path:
        raise HTTPException(
            status_code=400,
            detail='Paper has no processed/cleaned images on disk.',
        )

    # 1. Insert preliminary row to claim a mistake_id.
    mistake_id = db.create_mistake(
        paper_id=payload.paper_id,
        child_id=paper.child_id,
        subject=paper.subject,
        crop_x=payload.crop_x,
        crop_y=payload.crop_y,
        crop_width=payload.crop_width,
        crop_height=payload.crop_height,
        note=payload.note,
        error_type=payload.error_type,
    )
    if mistake_id is None:
        raise HTTPException(
            status_code=400,
            detail='Invalid mistake metadata (child_id/subject/error_type).',
        )

    # 2. Crop both source images into data/mistakes/{id}/.
    out_dir = config.MISTAKES_DIR / str(mistake_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    original_dst = out_dir / 'original.jpg'
    clean_dst = out_dir / 'clean.jpg'

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            crop_and_save,
            paper.processed_path,
            str(original_dst),
            payload.crop_x,
            payload.crop_y,
            payload.crop_width,
            payload.crop_height,
        )
        await loop.run_in_executor(
            None,
            crop_and_save,
            paper.cleaned_path,
            str(clean_dst),
            payload.crop_x,
            payload.crop_y,
            payload.crop_width,
            payload.crop_height,
        )
    except ValueError as exc:
        # Crop bounds validation failed — clean up and return 400.
        db.delete_mistake(mistake_id)
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Clean up the DB row so the caller can retry without zombies.
        db.delete_mistake(mistake_id)
        raise HTTPException(
            status_code=500,
            detail=f'Failed to crop mistake images: {exc}',
        ) from exc

    # 3. Backfill image paths.
    db.update_mistake_paths(
        mistake_id,
        mistake_image_path=str(original_dst),
        clean_mistake_image_path=str(clean_dst),
    )

    return MistakeCreateResponse(mistake_id=mistake_id)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get('', response_model=MistakeListResponse)
async def list_mistakes(
    child_id: Optional[str] = None,
    subject: Optional[str] = None,
    status: Optional[str] = None,
    paper_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: Database = Depends(get_db),
) -> MistakeListResponse:
    """Return a filtered, paginated list of mistakes."""

    mistakes = db.list_mistakes(
        child_id=child_id,
        subject=subject,
        status=status,
        paper_id=paper_id,
        limit=limit,
        offset=offset,
    )
    items = [mistake_to_out(m) for m in mistakes]
    total = db.count_mistakes(
        child_id=child_id,
        subject=subject,
        status=status,
        paper_id=paper_id,
    )
    return MistakeListResponse(mistakes=items, total=total)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@router.patch(
    '/{mistake_id}',
    response_model=SuccessResponse,
    responses={404: {'model': ErrorResponse}, 400: {'model': ErrorResponse}},
)
async def update_mistake(
    mistake_id: int,
    payload: MistakeUpdateRequest,
    db: Database = Depends(get_db),
) -> SuccessResponse:
    """Patch the status / note / error_type of an existing mistake."""

    existing = db.get_mistake(mistake_id)
    if existing is None:
        raise HTTPException(status_code=404, detail='Mistake not found')

    if (
        payload.status is None
        and payload.note is None
        and payload.error_type is None
    ):
        raise HTTPException(
            status_code=400,
            detail='At least one of status/note/error_type must be supplied.',
        )

    if payload.status is not None:
        ok = db.update_mistake_status(mistake_id, payload.status)
        if not ok:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid status: {payload.status}',
            )

    if payload.note is not None or payload.error_type is not None:
        ok = db.update_mistake_fields(
            mistake_id,
            note=payload.note,
            error_type=payload.error_type,
        )
        if not ok:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid error_type: {payload.error_type}',
            )

    return SuccessResponse(success=True)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete(
    '/{mistake_id}',
    response_model=SuccessResponse,
    responses={404: {'model': ErrorResponse}},
)
async def delete_mistake(
    mistake_id: int,
    db: Database = Depends(get_db),
) -> SuccessResponse:
    """Remove a mistake record (image files remain on disk for safety)."""

    if db.get_mistake(mistake_id) is None:
        raise HTTPException(status_code=404, detail='Mistake not found')

    ok = db.delete_mistake(mistake_id)
    if not ok:
        raise HTTPException(status_code=500, detail='Failed to delete mistake')
    return SuccessResponse(success=True)


__all__ = ['router']
