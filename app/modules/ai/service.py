"""The single entry point for every model call in the product.

Language (answers with citations) goes to Claude, with OpenAI as the fallback.
Decisions (score, route, escalate) go to Jev. Either way the call passes through
here, so it is metered, cached where that is safe, and refused when the workspace
has no credits left. No other module talks to a provider.
"""

import hashlib
import re

from typesafe_sdk import SystemOneResponse, TypeSafeClient

from app.core.exceptions import OutOfCredits
from app.core.tenancy import TenantCtx
from app.integrations.ai_provider import Completer, StructuredPrompt
from app.modules.ai.repository import AIRepository
from app.modules.ai.schemas import Answer, AskResult, CitedSentence, Verified
from app.modules.search.schemas import Hit

PRICE = {"assistant.ask": 1, "lead.score": 0}  # credits per call
ALLOWANCE = 200  # per workspace; lives on the subscription plan in the product

SYSTEM = (
    "You answer questions about one CRM workspace using only the records provided. "
    "Every sentence must list the record ids it relies on in `sources`. "
    "If the records do not answer the question, return no sentences. "
    "Propose at most 3 actions, each backed by a record id."
)
ANSWER_SCHEMA = Answer.model_json_schema()


def build_prompt(question: str, records: list[Hit]) -> StructuredPrompt:
    # Records go in as tagged blocks with their ids, so the model can cite them and
    # the verifier can check every citation against this exact list.
    lines = [f"<record id=\"{r.record_id}\" type=\"{r.record_type}\">{r.content}</record>" for r in records]
    user = "<records>\n" + "\n".join(lines) + f"\n</records>\n\nQuestion: {question}"
    return StructuredPrompt(SYSTEM, user, "answer", ANSWER_SCHEMA)


def normalise(question: str) -> str:
    """Case, spacing and trailing punctuation do not make a new question."""
    return re.sub(r"[?.!]+$", "", re.sub(r"\s+", " ", question.lower()).strip())


def verify(raw: object, retrieved: list[Hit]) -> Verified:
    """Every cited id must be in the retrieved set. A sentence with no valid source is dropped.

    This is the last word on what the user sees. A model can cite an id it invented
    or one from a different question; neither survives this step. Citation numbers
    follow first use, so the UI renders [1] [2] in reading order.
    """
    parsed = Answer.model_validate(raw)  # off-schema output raises here, before anything renders
    allowed = {h.record_id: h for h in retrieved}
    order: list[str] = []

    def num(record_id: str) -> int:
        if record_id not in order:
            order.append(record_id)
        return order.index(record_id) + 1

    kept, dropped = [], []
    for s in parsed.sentences:
        ok = [i for i in s.sources if i in allowed]
        if ok:
            kept.append(CitedSentence(text=s.text, sources=[num(i) for i in ok]))
        else:
            dropped.append(s.text)
    # an action is all or nothing: one unknown source and the action goes
    actions = [a for a in parsed.actions if a.sources and all(i in allowed for i in a.sources)]
    return Verified(sentences=kept, dropped=dropped, actions=actions,
                    citations=[allowed[i] for i in order], not_found=not kept)


class AIService:
    def __init__(self, repo: AIRepository, completer: Completer, jev: TypeSafeClient | None = None) -> None:
        self.repo, self.completer, self.jev = repo, completer, jev

    def ask(self, ctx: TenantCtx, question: str, retrieved: list[Hit]) -> AskResult:
        """Meter, cache, route, refuse."""
        # The cache key includes the exact evidence. Same question, same records:
        # the stored answer is still true. Same question after a record changed:
        # different ids or content, so a new key and a fresh answer.
        evidence = ",".join(sorted(h.record_id for h in retrieved))
        key = hashlib.sha256("|".join([ctx.workspace_id, normalise(question), evidence, self.completer.model]).encode()).hexdigest()

        cached = self.repo.cached_answer(key)
        if cached:
            self.repo.record_usage(ctx, "assistant.ask", self.completer.provider, self.completer.model, 0, 0, "hit", 0)
            return AskResult(**cached, cache="hit", credits=0)

        # refuse before the provider is called, not after the tokens are spent
        if self.credits(ctx) < PRICE["assistant.ask"]:
            raise OutOfCredits()
        out = self.completer.complete(build_prompt(question, retrieved))
        verified = verify(out.raw, retrieved)
        self.repo.store_answer(ctx, key, verified.model_dump())
        self.repo.record_usage(ctx, "assistant.ask", out.provider, out.model,
                               out.input_tokens, out.output_tokens, "miss", PRICE["assistant.ask"])
        return AskResult(**verified.model_dump(), cache="miss", credits=PRICE["assistant.ask"])

    def decide(self, ctx: TenantCtx, feature: str, state: dict, questions: dict) -> SystemOneResponse:
        """Typed questions to Jev. Decisions are never cached: the state changes too often to trust a stale one."""
        if self.jev is None:
            raise RuntimeError("AIService was built without a Jev client")
        res = self.jev.system_one(state=state, questions=questions)
        self.repo.record_usage(ctx, feature, "typesafe", res.model,
                               res.usage.input_tokens or 0, res.usage.output_tokens or 0, "bypass", PRICE[feature])
        return res

    def credits(self, ctx: TenantCtx) -> int:
        return ALLOWANCE - self.repo.credits_spent(ctx)
