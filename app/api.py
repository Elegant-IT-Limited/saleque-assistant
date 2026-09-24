import hashlib
import hmac
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field
from typesafe_sdk import TypeSafeClient

from .ai_service import AskResult, OutOfCredits, ask
from .db import as_workspace
from .embed import Embedder
from .jev import score_lead
from .providers import Completer
from .retrieve import retrieve


@dataclass
class Services:
    conn: Connection
    embedder: Embedder
    completer: Completer
    jev: TypeSafeClient
    secret: bytes


def sign(ws: str, secret: bytes) -> str:
    return ws + "." + hmac.new(secret, ws.encode(), hashlib.sha256).hexdigest()


def services(request: Request) -> Services:
    return request.app.state.services


def current_workspace(svc: Annotated[Services, Depends(services)], authorization: Annotated[str, Header()] = "") -> str:
    """The workspace comes from the verified session token. Never from the body, never from a query string."""
    token = authorization.removeprefix("Bearer ").strip()
    ws, _, _ = token.partition(".")
    if not ws or not hmac.compare_digest(token, sign(ws, svc.secret)):
        raise HTTPException(401, "invalid session")
    return ws


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a smuggled workspace_id is a 422, not a silent override
    question: str = Field(min_length=3, max_length=500)


class ScoreOut(BaseModel):
    owner: str
    priority: str
    fit: float
    intent: str
    confidence: float
    model: str


def create_app(svc: Services) -> FastAPI:
    app = FastAPI(title="SaleQue AI service", version="0.8.0")
    app.state.services = svc
    Ws = Annotated[str, Depends(current_workspace)]
    Svc = Annotated[Services, Depends(services)]

    @app.post("/v1/assistant/ask", response_model=AskResult)
    def assistant_ask(body: AskIn, ws: Ws, s: Svc) -> AskResult:
        with as_workspace(s.conn, ws) as conn:
            hits = retrieve(conn, ws, body.question, s.embedder)
            try:
                return ask(conn, ws, body.question, hits, s.completer)
            except OutOfCredits:
                raise HTTPException(402, "workspace is out of AI credits") from None

    @app.post("/v1/leads/{lead_id}/score", response_model=ScoreOut)
    def lead_score(lead_id: str, ws: Ws, s: Svc) -> ScoreOut:
        with as_workspace(s.conn, ws) as conn:
            try:
                route, res = score_lead(conn, ws, lead_id, s.jev)
            except LookupError:
                raise HTTPException(404, "lead not found") from None
        intent = res.choices["intent"]
        return ScoreOut(owner=route.owner, priority=route.priority, fit=res.scores["fit"].score,
                        intent=intent.choice, confidence=intent.confidence, model=res.model)

    return app
