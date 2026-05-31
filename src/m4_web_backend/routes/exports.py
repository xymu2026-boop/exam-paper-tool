"""Export-related API routes (``/api/export/*``).

The PDF export flow:

    1. Validate every requested mistake exists and belongs to ``child_id``.
    2. Reserve an ``export_id`` in the database with the precomputed PDF path.
    3. Call M5 in a worker thread (CPU + I/O bound).
    4. Return the resulting public URL.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from src.m2_data_layer import Database
from src.m5_pdf_export import ExportConfig, export_pdf as m5_export_pdf

from .. import config
from ..deps import get_db
from ..schemas import (
    ErrorResponse,
    ExportHistoryItem,
    ExportHistoryResponse,
    ExportPdfRequest,
    ExportPdfResponse,
)
from ..utils import to_static_url

router = APIRouter(prefix='/api/export', tags=['export'])


# ---------------------------------------------------------------------------
# Export PDF
# ---------------------------------------------------------------------------

@router.post(
    '/pdf',
    response_model=ExportPdfResponse,
    responses={
        400: {'model': ErrorResponse},
        404: {'model': ErrorResponse},
        500: {'model': ErrorResponse},
    },
)
async def export_pdf_route(
    payload: ExportPdfRequest,
    db: Database = Depends(get_db),
) -> ExportPdfResponse:
    """Render the selected mistakes into a single PDF and log the action."""

    if not payload.mistake_ids:
        raise HTTPException(status_code=400, detail='mistake_ids is empty')

    image_paths: list[str] = []
    subjects: set[str] = set()

    for mid in payload.mistake_ids:
        mistake = db.get_mistake(mid)
        if mistake is None:
            raise HTTPException(
                status_code=404,
                detail=f'Mistake {mid} not found',
            )
        if mistake.child_id != payload.child_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f'Mistake {mid} belongs to child_id={mistake.child_id}, '
                    f'expected {payload.child_id}'
                ),
            )
        # Prefer the "clean" (erased) version for printing so the child
        # is not biased by previous answers.  Fall back to the originally
        # cropped image if the clean version is missing.
        path = mistake.clean_mistake_image_path or mistake.mistake_image_path
        if not path:
            raise HTTPException(
                status_code=500,
                detail=f'Mistake {mid} has no cropped image on disk.',
            )
        image_paths.append(path)
        subjects.add(mistake.subject)

    # Pick a representative subject for the export log (None if multi-subject).
    subject_for_log: Optional[str] = (
        next(iter(subjects)) if len(subjects) == 1 else None
    )

    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Reserve the export_id first so we can deterministically compute the
    # PDF path before invoking M5.
    # The pdf_path stored in the DB is the relative-to-cwd path; the URL
    # returned to the client is the matching ``/static/data/...`` URL.
    placeholder_pdf_path = str(config.EXPORTS_DIR / 'pending.pdf')
    export_id = db.create_export_log(
        child_id=payload.child_id,
        mistake_ids=payload.mistake_ids,
        pdf_path=placeholder_pdf_path,
        subject=subject_for_log,
    )
    if export_id is None:
        raise HTTPException(
            status_code=400,
            detail='Invalid export metadata (child_id/subject).',
        )

    pdf_path = config.EXPORTS_DIR / f'{export_id}.pdf'

    # Update the log with the real path now that we know export_id.
    # (Direct SQL — narrow scope, single column update.)
    with db._lock:  # noqa: SLF001 — narrow internal access
        db.conn.execute(
            'UPDATE export_log SET pdf_path = ? WHERE id = ?',
            (str(pdf_path), export_id),
        )

    cfg = ExportConfig(layout=payload.layout, title=payload.title or '')

    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(
        None,
        m5_export_pdf,
        image_paths,
        str(pdf_path),
        cfg,
    )

    if not ok:
        raise HTTPException(
            status_code=500,
            detail='PDF generation failed',
        )

    pdf_url = to_static_url(str(pdf_path)) or f'/static/data/exports/{export_id}.pdf'
    return ExportPdfResponse(
        pdf_url=pdf_url,
        export_id=export_id,
        title=payload.title,
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.get('/history', response_model=ExportHistoryResponse)
async def export_history(
    child_id: Optional[str] = None,
    limit: int = 20,
    db: Database = Depends(get_db),
) -> ExportHistoryResponse:
    """Return recent export log entries with browser-friendly PDF URLs."""

    rows = db.list_export_logs(child_id=child_id, limit=limit)
    items: list[ExportHistoryItem] = []
    for row in rows:
        items.append(
            ExportHistoryItem(
                id=row['id'],
                child_id=row['child_id'],
                subject=row.get('subject'),
                mistake_ids=row.get('mistake_ids') or [],
                pdf_path=row['pdf_path'],
                created_at=row['created_at'],
                pdf_url=to_static_url(row['pdf_path']),
            )
        )
    return ExportHistoryResponse(exports=items)


__all__ = ['router']
