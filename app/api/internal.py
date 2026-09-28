"""Internal API: the routes the SaleQue webapp calls, authenticated by session token."""

from fastapi import APIRouter

from app.modules.ai.api.internal import router as ai_router
from app.modules.lead.api.internal import router as lead_router

router = APIRouter(prefix="/api/internal")
router.include_router(ai_router)
router.include_router(lead_router)
