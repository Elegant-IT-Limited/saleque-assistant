from typing import Annotated

from fastapi import Depends

from app.core.dependencies import DbDep
from app.modules.ai.dependencies import AIServiceDep
from app.modules.lead.repository import LeadRepository
from app.modules.lead.service import LeadScoringService


def get_lead_scoring_service(db: DbDep, ai: AIServiceDep) -> LeadScoringService:
    return LeadScoringService(LeadRepository(db), ai)


LeadScoringServiceDep = Annotated[LeadScoringService, Depends(get_lead_scoring_service)]
