"""Lead scoring: typed questions to Jev, and a routing rule anyone on the team can read.

A chat model can produce a number, but not a calibrated one, and the same lead can
score differently on a retry. Jev answers each question with a type (score, choice,
yes/no) and a confidence, so the routing below is plain Python, not prompt tuning.
"""

from typesafe_sdk import Choice, Noul, Score, SystemOneResponse

from app.core.exceptions import NotFound
from app.core.tenancy import TenantCtx
from app.modules.ai.service import AIService
from app.modules.lead.repository import LeadRepository
from app.modules.lead.schemas import Route

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

# Below this confidence on intent, a person decides. A lead parked in review costs
# a minute of someone's time; a real buyer archived as noise costs the deal. Tune
# this from what the review queue shows, not by feel.
AUTO = 0.80


def decide(res: SystemOneResponse) -> Route:
    intent, fit, budget = res.choices["intent"], res.scores["fit"], res.nouls["has_budget"]
    # the confidence gate comes first: an unsure "noise" must not archive a real lead
    if intent.confidence < AUTO:
        return Route("review", "normal")
    if intent.choice == "noise":
        return Route("archived", "normal")
    if intent.choice == "support":
        return Route("success", "normal")
    hot = fit.score >= 2.0 and (intent.choice == "buying" or budget.noul >= 0.7)
    return Route("sales", "high" if hot else "normal")


class LeadScoringService:
    def __init__(self, repo: LeadRepository, ai: AIService) -> None:
        self.repo, self.ai = repo, ai

    def score(self, ctx: TenantCtx, lead_id: str) -> tuple[Route, SystemOneResponse]:
        lead = self.repo.get(lead_id)
        if lead is None:
            raise NotFound()
        res = self.ai.decide(ctx, "lead.score",
                             state={"lead": lead, "ideal_customer": self.repo.workspace_icp(ctx)},
                             questions=LEAD_QUESTIONS)
        route = decide(res)
        intent = res.choices["intent"]
        self.repo.save_score(ctx, lead_id, res.model, res.scores["fit"].score, intent.choice, intent.confidence,
                             route, {k: a.model_dump() for k, a in res.answers.items()})
        return route, res
