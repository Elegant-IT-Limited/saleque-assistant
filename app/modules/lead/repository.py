"""Database access for lead scoring."""

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.core.tenancy import TenantCtx
from app.modules.lead.schemas import Route


class LeadRepository:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def get(self, lead_id: str) -> dict | None:
        # no workspace filter needed for correctness: RLS returns nothing for a lead
        # in another workspace, and the service turns that into a 404
        return self.conn.execute("select name, company, email, stage, notes from leads where id = %s", [lead_id]).fetchone()

    def workspace_icp(self, ctx: TenantCtx) -> str | None:
        row = self.conn.execute("select icp from workspaces where id = %s", [ctx.workspace_id]).fetchone()
        return row["icp"] if row else None

    def save_score(self, ctx: TenantCtx, lead_id: str, model: str, fit: float, intent: str,
                   confidence: float, route: Route, answers: dict) -> None:
        self.conn.execute(
            """insert into lead_scores (lead_id, workspace_id, model, fit, intent, confidence, owner, priority, answers)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               on conflict (lead_id) do update set model = excluded.model, fit = excluded.fit, intent = excluded.intent,
                 confidence = excluded.confidence, owner = excluded.owner, priority = excluded.priority,
                 answers = excluded.answers, scored_at = now()""",
            [lead_id, ctx.workspace_id, model, fit, intent, confidence, route.owner, route.priority, Jsonb(answers)],
        )
