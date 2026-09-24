"""The real Anthropic and OpenAI SDKs, pointed at recorded HTTP payloads instead of the network."""

import json

import anthropic
import httpx2
import openai

from app.answer import verify
from app.providers import ClaudeCompleter, OpenAICompleter, WithFallback
from app.retrieve import Hit

HIT = Hit("deal", "3f2504e0-4f89-41d3-9a0c-0305e82c3301", "Deal Northwind renewal, $48,000, stage Negotiation.", 0.03)
ANSWER = {"sentences": [{"text": "The deal is in Negotiation.", "sources": [HIT.record_id]}], "actions": []}


def claude(status: int, seen: list) -> ClaudeCompleter:
    def handler(req: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(req.content))
        if status != 200:
            return httpx2.Response(status, json={"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
        return httpx2.Response(200, json={
            "id": "msg_01", "type": "message", "role": "assistant", "model": "claude-sonnet-5",
            "content": [{"type": "tool_use", "id": "toolu_01", "name": "answer", "input": ANSWER}],
            "stop_reason": "tool_use", "stop_sequence": None, "usage": {"input_tokens": 1840, "output_tokens": 96},
        })

    client = anthropic.Anthropic(api_key="sk-ant-test", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    return ClaudeCompleter(client)


def gpt(seen: list) -> OpenAICompleter:
    def handler(req: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(req.content))
        return httpx2.Response(200, json={
            "id": "chatcmpl-1", "object": "chat.completion", "created": 1790000000, "model": "gpt-5-mini",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(ANSWER)}}],
            "usage": {"prompt_tokens": 1790, "completion_tokens": 88, "total_tokens": 1878},
        })

    client = openai.OpenAI(api_key="sk-test", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    return OpenAICompleter(client)


def test_claude_is_forced_into_the_answer_schema_and_parses_to_a_verified_answer():
    seen: list = []
    out = claude(200, seen).complete("Where is the Northwind deal?", [HIT])
    assert seen[0]["tool_choice"] == {"type": "tool", "name": "answer"}
    assert seen[0]["tools"][0]["input_schema"]["required"] == ["sentences"]
    assert HIT.record_id in seen[0]["messages"][0]["content"]
    assert (out.provider, out.input_tokens, out.output_tokens) == ("anthropic", 1840, 96)
    assert verify(out.raw, [HIT]).sentences[0].sources == [1]


def test_an_overloaded_primary_falls_back_to_openai_with_the_same_contract():
    c_seen: list = []
    o_seen: list = []
    out = WithFallback(claude(529, c_seen), gpt(o_seen)).complete("Where is the Northwind deal?", [HIT])
    assert len(c_seen) == 1 and len(o_seen) == 1
    assert o_seen[0]["response_format"]["json_schema"]["name"] == "answer"
    assert (out.provider, out.model) == ("openai", "gpt-5-mini")
    assert verify(out.raw, [HIT]).not_found is False
