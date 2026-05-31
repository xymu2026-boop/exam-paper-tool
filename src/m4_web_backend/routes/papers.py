"""Paper-related API routes (``/api/papers/*``).

The routes here orchestrate M1 (image processing) and M2 (data layer).
No SQL, no business algorithms — only file I/O, validation and delegation.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.m1_image_engine import process_paper as m1_process_paper
from src.m2_data_layer import Database

from .. import config
from ..deps import get_db
from ..schemas import (
    ErrorResponse,
    PaperListResponse,
    PaperOut,
    ProcessResponse,
    UploadResponse,
)
from ..utils import make_filename, paper_to_out

router = APIRouter(prefix='/api/papers', tags=['papers'])

# Chunk size used when streaming the upload from the multipart parser to disk.
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post(
    '/upload',
    response_model=UploadResponse,
    responses={400: {'model': ErrorResponse}, 500: {'model': ErrorResponse}},
)
async def upload_paper(
    file: UploadFile = File(...),
    child_id: str = Form(...),
    subject: str = Form(...),
    paper_type: str = Form('其他'),
    title: Optional[str] = Form(None),
    db: Database = Depends(get_db),
) -> UploadResponse:
    """Receive an exam paper image and register it with status ``pending``."""

    # --- Validate filename extension ---------------------------------------
    filename = file.filename or ''
    ext = Path(filename).suffix.lower()
    if ext not in config.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f'Unsupported file type: {ext or "(none)"}',
        )

    # --- Build destination path (filename normalised to .jpg) -------------
    target_dir = config.ORIGINALS_DIR / child_id / subject
    target_dir.mkdir(parents=True, exist_ok=True)
    # Store HEIC/PNG with their native extension for fidelity; M1 reads them.
    save_ext = ext if ext in {'.heic', '.png'} else '.jpg'
    dest_path = target_dir / make_filename(save_ext)

    # --- Stream upload to disk, enforcing the size cap --------------------
    total_size = 0
    try:
        with open(dest_path, 'wb') as out:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > config.MAX_UPLOAD_SIZE:
                    out.close()
                    try:
                        dest_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f'File too large (max '
                            f'{config.MAX_UPLOAD_SIZE // (1024 * 1024)}MB)'
                        ),
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f'Failed to save uploaded file: {exc}',
        ) from exc

    if total_size == 0:
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(status_code=400, detail='Empty file')

    # --- Insert DB row ----------------------------------------------------
    paper_id = db.create_paper(
        child_id=child_id,
        subject=subject,
        original_path=str(dest_path),
        paper_type=paper_type,
        title=title,
    )
    if paper_id is None:
        # Roll back the file we just wrote so the upload is atomic.
        try:
            dest_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise HTTPException(
            status_code=400,
            detail=(
                'Invalid metadata: child_id/subject/paper_type out of range'
            ),
        )

    return UploadResponse(paper_id=paper_id, status='pending')


# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------

@router.post(
    '/{paper_id}/process',
    response_model=ProcessResponse,
    responses={404: {'model': ErrorResponse}, 500: {'model': ErrorResponse}},
)
async def process_paper_route(
    paper_id: int,
    db: Database = Depends(get_db),
) -> ProcessResponse:
    """Run the M1 pipeline on a previously uploaded paper."""

    paper = db.get_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail='Paper not found')

    # Mark processing so concurrent triggers are visible.
    db.update_paper_status(paper_id, 'processing')

    output_dir = config.PROCESSED_DIR / str(paper_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    # M1 is CPU-bound; run it in a worker thread.
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        m1_process_paper,
        paper.original_path,
        str(output_dir),
    )

    if result.success:
        db.update_paper_status(
            paper_id,
            status='processed',
            processed_path=result.processed_path,
            cleaned_path=result.cleaned_path,
            quality_score=result.quality_score,
        )
        return ProcessResponse(
            status='processed',
            quality_score=result.quality_score,
            warnings=list(result.warnings or []),
        )

    db.update_paper_status(
        paper_id,
        status='failed',
        error_message=result.error,
    )
    # Return the failure body with HTTP 500 so clients can branch on status.
    raise HTTPException(
        status_code=500,
        detail=result.error or 'Image processing failed',
    )


# ---------------------------------------------------------------------------
# List + detail
# ---------------------------------------------------------------------------

@router.get('', response_model=PaperListResponse)
async def list_papers(
    child_id: Optional[str] = None,
    subject: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Database = Depends(get_db),
) -> PaperListResponse:
    """Return a filtered, paginated list of papers."""

    papers = db.list_papers(
        child_id=child_id,
        subject=subject,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [paper_to_out(p) for p in papers]
    total = db.count_papers(
        child_id=child_id,
        subject=subject,
        status=status,
    )
    return PaperListResponse(papers=items, total=total)


@router.get(
    '/{paper_id}',
    response_model=PaperOut,
    responses={404: {'model': ErrorResponse}},
)
async def get_paper(
    paper_id: int,
    db: Database = Depends(get_db),
) -> PaperOut:
    """Return a single paper with browser-friendly image URLs."""

    paper = db.get_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail='Paper not found')
    return paper_to_out(paper)


__all__ = ['router']
