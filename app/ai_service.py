import hashlib
import re

from psycopg import Connection
from psycopg.types.json import Jsonb

from .answer import Verified, verify
from .providers import Completer
from .retrieve import Hit

PRICE = {"assistant.ask": 1, "lead.score": 0, "embed.record": 0}
ALLOWANCE = 200  # lives on the workspace plan in production


class OutOfCredits(Exception):
    pass


class AskResult(Verified):
    cache: str
    credits: int


def normalise(q: str) -> str:
    return re.sub(r"[?.!]+$", "", re.sub(r"\s+", " ", q.lower()).strip())


def ask(conn: Connection, ws: str, question: str, retrieved: list[Hit], completer: Completer) -> AskResult:
    """One door for every model call: meter, cache, route, refuse."""
    evidence = ",".join(sorted(h.record_id for h in retrieved))
    key = hashlib.sha256("|".join([ws, normalise(question), evidence, completer.model]).encode()).hexdigest()

    cached = conn.execute("select answer from answer_cache where key = %s and expires_at > now()", [key]).fetchone()
    if cached:
        ledger(conn, ws, "assistant.ask", completer.provider, completer.model, 0, 0, "hit", 0)
        return AskResult(**cached["answer"], cache="hit", credits=0)

    if credits(conn, ws) < PRICE["assistant.ask"]:
        raise OutOfCredits(ws)
    out = completer.complete(question, retrieved)
    verified = verify(out.raw, retrieved)
    conn.execute(
        "insert into answer_cache (key, workspace_id, answer, expires_at) values (%s, %s, %s, now() + interval '24 hours')",
        [key, ws, Jsonb(verified.model_dump())],
    )
    ledger(conn, ws, "assistant.ask", out.provider, out.model, out.input_tokens, out.output_tokens, "miss", PRICE["assistant.ask"])
    return AskResult(**verified.model_dump(), cache="miss", credits=PRICE["assistant.ask"])


def ledger(conn: Connection, ws: str, feature: str, provider: str, model: str,
           input_tokens: int, output_tokens: int, cache: str, spent: int) -> None:
    conn.execute(
        """insert into ai_ledger (workspace_id, feature, provider, model, input_tokens, output_tokens, cache, credits)
           values (%s, %s, %s, %s, %s, %s, %s, %s)""",
        [ws, feature, provider, model, input_tokens, output_tokens, cache, spent],
    )


def credits(conn: Connection, ws: str) -> int:
    spent = conn.execute("select coalesce(sum(credits), 0) as s from ai_ledger where workspace_id = %s", [ws]).fetchone()["s"]
    return ALLOWANCE - int(spent)
