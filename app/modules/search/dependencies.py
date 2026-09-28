from typing import Annotated

from fastapi import Depends

from app.core.dependencies import ContainerDep, DbDep
from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService


def get_search_service(db: DbDep, container: ContainerDep) -> SearchService:
    # built per request on the request's own connection, so it shares that transaction and tenant scope
    return SearchService(SearchRepository(db), container.embedder)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
