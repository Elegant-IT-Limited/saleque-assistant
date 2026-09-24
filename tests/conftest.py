import os

import pytest

from app.db import connect, reset
from tests.seed import seed

PG_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")


@pytest.fixture(scope="session")
def conn():
    c = connect(PG_URL)
    yield c
    c.close()


@pytest.fixture(scope="module")
def db(conn):
    """Fresh schema and seed data per test module, on a real PostgreSQL with pgvector."""
    reset(conn)
    seed(conn)
    return conn
