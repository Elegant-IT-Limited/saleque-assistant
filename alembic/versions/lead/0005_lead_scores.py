"""lead: Jev decisions on a lead (typed answers, confidence, the route taken)

Revision ID: 0005_lead
Revises: 0004_ai
Create Date: 2026-09-28
"""

from alembic import op

from app.db.rls import enable_tenant_rls

revision = "0005_lead"
down_revision = "0004_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One row per lead, overwritten on rescore. `answers` keeps the full typed
    # response so a disputed route can be explained later without calling Jev again.
    op.execute("""
        create table lead_scores (
          lead_id      uuid primary key references leads(id) on delete cascade,
          workspace_id uuid not null references workspaces(id) on delete cascade,
          model        text not null,
          fit          real not null,
          intent       text not null,
          confidence   real not null,
          owner        text not null,
          priority     text not null,
          answers      jsonb not null,
          scored_at    timestamptz not null default now()
        )
    """)
    op.execute(enable_tenant_rls("lead_scores"))


def downgrade() -> None:
    op.execute("drop table lead_scores")
