# M4 Web Backend Technical Implementation Plan

> **Module**: M4 (Web Backend)
> **Date**: 2026-05-31
> **Status**: Design Document

---

## 1. 模块职责

M4 is the **glue layer** of the entire system. It does not implement any business algorithms. Its sole responsibility is orchestration: receive an HTTP request, validate input, delegate to M1 (image processing), M2 (data layer), or M5 (PDF export), assemble the result, and return an HTTP response. M4 also serves the M3 frontend static files and exposes the `data/` directory so that images are accessible via HTTP.

---

## 2. 输入输出

### 2.1 API Endpoints

All 10 REST routes are defined in `INTERFACE-CONTRACT.md` Section 4.4. M4 also mounts two static file directories.

#### Static File Serving

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Serves `src/m3_web_frontend/index.html` and associated assets |
| `GET /static/data/{path:path}` | Serves files from the `data/` directory (images, PDFs) |

#### Paper Routes

**POST /api/papers/upload**

- **Request**: `multipart/form-data`
  - `file`: `UploadFile` (image file)
  - `child_id`: string (Form field), must be `K1` or `K2`
  - `subject`: string (Form field), must be one of `数学`, `语文`, `英语`, `科学`, `其他`
  - `paper_type`: string (Form field, optional), default `其他`
  - `title`: string (Form field, optional)
- **Success Response** (200):
  ```json
  {"paper_id": 1, "status": "pending"}
  ```
- **Error Responses**:
  - `400`: Invalid file type, missing required field, or file exceeds 16MB
  - `500`: File system error or database write failure

**POST /api/papers/{paper_id}/process**

- **Request**: Path parameter `paper_id: int`
- **Success Response** (200):
  ```json
  {"status": "processed", "quality_score": 0.75, "warnings": ["..."]}
  ```
- **Error Responses**:
  - `404`: Paper not found
  - `500`: M1 processing failure (status updated to `failed` in DB)

**GET /api/papers**

- **Request**: Query parameters (all optional)
  - `child_id`: string
  - `subject`: string
  - `status`: string (`pending`, `processing`, `processed`, `failed`)
  - `limit`: int, default 50
  - `offset`: int, default 0
- **Success Response** (200):
  ```json
  {"papers": [...], "total": 42}
  ```

**GET /api/papers/{paper_id}**

- **Request**: Path parameter `paper_id: int`
- **Success Response** (200): Paper object enriched with `original_url`, `processed_url`, `cleaned_url`
- **Error Responses**:
  - `404`: Paper not found

#### Mistake Routes

**POST /api/mistakes**

- **Request**: JSON body
  - `paper_id`: int
  - `crop_x`: int
  - `crop_y`: int
  - `crop_width`: int
  - `crop_height`: int
  - `note`: string (optional)
  - `error_type`: string (optional), one of `粗心`, `概念不清`, `计算错误`, `不会做`, `其他`
- **Success Response** (200):
  ```json
  {"mistake_id": 1}
  ```
- **Error Responses**:
  - `404`: Paper not found
  - `500`: Image crop failure or DB write failure

**GET /api/mistakes**

- **Request**: Query parameters (all optional)
  - `child_id`: string
  - `subject`: string
  - `status`: string
  - `limit`: int, default 100
  - `offset`: int, default 0
- **Success Response** (200):
  ```json
  {"mistakes": [...], "total": 15}
  ```

**PATCH /api/mistakes/{mistake_id}**

- **Request**: Path parameter `mistake_id: int`; JSON body (at least one field required)
  - `status`: string (optional)
  - `note`: string (optional)
  - `error_type`: string (optional)
- **Success Response** (200):
  ```json
  {"success": true}
  ```
- **Error Responses**:
  - `404`: Mistake not found

**DELETE /api/mistakes/{mistake_id}**

- **Request**: Path parameter `mistake_id: int`
- **Success Response** (200):
  ```json
  {"success": true}
  ```
- **Error Responses**:
  - `404`: Mistake not found

#### Export Routes

**POST /api/export/pdf**

- **Request**: JSON body
  - `child_id`: string
  - `mistake_ids`: list[int]
  - `layout`: string (optional), default `one_per_page`; options: `one_per_page`, `two_per_page`, `compact`
