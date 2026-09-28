import os

import pytest

from app.db.migrate import reset
from app.db.session import connect
from tests.support.seed import seed

PG_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")


@pytest.fixture(scope="module")
def db():
    """Fresh schema from the migrations, and seed data, per test module.

    Real PostgreSQL with pgvector, not a mock: the tests that matter most here are
    about RLS, indexes and triggers, and none of those exist in a fake.
    """
    reset(PG_URL)
    conn = connect(PG_URL)
    seed(conn)
    yield conn
    conn.close()
