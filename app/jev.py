"""Decisions go to Jev, a System One model: typed answers with calibrated confidence, no prose to parse.

Language (answers with citations) goes to Claude or OpenAI. Decisions (score, route, escalate) go here.
"""

from dataclasses import dataclass

from psycopg import Connection
from psycopg.types.json import Jsonb
from typesafe_sdk import Choice, Noul, Score, SystemOneResponse, TypeSafeClient

from .ai_service import PRICE, ledger

LEAD_QUESTIONS = {
    "fit": Score(
        instructions="How well does this lead match the workspace's ideal customer profile?",
        criteria=["No match", "Weak match", "Good match", "Strong match"],
    ),
    "intent": Choice(
        instructions="What does the lead want right now?",
        criteria={
            "buying": "Asks for pricing, a proposal or a start date",
            "evaluating": "Comparing options, no timeline yet",
            "support": "Existing customer with a problem",
            "noise": "Spam, recruiting or unrelated",
        },
    ),
    "has_budget": Noul(instructions="The lead mentions a budget, funding or an approved spend"),
}

AUTO = 0.80  # below this confidence, a person decides


@dataclass(frozen=True)
class Route:
    owner: str  # sales | success | review | archived
    priority: str  # high | normal


def decide(res: SystemOneResponse) -> Route:
    intent, fit, budget = res.choices["intent"], res.scores["fit"], res.nouls["has_budget"]
    if intent.confidence < AUTO:
        return Route("review", "normal")
    if intent.choice == "noise":
        return Route("archived", "normal")
    if intent.choice == "support":
        return Route("success", "normal")
    hot = fit.score >= 2.0 and (intent.choice == "buying" or budget.noul >= 0.7)
    return Route("sales", "high" if hot else "normal")


def score_lead(conn: Connection, ws: str, lead_id: str, jev: TypeSafeClient) -> tuple[Route, SystemOneResponse]:
    lead = conn.execute("select name, company, email, stage, notes from leads where id = %s", [lead_id]).fetchone()
    if lead is None:
        raise LookupError(lead_id)
    icp = conn.execute("select icp from workspaces where id = %s", [ws]).fetchone()
    res = jev.system_one(state={"lead": lead, "ideal_customer": icp["icp"] if icp else None}, questions=LEAD_QUESTIONS)
    route = decide(res)
    conn.execute(
        """insert into lead_scores (lead_id, workspace_id, model, fit, intent, confidence, owner, priority, answers)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (lead_id) do update set model = excluded.model, fit = excluded.fit, intent = excluded.intent,
             confidence = excluded.confidence, owner = excluded.owner, priority = excluded.priority,
             answers = excluded.answers, scored_at = now()""",
        [lead_id, ws, res.model, res.scores["fit"].score, res.choices["intent"].choice,
         res.choices["intent"].confidence, route.owner, route.priority,
         Jsonb({k: a.model_dump() for k, a in res.answers.items()})],
    )
    ledger(conn, ws, "lead.score", "typesafe", res.model,
           res.usage.input_tokens or 0, res.usage.output_tokens or 0, "bypass", PRICE["lead.score"])
    return route, res
