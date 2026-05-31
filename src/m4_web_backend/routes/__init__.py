"""Route package — exposes router instances for `app.py` to include."""

from .papers import router as papers_router
from .mistakes import router as mistakes_router
from .exports import router as exports_router

__all__ = ['papers_router', 'mistakes_router', 'exports_router']
