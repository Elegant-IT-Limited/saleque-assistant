"""Deterministic stand-ins. Provider tests go further and run the real SDKs against recorded HTTP payloads."""

import json

import httpx2
from typesafe_sdk import RetryPolicy, TypeSafeClient

from app.providers import Completion
from app.retrieve import Hit


class FakeCompleter:
    """Builds a structured answer from the retrieved records, plus two unsupported sentences on purpose."""

    provider, model = "test", "fake-structured-1"

    def complete(self, question: str, records: list[Hit]) -> Completion:
        def by(kind: str, needle: str) -> Hit | None:
            return next((r for r in records if r.record_type == kind and needle in r.content), None)

        email, note, task, deal = by("activity", "Pricing confirmation"), by("activity", "Call notes"), by("task", "SOW"), by("deal", "renewal")

        def s(text: str, *hits: Hit | None) -> dict:
            return {"text": text, "sources": [h.record_id for h in hits if h]}

        raw = {
            "sentences": [
                s("Three commitments are on record for Northwind.", email, note, task),
                s("Renewal price held at $48,000 for 12 months, confirmed by email on 9 Sep.", email),
                s("Two extra seats included at no charge, agreed on the 12 Sep call with Maya Chen.", note),
                s("An updated SOW was promised by 20 Sep. That task is still open.", task),
                s("The deal sits in Negotiation with a close date of 30 Sep.", deal),
                {"text": "Northwind also asked about an API add-on.", "sources": []},
                {"text": "They mentioned a competitor quote.", "sources": ["ffffffff-0000-4000-8000-000000000000"]},
            ],
            "actions": [
                {"type": "task", "title": "Send the updated SOW to Maya Chen", "due": "today", "sources": [task.record_id] if task else []},
                {"type": "deal_update", "title": "Add 2 seats to the Northwind renewal deal", "sources": [note.record_id] if note else []},
                {"type": "calendar_hold", "title": "Book the renewal call before 30 Sep", "sources": [deal.record_id] if deal else []},
            ],
        }
        return Completion(raw, self.provider, self.model, 3912, 418)


FIT_LEGEND = {"0": "No match", "1": "Weak match", "2": "Good match", "3": "Strong match"}

# Recorded System One responses, keyed by lead name. Same wire shape as POST /v1/systemone.
JEV_ANSWERS = {
    "Daniel Reyes": ("buying", 0.93, {"buying": 0.93, "evaluating": 0.05, "support": 0.0, "noise": 0.02}, 2.61, 0.91),
    "Priya Nair": ("evaluating", 0.58, {"buying": 0.21, "evaluating": 0.58, "support": 0.03, "noise": 0.18}, 1.12, 0.04),
    "SEO Growth Team": ("noise", 0.97, {"buying": 0.01, "evaluating": 0.01, "support": 0.01, "noise": 0.97}, 0.06, 0.0),
    "Lars Petersen": ("evaluating", 0.86, {"buying": 0.1, "evaluating": 0.86, "support": 0.0, "noise": 0.04}, 2.2, 0.12),
}


def jev_response(name: str) -> dict:
    choice, conf, probs, fit, budget = JEV_ANSWERS[name]
    return {
        "model": "jev-1.13.0",
        "answers": {
            "intent": {"type": "choice", "choice": choice, "confidence": conf, "probabilities": probs},
            "fit": {"type": "score", "score": fit, "confidence": 0.88, "legend": FIT_LEGEND,
                    "probabilities": {"0": 0.02, "1": 0.1, "2": 0.13, "3": 0.75}},
            "has_budget": {"type": "noul", "noul": budget},
        },
        "usage": {"input_tokens": 212, "output_tokens": 38},
    }


def fake_jev(seen: list[dict] | None = None) -> TypeSafeClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        if seen is not None:
            seen.append({"path": request.url.path, "body": body})
        return httpx2.Response(200, json=jev_response(body["state"]["lead"]["name"]))

    return TypeSafeClient(api_key="ts_test", model="jev-1.13", transport=httpx2.MockTransport(handler), retry=RetryPolicy(max_retries=0))
