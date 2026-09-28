"""FastAPI dependency providers shared by every module.

The Container holds the long-lived clients (connection pool, embedder, model
adapters). main.py builds it from settings in production; tests build it by hand
with recorded clients, and nothing else in the app needs to know the difference.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from psycopg import Connection
from typesafe_sdk import TypeSafeClient

from app.core.security import verify_session
from app.core.tenancy import TenantCtx
from app.db.session import ConnectionSource, as_workspace
from app.integrations.ai_provider import Completer
from app.integrations.embeddings import Embedder


@dataclass
class Container:
    db: ConnectionSource
    embedder: Embedder
    completer: Completer
    jev: TypeSafeClient
    session_secret: bytes


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_current_tenant(
    container: Annotated[Container, Depends(get_container)],
    authorization: Annotated[str, Header()] = "",
) -> TenantCtx:
    workspace_id = verify_session(authorization.removeprefix("Bearer ").strip(), container.session_secret)
    if workspace_id is None:
        raise HTTPException(401, "invalid session")
    return TenantCtx(workspace_id)


def get_db(
    container: Annotated[Container, Depends(get_container)],
    ctx: Annotated[TenantCtx, Depends(get_current_tenant)],
) -> Iterator[Connection]:
    """A connection of its own for this request, in one transaction, scoped to the caller's workspace."""
    with container.db.connection() as conn, as_workspace(conn, ctx.workspace_id) as scoped:
        yield scoped


ContainerDep = Annotated[Container, Depends(get_container)]
TenantDep = Annotated[TenantCtx, Depends(get_current_tenant)]
DbDep = Annotated[Connection, Depends(get_db)]
