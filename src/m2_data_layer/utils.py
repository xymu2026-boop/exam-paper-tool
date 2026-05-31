"""Utility helpers for M2 — Row-to-dataclass mapping & dynamic WHERE builder.

All functions in this module are pure (no side effects) and operate only
on in-memory data structures.
"""

import json
from typing import Any, Optional
import sqlite3

from .models import Paper, Mistake, ExportLog


# ---------------------------------------------------------------------------
# Row → dataclass helpers
# ---------------------------------------------------------------------------

# Pre-compute the set of field names each dataclass expects so that
# ``row_to_*`` can safely ignore any extra columns returned by ``SELECT *``
# (e.g. the ``paper`` table has a ``created_at`` column that is not part
# of the public ``Paper`` dataclass — see INTERFACE-CONTACT.md §4.2).
_PAPER_FIELDS: frozenset[str] = frozenset(Paper.__dataclass_fields__.keys())


def row_to_paper(row: sqlite3.Row) -> Paper:
    """Convert a ``sqlite3.Row`` from ``SELECT * FROM paper`` into a
    :class:`Paper` dataclass.

    Only columns that are declared as fields on the ``Paper`` dataclass
    are kept; extra columns from the database are silently dropped.
    """
    data = {k: row[k] for k in _PAPER_FIELDS if k in row.keys()}
    return Paper(**data)


def row_to_mistake(row: sqlite3.Row) -> Mistake:
    """Convert a ``sqlite3.Row`` from ``SELECT * FROM mistake`` into a
    :class:`Mistake` dataclass.
    """
    return Mistake(**dict(row))


def row_to_export_log(row: sqlite3.Row) -> ExportLog:
    """Convert a ``sqlite3.Row`` from ``SELECT * FROM export_log`` into an
    :class:`ExportLog` dataclass.

    The ``mistake_ids`` column is stored as a JSON string in the database;
    this helper transparently deserialises it back to ``list[int]``.
    """
    data = dict(row)
    try:
        data['mistake_ids'] = json.loads(data['mistake_ids'])
    except (json.JSONDecodeError, TypeError, KeyError):
        data['mistake_ids'] = []
    return ExportLog(**data)


# ---------------------------------------------------------------------------
# Dynamic WHERE clause builder
# ---------------------------------------------------------------------------

def build_where(conditions: dict[str, Optional[Any]]) -> tuple[str, list]:
    """Build a parameterised ``WHERE`` clause from *conditions*.

    Only entries whose value is **not** ``None`` are included in the
    output.  Values are bound via ``?`` placeholders to prevent SQL
    injection.

    Args:
        conditions:
            Mapping of ``{column_name: value_or_None}``.

    Returns:
        ``(where_clause_string, params_list)``.  The clause string is
        empty (``""``) when *conditions* is empty or all values are
        ``None``.

    Example::

        >>> build_where({'child_id': 'K1', 'status': None, 'subject': '数学'})
        (' WHERE child_id = ? AND subject = ?', ['K1', '数学'])
    """
    clauses: list[str] = []
    params: list[Any] = []
    for col, val in conditions.items():
        if val is not None:
            clauses.append(f"{col} = ?")
            params.append(val)
    if clauses:
        return " WHERE " + " AND ".join(clauses), params
    return "", []