- **Success Response** (200):
  ```json
  {"pdf_url": "/static/data/exports/1.pdf", "export_id": 1}
  ```
- **Error Responses**:
  - `400`: Empty `mistake_ids` or invalid `layout`
  - `404`: One or more mistakes not found
  - `500`: M5 export failure

**GET /api/export/history**

- **Request**: Query parameters (all optional)
  - `child_id`: string
  - `limit`: int, default 20
- **Success Response** (200):
  ```json
  {"exports": [...]}
  ```

### 2.2 Complete Data Flow

The upload flow illustrates the full data flow through M4:

```
User (browser) ──multipart──► M4 /api/papers/upload
                                    │
                                    ▼
                              Validate file type & size
                                    │
                                    ▼
                              Generate filename
                                    │
                                    ▼
                              Save to data/originals/{child_id}/{subject}/
                                    │
                                    ▼
                              Call M2 db.create_paper(...)
                                    │
                                    ▼
                         ◄── Return JSON {paper_id, status}
```

The process flow extends this:

```
User ──POST /api/papers/{id}/process──► M4
                                              │
                                              ▼
                                        M2 db.get_paper(id)
                                              │
                                              ▼
                                        M2 db.update_paper_status('processing')
                                              │
                                              ▼
                                        M1.process_paper(original_path, output_dir)
                                              │
                                              ▼
                                        M2 db.update_paper_status(...) ──► Return result
```

---

## 3. 技术选型

| Component | Choice | Reason |
|-----------|--------|--------|
| Web Framework | **FastAPI** | Native async support, automatic OpenAPI/Swagger generation, tight Pydantic integration, and excellent type safety. Compared to Flask, FastAPI handles async I/O without extensions and produces interactive API docs automatically. |
| ASGI Server | **Uvicorn** | Lightweight, high-performance ASGI server. Chosen over Gunicorn because the deployment target is a single machine (a home Mac), so process-level multi-worker management is unnecessary complexity. |
| File Upload Parsing | **python-multipart** | Required by FastAPI's `UploadFile` and `File` form handling for `multipart/form-data` requests. |
| Data Validation | **Pydantic v2** | Enforces request/response schemas at runtime, generates Swagger UI automatically, and provides clear validation error messages to API consumers. |
| Static Files | **FastAPI StaticFiles** | Built-in mount support (`app.mount`) for serving both the M3 frontend directory and the `data/` directory under distinct URL prefixes. |
| Why NOT Django | | Django is full-stack and ORM-heavy. The project needs only a thin API glue layer; Django's admin, ORM, and template system are all unused overhead. |
| Why NOT Flask | | Flask lacks native async support and automatic OpenAPI docs. FastAPI's developer experience is superior for this API-centric module. |

---

## 4. 核心算法/流程

### 4.1 Upload Flow (Most Complex)

1. **Receive request**: FastAPI reads `file: UploadFile` plus query parameters `child_id`, `subject`, `paper_type`, `title`.
2. **Validate file type**: Read the filename extension. Reject if not in `{.jpg, .jpeg, .png, .heic}` (case-insensitive). Return `400` with `{"error": "Unsupported file type: .gif"}`.
3. **Validate file size**: Before full read, stream the file and accumulate size. If total exceeds 16MB, discard and return `400` with `{"error": "File too large (max 16MB)"}`.
4. **Generate filename**: Call utility `make_filename(ext)` which produces `{timestamp}_{uuid4_short}.jpg` (e.g., `20260531_153022_a1b2c3d4.jpg`). If the input is `.heic` or `.png`, the saved file is still normalized to `.jpg` after conversion or direct copy.
5. **Ensure directory exists**: Compute target path `data/originals/{child_id}/{subject}/`. Use `Path.mkdir(parents=True, exist_ok=True)`.
6. **Save file to disk**: Write the streamed bytes to the computed target path asynchronously (using `aiofiles` or `run_in_executor` with standard I/O).
7. **Insert database record**: Call `db.create_paper(child_id, subject, original_path, paper_type, title)` to get the auto-increment `paper_id` with `status='pending'`.
8. **Return response**: Return JSON `{"paper_id": paper_id, "status": "pending"}` with status `200`.

### 4.2 Process Flow

