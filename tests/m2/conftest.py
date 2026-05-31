"""pytest fixtures for M2 tests.

Every test receives a fresh ``Database(':memory:')`` instance via the
``db`` fixture to guarantee isolation and zero disk I/O.
"""

import pytest

from src.m2_data_layer import Database


@pytest.fixture(scope="function")
def db():
    """Provide a fresh :class:`Database` backed by an in-memory SQLite
    database.  The connection is automatically closed after each test."""
    database = Database(":memory:")
    yield database
    database.close()
