"""M4 internal utilities — shared helpers used by route modules.

These functions are intentionally small and pure so they can be unit-tested
in isolation if needed.  The route modules pull them in to keep handler
bodies focused on orchestration.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from . import config
from .schemas import MistakeOut, PaperOut


def make_filename(ext: str = '.jpg') -> str:
    """Return ``{YYYYMMDD_HHMMSS}_{uuid4_short}{ext}``.

    The 8-char hex suffix keeps collisions astronomically unlikely even
    when multiple uploads share the same wall-clock second.
    """
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    short = uuid.uuid4().hex[:8]
    if not ext.startswith('.'):
        ext = f'.{ext}'
    return f'{ts}_{short}{ext}'


def crop_and_save(
    src_path: str,
    dst_path: str,
    x: int,
    y: int,
    w: int,
    h: int,
    quality: int = 92,
) -> None:
    """Crop a rectangle from ``src_path`` and save the result to ``dst_path``.

    The destination's parent directory is created automatically.  Pillow
    handles JPEG/PNG/HEIC transparently; the output is always JPEG.

    Raises:
        ValueError: If the requested crop rectangle lies (even partially)
            outside the source image bounds, or if ``w``/``h`` are not
            positive.
    """
    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src_path) as img:
        if w <= 0 or h <= 0:
            raise ValueError(
                f'Crop dimensions must be positive (got w={w}, h={h})'
            )
        if (
            x < 0
            or y < 0
            or x + w > img.width
            or y + h > img.height
        ):
            raise ValueError(
                'Crop region exceeds image bounds: '
                f'requested ({x}, {y}, {x + w}, {y + h}), '
                f'image size {img.width}x{img.height}'
            )
        # Convert to RGB before saving as JPEG to avoid mode errors on PNG.
        cropped = img.crop((x, y, x + w, y + h))
        if cropped.mode in ('RGBA', 'P', 'LA'):
            cropped = cropped.convert('RGB')
        cropped.save(dst_path, format='JPEG', quality=quality)


def to_static_url(path: Optional[str]) -> Optional[str]:
    """Map a local filesystem path under ``data/`` to its ``/static/data/...`` URL.

    Returns ``None`` if the input is falsy.  Paths outside ``data/`` are
    returned unchanged because the frontend may already have absolute URLs.
    """
    if not path:
        return None
    p = Path(path)
    # Try to express the path relative to the data root.
    try:
        rel = p.resolve().relative_to(config.DATA_DIR.resolve())
        return f'/static/data/{rel.as_posix()}'
    except (ValueError, OSError):
        # Not under data/, fall back to the raw path.
        # Most call sites store relative paths like "data/originals/..." —
        # strip a leading "data/" if present.
        s = str(path).replace(os.sep, '/')
        if s.startswith('data/'):
            return f'/static/{s}'
        return s


def paper_to_out(paper) -> PaperOut:
    """Serialise a ``Paper`` dataclass to a :class:`PaperOut` Pydantic model."""
    return PaperOut(
        id=paper.id,
        child_id=paper.child_id,
        subject=paper.subject,
        paper_type=paper.paper_type,
        title=paper.title,
        original_path=paper.original_path,
        processed_path=paper.processed_path,
        cleaned_path=paper.cleaned_path,
        upload_time=paper.upload_time,
        status=paper.status,
        quality_score=paper.quality_score,
        error_message=paper.error_message,
        original_url=to_static_url(paper.original_path),
        processed_url=to_static_url(paper.processed_path),
        cleaned_url=to_static_url(paper.cleaned_path),
    )


def mistake_to_out(mistake) -> MistakeOut:
    """Serialise a ``Mistake`` dataclass to a :class:`MistakeOut` Pydantic model."""
    return MistakeOut(
        id=mistake.id,
        paper_id=mistake.paper_id,
        child_id=mistake.child_id,
        subject=mistake.subject,
        crop_x=mistake.crop_x,
        crop_y=mistake.crop_y,
        crop_width=mistake.crop_width,
        crop_height=mistake.crop_height,
        mistake_image_path=mistake.mistake_image_path,
        clean_mistake_image_path=mistake.clean_mistake_image_path,
        note=mistake.note,
        error_type=mistake.error_type,
        status=mistake.status,
        created_at=mistake.created_at,
        reviewed_at=mistake.reviewed_at,
        mistake_image_url=to_static_url(mistake.mistake_image_path),
        clean_mistake_image_url=to_static_url(mistake.clean_mistake_image_path),
    )


__all__ = [
    'make_filename',
    'crop_and_save',
    'to_static_url',
    'paper_to_out',
    'mistake_to_out',
]
