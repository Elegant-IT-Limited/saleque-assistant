"""Connections and the per-request tenant scope.

Two walls stand between workspaces. Every query carries a workspace_id filter, and
underneath it Postgres Row Level Security refuses rows from any other workspace.
as_workspace() is what switches the second wall on.
"""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# autocommit on the raw connection; every unit of work opens its own transaction
# through as_workspace(), so nothing ever runs in an implicit one
CONNECTION_KWARGS = {"autocommit": True, "row_factory": dict_row}


class ConnectionSource(Protocol):
    """Anything that lends out a connection for one unit of work: a pool in production."""

    def connection(self) -> AbstractContextManager[psycopg.Connection]: ...


def connect(url: str) -> psycopg.Connection:
    """A single connection, for scripts and tests. The app itself always goes through a pool."""
    return psycopg.connect(url, **CONNECTION_KWARGS)


def create_pool(url: str, max_size: int = 10) -> ConnectionPool:
    # One connection per in-flight request. Sharing one connection across FastAPI's
    # worker threads would nest one request's transaction inside another's, and the
    # second request's workspace setting would apply to the first request's queries.
    return ConnectionPool(url, kwargs=CONNECTION_KWARGS, max_size=max_size, open=True)


@contextmanager
def as_workspace(conn: psycopg.Connection, workspace_id: str) -> Iterator[psycopg.Connection]:
    """Run the block in one transaction, as app_user, scoped to one workspace.

    Both settings are transaction-local (`set local`, and `true` as the third
    argument of set_config), so when the transaction ends they end with it. A pooled
    connection can never carry one tenant's scope into the next request.
    """
    with conn.transaction():
        # app_user has no BYPASSRLS, so from here the policies apply to every statement
        conn.execute("set local role app_user")
        conn.execute("select set_config('app.workspace_id', %s, true)", [str(workspace_id)])
        yield conn
