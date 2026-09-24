from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=True, row_factory=dict_row)


def reset(conn: psycopg.Connection) -> None:
    """Tests and local dev only: rebuild the schema from sql/schema.sql."""
    conn.execute("drop schema if exists public cascade; create schema public;")
    conn.execute(SCHEMA.read_text())


@contextmanager
def as_workspace(conn: psycopg.Connection, workspace_id: str) -> Iterator[psycopg.Connection]:
    """Every request runs here: one transaction, the application role, one workspace.

    Both settings are transaction-local, so a pooled connection can never carry
    one tenant's scope into the next request.
    """
    with conn.transaction():
        conn.execute("set local role app_user")
        conn.execute("select set_config('app.workspace_id', %s, true)", [str(workspace_id)])
        yield conn
