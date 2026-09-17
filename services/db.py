"""Small PostgreSQL connection helper shared by the independent services."""

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


def database_url() -> str:
    """Return the configured URL, with an explicit development-only default."""
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured

    environment = os.getenv("ENVIRONMENT", os.getenv("NODE_ENV", "development")).lower()
    if environment in {"production", "prod"}:
        raise RuntimeError("DATABASE_URL is required when ENVIRONMENT=production")

    # This is a PostgreSQL server default for local development, never a file DB.
    return "postgresql://postgres:postgres@localhost:5432/gart_gallery"


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """Open one transaction and commit it only when the service operation succeeds."""
    with psycopg.connect(database_url(), row_factory=dict_row) as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
