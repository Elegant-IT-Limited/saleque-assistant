from dataclasses import dataclass

from psycopg import Connection

from .embed import Embedder, to_vec


@dataclass(frozen=True)
class Hit:
    record_type: str
    record_id: str
    content: str
    score: float


# Vector search and full text search in one round trip, fused with reciprocal rank fusion (k = 60).
# The workspace filter is the first wall. RLS underneath makes it redundant on purpose.
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


def retrieve(conn: Connection, ws: str, question: str, embedder: Embedder, k: int = 8) -> list[Hit]:
    rows = conn.execute(HYBRID, {"vec": to_vec(embedder.embed(question)), "text": question, "ws": ws, "k": k}).fetchall()
    return [Hit(**r) for r in rows]
