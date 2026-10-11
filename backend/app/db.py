"""Postgres access: one shared connection pool with pgvector registered."""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings


@lru_cache
def _pool() -> ConnectionPool:
    pool = ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=5,
        open=False,
        configure=register_vector,
        # prepare_threshold=None: safe behind Supabase's transaction pooler
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
    )
    pool.open(wait=True, timeout=30)
    return pool


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """Yield a pooled connection; commits on success, rolls back on error."""
    with _pool().connection() as conn:
        yield conn


def close_pool() -> None:
    if _pool.cache_info().currsize:
        _pool().close()
        _pool.cache_clear()


def as_floats(vector) -> list[float]:
    """pgvector columns come back as Vector (or ndarray, depending on version): normalise to a float list."""
    to_list = getattr(vector, "to_list", None)
    return to_list() if to_list else np.asarray(vector, dtype=float).tolist()
