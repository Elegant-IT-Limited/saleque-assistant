"""Connections and the per-request tenant scope.

Two walls stand between workspaces. Every query carries a workspace_id filter, and
underneath it Postgres Row Level Security refuses rows from any other workspace.
as_workspace() is what switches the second wall on.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


def connect(url: str) -> psycopg.Connection:
    # autocommit on the raw connection; every unit of work opens its own
    # transaction through as_workspace() so nothing runs in an implicit one.
    return psycopg.connect(url, autocommit=True, row_factory=dict_row)


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
