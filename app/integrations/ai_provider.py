"""Chat model adapters: Claude and OpenAI behind one interface.

Adapters know how to talk to a provider and nothing about CRM data. The ai module
builds the prompt and the schema; an adapter only has to return JSON in that shape.
Nothing outside app/modules/ai calls these directly.
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
import openai


@dataclass(frozen=True)
class StructuredPrompt:
    system: str
    user: str
    schema_name: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class Completion:
    raw: object  # parsed JSON, not yet validated; the ai module validates it
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


class Completer(Protocol):
    provider: str
    model: str

    def complete(self, prompt: StructuredPrompt) -> Completion: ...


class ClaudeCompleter:
    """Claude with a forced tool call, so the reply is schema-shaped JSON, never prose."""

    provider = "anthropic"

    def __init__(self, client: anthropic.Anthropic, model: str = "claude-sonnet-5") -> None:
        self.client, self.model = client, model

    def complete(self, prompt: StructuredPrompt) -> Completion:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=prompt.system,
            # A single tool whose input schema is the answer schema, and tool_choice
            # pinned to it: Claude cannot reply with free text.
            tools=[{"name": prompt.schema_name, "description": "Return the structured answer.", "input_schema": prompt.schema}],
            tool_choice={"type": "tool", "name": prompt.schema_name},
            messages=[{"role": "user", "content": prompt.user}],
        )
        raw = next(b.input for b in msg.content if b.type == "tool_use")
        return Completion(raw, self.provider, msg.model, msg.usage.input_tokens, msg.usage.output_tokens)


class OpenAICompleter:
    """OpenAI with a JSON schema response format. Same contract as Claude."""

    provider = "openai"

    def __init__(self, client: openai.OpenAI, model: str = "gpt-5-mini") -> None:
        self.client, self.model = client, model

    def complete(self, prompt: StructuredPrompt) -> Completion:
        r = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt.system}, {"role": "user", "content": prompt.user}],
            response_format={"type": "json_schema", "json_schema": {"name": prompt.schema_name, "schema": prompt.schema}},
        )
        # an empty message still has to reach the validator, which rejects it
        raw = json.loads(r.choices[0].message.content or "{}")
        return Completion(raw, self.provider, r.model, r.usage.prompt_tokens, r.usage.completion_tokens)


def should_fall_back(exc: Exception) -> bool:
    """Outages, rate limits and timeouts move to the fallback. Our own mistakes do not.

    A 400, 401 or 422 means the request or the key is wrong, and sending the same
    request to a second provider would only hide that. A reply that parses but fails
    validation is not retried here either: that is a prompt problem.
    """
    if isinstance(exc, (anthropic.APIConnectionError, openai.APIConnectionError)):
        return True  # includes timeouts
    if isinstance(exc, (anthropic.APIStatusError, openai.APIStatusError)):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


class WithFallback:
    """Primary first. On an outage, rate limit or timeout, the fallback answers instead."""

    def __init__(self, primary: Completer, fallback: Completer) -> None:
        self.primary, self.fallback = primary, fallback
        self.provider, self.model = primary.provider, primary.model

    def complete(self, prompt: StructuredPrompt) -> Completion:
        try:
            return self.primary.complete(prompt)
        except (anthropic.APIError, openai.APIError) as exc:
            if not should_fall_back(exc):
                raise
            # The Completion carries the provider that actually answered, so the
            # ledger records OpenAI here, not Claude.
            return self.fallback.complete(prompt)
