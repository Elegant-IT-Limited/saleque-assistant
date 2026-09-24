create extension if not exists vector;

create table workspaces (
  id    uuid primary key,
  name  text not null,
  icp   text            -- ideal customer profile, read by lead scoring
);

-- every record table carries workspace_id; RLS is enforced on all of them
create table leads     (id uuid primary key, workspace_id uuid not null references workspaces(id) on delete cascade, name text not null, company text, email text, stage text not null default 'new', notes text, updated_at timestamptz not null default now());
create table accounts  (id uuid primary key, workspace_id uuid not null references workspaces(id) on delete cascade, name text not null, domain text, plan text, notes text, updated_at timestamptz not null default now());
create table deals     (id uuid primary key, workspace_id uuid not null references workspaces(id) on delete cascade, account_id uuid, title text not null, amount_cents bigint not null, stage text not null, close_date date, notes text, updated_at timestamptz not null default now());
create table tasks     (id uuid primary key, workspace_id uuid not null references workspaces(id) on delete cascade, title text not null, due_date date, status text not null default 'open', assignee text, related_deal uuid, updated_at timestamptz not null default now());
create table activities(id uuid primary key, workspace_id uuid not null references workspaces(id) on delete cascade, kind text not null, subject text not null, body text not null, account_id uuid, occurred_at timestamptz not null default now(), updated_at timestamptz not null default now());

-- one rendered document per record, embedded once per content change
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
);
create index embeddings_hnsw on embeddings using hnsw (embedding vector_cosine_ops);
create index embeddings_tsv  on embeddings using gin (tsv);
create index embeddings_ws   on embeddings (workspace_id);

-- a deleted record takes its embedding with it, in the same transaction
create function drop_embedding() returns trigger language plpgsql as $$
begin
  delete from embeddings where record_type = tg_argv[0] and record_id = old.id;
  return old;
end $$;
create trigger leads_drop_embedding      after delete on leads      for each row execute function drop_embedding('lead');
create trigger accounts_drop_embedding   after delete on accounts   for each row execute function drop_embedding('account');
create trigger deals_drop_embedding      after delete on deals      for each row execute function drop_embedding('deal');
create trigger tasks_drop_embedding      after delete on tasks      for each row execute function drop_embedding('task');
create trigger activities_drop_embedding after delete on activities for each row execute function drop_embedding('activity');

-- outbox: the write transaction records intent, a worker does the embedding
create table embed_outbox (
  id           bigserial primary key,
  workspace_id uuid not null,
  record_type  text not null,
  record_id    uuid not null,
  enqueued_at  timestamptz not null default now(),
  processed_at timestamptz
);

-- Jev decisions on a lead: typed answers, calibrated confidence, the route taken
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
);

-- every model call, priced and attributed
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
);
create table answer_cache (
  key          text primary key,   -- sha256 hex
  workspace_id uuid not null,
  answer       jsonb not null,
  expires_at   timestamptz not null
);

-- second wall: the database enforces the tenant even when a query forgets the filter
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'app_user') then create role app_user nologin; end if;
end $$;
grant usage on schema public to app_user;
grant select, insert, update, delete on all tables in schema public to app_user;
grant usage, select on all sequences in schema public to app_user;

do $$ declare t text; begin
  foreach t in array array['leads','accounts','deals','tasks','activities','embeddings','embed_outbox','lead_scores','ai_ledger','answer_cache'] loop
    execute format('alter table %I enable row level security', t);
    execute format('alter table %I force row level security', t);
    execute format('create policy %I_ws on %I using (workspace_id = current_setting(''app.workspace_id'', true)::uuid) with check (workspace_id = current_setting(''app.workspace_id'', true)::uuid)', t, t);
  end loop;
end $$;