1. **Lookup paper**: Call `db.get_paper(paper_id)`. If `None`, raise `HTTPException(404)`.
2. **Guard against double processing**: If `paper.status` is already `'processing'`, return `409` or return current state (design decision: idempotent re-trigger is acceptable; guard against concurrent triggers via naive check).
3. **Update status**: Call `db.update_paper_status(paper_id, 'processing')`.
4. **Ensure output directory**: Create `data/processed/{paper_id}/` via `mkdir(parents=True, exist_ok=True)`.
5. **Call M1**: Invoke `m1_image_engine.engine.process_paper(paper.original_path, output_dir)`. Because M1 is CPU-bound image processing, execute inside a thread pool via `asyncio.get_event_loop().run_in_executor(None, ...)` to avoid blocking the async event loop.
6. **Handle success** (`result.success == True`):
   - Call `db.update_paper_status(paper_id, 'processed', processed_path=result.processed_path, cleaned_path=result.cleaned_path, quality_score=result.quality_score)`.
   - Return `{"status": "processed", "quality_score": result.quality_score, "warnings": result.warnings or []}`.
7. **Handle failure** (`result.success == False`):
   - Call `db.update_paper_status(paper_id, 'failed', error_message=result.error)`.
   - Return `{"status": "failed", "quality_score": None, "warnings": [], "error": result.error}` with HTTP `500`.

### 4.3 Mistake Creation Flow

1. **Receive coordinates**: Parse JSON body `paper_id`, `crop_x`, `crop_y`, `crop_width`, `crop_height`, plus optional `note` and `error_type`.
2. **Lookup paper**: `db.get_paper(paper_id)`. If `None`, return `404`.
3. **Check prerequisite**: If `paper.status != 'processed'`, return `400` because crop source images do not yet exist.
4. **Insert preliminary DB record**: Call `db.create_mistake(...)` with `mistake_image_path=None` and `clean_mistake_image_path=None` to obtain the `mistake_id`.
5. **Create directory**: `data/mistakes/{mistake_id}/`.
6. **Crop images**: Use Pillow to crop `paper.processed_path` into `data/mistakes/{mistake_id}/original.jpg`, and `paper.cleaned_path` into `data/mistakes/{mistake_id}/clean.jpg`.
7. **Update DB with paths**: After cropping, call `db.update_mistake_paths(mistake_id, mistake_image_path=original.jpg, clean_mistake_image_path=clean.jpg)` to backfill the saved image paths into the database record.
8. **Return response**: `{"mistake_id": mistake_id}`.

### 4.4 Export Flow

1. **Receive request**: Parse `child_id`, `mistake_ids`, `layout`, and optional `title`.
2. **Validate IDs**: Iterate `mistake_ids` and call `db.get_mistake(id)` for each. If any is missing, return `404`. If any `child_id` does not match the request `child_id`, return `400`.
3. **Collect image paths**: Build a list of absolute paths from `mistake.mistake_image_path` for each mistake, preserving the order from `mistake_ids`.
4. **Reserve export log**: Call `db.create_export_log(child_id, mistake_ids, pdf_path, subject)` to get `export_id`. The `pdf_path` is precomputed as `data/exports/{export_id}.pdf`.
5. **Call M5**: Build `ExportConfig(layout=layout, title=title or '')` and call `m5_pdf_export.exporter.export_pdf(image_paths, pdf_path, config)`. Execute in thread pool because PDF generation is I/O and CPU intensive.
6. **Handle failure**: If M5 returns `False`, return `500` with `{"error": "PDF generation failed"}`.
7. **Return success**: `{"pdf_url": f"/static/data/exports/{export_id}.pdf", "export_id": export_id}`.

### 4.5 Error Handling Decision Tree

```
Request arrives
    │
    ▼
Pydantic validation error? ──YES──► 400 {"error": "detail..."}
    │ NO
    ▼
Missing required query/body param? ──YES──► 400 {"error": "Missing field X"}
    │ NO
    ▼
File validation error (type/size)? ──YES──► 400 {"error": "..."}
    │ NO
    ▼
Resource lookup (DB get_*) returns None? ──YES──► 404 {"error": "Paper/Mistake not found"}
    │ NO
    ▼
Business rule violation? ──YES──► 400 or 409 {"error": "..."}
    │ NO
    ▼
Delegate to M1/M2/M5
    │
    ▼
M1/M5 returns success=False? ──YES──► 500 {"error": result.error}
    │ NO
    ▼
DB write returns False/exception? ──YES──► 500 {"error": "Internal database error"}
    │ NO
    ▼
Return 200 with success payload
```

