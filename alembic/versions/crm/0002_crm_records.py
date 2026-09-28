"""crm: the records the assistant reads (leads, accounts, deals, tasks, activities)

In the product each of these tables belongs to its own module (lead, account, deal,
task, activity). The reference build creates a minimal copy of each, with only the
columns the assistant renders, so the AI layer has real data to work against.

Revision ID: 0002_crm
Revises: 0001_core
Create Date: 2026-09-28
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0002_crm"
down_revision = "0001_core"
branch_labels = None
depends_on = None

TABLES = ["leads", "accounts", "deals", "tasks", "activities"]


def upgrade() -> None:
    # every record table carries workspace_id, and RLS is enforced on all of them
    op.execute("""
        create table leads (
          id           uuid primary key,
          workspace_id uuid not null references workspaces(id) on delete cascade,
          name         text not null,
          company      text,
          email        text,
          stage        text not null default 'new',
          notes        text,
          updated_at   timestamptz not null default now()
        )
    """)
    op.execute("""
        create table accounts (
          id           uuid primary key,
          workspace_id uuid not null references workspaces(id) on delete cascade,
          name         text not null,
          domain       text,
          plan         text,
          notes        text,
          updated_at   timestamptz not null default now()
        )
    """)
    op.execute("""
        create table deals (
          id           uuid primary key,
          workspace_id uuid not null references workspaces(id) on delete cascade,
          account_id   uuid,
          title        text not null,
          amount_cents bigint not null,
          stage        text not null,
          close_date   date,
          notes        text,
          updated_at   timestamptz not null default now()
        )
    """)
    op.execute("""
        create table tasks (
          id           uuid primary key,
          workspace_id uuid not null references workspaces(id) on delete cascade,
          title        text not null,
          due_date     date,
          status       text not null default 'open',
          assignee     text,
          related_deal uuid,
          updated_at   timestamptz not null default now()
        )
    """)
    op.execute("""
        create table activities (
          id           uuid primary key,
          workspace_id uuid not null references workspaces(id) on delete cascade,
          kind         text not null,
          subject      text not null,
          body         text not null,
          account_id   uuid,
          occurred_at  timestamptz not null default now(),
          updated_at   timestamptz not null default now()
        )
    """)
    for table in TABLES:
        op.execute(enable_tenant_rls(table))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"drop table {table}")
