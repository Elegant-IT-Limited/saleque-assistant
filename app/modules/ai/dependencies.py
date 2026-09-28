from typing import Annotated

from fastapi import Depends

from app.core.dependencies import ContainerDep, DbDep
from app.modules.ai.repository import AIRepository
from app.modules.ai.service import AIService


def get_ai_service(db: DbDep, container: ContainerDep) -> AIService:
    # the chat adapter and Jev both come from the container, so tests swap them in one place
    return AIService(AIRepository(db), container.completer, container.jev)


AIServiceDep = Annotated[AIService, Depends(get_ai_service)]