---

## 5. 接口设计

### 5.1 Route Handler Summary

| Method | Path | Query / Body Params | Response Model | Status Codes |
|--------|------|--------------------|----------------|--------------|
| POST | `/api/papers/upload` | `file` (UploadFile), `child_id`, `subject`, `paper_type`, `title` | `UploadResponse` | 200, 400, 500 |
| POST | `/api/papers/{paper_id}/process` | `paper_id` (path) | `ProcessResponse` | 200, 404, 500 |
| GET | `/api/papers` | `child_id`, `subject`, `status`, `limit`, `offset` | `PaperListResponse` | 200 |
| GET | `/api/papers/{paper_id}` | `paper_id` (path) | `PaperOut` | 200, 404 |
| POST | `/api/mistakes` | `MistakeCreateRequest` (JSON) | `MistakeCreateResponse` | 200, 404, 500 |
| GET | `/api/mistakes` | `child_id`, `subject`, `status`, `limit`, `offset` | `MistakeListResponse` | 200 |
| PATCH | `/api/mistakes/{mistake_id}` | `mistake_id` (path), `MistakeUpdateRequest` (JSON) | `SuccessResponse` | 200, 404 |
| DELETE | `/api/mistakes/{mistake_id}` | `mistake_id` (path) | `SuccessResponse` | 200, 404 |
| POST | `/api/export/pdf` | `ExportPdfRequest` (JSON) | `ExportPdfResponse` | 200, 400, 404, 500 |
| GET | `/api/export/history` | `child_id`, `limit` | `ExportHistoryResponse` | 200 |

### 5.2 Pydantic Schemas (`schemas.py`)

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class ErrorResponse(BaseModel):
    error: str

class UploadResponse(BaseModel):
    paper_id: int
    status: str = 'pending'

class ProcessResponse(BaseModel):
    status: str
    quality_score: Optional[float] = None
    warnings: List[str] = []
    error: Optional[str] = None

class PaperOut(BaseModel):
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

class MistakeCreateRequest(BaseModel):
    paper_id: int
    crop_x: int
    crop_y: int
    crop_width: int = Field(..., gt=0)
    crop_height: int = Field(..., gt=0)
    note: Optional[str] = None
    error_type: Optional[str] = None

    @field_validator('error_type')
    @classmethod
    def check_error_type(cls, v):
        allowed = {'粗心', '概念不清', '计算错误', '不会做', '其他'}
        if v is not None and v not in allowed:
            raise ValueError(f'error_type must be one of {allowed}')
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

class SuccessResponse(BaseModel):
    success: bool

class ExportPdfRequest(BaseModel):
    child_id: str
    mistake_ids: List[int]
    layout: str = 'one_per_page'
    title: Optional[str] = None

    @field_validator('layout')
    @classmethod
    def check_layout(cls, v):
        allowed = {'one_per_page', 'two_per_page', 'compact'}
        if v not in allowed:
            raise ValueError(f'layout must be one of {allowed}')
        return v

class ExportPdfResponse(BaseModel):
    pdf_url: str
    export_id: int
    title: Optional[str] = None

class ExportHistoryItem(BaseModel):
    id: int
    child_id: str
    subject: Optional[str] = None
    mistake_ids: str  # JSON array string from DB
    pdf_path: str
    created_at: str
    pdf_url: Optional[str] = None

class ExportHistoryResponse(BaseModel):
    exports: List[ExportHistoryItem]
```

### 5.3 Dependency Injection

```python
# deps.py
from functools import lru_cache
from src.m2_data_layer.db import Database
from .config import DB_PATH

@lru_cache(maxsize=1)
def get_db() -> Database:
    return Database(str(DB_PATH))
```

Every route handler declares `db: Database = Depends(get_db)`. The `lru_cache` ensures a singleton `Database` instance across the application lifetime.

### 5.4 Configuration Object (`config.py`)

```python
from pathlib import Path

