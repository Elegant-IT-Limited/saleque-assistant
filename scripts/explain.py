"""EXPLAIN ANALYZE on the scoped search, plus the second wall, against a real PostgreSQL."""

import os
import re
import uuid

import psycopg

from app.db import as_workspace, connect, reset
from app.embed import to_vec
from tests.seed import B_IDS, WS_A, WS_B, embedder, seed

dim, bold = (lambda s: f"\x1b[2m{s}\x1b[0m"), (lambda s: f"\x1b[1m{s}\x1b[0m")
green, red, cyan = (lambda s: f"\x1b[32m{s}\x1b[0m"), (lambda s: f"\x1b[31m{s}\x1b[0m"), (lambda s: f"\x1b[36m{s}\x1b[0m")

conn = connect(os.environ["DATABASE_URL"])
reset(conn)
seed(conn)

# bulk: 1,500 extra records per workspace so the planner has something to choose between
for ws in (WS_A, WS_B):
    with as_workspace(conn, ws) as c, c.cursor() as cur:
        rows = []
        for i in range(1500):
            doc = (f"Activity {i}: {['call', 'email', 'meeting', 'note'][i % 4]} with contact {i} about "
                   f"{['pricing', 'renewal', 'onboarding', 'support', 'invoice'][i % 5]} on 2026-0{1 + i % 9}-1{i % 9}.")
            rows.append([ws, str(uuid.uuid4()), doc, doc, embedder.model, to_vec(embedder.embed(doc))])
        cur.executemany(
            """insert into embeddings (workspace_id, record_type, record_id, content, content_hash, model, embedding)
               values (%s, 'activity', %s, %s, sha256(convert_to(%s, 'UTF8')), %s, %s::vector)""", rows)
conn.execute("analyze embeddings")

q = to_vec(embedder.embed("What did we promise Northwind before the renewal call?"))
elide = lambda s: re.sub(r"'\[[-0-9.,e]+\]'::vector", "$question::vector", s)  # noqa: E731
n = conn.execute("select count(*) as n from embeddings").fetchone()["n"]

print(bold("1. scoped retrieval, EXPLAIN ANALYZE") + dim(f"  ({n:,} embeddings, 2 workspaces, HNSW on cosine)"))
with as_workspace(conn, WS_A) as c:
    plan = c.execute(f"""explain (analyze, costs off) select record_type, record_id from embeddings
                         where workspace_id = '{WS_A}' order by embedding <=> '{q}'::vector limit 8""").fetchall()
for r in plan:
    print("   " + elide(r["QUERY PLAN"]))
print(dim("   note: the One-Time Filter line is the RLS policy; for a 1.5k-row tenant the planner picks the workspace index and an exact top-N sort"))

print("\n" + bold("1b. same search across the whole table") + dim("  (large tenant or admin path: the planner switches to the HNSW index)"))
for r in conn.execute(f"explain (analyze, costs off) select record_type, record_id from embeddings order by embedding <=> '{q}'::vector limit 8").fetchall():
    print("   " + elide(r["QUERY PLAN"]))

print("\n" + bold("2. second wall") + dim("  (same table, NO workspace filter, running as app_user for workspace A)"))
with as_workspace(conn, WS_A) as c:
    rows = c.execute("select record_id::text from embeddings order by embedding <=> %s::vector limit 50", [q]).fetchall()
leaked = sum(r["record_id"] in B_IDS for r in rows)
print(f"   rows returned: {len(rows)}   from workspace B: {green('0') if leaked == 0 else red(str(leaked))}   "
      + dim("policy: workspace_id = current_setting('app.workspace_id')"))

print("\n" + bold("3. same query as the database owner") + dim("  (what the policy protects against)"))
for r in conn.execute("select workspace_id::text as ws, count(*) as n from embeddings group by 1 order by 1").fetchall():
    print(f"   {cyan(r['ws'][:8])}  {r['n']} embeddings")

print("\n" + bold("4. write with a foreign workspace_id, as app_user for A"))
try:
    with as_workspace(conn, WS_A) as c:
        c.execute("insert into tasks values (gen_random_uuid(), %s, 'smuggled', null, 'open', null, null)", [WS_B])
    print("   " + red("accepted (this must never print)"))
except psycopg.errors.InsufficientPrivilege as e:
    print("   " + green("rejected") + dim("  " + str(e).splitlines()[0]))
