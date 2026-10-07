"""Postgres connection helper with pgvector registered."""
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector

from app.config import get_settings


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(get_settings().database_url)
    try:
        register_vector(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
