"""Lead routes for the webapp."""

from fastapi import APIRouter

from app.core.dependencies import TenantDep
from app.modules.lead.dependencies import LeadScoringServiceDep
from app.modules.lead.schemas import ScoreOut

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/{lead_id}/score", response_model=ScoreOut)
def score(lead_id: str, ctx: TenantDep, scoring: LeadScoringServiceDep) -> ScoreOut:
    route, res = scoring.score(ctx, lead_id)
    intent = res.choices["intent"]
    return ScoreOut(owner=route.owner, priority=route.priority, fit=res.scores["fit"].score,
                    intent=intent.choice, confidence=intent.confidence, model=res.model)
