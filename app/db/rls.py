"""Row Level Security for tenant tables, used by the migrations.

Kept in one function so every tenant table gets the identical policy. A table
added later with a hand-written, slightly different policy is the kind of drift
that only shows up in an incident review.
"""


def enable_tenant_rls(table: str) -> str:
    # FORCE applies the policy to the table owner too. Without it, anything that
    # runs as the owner (a migration, a one-off script) silently sees every tenant.
    return f"""
        alter table {table} enable row level security;
        alter table {table} force row level security;
        create policy {table}_ws on {table}
            using (workspace_id = current_setting('app.workspace_id', true)::uuid)
            with check (workspace_id = current_setting('app.workspace_id', true)::uuid);
    """
