import hashlib

from psycopg import Connection, sql

from .embed import Embedder, to_vec
from .render import TABLE, RecordType, render_document


def _row(conn: Connection, kind: RecordType, record_id: str) -> dict | None:
    q = sql.SQL("select * from {} where id = %s").format(sql.Identifier(TABLE[kind]))
    return conn.execute(q, [record_id]).fetchone()


def enqueue_if_changed(conn: Connection, ws: str, kind: RecordType, record_id: str) -> bool:
    """Called inside the write transaction. Enqueues only when the rendered document changed."""
    row = _row(conn, kind, record_id)
    if row is None:
        return False
    digest = hashlib.sha256(render_document(kind, row).encode()).digest()
    prev = conn.execute(
        "select content_hash from embeddings where record_type = %s and record_id = %s", [kind, record_id]
    ).fetchone()
    if prev and bytes(prev["content_hash"]) == digest:
        return False
    conn.execute(
        "insert into embed_outbox (workspace_id, record_type, record_id) values (%s, %s, %s)", [ws, kind, record_id]
    )
    return True


def drain_outbox(conn: Connection, ws: str, embedder: Embedder, batch: int = 100) -> int:
    """Worker: claim pending rows (safe with many workers), embed, upsert, mark done."""
    pending = conn.execute(
        """select id, record_type, record_id from embed_outbox
            where processed_at is null order by id limit %s for update skip locked""",
        [batch],
    ).fetchall()
    for p in pending:
        row = _row(conn, p["record_type"], p["record_id"])
        if row is not None:
            doc = render_document(p["record_type"], row)
            conn.execute(
                """insert into embeddings (workspace_id, record_type, record_id, content, content_hash, model, embedding)
                   values (%s, %s, %s, %s, %s, %s, %s::vector)
                   on conflict (workspace_id, record_type, record_id) do update
                      set content = excluded.content, content_hash = excluded.content_hash,
                          model = excluded.model, embedding = excluded.embedding, updated_at = now()""",
                [ws, p["record_type"], p["record_id"], doc, hashlib.sha256(doc.encode()).digest(),
                 embedder.model, to_vec(embedder.embed(doc))],
            )
        conn.execute("update embed_outbox set processed_at = now() where id = %s", [p["id"]])
    return len(pending)
