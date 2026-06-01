"""Debug route: single-call upload + process with full file metadata."""

from __future__ import annotations

import asyncio
import uuid
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from .. import config
from ..deps import get_db

router = APIRouter(prefix="/api/debug", tags=["debug"])
DEBUG_DIR = config.DATA_DIR / "debug"


def _file_info(path: str | None):
    if path is None or not Path(path).exists():
        return None
    p = Path(path)
    size = p.stat().st_size
    try:
        img = Image.open(p)
        w, h = img.size
    except Exception:
        w, h = 0, 0
    return {"file": p.name, "size_bytes": size, "size_kb": round(size / 1024, 1), "width": w, "height": h}


def _public_url(path: str | None):
    if path is None:
        return None
    p = Path(path).resolve()
    data_root = config.DATA_DIR.resolve()
    try:
        rel = p.relative_to(data_root)
    except ValueError:
        return None
    return f"/static/data/{rel.as_posix()}"


@router.post("/process")
async def debug_process(file: UploadFile = File(...)):
    ext = Path(file.filename or "upload.jpg").suffix.lower()
    if ext not in (config.ALLOWED_EXTENSIONS | {'.heic', '.HEIC'}):
        return JSONResponse({"error": f"不支持的文件类型: {ext}"}, status_code=400)

    contents = await file.read()
    if len(contents) == 0:
        return JSONResponse({"error": "上传的文件为空 (0 bytes)"}, status_code=400)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6]
    session_id = f"{ts}_{uid}"
    out_dir = DEBUG_DIR / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = out_dir / f"upload{ext}"
    tmp_path.write_bytes(contents)

    db = get_db()
    paper_id = db.create_paper(child_id="K1", subject="其他", original_path=str(tmp_path), title=f"Debug {session_id}")
    db.update_paper_status(paper_id, "processing")

    loop = asyncio.get_event_loop()
    errors: list[str] = []

    try:
        from src.m1_image_engine.engine import process_paper
        result = await loop.run_in_executor(None, process_paper, str(tmp_path), str(out_dir))
    except Exception as e:
        db.update_paper_status(paper_id, "failed", error_message=str(e))
        return JSONResponse({"error": f"处理异常: {e}", "session_id": session_id}, status_code=500)

    if not result.success:
        db.update_paper_status(paper_id, "failed", error_message=result.error or "unknown")
        return JSONResponse({
            "error": result.error or "处理失败",
            "session_id": session_id,
            "warnings": result.warnings,
        }, status_code=500)

    db.update_paper_status(paper_id, "processed",
                           processed_path=str(result.processed_path),
                           cleaned_path=str(result.cleaned_path),
                           quality_score=result.quality_score)

    stage_keys = [
        ("original", result.original_path),
        ("processed", result.processed_path),
        ("red_mask", result.red_mask_path),
        ("handwriting_mask", result.hw_mask_path),
        ("combined_mask", result.combined_mask_path),
        ("cleaned", result.cleaned_path),
    ]

    stages = {}
    for key, fpath in stage_keys:
        info = _file_info(fpath)
        url = _public_url(fpath)
        if url is None and fpath is not None:
            errors.append(f"path_resolution_failed: {key} at {fpath}")
        if info is None and fpath is not None:
            errors.append(f"file_missing: {key} expected at {fpath}")
        stages[key] = {
            "url": url,
            "file": info["file"] if info else None,
            "size_kb": info["size_kb"] if info else None,
            "width": info["width"] if info else None,
            "height": info["height"] if info else None,
        }

    response = {
        "session_id": session_id,
        "quality_score": round(result.quality_score, 2),
        "warnings": result.warnings,
        "errors": errors,
        "stages": stages,
    }
    return response


@router.post("/cleanup")
async def debug_cleanup():
    try:
        shutil.rmtree(DEBUG_DIR, ignore_errors=True)
        return {"status": "cleaned"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
