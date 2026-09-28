from collections.abc import Iterator
from contextlib import contextmanager

import psycopg


class SingleConnection:
    """A ConnectionSource over one connection.

    Only for tests: TestClient sends one request at a time, so lending the same
    connection to each request is safe here. The app uses a real pool.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        yield self.conn
