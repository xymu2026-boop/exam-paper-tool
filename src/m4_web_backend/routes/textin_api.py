"""TextIn Web API — upload + process + results serving."""

from __future__ import annotations

import uuid, asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

from .. import config

router = APIRouter(prefix="/api/textin", tags=["textin"])
WEB_JOBS_DIR = config.DATA_DIR / "api_eval" / "textin" / "web_jobs"


@router.post("/process")
async def textin_process(file: UploadFile = File(...), mode: str = Form("all")):
    ext = Path(file.filename or "upload.jpg").suffix.lower()
    if ext not in (config.ALLOWED_EXTENSIONS | {'.webp', '.WEBP', '.heic', '.HEIC'}):
        return JSONResponse({"ok": False, "error": f"不支持的文件类型: {ext}"}, status_code=400)

    contents = await file.read()
    if len(contents) == 0:
        return JSONResponse({"ok": False, "error": "上传文件为空"}, status_code=400)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:6]
    job_id = f"textin_{ts}_{uid}"
    out_dir = WEB_JOBS_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    orig_path = out_dir / f"original{ext}"
    orig_path.write_bytes(contents)

    preset_filter = None
    if mode != "all":
        preset_filter = [mode]

    try:
        from src.m1_image_engine.providers.textin.experiment import run_textin_presets
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_textin_presets, contents, str(out_dir), preset_filter)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e), "job_id": job_id}, status_code=500)

    results_out = []
    for r in result["results"]:
        entry = {
            "preset": r["preset"],
            "description": r.get("description", ""),
            "ok": r["ok"],
            "duration_ms": r.get("duration_ms", 0),
            "error": r.get("error"),
            "stage_failed": r.get("stage_failed"),
        }
        if r["ok"]:
            entry["image_url"] = f"/api/textin/results/{job_id}/{r['preset']}.jpg"
            entry["response_url"] = f"/api/textin/results/{job_id}/responses/{r['preset']}.json"
        results_out.append(entry)

    return {
        "ok": result["ok"],
        "job_id": job_id,
        "original_url": f"/api/textin/results/{job_id}/original{ext}",
        "results": results_out,
        "errors": result["errors"],
    }


@router.get("/results/{job_id}/{filename:path}")
async def serve_result(job_id: str, filename: str):
    path = WEB_JOBS_DIR / job_id / filename
    if not path.exists():
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    return FileResponse(path)
