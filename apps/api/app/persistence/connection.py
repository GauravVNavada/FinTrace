from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


@contextmanager
def connection(database_url: str) -> Iterator[Any]:
    """Open one bounded transaction and roll it back if the caller fails."""
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def check_connection(database_url: str) -> bool:
    try:
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False
