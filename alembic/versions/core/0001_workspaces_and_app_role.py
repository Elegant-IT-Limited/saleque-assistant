"""core: pgvector, workspaces, and the role the application runs as

Revision ID: 0001_core
Revises:
Create Date: 2026-09-28
"""

from alembic import op

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("create extension if not exists vector")

    op.execute("""
        create table workspaces (
          id    uuid primary key,
          name  text not null,
          icp   text            -- ideal customer profile, read by lead scoring
        )
    """)

    # The application never connects as the table owner. It switches to app_user
    # inside each request (app/db/session.py), and app_user cannot bypass RLS.
    # Roles are cluster-wide, so this survives a schema reset; guard the create.
    op.execute("""
        do $$ begin
          if not exists (select 1 from pg_roles where rolname = 'app_user') then
            create role app_user nologin;
          end if;
        end $$
    """)
    op.execute("grant usage on schema public to app_user")
    op.execute("grant select, insert, update, delete on workspaces to app_user")
    # Tables and sequences created by later migrations get the same grants
    # automatically, so no module migration can forget them.
    op.execute("alter default privileges in schema public grant select, insert, update, delete on tables to app_user")
    op.execute("alter default privileges in schema public grant usage, select on sequences to app_user")


def downgrade() -> None:
    op.execute("alter default privileges in schema public revoke usage, select on sequences from app_user")
    op.execute("alter default privileges in schema public revoke select, insert, update, delete on tables from app_user")
    op.execute("drop table workspaces")
    # app_user and the vector extension are left in place: other databases on the
    # same cluster may depend on them.
