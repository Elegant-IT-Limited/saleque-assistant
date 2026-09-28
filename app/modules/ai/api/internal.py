"""Assistant routes for the webapp. Thin by design: validate, call services, return."""

from fastapi import APIRouter

from app.core.dependencies import TenantDep
from app.modules.ai.dependencies import AIServiceDep
from app.modules.ai.schemas import AskIn, AskResult
from app.modules.search.dependencies import SearchServiceDep

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask", response_model=AskResult)
def ask(body: AskIn, ctx: TenantDep, search: SearchServiceDep, ai: AIServiceDep) -> AskResult:
    # both services share the request's transaction, already scoped to ctx
    return ai.ask(ctx, body.question, search.retrieve(ctx, body.question))
