"""M4 FastAPI application entry point.

Run with::

    python -m src.m4_web_backend.app

The server listens on ``0.0.0.0:8900`` so that other devices on the LAN
(e.g. a phone) can reach it directly at ``http://<host>:8900``.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .deps import get_db
from .routes import exports_router, mistakes_router, papers_router
from .routes.debug import router as debug_router
from .routes.textin_api import router as textin_router

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: bootstrap directories, verify M1/M5 imports, init DB.
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan hook."""
    # 1. Ensure every data directory exists.
    for d in (
        config.DATA_DIR,
        config.ORIGINALS_DIR,
        config.PROCESSED_DIR,
        config.MISTAKES_DIR,
        config.EXPORTS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)

    # 2. Verify that the M1 and M5 modules import cleanly.  If they
    #    don't, the operator should see a clear error at startup rather
    #    than a 500 mid-request.
    try:
        from src.m1_image_engine import process_paper  # noqa: F401
        from src.m5_pdf_export import export_pdf  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment-specific
        logger.error(
            'Fatal: M1 or M5 module import failed: %s. '
            'Run `pip install -r requirements.txt` and retry.',
            exc,
        )
        raise

    # 3. Touch the database to run migrations eagerly.
    get_db()

    yield

    # On shutdown: close DB cleanly so SQLite checkpoints WAL.
    try:
        db = get_db()
        db.close()
    except Exception:  # pragma: no cover - best-effort cleanup
        pass
    get_db.cache_clear()


def create_app() -> FastAPI:
    """Application factory used by tests and the CLI entry point."""
    app = FastAPI(
        title='试卷宝 API',
        description='Exam Paper Tool — backend API and static file server.',
        version='1.0',
        lifespan=lifespan,
    )

    # --- CORS (LAN-only deployment, no auth) ----------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    # --- API routers ----------------------------------------------------
    app.include_router(papers_router)
    app.include_router(mistakes_router)
    app.include_router(exports_router)
    app.include_router(debug_router)
    app.include_router(textin_router)

    # --- Uniform error envelope ----------------------------------------
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(  # type: ignore[unused-function]
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={'error': exc.detail if isinstance(exc.detail, str) else str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(  # type: ignore[unused-function]
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Surface validation errors in the standard envelope.  Pydantic
        # error objects can contain non-JSON-serialisable ``ctx`` values
        # (e.g. raw ``ValueError`` instances), so we stringify them here.
        errors = exc.errors()
        first = errors[0] if errors else {'msg': 'invalid request'}
        msg = str(first.get('msg', 'invalid request'))
        safe_details: list[dict] = []
        for e in errors:
            safe_details.append(
                {
                    'loc': [str(p) for p in e.get('loc', [])],
                    'msg': str(e.get('msg', '')),
                    'type': str(e.get('type', '')),
                }
            )
        return JSONResponse(
            status_code=400,
            content={'error': msg, 'details': safe_details},
        )

    # --- Static mounts --------------------------------------------------
    # The `data/` directory holds user uploads, processed images, mistake
    # crops and exported PDFs.  Mount it *before* the catch-all frontend
    # so the more specific prefix wins.
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    app.mount(
        '/static/data',
        StaticFiles(directory=str(config.DATA_DIR)),
        name='static-data',
    )

    # The M3 frontend is served at the root.  We only mount it if the
    # directory exists and has an index.html, otherwise the API stays
    # accessible at /api/* and /docs without 500s during early M3 dev.
    frontend_index = config.FRONTEND_DIR / 'index.html'
    if frontend_index.is_file():
        app.mount(
            '/',
            StaticFiles(directory=str(config.FRONTEND_DIR), html=True),
            name='frontend',
        )
    else:
        # Provide a tiny placeholder so `GET /` is not a 404 during dev.
        @app.get('/', include_in_schema=False)
        async def _root_placeholder():  # type: ignore[unused-function]
            return JSONResponse(
                content={
                    'message': '试卷宝 API is running.',
                    'frontend': 'M3 frontend not yet built — see /docs for API.',
                    'docs': '/docs',
                }
            )

    return app


app = create_app()


def main() -> int:
    """CLI entry point: ``python -m src.m4_web_backend.app``."""
    import uvicorn

    try:
        uvicorn.run(
            'src.m4_web_backend.app:app',
            host=config.HOST,
            port=config.PORT,
            reload=False,
        )
    except OSError as exc:
        print(
            f'Failed to bind {config.HOST}:{config.PORT} — {exc}',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
