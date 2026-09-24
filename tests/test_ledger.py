import pytest

from app.ai_service import OutOfCredits, ask, credits, ledger
from app.db import as_workspace
from app.retrieve import retrieve
from tests.fakes import FakeCompleter
from tests.seed import WS_A, WS_B, embedder

Q = "What did we promise Northwind before the renewal call?"


def test_meters_one_credit_on_a_miss_and_zero_on_the_cached_repeat(db):
    with as_workspace(db, WS_A) as c:
        hits = retrieve(c, WS_A, Q, embedder)
        first = ask(c, WS_A, Q, hits, FakeCompleter())
        second = ask(c, WS_A, Q.upper() + "  ", hits, FakeCompleter())
        balance = credits(c, WS_A)
    assert (first.cache, first.credits) == ("miss", 1)
    assert (second.cache, second.credits) == ("hit", 0)
    assert balance == 199


def test_different_evidence_changes_the_cache_key(db):
    q = "Renewal status for Northwind"
    with as_workspace(db, WS_A) as c:
        hits = retrieve(c, WS_A, q, embedder)
        first = ask(c, WS_A, q, hits, FakeCompleter())
        second = ask(c, WS_A, q, hits[:-1], FakeCompleter())
    assert first.cache == "miss"
    assert second.cache == "miss"


def test_refuses_before_calling_a_model_when_credits_run_out(db):
    calls = []

    class Counting(FakeCompleter):
        def complete(self, question, records):
            calls.append(question)
            return super().complete(question, records)

    with as_workspace(db, WS_B) as c:
        ledger(c, WS_B, "assistant.ask", "test", "fake-structured-1", 0, 0, "miss", 200)
        with pytest.raises(OutOfCredits):
            ask(c, WS_B, "Northwind price", retrieve(c, WS_B, "Northwind price", embedder), Counting())
    assert calls == []
