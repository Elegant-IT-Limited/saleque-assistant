"""Database access for search: embeddings, the outbox, and the hybrid query. No business rules here."""

from psycopg import Connection, sql

from app.core.tenancy import TenantCtx
from app.modules.search.schemas import RECORD_TABLES, Hit, RecordType

# Vector search and full text search in one round trip, fused with reciprocal rank
# fusion (k = 60). The workspace filter is the first wall. RLS underneath makes it
# redundant on purpose.
HYBRID = """
with q as (select %(vec)s::vector as v, plainto_tsquery('english', %(text)s) as t),
vec as (
  select record_type, record_id, content, row_number() over (order by embedding <=> q.v) as r
    from embeddings, q where workspace_id = %(ws)s
   order by embedding <=> q.v limit 16),
fts as (
  select record_type, record_id, content, row_number() over (order by ts_rank(tsv, q.t) desc) as r
    from embeddings, q where workspace_id = %(ws)s and tsv @@ q.t
   order by ts_rank(tsv, q.t) desc limit 16)
select record_type, record_id::text, content, round(sum(1.0 / (60 + r))::numeric, 4)::float as score
  from (select * from vec union all select * from fts) both_lists
 group by record_type, record_id, content
 order by score desc, record_id
 limit %(k)s
"""


class SearchRepository:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def hybrid(self, ctx: TenantCtx, vec: str, text: str, k: int) -> list[Hit]:
        rows = self.conn.execute(HYBRID, {"vec": vec, "text": text, "ws": ctx.workspace_id, "k": k}).fetchall()
        return [Hit(**r) for r in rows]

    def record(self, kind: RecordType, record_id: str) -> dict | None:
        # table names cannot be bound parameters; Identifier quotes them safely
        q = sql.SQL("select * from {} where id = %s").format(sql.Identifier(RECORD_TABLES[kind]))
        return self.conn.execute(q, [record_id]).fetchone()

    def stored_hash(self, kind: RecordType, record_id: str) -> bytes | None:
        row = self.conn.execute(
            "select content_hash from embeddings where record_type = %s and record_id = %s", [kind, record_id]
        ).fetchone()
        return bytes(row["content_hash"]) if row else None

    def enqueue(self, ctx: TenantCtx, kind: RecordType, record_id: str) -> None:
        self.conn.execute(
            "insert into embed_outbox (workspace_id, record_type, record_id) values (%s, %s, %s)",
            [ctx.workspace_id, kind, record_id],
        )

    def claim_pending(self, batch: int) -> list[dict]:
        # SKIP LOCKED lets several workers drain the same outbox without ever
        # picking the same row, and without waiting on each other's locks.
        return self.conn.execute(
            """select id, record_type, record_id from embed_outbox
                where processed_at is null order by id limit %s for update skip locked""",
            [batch],
        ).fetchall()

    def upsert_embedding(self, ctx: TenantCtx, kind: str, record_id: str, content: str,
                         digest: bytes, model: str, vec: str) -> None:
        self.conn.execute(
            """insert into embeddings (workspace_id, record_type, record_id, content, content_hash, model, embedding)
               values (%s, %s, %s, %s, %s, %s, %s::vector)
               on conflict (workspace_id, record_type, record_id) do update
                  set content = excluded.content, content_hash = excluded.content_hash,
                      model = excluded.model, embedding = excluded.embedding, updated_at = now()""",
            [ctx.workspace_id, kind, record_id, content, digest, model, vec],
        )

    def mark_processed(self, outbox_id: int) -> None:
        self.conn.execute("update embed_outbox set processed_at = now() where id = %s", [outbox_id])
