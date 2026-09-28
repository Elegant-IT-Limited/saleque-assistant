"""Background task: drain the embedding outbox for one workspace.

Kept thin on purpose: the caller opens the tenant scope (as_workspace) and this
task hands over to the search service, so a test and any job runner share one
code path.
"""

from psycopg import Connection

from app.core.tenancy import TenantCtx
from app.integrations.embeddings import Embedder
from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService


def embed_pending(conn: Connection, ctx: TenantCtx, embedder: Embedder, batch: int = 100) -> int:
    """`conn` must already be inside as_workspace(ctx.workspace_id)."""
    return SearchService(SearchRepository(conn), embedder).embed_pending(ctx, batch)
