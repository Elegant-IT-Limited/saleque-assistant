"""Composition root: builds the FastAPI app and wires the real clients.

Run with `uvicorn app.main:create_app --factory`. Tests call create_app() with a
Container of recorded clients instead, so no test ever reaches a provider.
"""

import anthropic
import openai
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.dependencies import Container
from app.core.exceptions import register_exception_handlers
from app.core.routers import register_routers
from app.db.session import connect
from app.integrations.ai_provider import ClaudeCompleter, OpenAICompleter, WithFallback
from app.integrations.embeddings import OpenAIEmbedder
from app.integrations.typesafe import jev_client


def build_container(settings: Settings) -> Container:
    def secret(v) -> str:
        return v.get_secret_value() if v else ""

    oa = openai.OpenAI(api_key=secret(settings.openai_api_key))
    completer = WithFallback(
        ClaudeCompleter(anthropic.Anthropic(api_key=secret(settings.anthropic_api_key)), settings.claude_model),
        OpenAICompleter(oa, settings.openai_model),
    )
    return Container(
        conn=connect(settings.database_url),
        embedder=OpenAIEmbedder(oa, settings.embedding_model),
        completer=completer,
        jev=jev_client(settings),
        session_secret=settings.session_secret.get_secret_value().encode(),
    )


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="SaleQue AI service", version="0.9.0")
    app.state.container = container or build_container(get_settings())
    register_exception_handlers(app)
    register_routers(app)
    return app
