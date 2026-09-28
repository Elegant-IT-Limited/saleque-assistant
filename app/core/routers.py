"""The one place routers are mounted.

Each API surface aggregates its module routers (app/api/internal.py today; backoffice
and a public v1 later). Adding a surface is one line here, adding a module route is
one line in the surface file.
"""

from fastapi import FastAPI

from app.api.internal import router as internal_router


def register_routers(app: FastAPI) -> None:
    app.include_router(internal_router)
