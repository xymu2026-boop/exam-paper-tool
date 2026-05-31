"""M4 dependency injection helpers.

The ``Database`` instance is a singleton (cached via ``lru_cache``) so that
every route handler shares one SQLite connection.  Tests replace the cache
target by calling ``get_db.cache_clear()`` before swapping in a temp DB.
"""

from __future__ import annotations

from functools import lru_cache

from src.m2_data_layer import Database

from . import config


@lru_cache(maxsize=1)
def get_db() -> Database:
    """Return the singleton ``Database`` instance.

    The database file path comes from :mod:`src.m4_web_backend.config`.
    The first call performs the connection and runs migrations; subsequent
    calls reuse the cached instance.
    """
    return Database(str(config.DB_PATH))


__all__ = ['get_db']
