"""Database access for the ai module: the answer cache and the usage ledger."""

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.core.tenancy import TenantCtx


class AIRepository:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def cached_answer(self, key: str) -> dict | None:
        row = self.conn.execute("select answer from answer_cache where key = %s and expires_at > now()", [key]).fetchone()
        return row["answer"] if row else None

    def store_answer(self, ctx: TenantCtx, key: str, answer: dict, ttl_hours: int = 24) -> None:
        self.conn.execute(
            "insert into answer_cache (key, workspace_id, answer, expires_at) "
            "values (%s, %s, %s, now() + make_interval(hours => %s))",
            [key, ctx.workspace_id, Jsonb(answer), ttl_hours],
        )

    def record_usage(self, ctx: TenantCtx, feature: str, provider: str, model: str,
                     input_tokens: int, output_tokens: int, cache: str, credits: int) -> None:
        self.conn.execute(
            """insert into ai_ledger (workspace_id, feature, provider, model, input_tokens, output_tokens, cache, credits)
               values (%s, %s, %s, %s, %s, %s, %s, %s)""",
            [ctx.workspace_id, feature, provider, model, input_tokens, output_tokens, cache, credits],
        )

    def credits_spent(self, ctx: TenantCtx) -> int:
        row = self.conn.execute(
            "select coalesce(sum(credits), 0) as s from ai_ledger where workspace_id = %s", [ctx.workspace_id]
        ).fetchone()
        return int(row["s"])
