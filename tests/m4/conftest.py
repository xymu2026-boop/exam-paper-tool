"""Shared pytest fixtures for the M4 integration test suite.

Strategy:
- M2 (Database) uses a real temporary SQLite file per test.
- M1 (process_paper) and M5 (export_pdf) are monkey-patched to deterministic
  fakes so we never invoke OpenCV or fpdf2 inside the suite.
- The data root is redirected to ``tmp_path`` so uploaded files, processed
  outputs, mistake crops and exports never pollute the workspace.
"""

from __future__ import annotations

import io
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Ensure the project root is on sys.path so ``src.*`` imports resolve when
# pytest is invoked from a different working directory.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class _FakeProcessResult:
    """Stand-in for :class:`src.m1_image_engine.ProcessResult`."""

    success: bool
    processed_path: Optional[str] = None
    cleaned_path: Optional[str] = None
    quality_score: float = 0.0
    warnings: Optional[list] = None
    error: Optional[str] = None


def _make_fake_image(path: Path, size: tuple[int, int] = (400, 600)) -> None:
    """Write a deterministic JPEG to ``path`` so cropping has real bytes to chew on."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGB', size, color=(240, 240, 240))
    img.save(path, format='JPEG', quality=80)


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect M4 config paths to a per-test ``tmp_path`` directory."""
    from src.m4_web_backend import config as m4_config

    root = tmp_path / 'data'
    root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(m4_config, 'DATA_DIR', root)
    monkeypatch.setattr(m4_config, 'ORIGINALS_DIR', root / 'originals')
    monkeypatch.setattr(m4_config, 'PROCESSED_DIR', root / 'processed')
    monkeypatch.setattr(m4_config, 'MISTAKES_DIR', root / 'mistakes')
    monkeypatch.setattr(m4_config, 'EXPORTS_DIR', root / 'exports')
    monkeypatch.setattr(m4_config, 'DB_PATH', root / 'test.db')

    # Also redirect the FRONTEND_DIR to a dedicated test-only frontend so
    # the static-mount test exercises real files even when the real M3
    # frontend folder is empty.
    fe = tmp_path / 'frontend'
    fe.mkdir(parents=True, exist_ok=True)
    (fe / 'index.html').write_text(
        '<!doctype html><title>试卷宝</title><h1>hello</h1>',
        encoding='utf-8',
    )
    (fe / 'paper.html').write_text('<title>paper</title>', encoding='utf-8')
    monkeypatch.setattr(m4_config, 'FRONTEND_DIR', fe)

    return root


@pytest.fixture
def fake_m1(monkeypatch: pytest.MonkeyPatch, data_root: Path):
    """Patch M1.process_paper to a deterministic stub.

    The stub writes two tiny JPEGs into ``output_dir`` and returns success.
    Override behaviour by reassigning the module-level ``mode`` attribute.
    """
    state = {'mode': 'success', 'last_call': None}

    def fake_process_paper(input_path: str, output_dir: str):
        state['last_call'] = (input_path, output_dir)
        if state['mode'] == 'failure':
            return _FakeProcessResult(
                success=False,
                error='simulated failure',
                warnings=['fake'],
            )

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        processed_path = out / 'processed.jpg'
        cleaned_path = out / 'cleaned.jpg'
        _make_fake_image(processed_path)
        _make_fake_image(cleaned_path)
        return _FakeProcessResult(
            success=True,
            processed_path=str(processed_path),
            cleaned_path=str(cleaned_path),
            quality_score=0.75,
            warnings=['ok'],
        )

    # Patch *both* the original module and the import alias inside the
    # routes module — Python re-binds the name at import time.
    import src.m1_image_engine as m1_pkg
    import src.m1_image_engine.engine as m1_engine
    from src.m4_web_backend.routes import papers as papers_route

    monkeypatch.setattr(m1_engine, 'process_paper', fake_process_paper)
    monkeypatch.setattr(m1_pkg, 'process_paper', fake_process_paper)
    monkeypatch.setattr(papers_route, 'm1_process_paper', fake_process_paper)
    return state


@pytest.fixture
def fake_m5(monkeypatch: pytest.MonkeyPatch):
    """Patch M5.export_pdf to a stub that writes a tiny placeholder file."""
    state = {'mode': 'success', 'last_call': None}

    def fake_export_pdf(image_paths, output_path, config=None):
        state['last_call'] = (list(image_paths), output_path, config)
        if state['mode'] == 'failure':
            return False
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b'%PDF-1.4 fake\n')
        return True

    import src.m5_pdf_export as m5_pkg
    import src.m5_pdf_export.exporter as m5_exporter
    from src.m4_web_backend.routes import exports as exports_route

    monkeypatch.setattr(m5_exporter, 'export_pdf', fake_export_pdf)
    monkeypatch.setattr(m5_pkg, 'export_pdf', fake_export_pdf)
    monkeypatch.setattr(exports_route, 'm5_export_pdf', fake_export_pdf)
    return state


@pytest.fixture
def client(data_root: Path, fake_m1, fake_m5) -> TestClient:
    """Build a fresh ``TestClient`` with patched config and dependencies."""
    from src.m4_web_backend.app import create_app
    from src.m4_web_backend.deps import get_db

    # Drop any cached DB instance pointing at a previous test's database.
    get_db.cache_clear()

    app = create_app()
    with TestClient(app) as c:
        yield c

    get_db.cache_clear()


# ---------------------------------------------------------------------------
# Helper factories used by individual test modules
# ---------------------------------------------------------------------------

def make_jpeg_bytes(size: tuple[int, int] = (300, 400)) -> bytes:
    """Return JPEG bytes of a small placeholder image."""
    buf = io.BytesIO()
    Image.new('RGB', size, color=(220, 220, 220)).save(buf, format='JPEG')
    return buf.getvalue()


def make_png_bytes(size: tuple[int, int] = (300, 400)) -> bytes:
    """Return PNG bytes of a small placeholder image."""
    buf = io.BytesIO()
    Image.new('RGB', size, color=(220, 220, 220)).save(buf, format='PNG')
    return buf.getvalue()


@pytest.fixture
def sample_jpeg() -> bytes:
    return make_jpeg_bytes()


@pytest.fixture
def sample_png() -> bytes:
    return make_png_bytes()