DATA_DIR = Path('data')
ORIGINALS_DIR = DATA_DIR / 'originals'
PROCESSED_DIR = DATA_DIR / 'processed'
MISTAKES_DIR = DATA_DIR / 'mistakes'
EXPORTS_DIR = DATA_DIR / 'exports'
DB_PATH = DATA_DIR / 'exam_paper.db'
FRONTEND_DIR = Path('src/m3_web_frontend')
HOST = '0.0.0.0'
PORT = 8900
MAX_UPLOAD_SIZE = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic'}
```

### 5.5 CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
```

This allows any device on the local network (phones, tablets, other computers) to access the API and static files without authentication.

---

## 6. 数据结构

### 6.1 `config.py` Constants

All filesystem paths, network settings, and upload constraints are centralized in `config.py`:

- `DATA_DIR`: Root data folder (`data/`)
- `ORIGINALS_DIR`: `data/originals/`
- `PROCESSED_DIR`: `data/processed/`
- `MISTAKES_DIR`: `data/mistakes/`
- `EXPORTS_DIR`: `data/exports/`
- `DB_PATH`: `data/exam_paper.db`
- `FRONTEND_DIR`: `src/m3_web_frontend/`
- `HOST = '0.0.0.0'`: Bind to all interfaces for LAN access
- `PORT = 8900`: Fixed application port
- `MAX_UPLOAD_SIZE = 16 * 1024 * 1024`: 16 megabytes
- `ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic'}`

### 6.2 `deps.py`

Provides the `get_db()` dependency. It uses `functools.lru_cache(maxsize=1)` to guarantee that the `Database` object is instantiated exactly once. On application shutdown, a lifespan event handler or `atexit` hook should call `db.conn.close()` to release the SQLite connection cleanly.

### 6.3 `schemas.py`

Contains every Pydantic model used for request bodies, query parameter validation, and response serialization. Field validators enforce business constraints (e.g., `crop_width > 0`, `layout` must be an allowed enum value). Response models for `PaperOut` and `MistakeOut` include computed `*_url` fields so the frontend receives absolute or root-relative URLs instead of raw filesystem paths.

### 6.4 File Naming Utility

```python
from datetime import datetime
import uuid

def make_filename(ext: str = '.jpg') -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    short = uuid.uuid4().hex[:8]
    return f'{ts}_{short}{ext}'
```

This guarantees globally unique filenames even under high-frequency concurrent uploads, eliminating filesystem collision risk.

### 6.5 Image Cropping Utility

```python
from PIL import Image
from pathlib import Path

def crop_and_save(src_path: str, dst_path: str,
                  x: int, y: int, w: int, h: int) -> None:
    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src_path) as img:
        img.crop((x, y, x + w, y + h)).save(dst_path, quality=92)
```

This is a synchronous, blocking operation. It will be wrapped with `run_in_executor` when invoked from async route handlers.

---

## 7. 测试策略

### 7.1 Testing Framework

- Use FastAPI's built-in `TestClient` (from `fastapi.testclient`).
- Run with `pytest tests/m4/ -v`.

### 7.2 Mock Strategy

| Dependency | Mock Approach |
|------------|---------------|
| M1 (`process_paper`) | Monkeypatch `src.m1_image_engine.engine.process_paper` to return a controlled `ProcessResult` (success or failure) without real image processing. |
| M5 (`export_pdf`) | Monkeypatch `src.m5_pdf_export.exporter.export_pdf` to touch an output file and return `True`, or return `False` for failure scenarios. |
| M2 (`Database`) | Use a **real** temporary SQLite file per test fixture (`tmp_path / "test.db"`). This validates actual SQL and schema behavior without mocking CRUD logic. |

### 7.3 Test Scenarios

