"""Provider adapters. The AI service is the only caller; nothing else in the product talks to a model."""

import json
from dataclasses import dataclass
from typing import Protocol

import anthropic
import openai

from .answer import Answer
from .retrieve import Hit

SYSTEM = (
    "You answer questions about one CRM workspace using only the records provided. "
    "Every sentence must list the record ids it relies on in `sources`. "
    "If the records do not answer the question, return no sentences. "
    "Propose at most 3 actions, each backed by a record id."
)
ANSWER_SCHEMA = Answer.model_json_schema()


@dataclass(frozen=True)
class Completion:
    raw: object
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


class Completer(Protocol):
    provider: str
    model: str

    def complete(self, question: str, records: list[Hit]) -> Completion: ...


def user_prompt(question: str, records: list[Hit]) -> str:
    lines = [f"<record id=\"{r.record_id}\" type=\"{r.record_type}\">{r.content}</record>" for r in records]
    return "<records>\n" + "\n".join(lines) + f"\n</records>\n\nQuestion: {question}"


class ClaudeCompleter:
    """Claude with a forced tool call, so the reply is schema-shaped JSON, never prose."""

    provider = "anthropic"

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-5") -> None:
        self.client, self.model = client, model

    def complete(self, question: str, records: list[Hit]) -> Completion:
        msg = self.client.messages.create(
            model=self.model, max_tokens=1024, system=SYSTEM,
            tools=[{"name": "answer", "description": "Return the cited answer.", "input_schema": ANSWER_SCHEMA}],
            tool_choice={"type": "tool", "name": "answer"},
            messages=[{"role": "user", "content": user_prompt(question, records)}],
        )
        raw = next(b.input for b in msg.content if b.type == "tool_use")
        return Completion(raw, self.provider, msg.model, msg.usage.input_tokens, msg.usage.output_tokens)


class OpenAICompleter:
    """OpenAI with a JSON schema response format. Same contract, same verifier downstream."""

    provider = "openai"

    def __init__(self, client: openai.OpenAI, model: str = "gpt-5-mini") -> None:
        self.client, self.model = client, model

    def complete(self, question: str, records: list[Hit]) -> Completion:
        r = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt(question, records)}],
            response_format={"type": "json_schema", "json_schema": {"name": "answer", "schema": ANSWER_SCHEMA}},
        )
        raw = json.loads(r.choices[0].message.content or "{}")
        return Completion(raw, self.provider, r.model, r.usage.prompt_tokens, r.usage.completion_tokens)


class WithFallback:
    """Primary first. On a provider outage, rate limit or timeout, the fallback answers instead."""

    def __init__(self, primary: Completer, fallback: Completer) -> None:
        self.primary, self.fallback = primary, fallback
        self.provider, self.model = primary.provider, primary.model

    def complete(self, question: str, records: list[Hit]) -> Completion:
        try:
            return self.primary.complete(question, records)
        except (anthropic.APIStatusError, anthropic.APIConnectionError, openai.APIStatusError, openai.APIConnectionError):
            return self.fallback.complete(question, records)
