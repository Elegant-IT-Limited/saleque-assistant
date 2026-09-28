"""ai: the ledger of every model call, and the answer cache

Revision ID: 0004_ai
Revises: 0003_search
Create Date: 2026-09-28
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0004_ai"
down_revision = "0003_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Every model call, priced and attributed to a workspace and a feature. Credit
    # balances are computed from this table, so it is append-only by convention.
    op.execute("""
        create table ai_ledger (
          id            bigserial primary key,
          workspace_id  uuid not null references workspaces(id) on delete cascade,
          feature       text not null,
          provider      text not null,
          model         text not null,
          input_tokens  int  not null default 0,
          output_tokens int  not null default 0,
          cache         text not null check (cache in ('hit','miss','bypass')),
          credits       int  not null,
          created_at    timestamptz not null default now()
        )
    """)
    op.execute("""
        create table answer_cache (
          key          text primary key,   -- sha256 hex, see AIService.ask
          workspace_id uuid not null,
          answer       jsonb not null,
          expires_at   timestamptz not null
        )
    """)
    for table in ("ai_ledger", "answer_cache"):
        op.execute(enable_tenant_rls(table))


def downgrade() -> None:
    op.execute("drop table answer_cache")
    op.execute("drop table ai_ledger")