| Scenario | Endpoint | Expected Behavior |
|----------|----------|-------------------|
| Upload success | `POST /api/papers/upload` | Returns `paper_id`, file exists on disk, DB row `status='pending'` |
| Upload invalid type | `POST /api/papers/upload` | Returns `400`, no file written, no DB row |
| Upload oversized | `POST /api/papers/upload` | Returns `400`, stream discarded early |
| Process success | `POST /api/papers/{id}/process` | Returns `status='processed'`, DB updated with paths and score |
| Process M1 failure | `POST /api/papers/{id}/process` | Returns `500`, DB `status='failed'`, `error_message` populated |
| Process paper not found | `POST /api/papers/{id}/process` | Returns `404` |
| List papers | `GET /api/papers` | Returns list and total count, respects query filters |
| Get paper detail | `GET /api/papers/{id}` | Returns enriched `PaperOut` with URLs |
| Mistake create | `POST /api/mistakes` | Returns `mistake_id`, cropped images exist on disk |
| Mistake list | `GET /api/mistakes` | Returns list with total |
| Mistake update | `PATCH /api/mistakes/{id}` | DB row updated, returns `{"success": true}` |
| Mistake delete | `DELETE /api/mistakes/{id}` | DB row removed, returns `{"success": true}` |
| Export PDF | `POST /api/export/pdf` | M5 called with correct args, returns `pdf_url` and `export_id` |
| Export history | `GET /api/export/history` | Returns list of prior exports |
| Static file serving | `GET /` and `GET /static/data/...` | Returns HTML or image bytes with correct MIME type |
| Swagger UI | `GET /docs` | Returns valid OpenAPI JSON spec, no errors |

### 7.4 Coverage Target

Every route must have at least one happy-path test and one error-path test. The upload and process flows require the most coverage due to branching on file validation, M1 success/failure, and DB state transitions.

---

## 8. 风险与对策

### 8.1 M1 Processing Blocks the Async Event Loop

M1 performs CPU-heavy image processing (OpenCV, PIL, numpy). If invoked directly inside an async route handler, it will freeze the entire Uvicorn event loop, causing all concurrent requests to stall.

**Mitigation**: Wrap every M1 and M5 call in `asyncio.get_event_loop().run_in_executor(None, func, ...)`. For the MVP, a single default thread pool is sufficient. If throughput becomes an issue later, a dedicated `ProcessPoolExecutor` can be introduced.

### 8.2 File System Race Conditions During Concurrent Uploads

Two simultaneous uploads could theoretically write to the same temporary filename if timestamp collisions occur.

**Mitigation**: The `make_filename()` utility includes a UUID4 short segment (8 hex characters), making filename collisions statistically impossible. Additionally, each paper gets its own `processed/{paper_id}/` directory, and each mistake gets its own `mistakes/{mistake_id}/` directory, so parallel operations on different resources never touch the same path.

### 8.3 Large File Uploads Causing Memory Pressure

Reading an entire upload into memory before writing to disk can exhaust RAM, especially on a home machine with limited resources.

**Mitigation**: Enforce the 16MB hard limit before any disk write. FastAPI's `UploadFile` already streams the file to a temporary SpooledTemporaryFile; M4 will read this stream in chunks and write asynchronously to the final destination rather than buffering the entire payload in memory.

### 8.4 M1/M5 Import Failures at Startup

If M1 or M5 modules are missing, renamed, or have unmet native dependencies (e.g., OpenCV not compiled for the current platform), the M4 application will crash on first import.

**Mitigation**: Perform imports at module level with a clear `try/except ImportError` guard that logs a descriptive fatal error message (e.g., "M1 image engine not found. Please ensure opencv-python is installed"). In development, this helps the developer diagnose environment issues immediately rather than seeing a generic traceback.

### 8.5 Database Connection Leaks

The `Database` class holds an open SQLite connection. If the application restarts frequently (e.g., during development with auto-reload), old connections may not be closed properly.

**Mitigation**: Use `lru_cache(maxsize=1)` for the singleton `Database` instance. Register a FastAPI lifespan event handler that calls `db.conn.close()` on application shutdown. SQLite handles multiple readers well, but proper cleanup prevents `ResourceWarning` noise and ensures WAL files are checkpointed.

### 8.6 Port Conflict on 8900

If another service on the home network or the local machine is already bound to port 8900, Uvicorn will fail to start with an `Address already in use` error.

**Mitigation**: On startup failure, catch the `OSError`, print a clear message ("Port 8900 is already in use. Run with `--port <number>` to override."), and exit with a non-zero status. The `config.py` value remains the default, but the startup script can accept an environment variable or CLI argument to override `PORT`.
