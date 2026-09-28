"""search: one embedding per record, the embedding outbox, and cleanup on delete

Revision ID: 0003_search
Revises: 0002_crm
Create Date: 2026-09-28
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0003_search"
down_revision = "0002_crm"
branch_labels = None
depends_on = None

RECORD_TABLES = {"lead": "leads", "account": "accounts", "deal": "deals", "task": "tasks", "activity": "activities"}


def upgrade() -> None:
    # one rendered document per record, embedded once per content change
    op.execute("""
        create table embeddings (
          id            bigserial primary key,
          workspace_id  uuid not null references workspaces(id) on delete cascade,
          record_type   text not null check (record_type in ('lead','account','deal','task','activity')),
          record_id     uuid not null,
          content       text not null,
          content_hash  bytea not null,
          model         text not null,
          embedding     vector(1536) not null,
          tsv           tsvector generated always as (to_tsvector('english', content)) stored,
          updated_at    timestamptz not null default now(),
          unique (workspace_id, record_type, record_id)
        )
    """)
    # HNSW for semantic search, GIN for full text, and a plain index on the tenant
    # column: for a small workspace the planner prefers filtering by workspace and
    # sorting exactly over walking the HNSW graph (see scripts/explain.py).
    op.execute("create index embeddings_hnsw on embeddings using hnsw (embedding vector_cosine_ops)")
    op.execute("create index embeddings_tsv on embeddings using gin (tsv)")
    op.execute("create index embeddings_ws on embeddings (workspace_id)")

    # A deleted record takes its embedding with it, in the same transaction. Doing
    # this in the app would leave a window where search can still cite a record
    # that no longer exists.
    op.execute("""
        create function drop_embedding() returns trigger language plpgsql as $$
        begin
          delete from embeddings where record_type = tg_argv[0] and record_id = old.id;
          return old;
        end $$
    """)
    for kind, table in RECORD_TABLES.items():
        op.execute(
            f"create trigger {table}_drop_embedding after delete on {table} "
            f"for each row execute function drop_embedding('{kind}')"
        )

    # The write transaction records the intent to embed; a worker does the slow part.
    op.execute("""
        create table embed_outbox (
          id           bigserial primary key,
          workspace_id uuid not null,
          record_type  text not null,
          record_id    uuid not null,
          enqueued_at  timestamptz not null default now(),
          processed_at timestamptz
        )
    """)

    for table in ("embeddings", "embed_outbox"):
        op.execute(enable_tenant_rls(table))


def downgrade() -> None:
    op.execute("drop table embed_outbox")
    for table in RECORD_TABLES.values():
        op.execute(f"drop trigger {table}_drop_embedding on {table}")
    op.execute("drop function drop_embedding()")
    op.execute("drop table embeddings")
