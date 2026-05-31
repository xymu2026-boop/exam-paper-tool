"""M4 central configuration.

All filesystem paths, network bindings, and upload limits are defined here.
Other modules import from this single source of truth so that swapping the
data root (for tests) only requires monkey-patching one module.
"""

from __future__ import annotations

from pathlib import Path

# --- Filesystem layout (relative to the working directory by default) ----
DATA_DIR: Path = Path('data')
ORIGINALS_DIR: Path = DATA_DIR / 'originals'
PROCESSED_DIR: Path = DATA_DIR / 'processed'
MISTAKES_DIR: Path = DATA_DIR / 'mistakes'
EXPORTS_DIR: Path = DATA_DIR / 'exports'
DB_PATH: Path = DATA_DIR / 'exam_paper.db'

# --- M3 frontend static directory ----------------------------------------
FRONTEND_DIR: Path = Path('src/m3_web_frontend')

# --- Network ---------------------------------------------------------------
HOST: str = '0.0.0.0'
PORT: int = 8900

# --- Upload constraints ---------------------------------------------------
MAX_UPLOAD_SIZE: int = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS: set[str] = {'.jpg', '.jpeg', '.png', '.heic'}

__all__ = [
    'DATA_DIR',
    'ORIGINALS_DIR',
    'PROCESSED_DIR',
    'MISTAKES_DIR',
    'EXPORTS_DIR',
    'DB_PATH',
    'FRONTEND_DIR',
    'HOST',
    'PORT',
    'MAX_UPLOAD_SIZE',
    'ALLOWED_EXTENSIONS',
]
